"""Few-shot optimization pipeline.

Turns the given examples into an instruction + few-shot demo set for a frozen
task LM, in stages that can only keep or raise the score:

    0. Baseline       — the starting instruction + every given example.
    1. Compression    — MIPROv2 re-selects the instruction and a demo subset.
    2. Rounds (x N)   — augmentation (synthetic demos that pass the score gate,
                        see ``harvest``) followed by re-compression over the
                        grown pool.

Scoring uses every given example: each one is answered with its own demo (and
the synthetic demos generated from it) left out of the prompt, so the score of
a candidate is the score of the very prompt that is returned. Every change — a
compression result, a synthetic batch — is decided by the ``Judge``: it must
raise the reference likelihood by more than its noise and must not lower the
metric (``judge.py``); otherwise the current prompt stays, so no stage lowers
the score. Every stage is recorded in ``history`` with its prompt, so each
stage can be evaluated on its own.
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import dspy

from src.optimizer.generator import Generator
from src.optimizer.harvest import HarvestOutcome, harvest
from src.optimizer.judge import Candidate, Judge
from src.optimizer.likelihood import ReferenceScorer
from src.optimizer.mipro_step import MIPROOutcome, run_mipro
from src.optimizer.scoring import build_program
from src.optimizer.style import style_instructions
from src.optimizer.task import Example, Task


@dataclass
class OptimizeConfig:
    """Knobs for the optimization pipeline."""

    rounds: int = 1
    instruction: str | None = None  # the instruction the baseline starts from
    # MIPRO (compression and re-compression) — dspy.teleprompt.MIPROv2
    mipro_auto: str = "light"
    mipro_num_threads: int | None = None
    # Augmentation (harvest)
    n_iterations: int = 6
    n_per_iteration: int = 3
    seeds_per_iteration: int = 4
    feedback: bool = False  # textual feedback refines each synthetic demo before the gate
    feedback_mode: str = "critique"  # "critique", "likelihood", or "auto" (likelihood when the server supports it)
    generator_mode: str = "new"  # "new" situations, or "vary": one conclusion-keeping variation per seed
    # Decisions (judge.py): a change must raise the evidence (by more than gate_z
    # paired standard errors and gate_margin) and must not lower the metric.
    use_likelihood: bool = True  # reference scoring (evidence, likelihood feedback) when the server supports it
    evidence: str = "metric"  # "metric", "top1" (first-choice share) or "llh" (mean log-probability)
    gate_z: float = 0.0
    gate_margin: float = 0.0
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
    notes: list[str] = field(default_factory=list)  # things the caller should know (e.g. a fallback)


def _snapshot(task: Task, step: str, state: Candidate, judge: Judge, **extra: Any) -> dict:
    """History entry for the prompt a stage ends with (rendered when the task
    can render one), so every stage can be evaluated on its own."""
    entry = {
        "step": step,
        "holdout": round(judge.measure(state), 4),
        "n_demos": len(state.demos),
        "n_synthetic": sum(d.synthetic for d in state.demos),
        **extra,
        "instruction": state.instruction,
    }
    if judge.uses_likelihood and state.evidence:
        entry[f"holdout_{judge.kind}"] = round(sum(state.evidence) / len(state.evidence), 4)
    render = getattr(task, "render_system_prompt", None)
    if callable(render):
        entry["system_prompt"] = render(state.instruction, state.demos)
    return entry


def compress(
    task: Task,
    state: Candidate,
    pool: list[Example],
    judge: Judge,
    *,
    lm: Any,
    auto: str,
    num_threads: int | None,
    seed: int,
) -> tuple[Candidate, str]:
    """MIPROv2 over (instruction, subsets of ``pool``), with instruction
    candidates measured from the given examples' style (``style.py``) added to
    MIPRO's own. The options — MIPRO's result, the whole pool under the current
    instruction, each style candidate with the current demos — are tried in
    order of their evidence, and the first that ``judge`` finds an improvement
    over ``state`` replaces it; if none is, ``state`` stays.
    Returns (new state, which option won)."""
    given = [e for e in pool if not e.synthetic]
    extras = style_instructions(state.instruction, given)
    m: MIPROOutcome = run_mipro(
        task,
        pool,
        judge.scoring,
        lm=lm,
        instruction=state.instruction,
        auto=auto,
        num_threads=num_threads,
        seed=seed,
        extra_instructions=list(extras.values()),
    )

    def mean(xs: list[float] | None) -> float:
        return sum(xs) / len(xs) if xs else float("-inf")

    with dspy.context(lm=lm):
        options = []
        if [d.key for d in pool] != [d.key for d in state.demos]:
            options.append(("pool", judge.candidate(state.instruction, list(pool))))
        options += [(f"style:{name}", judge.candidate(instr, list(state.demos))) for name, instr in extras.items()]
        options.append(("mipro", judge.candidate(m.instruction, list(m.demos) or list(pool))))
        chosen, best, tried = "unchanged", state, []
        for name, cand in sorted(options, key=lambda o: mean(o[1].evidence), reverse=True):
            ok, why = judge.improves(cand, state)
            tried.append(f"{name}({len(cand.demos)}) {why}{' -> yes' if ok else ''}")
            if ok:
                chosen, best = name, cand
                break
    print("[optimize] compression options: " + " | ".join(tried) + f" => {chosen}")
    return best, chosen


def _disk_cache(name: str) -> Any:
    """A diskcache next to DSPy's cache (shared by runs with the same cache dir), or None."""
    try:
        import diskcache

        root = os.environ.get("DSPY_CACHEDIR") or os.path.join(Path.home(), ".dspy_cache")
        return diskcache.Cache(os.path.join(root, name))
    except Exception as e:  # noqa: BLE001
        print(f"[optimize] {name} cache unavailable: {e!r}")
        return None


