"""Service orchestration: examples + LLM url  ->  optimized system prompt.

Builds the task/generation/reflection LMs from the request's ``llm_url`` (an
OpenAI-compatible endpoint), runs the optimizer, and renders the resulting
instruction + curated demos into a single system-prompt string returned to the
caller.
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Callable, Sequence
from typing import Any

import dspy
import litellm

from src.fewshot_task import (
    DEFAULT_METRIC,
    METRICS,
    FewShotTask,
    default_instruction,
    format_system_prompt,
    has_hangul,
    is_image_ref,
)
from src.optimizer import Example, OptimizeConfig, run_optimization
from src.optimizer.task import split_examples
from src.schemas import RunParams, RunResult


# Per-request timeout (seconds) for every LLM call: a hung LLM server then fails
# the call (which is retried) instead of blocking the job forever.
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "600"))


class _OpenAIChatLM:
    """Minimal chat callable for the synthetic-demo Generator: takes a list of
    ``{role, content}`` messages and returns the assistant text. Uses the openai
    SDK pointed at the request's OpenAI-compatible ``llm_url``."""

    def __init__(
        self, model: str, base_url: str, api_key: str, temperature: float = 0.9, max_tokens: int = 4096
    ) -> None:
        from openai import OpenAI

        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=LLM_TIMEOUT_SECONDS)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens  # a runaway reply stops here, not at the server's context limit

    def __call__(self, messages: Sequence[dict[str, str]]) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=list(messages),
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        return resp.choices[0].message.content or ""


def _task_max_tokens(examples: Sequence[Example]) -> int:
    """Output cap for the task LM: twice the longest example answer, counting a
    character as a token (the worst case), and at least 512. Answers like the
    examples fit easily, while a candidate prompt that makes the model ramble
    (or loop) is cut off in seconds instead of running to the server's context
    limit — which also outlasts the call timeout and keeps the server busy."""
    longest = max((len(v) for ex in examples for v in ex.outputs.values()), default=0)
    return max(512, 2 * longest)


def _detect_model(llm_url: str, api_key: str | None = None) -> str | None:
    """Query ``{llm_url}/models`` for the first served model id.

    ``api_key`` is sent as a bearer token: a server started with
    ``vllm serve --api-key ...`` rejects every unauthenticated ``/v1/*`` call,
    including ``/models``."""
    req = urllib.request.Request(f"{llm_url.rstrip('/')}/models")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
            if data.get("data"):
                return data["data"][0]["id"]
    except Exception as e:
        print(f"[service] model auto-detect failed: {e!r}")
    return None


def render_system_prompt(instruction: str | None, demos: Sequence[Example]) -> str:
    """Render (instruction, demos) into the text system prompt — the same format
    every candidate was scored with during optimization."""
    return format_system_prompt(
        instruction,
        [(d.inputs.get("query", ""), d.outputs.get("response", "")) for d in demos],
    )


def validate_params(params: RunParams) -> None:
    """Fail-fast request validation (cheap, no LLM calls). Raises ValueError."""
    if not params.optimize:
        if not params.examples:
            raise ValueError("at least 1 example is required.")
    else:
        if not params.llm_url:
            raise ValueError("llm_url is required (OpenAI-compatible base, e.g. http://host:8000/v1).")
        if len(params.examples) < 2:
            raise ValueError("at least 2 examples are required (each one is scored with the others as demos).")
    if not 0 <= params.holdout_fraction < 1:
        raise ValueError(f"holdout_fraction must be in [0, 1) (0: no split, leave-one-out); got {params.holdout_fraction}")
    if params.metric is not None and params.metric not in METRICS:
        raise ValueError(f"unknown metric {params.metric!r}; expected one of: {', '.join(METRICS)}")
    if params.vlm:
        for name, items in (("examples", params.examples), ("validation", params.validation)):
            for i, ex in enumerate(items):
                if ex.image and not is_image_ref(ex.image):
                    raise ValueError(f"{name}[{i}].image must be a data:image/... URI or an http(s) URL.")


def resolve_metric(requested: str | None, examples: Sequence[Example]) -> tuple[str, list[str]]:
    """The metric a job scores with, plus notes for ``result.warnings``.

    Omitted: SPICE — unless most example responses are Korean, since SPICE's
    CoreNLP parser reads English only; those jobs use token_f1. An explicit
    metric is always honored (SPICE on Korean then only matches identical words).
    """
    korean = 2 * sum(has_hangul(e.outputs.get("response", "")) for e in examples) > len(examples)
    if requested is None:
        if korean:
            return "token_f1", ["examples are Korean and SPICE is English-only: scored with token_f1 "
                                "(pass metric='spice' to force SPICE)"]
        return DEFAULT_METRIC, []
    if requested == "spice" and korean:
        return "spice", ["SPICE is English-only: Korean responses only match on identical words"]
    return requested, []


def _to_examples(params: RunParams, items: Sequence[Any] | None = None) -> list[Example]:
    return [
        Example(
            inputs={"query": ex.query, **({"image": ex.image} if (params.vlm and ex.image) else {})},
            outputs={"response": ex.response},
        )
        for ex in (params.examples if items is None else items)
    ]


