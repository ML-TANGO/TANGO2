"""Generic few-shot Task adapter for the optimization service.

Wraps an arbitrary (query -> response) text task into the ``Task`` contract in
``src/optimizer/task.py``. The optimizer grows and selects few-shot demos + an
instruction for a frozen task LM; the metric scores how close the model's
response is to the gold response.

Scoring format = deployed format
--------------------------------
Every candidate (instruction, demos) is scored exactly the way the service's
output is used at inference: the system message is ``format_system_prompt``
(the very text ``/run`` returns), the user message is the query (plus the
image), and the whole reply is the response — no DSPy field markers and no
chain of thought (``SystemPromptAdapter`` / ``SystemPromptProgram``). So the
score the optimizer maximizes is the score of the prompt it returns.

Leave-one-out scoring
---------------------
Every given example is both a demo candidate and a scoring example. When the
program answers a query, it leaves out the demo with that very input and every
synthetic demo generated from it (``Example.origin``) — so a score never comes
from the answer sitting in the prompt. A new query matches no demo, so the
deployed prompt is the full demo list, exactly what was scored.

VLM support (``vlm=true``)
--------------------------
With ``supports_image=True`` an example may carry an image
(``Example.inputs["image"]``: a ``data:image/...`` URI or an http(s) URL) and the
program becomes query+image -> response, so scoring and MIPRO show the image to
the (vision) task LM:

  * ``input_keys`` gains ``"image"``; ``prepare_inputs`` turns the stored
    reference into a ``dspy.Image`` right before a program sees it.
  * ``text_input_keys`` stays ``("query",)``: the synthetic-demo generator can
    only write text, so synthetic demos carry no image.
  * The system prompt is plain text, as a VLM receives it at inference; only
    the query's own image goes into the user message. Demos therefore appear
    without their images (``result.demos`` keeps the image references).

The text path (``supports_image=False``) never looks at images.
"""

from __future__ import annotations

import importlib.util
import os
import re
import threading
from collections.abc import Sequence
from typing import Any

import dspy

from src import spice
from src.optimizer.task import Example, example_key

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


def default_instruction(supports_image: bool = False) -> str:
    """The instruction a prompt starts from before any optimization."""
    return (GenerateResponseVLM if supports_image else GenerateResponse).instructions


# --------------------------------------------------------------------- #
# The deployed prompt format, used for scoring as well
# --------------------------------------------------------------------- #


def format_system_prompt(instruction: str | None, demos: Sequence[tuple[str, str]]) -> str:
    """Render (instruction, [(query, response), ...]) into the text system prompt
    the service returns — and that every candidate is scored with."""
    parts: list[str] = []
    if instruction and instruction.strip():
        parts.append(instruction.strip())
    if demos:
        parts.append("Here are some examples:")
        for query, response in demos:
            parts.append(f"Query: {query.strip()}\nResponse: {response.strip()}")
    return "\n\n".join(parts).strip()


class SystemPromptAdapter(dspy.Adapter):
    """Formats a predictor call as the deployed prompt is used: system message =
    ``format_system_prompt(instructions, demos)``, user message = the query
    (with the image, if any), and the whole reply is the response."""

    def format(self, signature: Any, demos: list[Any], inputs: dict[str, Any]) -> list[dict[str, Any]]:
        system = format_system_prompt(
            signature.instructions,
            [(str(d.get("query", "")), str(d.get("response", ""))) for d in demos],
        )
        user: Any = str(inputs.get("query", ""))
        image = inputs.get("image")
        if image is not None:
            user = [{"type": "image_url", "image_url": {"url": image.url}}, {"type": "text", "text": user}]
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def parse(self, signature: Any, completion: str) -> dict[str, Any]:
        return {"response": completion.strip()}


class DemoOrigins:
    """Which given examples each synthetic demo was generated from (demo key ->
    keys). Shared by reference, never copied: MIPRO deep-copies programs."""

    def __init__(self) -> None:
        self._origins: dict[str, frozenset[str]] = {}

    def add(self, examples: Sequence[Example]) -> None:
        for ex in examples:
            if ex.origin:
                self._origins[ex.key] = frozenset(ex.origin)

    def related(self, query_key: str, demo_key: str) -> bool:
        """The demo is the query's own example, or was generated from it."""
        return demo_key == query_key or query_key in self._origins.get(demo_key, ())

    def __deepcopy__(self, memo: dict) -> DemoOrigins:
        return self


def _demo_key(demo: Any, input_keys: Sequence[str]) -> str:
    return example_key({k: demo.get(k) for k in input_keys})


