"""Service orchestration: examples + LLM url  ->  optimized system prompt.

Builds the task/generation/reflection LMs from the request's ``llm_url`` (an
OpenAI-compatible endpoint), runs the optimizer, and renders the resulting
instruction + curated demos into a single system-prompt string returned to the
caller.
"""

from __future__ import annotations

import json
import os
import random
import urllib.request
from collections.abc import Sequence
from typing import Any

import dspy

from src.fewshot_task import FewShotTask
from src.optimizer import Example, OptimizeConfig, run_optimization
from src.schemas import RunParams, RunResult


class _OpenAIChatLM:
    """Minimal chat callable for the synthetic-demo Generator: takes a list of
    ``{role, content}`` messages and returns the assistant text. Uses the openai
    SDK pointed at the request's OpenAI-compatible ``llm_url``."""

    def __init__(self, model: str, base_url: str, api_key: str, temperature: float = 0.9) -> None:
        from openai import OpenAI

        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self._model = model
        self._temperature = temperature

    def __call__(self, messages: Sequence[dict[str, str]]) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=list(messages),
            temperature=self._temperature,
        )
        return resp.choices[0].message.content or ""


def _detect_model(llm_url: str) -> str | None:
    """Query ``{llm_url}/models`` for the first served model id."""
    try:
        with urllib.request.urlopen(f"{llm_url.rstrip('/')}/models", timeout=5) as r:
            data = json.loads(r.read().decode())
            if data.get("data"):
                return data["data"][0]["id"]
    except Exception as e:
        print(f"[service] model auto-detect failed: {e!r}")
    return None


def _split(examples: list[Example], holdout_fraction: float, seed: int) -> tuple[list[Example], list[Example]]:
    """Shuffle and split into (seeds, holdout), each guaranteed >= 1 item."""
    n = len(examples)
    shuffled = list(examples)
    random.Random(seed).shuffle(shuffled)
    n_hold = max(1, min(n - 1, round(n * holdout_fraction)))
    holdout = shuffled[:n_hold]
    seeds = shuffled[n_hold:]
    return seeds, holdout


def render_system_prompt(instruction: str | None, demos: Sequence[Example]) -> str:
    """Render the optimized (instruction, demos) into a text system prompt."""
    parts: list[str] = []
    if instruction and instruction.strip():
        parts.append(instruction.strip())
    if demos:
        parts.append("Here are some examples:")
        for d in demos:
            q = d.inputs.get("query", "").strip()
            r = d.outputs.get("response", "").strip()
            parts.append(f"Query: {q}\nResponse: {r}")
    return "\n\n".join(parts).strip()


def optimize_system_prompt(params: RunParams) -> RunResult:
    """Run the full optimization for one ``/run`` request and return the result."""
    if not params.llm_url:
        raise ValueError("llm_url is required (OpenAI-compatible base, e.g. http://host:8000/v1).")
    if len(params.examples) < 2:
        raise ValueError("at least 2 examples are required (need >= 1 seed and >= 1 holdout).")

    llm_url = params.llm_url.rstrip("/")
    api_key = params.api_key or "EMPTY"
    model = params.model or _detect_model(llm_url)
    if not model:
        raise ValueError(f"could not determine model id; pass 'model' or ensure {llm_url}/models is reachable.")
    model_id = f"openai/{model}" if not model.startswith("openai/") else model

    # The harvest loop's textgrad engine rebind reads these as a fallback.
    os.environ["LLM_API_BASE"] = llm_url
    os.environ["LLM_API_KEY"] = api_key

    print(f"[service] model={model} url={llm_url} examples={len(params.examples)} vlm={params.vlm}")

    task_lm = dspy.LM(model=model_id, api_base=llm_url, api_key=api_key, temperature=0.0)
    reflection_lm = dspy.LM(model=model_id, api_base=llm_url, api_key=api_key, temperature=0.7)
    generation_lm = _OpenAIChatLM(model=model, base_url=llm_url, api_key=api_key, temperature=0.9)

    examples = [
        Example(
            inputs={"query": ex.query, **({"image": ex.image} if (params.vlm and ex.image) else {})},
            outputs={"response": ex.response},
        )
        for ex in params.examples
    ]
    seeds, holdout = _split(examples, params.holdout_fraction, params.seed)
    print(f"[service] split: {len(seeds)} seeds / {len(holdout)} holdout")

    task = FewShotTask(metric_name=params.metric, supports_image=params.vlm)
    config = OptimizeConfig(
        rounds=params.rounds,
        mipro_auto=params.mipro_auto,
        mipro_num_threads=params.mipro_num_threads,
        n_iterations=params.n_iterations,
        n_per_iteration=params.n_per_iteration,
        seeds_per_iteration=min(params.seeds_per_iteration, max(1, len(seeds))),
        accept_eps=0.0,
        seed=params.seed,
    )

    result = run_optimization(
        task,
        seeds,
        holdout,
        generation_lm=generation_lm,
        reflection_lm=reflection_lm,
        task_lm=task_lm,
        config=config,
    )

    system_prompt = render_system_prompt(result.instruction, result.final_demos)
    return RunResult(
        system_prompt=system_prompt,
        instruction=result.instruction,
        demos=[d.to_dict() for d in result.final_demos],
        n_examples=len(examples),
        n_seeds=result.seed_count,
        n_holdout=result.holdout_count,
        n_demos=len(result.final_demos),
        generated=result.generated_count,
        accepted=result.accepted_count,
        base_score=round(result.base_score, 4),
        final_score=round(result.final_score, 4),
        model=model,
        metric=params.metric,
        history=result.history,
    )