def baseline_result(params: RunParams, examples: list[Example]) -> RunResult:
    """``optimize=False``: the given examples as they are, under the default
    instruction — the prompt the optimizer starts from. No LLM calls, no scores
    (score it on your own test set)."""
    instruction = default_instruction(params.vlm)
    return RunResult(
        system_prompt=render_system_prompt(instruction, examples),
        instruction=instruction,
        demos=[e.to_dict() for e in examples],
        n_examples=len(examples),
        n_seeds=len(examples),
        n_holdout=0,
        n_demos=len(examples),
        generated=0,
        accepted=0,
        base_score=None,
        final_score=None,
        model=params.model or "",
        metric=resolve_metric(params.metric, examples)[0],  # what an optimization would score with
        history=[],
    )


def optimize_system_prompt(
    params: RunParams,
    progress_cb: Callable[[int], None] | None = None,
) -> RunResult:
    """Run the full optimization for one ``/run`` request and return the result.

    ``progress_cb`` (optional) receives coarse 0-100 checkpoints for the async
    job's /status report: 10 model resolved, 15 optimization started, 95 done.
    ``params.optimize=False`` skips optimization (see ``baseline_result``).
    """
    validate_params(params)
    examples = _to_examples(params)
    if not params.optimize:
        return baseline_result(params, examples)

    def _progress(pct: int) -> None:
        if progress_cb is not None:
            progress_cb(pct)

    llm_url = params.llm_url.rstrip("/")
    api_key = params.api_key or "EMPTY"
    model = params.model or _detect_model(llm_url, api_key)
    if not model:
        raise ValueError(
            f"could not determine model id; pass 'model', or ensure {llm_url}/models is reachable "
            "and 'api_key' matches the server's key."
        )
    model_id = f"openai/{model}" if not model.startswith("openai/") else model
    _progress(10)

    # The harvest loop's textgrad engine rebind reads these as a fallback.
    os.environ["LLM_API_BASE"] = llm_url
    os.environ["LLM_API_KEY"] = api_key
    # DSPy calls go through litellm. A module-level timeout keeps DSPy's cache
    # keys unchanged (a per-LM ``timeout`` kwarg would become part of them).
    litellm.request_timeout = LLM_TIMEOUT_SECONDS

    print(f"[service] model={model} url={llm_url} examples={len(params.examples)} vlm={params.vlm}")

    task_lm = dspy.LM(
        model=model_id, api_base=llm_url, api_key=api_key, temperature=0.0, max_tokens=_task_max_tokens(examples)
    )
    reflection_lm = dspy.LM(model=model_id, api_base=llm_url, api_key=api_key, temperature=0.7, max_tokens=2048)
    generation_lm = _OpenAIChatLM(model=model, base_url=llm_url, api_key=api_key, temperature=0.9)

    metric, metric_notes = resolve_metric(params.metric, examples)
    task = FewShotTask(metric_name=metric, supports_image=params.vlm)
    print(f"[service] metric={task.metric_name} (requested {params.metric or 'default'})")
    config = OptimizeConfig(
        rounds=params.rounds,
        instruction=default_instruction(params.vlm),
        mipro_auto=params.mipro_auto,
        mipro_num_threads=params.mipro_num_threads,
        n_iterations=params.n_iterations,
        n_per_iteration=params.n_per_iteration,
        seeds_per_iteration=min(params.seeds_per_iteration, len(examples)),
        feedback=params.feedback,
        feedback_mode=os.environ.get("FEEDBACK_MODE", "critique"),  # internal switches for experiments
        evidence=os.environ.get("JUDGE_EVIDENCE", "metric"),
        generator_mode=os.environ.get("GENERATOR_MODE", "new"),
        gate_z=float(os.environ.get("GATE_Z", "0")),
        seed=params.seed,
    )

    _progress(15)
    # Scoring examples: the caller's validation set, else a held-out share of the
    # examples (holdout_fraction > 0), else every example leave-one-out.
    holdout = None
    if params.validation:
        holdout = _to_examples(params, params.validation)
        print(f"[service] validation: {len(examples)} demo candidates, {len(holdout)} validation examples")
    elif params.holdout_fraction > 0:
        examples, holdout = split_examples(examples, params.holdout_fraction, params.seed)
        print(f"[service] holdout split: {len(examples)} demo candidates, {len(holdout)} held out for scoring")
    # Concurrent LLM requests while scoring a candidate (DSPy's default is 8). Internal
    # switch: more threads only change how fast a job runs, not what it decides.
    threads = int(os.environ.get("SCORING_THREADS", "0")) or dspy.settings.num_threads
    if config.mipro_num_threads is None:
        config.mipro_num_threads = threads
    with dspy.context(num_threads=threads):
        result = run_optimization(
            task,
            examples,
            generation_lm=generation_lm,
            reflection_lm=reflection_lm,
            task_lm=task_lm,
            config=config,
            holdout=holdout,
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
        metric=task.metric_name,  # the metric actually used (spice / bert_score may fall back)
        history=result.history,
        warnings=metric_notes + task.warnings + result.notes,
    )
