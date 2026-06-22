"""The holdout-scoring primitive.

``score_demos`` always measures a *whole demo set added together*, never a
per-demo marginal. Caller must be inside ``dspy.context(lm=...)``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

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


def score_demos_per_example(
    task: Task,
    demos: Sequence[Example],
    holdout: Sequence[Example],
    *,
    instruction: str | None = None,
) -> list[float]:
    """Per-example holdout metric vector for the program built from ``demos``
    (jointly, all of them) under ``instruction`` — one float per holdout item,
    in holdout order. Caller must be inside ``dspy.context(lm=...)``."""
    holdout = list(holdout)
    if not holdout:
        return []
    prog = build_program(task, demos, instruction)

    preds: list[dict[str, str]] = []
    for ex in holdout:
        try:
            result = prog(**{k: ex.inputs[k] for k in task.input_keys})
            pred = {k: str(getattr(result, k, "")) for k in task.output_keys}
        except Exception:
            pred = {k: "" for k in task.output_keys}
        preds.append(pred)

    batch_fn = getattr(task, "metric_batch", None)
    if callable(batch_fn):
        return [float(s) for s in batch_fn(list(holdout), preds)]
    return [float(task.metric(ex, p)) for ex, p in zip(holdout, preds)]


def score_demos(
    task: Task,
    demos: Sequence[Example],
    holdout: Sequence[Example],
    *,
    instruction: str | None = None,
) -> float:
    """Mean holdout metric of the task program built from ``demos`` (jointly,
    all of them) under ``instruction``. Caller is responsible for being inside
    ``dspy.context(lm=...)``."""
    scores = score_demos_per_example(task, demos, holdout, instruction=instruction)
    return float(sum(scores)) / len(scores) if scores else 0.0
