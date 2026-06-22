"""Textual-gradient harvest loop: grow the few-shot pool with synthetic demos.

Each iteration uses the textgrad apparatus (``tg.Variable`` + ``tg.TextLoss``
forward + ``loss.backward()`` + ``optimizer.step()``) to critique the current
generation prompt and propose an improved one. New demos are generated from that
prompt and accepted into the pool only if they raise the holdout score past a
noise band, measured against a baseline frozen at the start of each sub-round
(so accept/reject decisions within a sub-round are mutually comparable). On
acceptance the batch joins the pool, the baseline is recomputed against the
grown pool, and a fresh sub-round continues from the same prompt.

Must be called inside ``dspy.context(lm=task_lm)`` — ``score_demos`` reads the
active dspy LM. The critique / backward / step calls use the textgrad engine
built from ``reflection_lm``.
"""

from __future__ import annotations

import json
import os
import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import textgrad as tg

from src.optimizer.generator import Generator
from src.optimizer.scoring import score_demos
from src.optimizer.task import Example, Task

SeedResample = Literal["per_iter", "per_round"]


@dataclass
class HarvestOutcome:
    """Result of one ``harvest`` call (one round of generate + holdout-gate)."""

    final_pool: list[Example]
    final_prompt: str
    base_score: float  # baseline before iteration 0
    final_score: float  # holdout score of ``final_pool`` at end
    generated_total: int  # total demos generated across all iterations
    accepted_total: int  # total demos kept (= len(final_pool) - len(initial pool))
    iterations: list[dict] = field(default_factory=list)


_LOSS_EVAL_PROMPT = """You are evaluating a synthetic-data generation prompt by looking at the demos it just produced and how those demos affected a downstream task's holdout accuracy.

The artifact you receive will contain (a) the JSON demos the prompt generated, (b) the frozen baseline holdout score (= what the pool scored BEFORE these new demos were added), (c) the trial holdout score (= what the pool scored WITH these new demos added), and (d) whether the batch was accepted.

Give detailed, specific natural-language feedback CRITIQUING the prompt that produced these demos. Point to concrete weaknesses: are the demos too narrow, too similar to each other, too close to the seeds the prompt was given, factually wrong, formatted incorrectly, or unhelpfully easy for the downstream task? What KIND of demos would have raised the score more? Be concrete.

Do NOT propose a rewritten prompt — the next optimizer step will do that. Only critique."""

_LOSS_EVAL_PROMPT_EMPTY = """You are critiquing a synthetic-data generation prompt that just FAILED to produce ANY parseable demos. The downstream parser got 0 valid items out of the LM's response.

This is a FORMAT/STRUCTURE failure, not a demo-quality failure. There are no demos to look at — the artifact you receive just records that the batch was empty.

Diagnose what about the prompt likely caused the LM to produce unparseable output:
- Are the format requirements too rigid (over-specified JSON schema, exact tag names, exact whitespace, exact escape rules)?
- Is the structure ambiguous (multiple plausible interpretations of what the output should look like)?
- Are the instructions self-contradictory or impossible to satisfy together?
- Is critical context missing (the LM doesn't know what fields to fill, what kind of content goes where, what example length is expected)?
- Is the placeholder '{n_new}' embedded in a way that confuses the LM about the surrounding output format?
- Does the prompt ask the LM to produce a structure that is unnatural given the input domain (e.g., demanding nested JSON when the input is plain text)?

Give specific natural-language feedback on which part of the prompt to RELAX or RESTRUCTURE so the LM's output becomes parseable. Do NOT propose a rewrite — the next optimizer step will do that. Only diagnose."""

_PROMPT_ROLE = (
    "A prompt that instructs an LLM to produce synthetic training demos for a "
    "downstream task. Improvements should make the produced demos correct, "
    "diverse, and complementary to the existing pool — so that adding them to "
    "the pool raises the downstream task's holdout accuracy. The prompt MUST "
    "contain the literal placeholder '{n_new}' (the generator substitutes it "
    "with the number of examples to produce on each call)."
)

_RESULT_ROLE = (
    "Output of one generation+evaluation step: the demos the prompt produced, "
    "and how the holdout score changed when those demos were added to the pool."
)


def _format_demos_block(demos: Sequence[Example]) -> str:
    if not demos:
        return "(nothing parseable was generated)"
    return "\n".join(json.dumps(d.to_dict(), ensure_ascii=False) for d in demos)


