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
from collections.abc import Callable, Sequence
from typing import Any

import dspy

from src.fewshot_task import FewShotTask, PassthroughChatAdapter
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


def validate_params(params: RunParams) -> None:
    """Fail-fast request validation (cheap, no LLM calls). Raises ValueError."""
    if not params.llm_url:
        raise ValueError("llm_url is required (OpenAI-compatible base, e.g. http://host:8000/v1).")
    if len(params.examples) < 2:
        raise ValueError("at least 2 examples are required (need >= 1 seed and >= 1 holdout).")


def optimize_system_prompt(
    params: RunParams,
    progress_cb: Callable[[int], None] | None = None,
) -> RunResult:
    """Run the full optimization for one ``/run`` request and return the result.

    ``progress_cb`` (optional) receives coarse 0-100 checkpoints for the async
    job's /status report: 10 model resolved, 15 optimization started, 95 done.
    """
    validate_params(params)

    def _progress(pct: int) -> None:
        if progress_cb is not None:
            progress_cb(pct)

    llm_url = params.llm_url.rstrip("/")
    api_key = params.api_key or "EMPTY"
    model = params.model or _detect_model(llm_url)
    if not model:
        raise ValueError(f"could not determine model id; pass 'model' or ensure {llm_url}/models is reachable.")
    model_id = f"openai/{model}" if not model.startswith("openai/") else model
    _progress(10)

    # The harvest loop's textgrad engine rebind reads these as a fallback.
    os.environ["LLM_API_BASE"] = llm_url
    os.environ["LLM_API_KEY"] = api_key

    print(f"[service] model={model} url={llm_url} examples={len(params.examples)} vlm={params.vlm}")

    # 메타 LM 분리 — instruction 제안·reflection·예시 생성은 구조화 출력을 요구한다.
    #   과제 LM 이 VLM(SDS)이면 그 계약을 못 지켜 AdapterParseError 로 죽으므로,
    #   proposer_llm_url 이 오면 그쪽 텍스트 LM 에 메타 3역을 맡긴다.
    #   미지정이면 종전과 동일하게 세 LM 모두 llm_url 을 쓴다.
    meta_url = (params.proposer_llm_url or "").rstrip("/") or llm_url
    if meta_url != llm_url:
        meta_model = params.proposer_model or _detect_model(meta_url)
        if not meta_model:
            raise ValueError(
                f"could not determine proposer model id; pass 'proposer_model' "
                f"or ensure {meta_url}/models is reachable."
            )
    else:
        meta_model = model
    meta_model_id = f"openai/{meta_model}" if not meta_model.startswith("openai/") else meta_model
    print(f"[service] meta(proposer/reflection/generation) model={meta_model} url={meta_url}")

    task_lm = dspy.LM(model=model_id, api_base=llm_url, api_key=api_key, temperature=0.0)
    proposer_lm = dspy.LM(model=meta_model_id, api_base=meta_url, api_key=api_key, temperature=0.0)
    reflection_lm = dspy.LM(model=meta_model_id, api_base=meta_url, api_key=api_key, temperature=0.7)
    generation_lm = _OpenAIChatLM(model=meta_model, base_url=meta_url, api_key=api_key, temperature=0.9)

    examples = [
        Example(
            inputs={"query": ex.query, **({"image": ex.image} if (params.vlm and ex.image) else {})},
            outputs={"response": ex.response},
        )
        for ex in params.examples
    ]
    seeds, holdout = _split(examples, params.holdout_fraction, params.seed)
    print(f"[service] split: {len(seeds)} seeds / {len(holdout)} holdout")

    # 대상이 구조화 출력을 못 내면 단일 출력 Predict + 관대한 파서를 함께 건다.
    #   어댑터는 표준 파싱을 먼저 시도하므로 제안자(qwen)처럼 형식을 지키는 LM 에는
    #   아무 영향이 없다 — 실패했을 때만 원문을 단일 출력 필드로 넘긴다.
    if params.raw_task_output:
        dspy.configure(adapter=PassthroughChatAdapter())
        print('[service] raw_task_output=True — Predict + PassthroughChatAdapter')
    task = FewShotTask(metric_name=params.metric, supports_image=params.vlm,
                       raw_output=params.raw_task_output)
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

    _progress(15)
    result = run_optimization(
        task,
        seeds,
        holdout,
        generation_lm=generation_lm,
        reflection_lm=reflection_lm,
        task_lm=task_lm,
        proposer_lm=proposer_lm,
        config=config,
    )
    _progress(95)

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
