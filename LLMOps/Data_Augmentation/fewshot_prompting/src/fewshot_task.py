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
from dspy.adapters.chat_adapter import ChatAdapter

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


class PassthroughChatAdapter(ChatAdapter):
    """구조화 출력을 못 내는 LM(파인튜닝 VLM 등)을 위한 관대한 파서.

    dspy 는 LM 이 `[[ ## response ## ]]` 같은 필드 마커를 지켜 준다고 전제하지만,
    특정 과제로 파인튜닝된 모델(예: SDS 해상 VLM)은 그냥 산문을 낸다. 그러면
    ChatAdapter/JSONAdapter 가 AdapterParseError 로 죽어 최적화 자체가 불가능하다.

    표준 파싱을 **먼저** 시도하고, 실패했을 때 출력 필드가 하나뿐인 시그니처에 한해
    응답 원문을 그 필드로 넘긴다. 필드가 여럿이면 어느 조각이 무엇인지 알 수 없으므로
    그대로 올려보낸다(조용히 틀린 값을 만들지 않는다).
    """

    def parse(self, signature, completion):
        try:
            return super().parse(signature, completion)
        except Exception:
            outputs = list(signature.output_fields)
            if len(outputs) != 1:
                raise
            return {outputs[0]: (completion or "").strip()}


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
        # 대상 LM 이 구조화 출력을 못 낼 때(파인튜닝 VLM). 단일 출력 시그니처 +
        #   PassthroughChatAdapter 조합으로 응답 원문을 그대로 채점에 쓴다.
        raw_output: bool = False,
    ) -> None:
        self.name = name
        self.supports_image = supports_image
        self.raw_output = raw_output
        self._metric_fn = _METRICS.get(metric_name, token_f1)
        # Optimization is text-only; image (when present) is prepared but not a
        # generation/selection key — see module docstring.
        self.input_keys: tuple[str, ...] = ("query",)
        self.output_keys: tuple[str, ...] = ("response",)

    def build_dspy_program(self, demos: Sequence[Example]) -> Any:
        signature = GenerateResponseVLM if self.supports_image else GenerateResponse
        # ChainOfThought 는 outputs=[reasoning, response] 라 관대한 파서도 못 구한다
        #   (원문을 어느 필드에 넣을지 알 수 없음) → raw 모드는 단일 출력 Predict.
        program = dspy.Predict(signature) if self.raw_output else dspy.ChainOfThought(signature)
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
