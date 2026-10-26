"""Augmentation (harvest) loop: grow the demo set with synthetic examples that
measurably raise the score.

Each iteration generates a small batch of new examples from a few given ones
(``Generator.generate``) and keeps it only if adding it to the current demos
is an improvement by the ``Judge`` (the evidence rises by more than its noise
and the metric does not fall); the score therefore never drops within a round.
A rejected batch gets one more attempt with a fresh batch from the same given
examples.

With ``feedback=True`` every batch is refined with textual feedback before the
gate sees it — by default ``feedback.refine_by_likelihood`` (the parts of each
output the task model finds improbable under the current prompt are rewritten
the way the given examples write them), or ``feedback.refine`` (critique, then
revise) when the server cannot score references or ``feedback_mode`` is
"critique". Everything else is identical, so the settings differ only in the
feedback.

Must be called inside ``dspy.context(lm=task_lm)`` — scoring reads the active
dspy LM.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from src.optimizer.generator import Generator
from src.optimizer.judge import Candidate, Judge
from src.optimizer.style import style_notes
from src.optimizer.task import Example, Task

__all__ = ["Candidate", "HarvestOutcome", "harvest"]


@dataclass
class HarvestOutcome:
    """Result of one ``harvest`` call (one round of generate + gate)."""

    state: Candidate  # the demo set after the round (the input state plus accepted batches)
    accepted: list[Example]
    generated_total: int
    iterations: list[dict] = field(default_factory=list)


def harvest(
    task: Task,
    state: Candidate,
    given: Sequence[Example],
    judge: Judge,
    *,
    generator: Generator,
    reflection_lm: Any,
    n_iterations: int,
    n_per_iteration: int,
    seeds_per_iteration: int,
    feedback: bool,
    seed: int,
    feedback_mode: str = "auto",
    generator_mode: str = "new",
) -> HarvestOutcome:
    """Grow ``state.demos`` with synthetic demos generated from ``given``
    examples; a batch joins only if ``judge`` finds it an improvement.

    ``generator_mode``: "new" writes new situations from the seeds together
    (``Generator.generate``); "vary" writes one variation per seed that keeps
    its conclusions (``Generator.vary``) — its labels stay right where the
    generator cannot work out the right conclusion for a new situation."""
    rng = random.Random(seed)
    current = state
    accepted: list[Example] = []
    log: list[dict] = []
    generated_total = 0
    text_keys = getattr(task, "text_input_keys", task.input_keys)
    conventions = style_notes(given) if feedback else ""

    def attempt_batch(seeds: list[Example]) -> list[Example]:
        try:
            if generator_mode == "vary":
                with ThreadPoolExecutor(max_workers=max(1, n_per_iteration)) as pool:
                    parts = list(pool.map(lambda sd: generator.vary(sd, text_keys, task.output_keys, n=1),
                                          seeds[:n_per_iteration]))
                batch = [e for part in parts for e in part]
            else:
                batch = generator.generate(seeds, text_keys, task.output_keys, n=n_per_iteration)
        except Exception as e:  # noqa: BLE001 — a failed call is an empty batch
            print(f"[harvest] generator raised {e!r}")
            return []
        if feedback and batch:
            from src.optimizer import feedback as fb

            if feedback_mode != "critique" and judge.scorer is not None:
                batch = fb.refine_by_likelihood(
                    task, batch, seeds, scorer=judge.scorer, instruction=current.instruction, demos=current.demos,
                    reflection_lm=reflection_lm, conventions=conventions,
                )
            else:
                batch = fb.refine(task, batch, seeds, reflection_lm=reflection_lm, conventions=conventions)
        return batch

    for it in range(n_iterations):
        seeds = rng.sample(list(given), min(seeds_per_iteration, len(given)))
        entry: dict = {"iter": it, "attempts": []}
        for attempt in (1, 2):
            batch = attempt_batch(seeds)
            generated_total += len(batch)
            if not batch:
                entry["attempts"].append({"attempt": attempt, "demos": 0, "accepted": False})
                continue
            trial = judge.candidate(current.instruction, [*current.demos, *batch])
            ok, why = judge.improves(trial, current)
            kind = "refined" if feedback else "generated"
            print(f"[harvest] iter {it}.{attempt} ({kind}): {len(batch)} demos, {why} {'ACCEPT' if ok else 'reject'}")
            entry["attempts"].append({"attempt": attempt, "demos": len(batch), "why": why, "accepted": ok})
            if ok:
                current = trial
                accepted.extend(batch)
                break
        log.append(entry)

    return HarvestOutcome(state=current, accepted=accepted, generated_total=generated_total, iterations=log)
