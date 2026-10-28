"""DSPy MIPROv2 instruction + demo selection (compression).

The ``_MIPROv2PoolSubsets`` override replaces MIPRO's metric-filtered bootstrap
stage with candidate demo sets drawn from the pool itself (gold demos, never LM
outputs), always including the whole pool, so "keep every demo" stays one of
MIPRO's options.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import dspy
from dspy.teleprompt import MIPROv2

from src.optimizer.scoring import build_program, program_inputs
from src.optimizer.task import Example, Task, example_key


class _MIPROv2PoolSubsets(MIPROv2):
    """MIPROv2 with the few-shot candidate stage replaced by subsets of the
    trainset (the demo pool).

    The ``num_fewshot_candidates`` slots are filled as:
      - slot 0: the whole pool (no compression)
      - slot 1: the given examples only, when the pool holds synthetic demos
      - other slots: random subsets of size ~ Uniform[ceil(N/2), N-1]

    Why: the default bootstrap stage builds demos from the task LM's own
    outputs, filtered by the metric — for a few dozen gold examples that mostly
    collapses to 3-5 demos and drops the gold answers. Here every candidate is
    made of the pool's own (gold or gated synthetic) demos.
    """

    def __init__(
        self, *args: Any, given_flags: Sequence[bool] = (), extra_instructions: Sequence[str] = (), **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self._given_flags = list(given_flags)
        self._extra_instructions = list(extra_instructions)

    def _propose_instructions(self, program, trainset, demo_candidates, *args, **kwargs):
        """MIPRO's own proposals, plus the caller's extra candidates."""
        candidates = super()._propose_instructions(program, trainset, demo_candidates, *args, **kwargs)
        for i in candidates:
            for extra in self._extra_instructions:
                if extra not in candidates[i]:
                    candidates[i].append(extra)
        return candidates

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
            sizes.append(len(demos))

        push(list(trainset))
        given = [d for d, g in zip(trainset, self._given_flags) if g]
        if 0 < len(given) < n and num_fewshot_candidates >= 2:
            push(given)
        lo, hi = max(1, math.ceil(n / 2)), max(1, n - 1)
        lo = min(lo, hi)
        while len(sizes) < num_fewshot_candidates:
            size = rng.randint(lo, hi)
            order = list(range(n))
            rng.shuffle(order)
            keep = sorted(order[:size])  # subsets keep the pool's order
            push([trainset[i] for i in keep])

        print(f"[mipro] built {len(sizes)} candidate demo sets: sizes={sizes} (pool={n})")
        return demo_candidates


@dataclass
class MIPROOutcome:
    """Result of one public ``dspy.teleprompt.MIPROv2`` compile."""

    program: Any  # dspy.Module
    instruction: str | None
    demos: list[Example]  # the pool demos MIPRO kept as few-shot, in prompt order


def _to_dspy(ex: Example, task: Task) -> Any:
    inputs = program_inputs(task, ex)  # images as dspy.Image, like scoring
    return dspy.Example(**inputs, **ex.outputs).with_inputs(*inputs)


def _wrap_metric(task: Task):
    input_keys = task.input_keys
    output_keys = task.output_keys

    def metric(gold: Any, pred: Any, trace: Any = None) -> float:
        ex = Example(
            inputs={k: getattr(gold, k) for k in input_keys if isinstance(getattr(gold, k, None), str)},
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


def _extract_demos(program: Any, pool: Sequence[Example], task: Task) -> list[Example]:
    """Recover which pool Examples MIPRO kept as few-shot demos."""
    index = {example_key(program_inputs(task, ex)): ex for ex in pool}
    seen: set[str] = set()
    out: list[Example] = []
    for _name, predictor in program.named_predictors():
        for demo in getattr(predictor, "demos", None) or []:
            if not all(demo.get(k) is not None for k in task.output_keys):
                continue
            key = example_key({k: demo.get(k) for k in task.input_keys if demo.get(k) is not None})
            if key in index and key not in seen:
                seen.add(key)
                out.append(index[key])
    return out


def run_mipro(
    task: Task,
    pool: Sequence[Example],
    scoring: Sequence[Example],
    *,
    lm: Any,
    instruction: str | None = None,
    auto: str = "light",
    num_threads: int | None = None,
    seed: int = 9,
    extra_instructions: Sequence[str] = (),
) -> MIPROOutcome:
    """Compile ``task`` over ``pool`` with the public MIPROv2 optimizer.

    The student is warm-started with ``instruction`` and the whole pool as its
    demos; MIPRO's Bayesian search picks the instruction + demo subset that
    maximizes the metric on ``scoring`` (leave-one-out, see ``scoring.py``).
    ``extra_instructions`` join MIPRO's own proposals as candidates.
    """
    pool = list(pool)
    if not pool:
        raise ValueError("run_mipro: empty pool")

    train_dspy = [_to_dspy(e, task) for e in pool]
    val_dspy = [_to_dspy(e, task) for e in scoring]

    with dspy.context(lm=lm):
        student = build_program(task, pool, instruction)
        optimizer = _MIPROv2PoolSubsets(
            metric=_wrap_metric(task),
            auto=auto,
            prompt_model=lm,
            task_model=lm,
            max_bootstrapped_demos=len(pool),
            max_labeled_demos=len(pool),
            num_threads=num_threads,
            given_flags=[not e.synthetic for e in pool],
            extra_instructions=extra_instructions,
        )
        optimized = optimizer.compile(student, trainset=train_dspy, valset=val_dspy, seed=seed)

    return MIPROOutcome(
        program=optimized,
        instruction=_extract_instruction(optimized),
        demos=_extract_demos(optimized, pool, task),
    )