class _ReplayedChat:
    """A chat callable whose n-th call with the same messages returns the same
    reply in every run sharing the cache — like DSPy's cache of LM calls, but a
    repeated call still gets a fresh sample (the second attempt of an iteration
    must not repeat the first). Runs that differ only after generation (with and
    without feedback) therefore judge the same synthetic batches."""

    def __init__(self, lm: Any, cache: Any) -> None:
        self.lm, self.cache = lm, cache
        self._calls: collections.Counter[str] = collections.Counter()
        self._lock = threading.Lock()

    def __call__(self, messages: Any) -> str:
        model = str(getattr(self.lm, "_model", "") or getattr(self.lm, "model", ""))
        base = hashlib.sha256(json.dumps([model, list(messages)], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        with self._lock:
            self._calls[base] += 1
            key = f"{base}:{self._calls[base]}"
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        reply = self.lm(messages)
        self.cache.add(key, reply)  # a concurrent run that got here first wins, so both use its reply
        return self.cache.get(key, reply)


def _reference_scorer(task_lm: Any) -> tuple[ReferenceScorer | None, str | None]:
    """A reference-likelihood scorer for the task LM's server, or (None, why not).
    Its scores are cached next to DSPy's cache, so a re-run reuses them."""
    cache = _disk_cache("reference_logprobs")
    try:
        scorer = ReferenceScorer.from_dspy_lm(task_lm, cache=cache)
    except Exception as e:  # noqa: BLE001 — not an OpenAI-compatible dspy.LM
        return None, f"{type(e).__name__}: {e}"
    problem = scorer.probe()
    return (None, problem) if problem else (scorer, None)


def run_optimization(
    task: Task,
    examples: list[Example],
    *,
    generation_lm: Any,
    reflection_lm: Any,
    task_lm: Any,
    config: OptimizeConfig | None = None,
    holdout: list[Example] | None = None,
) -> OptimizeResult:
    """Run the pipeline and return the optimized program + instruction + demos.

    ``examples`` are the demo candidates (and the generator's seeds). Decisions
    score ``holdout`` when given — examples kept out of every prompt — and
    otherwise ``examples`` themselves, each with its own demo left out."""
    config = config or OptimizeConfig()
    examples = list(examples)
    if len(examples) < 2:
        raise ValueError("run_optimization needs at least 2 examples.")
    scoring = list(holdout) if holdout else examples
    replay = _disk_cache("generation_replay") if generation_lm is not None else None
    generator = Generator(_ReplayedChat(generation_lm, replay) if replay is not None else generation_lm,
                          n_per_call=config.n_per_iteration)
    notes: list[str] = []
    scorer = None
    if config.use_likelihood and (config.evidence != "metric" or (config.feedback and config.feedback_mode != "critique")):
        scorer, problem = _reference_scorer(task_lm)
        if problem:
            notes.append(f"reference likelihood unavailable ({problem}); decisions used the metric only, feedback the critique")
            print(f"[optimize] {notes[-1]}")
    judge = Judge(task, scoring, scorer=scorer, z=config.gate_z, margin=config.gate_margin, kind=config.evidence)

    with dspy.context(lm=task_lm):
        state = judge.candidate(config.instruction, list(examples), metric=True)
        base = judge.measure(state)
        history = [_snapshot(task, "baseline", state, judge)]
    llh = f", {judge.kind}={sum(state.evidence) / len(state.evidence):.4f}" if judge.uses_likelihood else ""
    print(f"[optimize] baseline: {len(examples)} demos, score={base:.4f}{llh}")

    state, chosen = compress(
        task, state, list(examples), judge,
        lm=task_lm, auto=config.mipro_auto, num_threads=config.mipro_num_threads, seed=config.seed,
    )
    with dspy.context(lm=task_lm):
        history.append(_snapshot(task, "compress", state, judge, chosen=chosen))

    pool = list(examples)
    generated_total = accepted_total = 0
    for r in range(1, config.rounds + 1):
        with dspy.context(lm=task_lm):
            outcome: HarvestOutcome = harvest(
                task,
                state,
                [e for e in pool if not e.synthetic],
                judge,
                generator=generator,
                reflection_lm=reflection_lm,
                n_iterations=config.n_iterations,
                n_per_iteration=config.n_per_iteration,
                seeds_per_iteration=config.seeds_per_iteration,
                feedback=config.feedback,
                seed=config.seed + r,
                feedback_mode=config.feedback_mode,
                generator_mode=config.generator_mode,
            )
            augmented = outcome.state
            augmented_score = judge.measure(augmented)
        generated_total += outcome.generated_total
        accepted_total += len(outcome.accepted)
        pool.extend(outcome.accepted)
        print(
            f"[optimize] round {r} augmentation: generated={outcome.generated_total} "
            f"accepted={len(outcome.accepted)} score {judge.measure(state):.4f} -> {augmented_score:.4f}"
        )
        state, chosen = compress(
            task, augmented, pool, judge,
            lm=task_lm, auto=config.mipro_auto, num_threads=config.mipro_num_threads, seed=config.seed + 10_000 + r,
        )
        with dspy.context(lm=task_lm):
            history.append(
                _snapshot(
                    task, f"round{r}", state, judge,
                    generated=outcome.generated_total, accepted=len(outcome.accepted),
                    augmented_holdout=round(augmented_score, 4), chosen=chosen, pool=len(pool),
                )
            )

    return OptimizeResult(
        program=build_program(task, state.demos, state.instruction),
        instruction=state.instruction,
        final_demos=list(state.demos),
        seed_count=len(examples),
        holdout_count=len(scoring),
        generated_count=generated_total,
        accepted_count=accepted_total,
        base_score=base,
        final_score=state.score,
        history=history,
        notes=notes,
    )
