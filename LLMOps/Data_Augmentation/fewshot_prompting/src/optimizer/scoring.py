"""The scoring primitive.

``score_demos`` always measures a *whole demo set added together*, never a
per-demo marginal. Caller must be inside ``dspy.context(lm=...)``. The
predictions are requested concurrently (up to ``dspy.settings.num_threads``),
so the LM server can batch them.

The examples scored are usually the given examples themselves: the task's
program leaves each example's own demo (and the synthetic demos generated from
it) out of the prompt it answers with — see ``src/fewshot_task.py``.
"""

from __future__ import annotations

import contextvars
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import dspy

from src.optimizer.task import Example, Task


def apply_instruction(program: Any, instruction: str | None) -> Any:
    """Override every predictor's signature instruction in place. No-op if falsy."""
    if not instruction:
        return program
    for _name, predictor in program.named_predictors():
        predictor.signature = predictor.signature.with_instructions(instruction)
    return program


def build_program(task: Task, demos: Sequence[Example], instruction: str | None) -> Any:
    """``task.build_dspy_program(demos)`` with ``instruction`` injected (if any)."""
    return apply_instruction(task.build_dspy_program(list(demos)), instruction)


def program_inputs(task: Task, ex: Example) -> dict[str, Any]:
    """Keyword arguments for calling ``task``'s program on ``ex``. Tasks with
    non-text inputs (images) convert them through ``task.prepare_inputs``."""
    prepare = getattr(task, "prepare_inputs", None)
    if callable(prepare):
        return prepare(ex.inputs)
    return {k: ex.inputs[k] for k in task.input_keys}


@dataclass
class Scored:
    """One scored example: the program's answer and its metric score."""

    example: Example
    prediction: dict[str, str]
    score: float


def evaluate_demos(
    task: Task,
    demos: Sequence[Example],
    examples: Sequence[Example],
    *,
    instruction: str | None = None,
) -> list[Scored]:
    """Answer every example with the program built from ``demos`` (jointly, all
    of them) under ``instruction`` and score it, in ``examples`` order."""
    examples = list(examples)
    if not examples:
        return []
    prog = build_program(task, demos, instruction)

    def predict(ex: Example) -> dict[str, str]:
        try:
            result = prog(**program_inputs(task, ex))
            return {k: str(getattr(result, k, "")) for k in task.output_keys}
        except Exception as e:  # noqa: BLE001 — a failed call scores as an empty answer
            print(f"[scoring] prediction failed: {type(e).__name__}: {e}")
            return {k: "" for k in task.output_keys}

    # DSPy keeps ``dspy.context(lm=...)`` in a ContextVar, which worker threads
    # do not inherit: run each prediction in a copy of the caller's context.
    with ThreadPoolExecutor(max_workers=max(1, min(dspy.settings.num_threads, len(examples)))) as pool:
        futures = [pool.submit(contextvars.copy_context().run, predict, ex) for ex in examples]
        preds = [f.result() for f in futures]

    batch_fn = getattr(task, "metric_batch", None)
    if callable(batch_fn):
        scores = [float(s) for s in batch_fn(examples, preds)]
    else:
        scores = [float(task.metric(ex, p)) for ex, p in zip(examples, preds)]
    return [Scored(ex, p, s) for ex, p, s in zip(examples, preds, scores)]


def likelihood_per_example(
    task: Task,
    demos: Sequence[Example],
    examples: Sequence[Example],
    *,
    instruction: str | None = None,
    scorer: Any,
    kind: str = "llh",
) -> list[float]:
    """Mean log-probability per token (``kind="llh"``) — or the share of tokens
    that are the model's first choice (``kind="top1"``) — of every example's
    reference answer under the program built from ``demos`` and
    ``instruction``: the very messages ``evaluate_demos`` would send, with the
    same demos left out, scored by a ``likelihood.ReferenceScorer``. In
    ``examples`` order. The task's program must render its messages
    (``SystemPromptProgram.messages``)."""
    examples = list(examples)
    if not examples:
        return []
    prog = build_program(task, demos, instruction)
    out_key = task.output_keys[0]

    def one(ex: Example) -> float:
        messages = prog.messages(**program_inputs(task, ex))
        reference = ex.outputs.get(out_key, "")
        if kind == "top1":
            return scorer.stats(messages, reference)[1]
        return scorer.mean_logprob(messages, reference)

    with ThreadPoolExecutor(max_workers=max(1, min(dspy.settings.num_threads, len(examples)))) as pool:
        return list(pool.map(one, examples))


def score_demos_per_example(
    task: Task,
    demos: Sequence[Example],
    examples: Sequence[Example],
    *,
    instruction: str | None = None,
) -> list[float]:
    """Per-example metric vector for the program built from ``demos`` under
    ``instruction`` — one float per example, in order."""
    return [s.score for s in evaluate_demos(task, demos, examples, instruction=instruction)]


def score_demos(
    task: Task,
    demos: Sequence[Example],
    examples: Sequence[Example],
    *,
    instruction: str | None = None,
) -> float:
    """Mean metric of the task program built from ``demos`` (jointly, all of
    them) under ``instruction``."""
    scores = score_demos_per_example(task, demos, examples, instruction=instruction)
    return float(sum(scores)) / len(scores) if scores else 0.0