def _coerce_engine(reflection_lm: Any) -> Any:
    """Map a ``dspy.LM`` (or string) to a textgrad engine.

    ``reflection_lm`` is typically a ``dspy.LM`` constructed like
    ``dspy.LM(model="openai/<name>", api_base="http://.../v1", ...)``. We route
    it through textgrad's ``ollama-<name>`` engine but **rebind the OpenAI
    client to the dspy.LM's own api_base/api_key** afterwards, because
    textgrad's ``ChatOpenAI`` hard-codes ``OLLAMA_BASE_URL`` for any
    ``ollama-*`` engine — without the rebind, requests fire at localhost:11434
    instead of the served model and silently no-op.
    """
    if isinstance(reflection_lm, tg.engine.base.EngineLM):
        return reflection_lm
    if isinstance(reflection_lm, str):
        return tg.get_engine(reflection_lm)
    model = getattr(reflection_lm, "model", None)
    if not isinstance(model, str):
        raise ValueError(
            "reflection_lm must be a dspy.LM (with `.model`), a textgrad engine, "
            f"or an engine name string — got {type(reflection_lm).__name__}"
        )
    if not model.startswith("openai/"):
        return tg.get_engine(model)

    engine = tg.get_engine(f"ollama-{model[len('openai/') :]}")

    kwargs = getattr(reflection_lm, "kwargs", {}) or {}
    api_base = kwargs.get("api_base") or os.environ.get("LLM_API_BASE")
    api_key = kwargs.get("api_key") or os.environ.get("LLM_API_KEY") or "EMPTY"
    if api_base and getattr(engine, "base_url", None) != api_base:
        from openai import OpenAI

        engine.client = OpenAI(base_url=api_base, api_key=api_key)
        engine.base_url = api_base
        print(f"[harvest] reflection engine rebound to {api_base} (model={engine.model_string})")
    return engine


