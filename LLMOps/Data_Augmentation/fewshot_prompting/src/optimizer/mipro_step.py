"""DSPy MIPROv2 instruction + demo selection.

The ``_MIPROv2RandomSubsets`` override replaces MIPRO's metric-filtered
bootstrap stage with metric-free random subsets of the trainset, giving the
caller direct control over how much of the trainset each candidate keeps.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import dspy
from dspy.teleprompt import MIPROv2

from src.optimizer.scoring import build_program
from src.optimizer.task import Example, Task


class _MIPROv2RandomSubsets(MIPROv2):
    """MIPROv2 with the few-shot candidate stage replaced by metric-free random
    subsets of the trainset.

    The ``num_fewshot_candidates`` slots are filled as:
      - slot 0: zero-shot (empty demos)
      - slot 1: labels-only — raw random sample of size min(max_labeled_demos, N)
      - slots 2..K-1: random subsets, size ~ Uniform[max_bootstrapped_demos/2,
        max_bootstrapped_demos] (clamped to [1, N])

    Why: the default bootstrap stage caps each shuffled slot at
    ``randint(1, max_bootstrapped_demos)`` and further drops candidates whose
    teacher trace fails the metric. On hard tasks with low pass-rate this
    collapses most candidate sets to 3-5 demos regardless of cap. This override
    removes the metric filter and pins the upper bound exactly at
    ``max_bootstrapped_demos`` so the caller has direct control over how much of
    the trainset MIPRO may discard per candidate.
    """

    def _bootstrap_fewshot_examples(
        self,
        program,
        trainset,
        seed,
        teacher,
        *,
        num_fewshot_candidates,
        max_bootstrapped_demos,
        max_labeled_demos,
        max_errors,
        metric_threshold,
    ):
        n = len(trainset)
        if n == 0 or num_fewshot_candidates <= 0:
            return None

        rng = random.Random(seed)
        n_preds = len(program.predictors())
        demo_candidates: dict[int, list[list]] = {i: [] for i in range(n_preds)}
        sizes: list[int] = []

        def push(demos: list) -> None:
            for i in range(n_preds):
                demo_candidates[i].append(list(demos))

        # slot 0: zero-shot baseline
        push([])
        sizes.append(0)

        # slot 1: labels-only baseline (raw sample, no metric filter)
        if num_fewshot_candidates >= 2:
            k = min(max_labeled_demos, n)
            push(rng.sample(list(trainset), k))
            sizes.append(k)

        # slots 2..K-1: metric-free random subsets.
        cap = max_bootstrapped_demos if max_bootstrapped_demos and max_bootstrapped_demos > 0 else n
        hi = max(1, min(cap, n))
        lo = max(1, min(int(cap / 2), hi))
        for _ in range(max(0, num_fewshot_candidates - 2)):
            size = rng.randint(lo, hi)
            shuffled = list(trainset)
            rng.shuffle(shuffled)
            push(shuffled[:size])
            sizes.append(size)

        print(
            f"[mipro_random] built {num_fewshot_candidates} candidate sets: "
            f"sizes={sizes} (trainset={n}, band=[{lo},{hi}])"
        )
        return demo_candidates


@dataclass
class MIPROOutcome:
    """Result of one public ``dspy.teleprompt.MIPROv2`` compile."""

    program: Any  # dspy.Module
    instruction: str | None
    demos: list[Example]  # curated subset of the trainset MIPRO kept as few-shot


def _to_dspy(ex: Example, input_keys: Sequence[str]) -> Any:
    return dspy.Example(**{**ex.inputs, **ex.outputs}).with_inputs(*input_keys)


def _wrap_metric(task: Task):
    input_keys = task.input_keys
    output_keys = task.output_keys

    def metric(gold: Any, pred: Any, trace: Any = None) -> float:
        ex = Example(
            inputs={k: str(getattr(gold, k)) for k in input_keys if hasattr(gold, k)},
            outputs={k: str(getattr(gold, k)) for k in output_keys if hasattr(gold, k)},
        )
        pred_dict = {k: (str(getattr(pred, k)) if hasattr(pred, k) else "") for k in output_keys}
        return float(task.metric(ex, pred_dict))

    return metric


def _extract_instruction(program: Any) -> str | None:
    for _name, predictor in program.named_predictors():
        sig = getattr(predictor, "signature", None)
        if sig is not None:
            return str(sig.instructions)
    return None


def _key(ex: Example) -> tuple[tuple[str, str], ...]:
    # Inputs-only: MIPRO's bootstrapped demos carry LM-generated outputs that
    # won't match gold verbatim, but their inputs come straight from trainset.
    return tuple(sorted(ex.inputs.items()))


def _extract_demos(
    program: Any,
    trainset: Sequence[Example],
    input_keys: Sequence[str],
    output_keys: Sequence[str],
) -> list[Example]:
    """Recover which trainset Examples MIPRO retained as few-shot demos."""
    index = {_key(ex): ex for ex in trainset}
    seen: set[tuple[tuple[str, str], ...]] = set()
    out: list[Example] = []
    for _name, predictor in program.named_predictors():
        for demo in getattr(predictor, "demos", None) or []:
            if not all(hasattr(demo, k) for k in (*input_keys, *output_keys)):
                continue
            rec = Example(
                inputs={k: str(getattr(demo, k)) for k in input_keys},
                outputs={k: str(getattr(demo, k)) for k in output_keys},
            )
            kk = _key(rec)
            if kk in index and kk not in seen:
                seen.add(kk)
                out.append(index[kk])
    return out


def run_mipro(
    task: Task,
    trainset: Sequence[Example],
    holdout: Sequence[Example],
    *,
    lm: Any,
    instruction: str | None = None,
    auto: str = "light",
    max_demos: int = 4,
    num_threads: int | None = None,
    seed: int = 9,
) -> MIPROOutcome:
    """Compile ``task`` over ``trainset`` with the public MIPROv2 optimizer.

    The student is warm-started with ``instruction`` (if any) and all of
    ``trainset`` as candidate demos; MIPRO's own Bayesian search picks the
    instruction + the demo subset that maximizes the metric on ``holdout``.
    """
    trainset = list(trainset)
    if not trainset:
        raise ValueError("run_mipro: empty trainset")

    train_dspy = [_to_dspy(e, task.input_keys) for e in trainset]
    val_dspy = [_to_dspy(e, task.input_keys) for e in holdout] if holdout else None

    with dspy.context(lm=lm):
        student = build_program(task, trainset, instruction)
        optimizer = _MIPROv2RandomSubsets(
            metric=_wrap_metric(task),
            auto=auto,
            prompt_model=lm,
            task_model=lm,
            max_bootstrapped_demos=max_demos,
            max_labeled_demos=max_demos,
            num_threads=num_threads,
        )
        optimized = optimizer.compile(student, trainset=train_dspy, valset=val_dspy, seed=seed)

    return MIPROOutcome(
        program=optimized,
        instruction=_extract_instruction(optimized),
        demos=_extract_demos(optimized, trainset, task.input_keys, task.output_keys),
    )