class SystemPromptProgram(dspy.Module):
    """query(+image) -> response through ``SystemPromptAdapter``. MIPRO still
    sees one ``Predict`` whose instruction and demos it can set; only this
    program's own LM calls use the deployed format. Each call leaves out the
    demos related to its own input (see "Leave-one-out scoring" above)."""

    def __init__(self, signature: Any, origins: DemoOrigins | None = None) -> None:
        super().__init__()
        self.predict = dspy.Predict(signature)
        self.origins = origins or DemoOrigins()

    def _demos_for(self, inputs: dict[str, Any]) -> list[Any]:
        keys = list(self.predict.signature.input_fields)
        query_key = example_key({k: inputs.get(k) for k in keys})
        return [d for d in self.predict.demos if not self.origins.related(query_key, _demo_key(d, keys))]

    def forward(self, **inputs: Any) -> Any:
        demos = self._demos_for(inputs)
        with dspy.context(adapter=SystemPromptAdapter()):
            return self.predict(**inputs, demos=demos)

    def messages(self, **inputs: Any) -> list[dict[str, Any]]:
        """The chat messages ``forward`` sends for ``inputs`` (same demos left out)."""
        return SystemPromptAdapter().format(self.predict.signature, self._demos_for(inputs), inputs)


# --------------------------------------------------------------------- #
# Metrics (semantic similarity, [0, 1])
# --------------------------------------------------------------------- #

# A run of Hangul syllables, or a run of any other word characters.
_TOKEN_RE = re.compile(r"[가-힣]+|[^\W가-힣]+", re.UNICODE)


def _tokens(text: str) -> list[str]:
    """Lower-cased word tokens. Hangul runs become syllable bigrams, so Korean
    words that differ only by a particle or ending ("사과는" / "사과가") still
    share their stem; other scripts keep whole-word tokens."""
    out: list[str] = []
    for tok in _TOKEN_RE.findall((text or "").lower()):
        if len(tok) > 1 and "가" <= tok[0] <= "힣":
            out.extend(tok[i : i + 2] for i in range(len(tok) - 1))
        else:
            out.append(tok)
    return out


def token_f1(gold: str, pred: str) -> float:
    """Token-overlap F1 in [0, 1] over ``_tokens``. Dependency-free default metric."""
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


# Multilingual by default (examples are often Korean): bert_score's own default
# for non-English text — as discriminative as xlm-roberta-large on our Korean
# probes at ~1/3 the size and CPU time. BERTSCORE_NUM_LAYERS is only needed for
# models bert_score has no layer default for.
BERTSCORE_MODEL = os.environ.get("BERTSCORE_MODEL", "bert-base-multilingual-cased")
_BERTSCORE_NUM_LAYERS = os.environ.get("BERTSCORE_NUM_LAYERS")

_bert_scorer = None
_bert_lock = threading.Lock()


def _load_bert_scorer() -> Any:
    """Load the BERTScore model once per process (thread-safe). Raises if the
    ``bert_score`` package is missing or the model cannot be loaded."""
    global _bert_scorer
    with _bert_lock:
        if _bert_scorer is None:
            from bert_score import BERTScorer

            print(f"[fewshot_task] loading BERTScore model {BERTSCORE_MODEL} (first use)...")
            _bert_scorer = BERTScorer(
                model_type=BERTSCORE_MODEL,
                num_layers=int(_BERTSCORE_NUM_LAYERS) if _BERTSCORE_NUM_LAYERS else None,
                rescale_with_baseline=False,
            )
        return _bert_scorer


def bert_score_installed() -> bool:
    """Whether the optional ``bert_score`` package is installed (image built
    with ``WITH_BERTSCORE=true``, or requirements-bertscore.txt)."""
    return importlib.util.find_spec("bert_score") is not None


def preload_bert_scorer() -> threading.Thread | None:
    """Start loading the BERTScore model in the background at service start, so
    the first bert_score job does not wait for the download. No-op when the
    package is not installed or ``BERTSCORE_PRELOAD=false``."""
    if os.environ.get("BERTSCORE_PRELOAD", "true").lower() in ("0", "false", "no") or not bert_score_installed():
        return None

    def run() -> None:
        try:
            _load_bert_scorer()
            print("[fewshot_task] BERTScore model ready")
        except Exception as e:  # noqa: BLE001 — e.g. offline; bert_score jobs fall back to token_f1
            print(f"[fewshot_task] BERTScore preload failed ({type(e).__name__}: {e})")

    thread = threading.Thread(target=run, name="bertscore-preload", daemon=True)
    thread.start()
    return thread


def _bert_f1(gold: str, pred: str) -> float:
    """BERTScore F1 in [0, 1] (raw, not baseline-rescaled)."""
    if not pred or not gold:
        return 0.0
    scorer = _load_bert_scorer()
    with _bert_lock:
        _, _, f1 = scorer.score([pred], [gold], verbose=False)
    return float(f1.item())


METRICS = ("spice", "token_f1", "bert_score")
DEFAULT_METRIC = "spice"
_HANGUL_RE = re.compile(r"[가-힣]")


def has_hangul(text: str) -> bool:
    return bool(_HANGUL_RE.search(text or ""))


# --------------------------------------------------------------------- #
# Task adapter
# --------------------------------------------------------------------- #