def harvest(
    task: Task,
    pool: Sequence[Example],
    holdout: Sequence[Example],
    *,
    generator: Generator,
    instruction: str | None,
    reflection_lm: Any,
    seed_prompt: str,
    n_iterations: int,
    n_per_iteration: int,
    seeds_per_iteration: int,
    accept_eps: float,
    seed: int,
    seed_resample: SeedResample = "per_round",
) -> HarvestOutcome:
    """Grow ``pool`` with synthetic demos that measurably raise the holdout
    score, steering the generation prompt with a textual gradient each iter."""
    rng = random.Random(seed)
    pool = list(pool)
    initial_pool_size = len(pool)
    if seed_resample == "per_round":
        seed_subset_pinned: list[Example] | None = (
            rng.sample(pool, min(seeds_per_iteration, len(pool))) if pool else []
        )
        print(f"[harvest] seed_resample=per_round (pinned subset size={len(seed_subset_pinned)})")
    else:
        seed_subset_pinned = None

    # ----- Frozen reference ------------------------------------------------
    frozen_baseline = score_demos(task, pool, holdout, instruction=instruction)
    initial_baseline = frozen_baseline
    print(
        f"[harvest] frozen baseline = {frozen_baseline:.4f} "
        f"(pool size {initial_pool_size}, holdout {len(holdout)}, eps={accept_eps})"
    )

    # ----- textgrad scaffolding -------------------------------------------
    engine = _coerce_engine(reflection_lm)
    tg.set_backward_engine(engine, override=True)

    prompt_var = tg.Variable(
        value=seed_prompt,
        requires_grad=True,
        role_description=_PROMPT_ROLE,
    )
    loss_fn = tg.TextLoss(_LOSS_EVAL_PROMPT, engine=engine)
    loss_fn_empty = tg.TextLoss(_LOSS_EVAL_PROMPT_EMPTY, engine=engine)
    optimizer = tg.TGD(parameters=[prompt_var], engine=engine, gradient_memory=2)

    iter_log: list[dict] = []
    generated_total = 0
    sub_round_idx = 0

    for it in range(n_iterations):
        p_gen = prompt_var.value
        print(f"[harvest debug] iter {it} p_gen ({len(p_gen)} chars), first 300:\n  {p_gen[:300]!r}")

        # (a) generate ----------------------------------------------------
        if seed_subset_pinned is not None:
            seed_subset = seed_subset_pinned
        elif pool:
            k = min(seeds_per_iteration, len(pool))
            seed_subset = rng.sample(pool, k)
        else:
            seed_subset = []
        try:
            new_demos = generator.generate(
                generation_prompt=p_gen,
                seeds=seed_subset,
                input_keys=task.input_keys,
                output_keys=task.output_keys,
                n=n_per_iteration,
                task_instruction=instruction,
            )
        except Exception as e:
            print(f"[harvest] iter {it}: generator raised {e!r} — empty batch")
            new_demos = []
        generated_total += len(new_demos)

        # (b) score (pool + batch) ----------------------------------------
        if new_demos:
            trial_score = score_demos(task, [*pool, *new_demos], holdout, instruction=instruction)
        else:
            trial_score = frozen_baseline

        # (c) accept/reject vs frozen baseline -----------------------------
        delta = trial_score - frozen_baseline
        accepted = bool(new_demos) and (delta >= accept_eps)
        accepted_demos_this_iter = new_demos if accepted else []

        verdict = "ACCEPT" if accepted else "REJECT"
        pool_now = len(pool) + len(accepted_demos_this_iter)
        print(
            f"[harvest] iter {it} (sub-round {sub_round_idx}): "
            f"generated={len(new_demos)} trial={trial_score:.4f} "
            f"(delta {delta:+.4f}) {verdict} pool_now={pool_now}"
        )
        iter_log.append(
            {
                "iter": it,
                "sub_round": sub_round_idx,
                "generated": len(new_demos),
                "trial_score": round(trial_score, 4),
                "delta_vs_frozen": round(delta, 4),
                "accepted": accepted,
                "pool_size_after": pool_now,
            }
        )

        # On ACCEPT, flush the batch into ``pool``, recompute the baseline
        # against the grown pool, and ``continue`` so the next iter starts a
        # fresh sub-round from the same prompt.
        if accepted:
            prev_baseline = frozen_baseline
            pool.extend(new_demos)
            frozen_baseline = score_demos(task, pool, holdout, instruction=instruction)
            sub_round_idx += 1
            print(
                f"[harvest] iter {it}: ACCEPT → sub-round "
                f"{sub_round_idx} begins (pool size={len(pool)}, "
                f"baseline {prev_baseline:.4f} -> {frozen_baseline:.4f})"
            )
            continue

        # (d) textgrad backward + step (skip on last iteration) ------------
        if it == n_iterations - 1:
            break

        if not new_demos:
            print(f"[harvest] iter {it}: 0 demos — using empty-batch loss prompt")
            result_value = (
                "The generation prompt produced 0 parseable demos in this iteration.\n"
                "The downstream parser saw no valid items in the LM's response.\n"
                "Treat this as a FORMAT/STRUCTURE failure of the prompt itself, "
                "not a demo-quality issue."
            )
            active_loss = loss_fn_empty
        else:
            result_value = (
                f"Demos the prompt produced (one JSON per line):\n"
                f"{_format_demos_block(new_demos)}\n\n"
                f"Frozen baseline holdout (pool only): {frozen_baseline:.4f}\n"
                f"Trial holdout (pool + these demos):   {trial_score:.4f}\n"
                f"Delta vs frozen baseline:             {delta:+.4f}\n"
                f"Accept threshold (noise band):        {accept_eps}\n"
                f"Decision:                             {'ACCEPT' if accepted else 'REJECT'}"
            )
            active_loss = loss_fn
        result_var = tg.Variable(
            value=result_value,
            predecessors=[prompt_var],
            requires_grad=True,
            role_description=_RESULT_ROLE,
        )

        try:
            loss = active_loss(result_var)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        except Exception as e:
            print(f"[harvest] iter {it}: backward/step raised {e!r} — keeping current prompt")
            continue

        # textgrad's TGD may produce a prompt without our literal '{n_new}'
        # placeholder; the generator does a literal replace, so patch it back.
        new_prompt_value = (prompt_var.value or "").strip()
        if not new_prompt_value:
            print(f"[harvest] iter {it}: optimizer returned empty prompt — restoring previous")
            prompt_var.value = p_gen
        elif "{n_new}" not in new_prompt_value:
            print(f"[harvest] iter {it}: optimizer dropped '{{n_new}}' — patching it in")
            prompt_var.value = new_prompt_value + "\n\nProduce exactly {n_new} new example(s)."

    final_score = score_demos(task, pool, holdout, instruction=instruction)
    accepted_total = len(pool) - initial_pool_size
    print(
        f"[harvest] done: sub_rounds={sub_round_idx} "
        f"base={initial_baseline:.4f} final_baseline={frozen_baseline:.4f} "
        f"final_score={final_score:.4f} "
        f"(delta {final_score - initial_baseline:+.4f}) "
        f"generated={generated_total} accepted={accepted_total} "
        f"final_pool={len(pool)}"
    )

    return HarvestOutcome(
        final_pool=pool,
        final_prompt=prompt_var.value,
        base_score=initial_baseline,
        final_score=final_score,
        generated_total=generated_total,
        accepted_total=accepted_total,
        iterations=iter_log,
    )
