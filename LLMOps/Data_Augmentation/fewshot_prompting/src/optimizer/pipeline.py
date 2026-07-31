"""Few-shot optimization pipeline.

Three phases turn a handful of seed examples into a curated instruction +
few-shot demo set for a frozen task LM:

    1. Pre-pass MIPRO     — propose an instruction and a starting demo subset.
    2. Harvest            — grow the pool with synthetic demos that measurably
                            raise the holdout score, steering the generation
                            prompt with a textual gradient (see ``harvest``).
    3. Selection MIPRO    — jointly re-select the instruction and the best demo
                            subset from the grown pool.

Holdout scoring always measures a whole demo set added together (never a
per-demo marginal). The harvest gate uses a baseline frozen per sub-round and a
noise band on accept/reject to avoid ratcheting on evaluation noise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import dspy

from src.optimizer.generator import DEFAULT_GENERATION_PROMPT, Generator
from src.optimizer.harvest import HarvestOutcome, harvest
from src.optimizer.mipro_step import MIPROOutcome, run_mipro
from src.optimizer.scoring import score_demos
from src.optimizer.task import Example, Task


@dataclass
class OptimizeConfig:
    """Knobs for the optimization pipeline."""

    rounds: int = 1
    # MIPRO (pre-pass and selection) — dspy.teleprompt.MIPROv2
    mipro_auto: str = "light"
    mipro_max_demos: int = 4
    mipro_num_threads: int | None = None
    # Harvest loop
    n_iterations: int = 6
    n_per_iteration: int = 3
    seeds_per_iteration: int = 4
    accept_eps: float = 0.0
    seed_generation_prompt: str = DEFAULT_GENERATION_PROMPT
    seed_resample: str = "per_round"
    seed: int = 0


@dataclass
class OptimizeResult:
    program: Any
    instruction: str | None
    final_demos: list[Example]
    seed_count: int
    holdout_count: int
    generated_count: int
    accepted_count: int
    base_score: float
    final_score: float
    history: list[dict] = field(default_factory=list)


def run_optimization(
    task: Task,
    seeds: list[Example],
    holdout: list[Example],
    *,
    generation_lm: Any,
    reflection_lm: Any,
    task_lm: Any,
    config: OptimizeConfig | None = None,
) -> OptimizeResult:
    """Run the pipeline and return the optimized program + instruction + demos."""
    config = config or OptimizeConfig()
    seeds = list(seeds)
    holdout = list(holdout)
    if len(seeds) < 1 or len(holdout) < 1:
        raise ValueError("run_optimization needs at least 1 seed and 1 holdout example.")

    generator = Generator(generation_lm, n_per_call=config.n_per_iteration)
    history: list[dict] = []

    # --- Phase 1: pre-pass MIPRO ------------------------------------------
    with dspy.context(lm=task_lm):
        base0 = score_demos(task, seeds, holdout, instruction=None)
    print(f"[optimize] pre-pass MIPRO over {len(seeds)} seeds (no-instruction holdout={base0:.4f})")
    m0: MIPROOutcome = run_mipro(
        task,
        seeds,
        holdout,
        lm=task_lm,
        instruction=None,
        auto="light",  # the pre-pass always runs the fast schedule
        max_demos=max(1, int(len(seeds) * 4 / 5)),
        num_threads=config.mipro_num_threads,
        seed=config.seed,
    )
    instruction = m0.instruction
    pool: list[Example] = list(m0.demos) if m0.demos else list(seeds)
    with dspy.context(lm=task_lm):
        s2 = score_demos(task, pool, holdout, instruction=instruction)
    history.append({"step": "pre-mipro", "holdout": round(s2, 4)})
    print(
        f"[optimize] pre-pass done: instruction={len(instruction or '')} chars, "
        f"pool={len(pool)}, holdout(pool+instruction)={s2:.4f}"
    )

    final: MIPROOutcome = m0
    generated_total = 0
    accepted_total = 0
    base_score = base0
    final_score = s2

    for r in range(config.rounds):
        # --- Phase 2: harvest ---------------------------------------------
        with dspy.context(lm=task_lm):
            outcome: HarvestOutcome = harvest(
                task,
                pool,
                holdout,
                generator=generator,
                instruction=instruction,
                reflection_lm=reflection_lm,
                seed_prompt=config.seed_generation_prompt,
                n_iterations=config.n_iterations,
                n_per_iteration=config.n_per_iteration,
                seeds_per_iteration=config.seeds_per_iteration,
                accept_eps=config.accept_eps,
                seed=config.seed + r,
                seed_resample=config.seed_resample,
            )
        generated_total += outcome.generated_total
        accepted_total += outcome.accepted_total
        combined = list(outcome.final_pool)
        print(
            f"[optimize] round {r} harvest: generated={outcome.generated_total} "
            f"accepted={outcome.accepted_total} (base={outcome.base_score:.4f} -> "
            f"final={outcome.final_score:.4f})"
        )

        # --- Phase 3: selection MIPRO over (instruction + grown pool) -----
        with dspy.context(lm=task_lm):
            pre = score_demos(task, combined, holdout, instruction=instruction)
        m: MIPROOutcome = run_mipro(
            task,
            combined,
            holdout,
            lm=task_lm,
            instruction=instruction,
            auto=config.mipro_auto,
            max_demos=max(1, len(pool)),
            num_threads=config.mipro_num_threads,
            seed=config.seed + 10_000 + r,
        )
        carried_demos = m.demos if m.demos else combined
        with dspy.context(lm=task_lm):
            post = score_demos(task, carried_demos, holdout, instruction=m.instruction)
        history.append(
            {
                "step": f"round{r}",
                "harvest_base": round(outcome.base_score, 4),
                "harvest_final": round(outcome.final_score, 4),
                "generated": outcome.generated_total,
                "accepted": outcome.accepted_total,
                "combined_holdout": round(pre, 4),
                "post_mipro_holdout": round(post, 4),
                "curated_demos": len(m.demos),
            }
        )
        print(
            f"[optimize] round {r} selection: combined(pool+accepted)={pre:.4f} -> "
            f"post-MIPRO={post:.4f} (curated {len(m.demos)} demos)"
        )

        final = m
        instruction = m.instruction
        pool = list(m.demos) if m.demos else combined
        final_score = post

    return OptimizeResult(
        program=final.program,
        instruction=final.instruction,
        final_demos=list(final.demos),
        seed_count=len(seeds),
        holdout_count=len(holdout),
        generated_count=generated_total,
        accepted_count=accepted_total,
        base_score=base_score,
        final_score=final_score,
        history=history,
    )