class FewShotTask:
    """A generic (query -> response) text task for the optimizer.

    ``metric_name``: "spice" (default; SPICE via a Java server, English only —
    see ``src/spice.py``), "token_f1" (no deps) or "bert_score" (needs the
    ``bert_score`` package). If SPICE / BERTScore cannot run, the whole run uses
    token_f1 instead: ``metric_name`` then reports the metric actually used and
    ``warnings`` says why.
    ``supports_image``: query+image -> response (``vlm=true``) — see module
    docstring. Off for the service's text ``/run`` path.
    """

    def __init__(
        self,
        *,
        name: str = "fewshot",
        metric_name: str = DEFAULT_METRIC,
        supports_image: bool = False,
    ) -> None:
        if metric_name not in METRICS:
            raise ValueError(f"unknown metric {metric_name!r}; expected one of: {', '.join(METRICS)}")
        self.name = name
        self.supports_image = supports_image
        self.metric_name = metric_name
        self.origins = DemoOrigins()
        self._warnings: list[str] = []
        self._failures: list[str] = []  # list.append is atomic across metric threads
        loaders = {"spice": spice.start, "bert_score": _load_bert_scorer}
        if metric_name in loaders:
            try:
                loaders[metric_name]()  # fail over now, not halfway through the run
            except Exception as e:  # noqa: BLE001 — not installed, download failed, ...
                self.metric_name = "token_f1"
                self._warnings.append(f"{metric_name} unavailable ({type(e).__name__}: {e}); used token_f1 instead")
                print(f"[fewshot_task] {self._warnings[-1]}")
        self.input_keys: tuple[str, ...] = ("query", "image") if supports_image else ("query",)
        # What the synthetic-demo generator can write (it cannot produce images).
        self.text_input_keys: tuple[str, ...] = ("query",)
        self.output_keys: tuple[str, ...] = ("response",)

    def prepare_inputs(self, inputs: dict[str, str]) -> dict[str, Any]:
        """Program keyword arguments for an example's ``inputs``: the image
        reference becomes a ``dspy.Image``; inputs the example lacks (e.g. the
        image of a synthetic demo) are left out."""
        out: dict[str, Any] = {k: inputs[k] for k in self.input_keys if k != "image" and k in inputs}
        if "image" in self.input_keys and inputs.get("image"):
            image = _to_dspy_image(inputs["image"])
            if image is not None:
                out["image"] = image
        return out

    def render_system_prompt(self, instruction: str | None, demos: Sequence[Example]) -> str:
        """The text system prompt for (instruction, demos) — see ``format_system_prompt``."""
        return format_system_prompt(
            instruction,
            [(d.inputs.get("query", ""), d.outputs.get("response", "")) for d in demos],
        )

    def build_dspy_program(self, demos: Sequence[Example]) -> Any:
        signature = GenerateResponseVLM if self.supports_image else GenerateResponse
        self.origins.add(demos)
        program = SystemPromptProgram(signature, self.origins)
        dspy_demos = []
        for d in demos:
            fields = self.prepare_inputs(d.inputs)
            dspy_demos.append(dspy.Example(**fields, response=d.outputs.get("response", "")).with_inputs(*fields))
        for _name, predictor in program.named_predictors():
            predictor.demos = list(dspy_demos)
        return program

    def metric(self, example: Example, prediction: dict[str, str]) -> float:
        return self.metric_batch([example], [prediction])[0]

    def metric_batch(self, examples: Sequence[Example], predictions: Sequence[dict[str, str]]) -> list[float]:
        """Scores for a whole batch — one SPICE server request for all of them.
        A pair the metric fails on is scored with token_f1 and counted."""
        pairs = [(e.outputs.get("response", ""), p.get("response", "")) for e, p in zip(examples, predictions)]
        if self.metric_name == "spice":
            try:
                return spice.spice_scores(pairs)
            except Exception as e:  # noqa: BLE001 — score this batch with token_f1
                self._failures.extend([repr(e)] * len(pairs))
        elif self.metric_name == "bert_score":
            scores = []
            for gold, pred in pairs:
                try:
                    scores.append(_bert_f1(gold, pred))
                except Exception as e:  # noqa: BLE001 — score this one pair with token_f1
                    self._failures.append(repr(e))
                    scores.append(token_f1(gold, pred))
            return scores
        return [token_f1(gold, pred) for gold, pred in pairs]

    @property
    def warnings(self) -> list[str]:
        """Metric problems the caller should know about (empty when none)."""
        out = list(self._warnings)
        if self._failures:
            out.append(
                f"{self.metric_name} failed on {len(self._failures)} prediction(s) "
                f"(first: {self._failures[0]}); token_f1 was used for those"
            )
        return out


def is_image_ref(value: str) -> bool:
    """Image references the service accepts: ``data:image/...`` URIs and http(s)
    URLs. Local paths are refused — images are forwarded to the caller-supplied
    ``llm_url``, so reading server files for them would leak those files."""
    return value.startswith(("data:image/", "http://", "https://"))


def _to_dspy_image(value: str) -> Any:
    """``dspy.Image`` for an accepted image reference (URLs are passed through
    for the LLM server to fetch), or None if it cannot be used."""
    if not is_image_ref(value):
        print(f"[fewshot_task] ignoring image {value[:40]!r}: not a data:image URI or http(s) URL")
        return None
    try:
        return dspy.Image(url=value)
    except Exception as e:  # noqa: BLE001 — malformed data URI, ...
        print(f"[fewshot_task] could not use image {value[:40]!r}: {e!r}")
        return None
