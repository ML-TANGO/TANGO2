"""Generic few-shot Task adapter for the optimization service.

Wraps an arbitrary (query -> response) text task into the ``Task`` contract in
``src/optimizer/task.py``. The optimizer grows and selects few-shot demos + an
instruction for a frozen task LM; the metric scores how close the model's
response is to the gold response.

VLM readiness
-------------
The ``/run`` request carries text examples, so the optimization path is
intentionally text-only: ``input_keys = ("query",)``. But the request schema and
this adapter are wired so an image can ride along on each example
(``Example.inputs["image"]`` as a base64 data URI / URL / path) without changing
optimization behavior:

  * ``build_dspy_program`` builds a query->response signature by default, and a
    query+image->response signature when ``supports_image=True`` — the hook a
    future VLM flow flips on.
  * The returned system prompt (instruction + demos) is plain text either way,
    which is exactly what a VLM is given as its system message; the image is
    supplied per-call at inference time, not baked into the prompt.

So images are *prepared for* end to end but never fed into the synthetic-demo
generator (you cannot synthesize images) nor required by the text optimization.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

import dspy

from src.optimizer.task import Example

# --------------------------------------------------------------------- #
# DSPy signatures
# --------------------------------------------------------------------- #


class GenerateResponse(dspy.Signature):
    """Respond to the user's query, following the style and format of the examples."""

    query: str = dspy.InputField(desc="The user's query.")
    response: str = dspy.OutputField(desc="The response to the query.")


class GenerateResponseVLM(dspy.Signature):
    """Respond to the user's query about the image, following the examples."""

    query: str = dspy.InputField(desc="The user's query.")
    image: dspy.Image = dspy.InputField(desc="An image the query refers to.")
    response: str = dspy.OutputField(desc="The response to the query.")


# --------------------------------------------------------------------- #
# Metrics (semantic similarity, [0, 1])
# --------------------------------------------------------------------- #

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall((text or "").lower())


def token_f1(gold: str, pred: str) -> float:
    """Token-overlap F1 in [0, 1]. Dependency-free default metric."""
    g, p = _tokens(gold), _tokens(pred)
    if not g and not p:
        return 1.0
    if not g or not p:
        return 0.0
    from collections import Counter

    gc, pc = Counter(g), Counter(p)
    overlap = sum((gc & pc).values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(p)
    recall = overlap / len(g)
    return 2 * precision * recall / (precision + recall)


_bert_scorer = None


def _bert_f1(gold: str, pred: str) -> float:
    """BERTScore F1 in [0, 1]. Lazily loads the model on first use; falls back
    to ``token_f1`` if the ``bert_score`` package is not installed."""
    global _bert_scorer
    if _bert_scorer is None:
        try:
            from bert_score import BERTScorer

            print("[fewshot_task] initializing BERTScore model (first use)...")
            _bert_scorer = BERTScorer(lang="en", rescale_with_baseline=False)
        except Exception as e:  # not installed or model download failed
            print(f"[fewshot_task] BERTScore unavailable ({e!r}); using token_f1")
            _bert_scorer = False
    if not _bert_scorer:
        return token_f1(gold, pred)
    if not pred or not gold:
        return 0.0
    try:
        _, _, f1 = _bert_scorer.score([pred], [gold], verbose=False)
        return float(f1.item())
    except Exception as e:
        print(f"[fewshot_task] BERTScore error ({e!r}); using token_f1")
        return token_f1(gold, pred)


_METRICS = {"token_f1": token_f1, "bert_score": _bert_f1}


# --------------------------------------------------------------------- #
# Task adapter
# --------------------------------------------------------------------- #


class FewShotTask:
    """A generic (query -> response) text task for the optimizer.

    ``metric_name``: "token_f1" (default, no deps) or "bert_score" (semantic,
    requires the ``bert_score`` package; falls back to token_f1 if missing).
    ``supports_image``: VLM readiness hook — see module docstring. Off for the
    service's text ``/run`` path.
    """

    def __init__(
        self,
        *,
        name: str = "fewshot",
        metric_name: str = "token_f1",
        supports_image: bool = False,
    ) -> None:
        self.name = name
        self.supports_image = supports_image
        self._metric_fn = _METRICS.get(metric_name, token_f1)
        # Optimization is text-only; image (when present) is prepared but not a
        # generation/selection key — see module docstring.
        self.input_keys: tuple[str, ...] = ("query",)
        self.output_keys: tuple[str, ...] = ("response",)

    def build_dspy_program(self, demos: Sequence[Example]) -> Any:
        signature = GenerateResponseVLM if self.supports_image else GenerateResponse
        program = dspy.ChainOfThought(signature)
        dspy_demos = []
        for d in demos:
            fields = {"query": d.inputs.get("query", ""), "response": d.outputs.get("response", "")}
            if self.supports_image and d.inputs.get("image"):
                fields["image"] = _to_dspy_image(d.inputs["image"])
            dspy_demos.append(dspy.Example(**fields).with_inputs(*self.input_keys))
        for _name, predictor in program.named_predictors():
            predictor.demos = list(dspy_demos)
        return program

    def metric(self, example: Example, prediction: dict[str, str]) -> float:
        gold = example.outputs.get("response", "")
        pred = prediction.get("response", "")
        return float(self._metric_fn(gold, pred))


def _to_dspy_image(value: str) -> Any:
    """Best-effort conversion of an image reference (data URI / base64 / url /
    path) to a ``dspy.Image``. Only used on the VLM path."""
    try:
        if value.startswith("data:") and "," in value:
            return dspy.Image.from_base64(value.split(",", 1)[1])
        if value.startswith(("http://", "https://")):
            return dspy.Image.from_url(value)
        return dspy.Image.from_file(value)
    except Exception as e:
        print(f"[fewshot_task] could not load image {value[:40]!r}: {e!r}")
        return None
