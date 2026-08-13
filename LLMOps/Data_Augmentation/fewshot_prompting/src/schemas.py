"""Pydantic request/response models for the fewshot_prompting service.

The platform calls ``POST /run`` with the standard Tango MSA envelope
(``workspace_id`` / ``project_id`` / ``params``). The optimization payload lives
in ``params`` (see ``RunParams``). For convenience the same fields are also
accepted at the top level, so a caller can post ``params`` flat.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExampleIn(BaseModel):
    """One few-shot example. ``image`` is optional and prepared for VLM use
    (base64 data URI / URL / path); it is NOT used by the text optimization."""

    query: str
    response: str
    image: str | None = None


class RunParams(BaseModel):
    """Optimization parameters (the meaningful body of ``/run``)."""

    examples: list[ExampleIn] = Field(default_factory=list)
    # OpenAI-compatible base URL of the served task/generation/reflection model,
    # e.g. "http://my-vllm-svc:8000/v1". Required.
    llm_url: str | None = None
    # Model id. If omitted, auto-detected from ``{llm_url}/models``.
    model: str | None = None
    # OpenAI-compatible base URL of a **text** LM used for the meta roles:
    #   instruction proposal (MIPRO GroundedProposer), textgrad reflection and
    #   synthetic example generation. Those roles must emit structured output
    #   (e.g. a JSON ``proposed_instruction``), which a VLM task model such as
    #   SDS cannot do — it answers the image instead and dspy dies with
    #   AdapterParseError. Omit to reuse ``llm_url`` (previous behavior).
    proposer_llm_url: str | None = None
    # Model id for ``proposer_llm_url``. Auto-detected from its /models if absent.
    proposer_model: str | None = None
    # 대상 LM 이 dspy 의 구조화 출력 계약을 못 지킬 때(파인튜닝 VLM 등) True.
    #   단일 출력 Predict + PassthroughChatAdapter 로 응답 원문을 그대로 채점한다.
    raw_task_output: bool = False
    api_key: str = "EMPTY"
    # Metric for holdout scoring: "token_f1" (default) or "bert_score".
    metric: str = "token_f1"
    # VLM readiness: accept image fields and use an image-capable signature.
    # Off by default — the text /run path optimizes on (query, response) only.
    vlm: bool = False
    # Fraction of examples held out for in-loop scoring (rest are seeds).
    holdout_fraction: float = 0.4
    # Optimization knobs (sensible defaults; override per request if needed).
    rounds: int = 1
    n_iterations: int = 6
    n_per_iteration: int = 3
    seeds_per_iteration: int = 4
    mipro_auto: str = "light"
    mipro_num_threads: int | None = None
    seed: int = 0
    # True: run synchronously and return the result in the /run response
    # (old behavior; only for small/fast jobs — the platform applies a 60 s
    # timeout). False (default): submit a job and poll GET /status.
    sync: bool = False


class RunRequest(BaseModel):
    """Tango MSA ``/run`` envelope. ``params`` carries the optimization payload;
    top-level fields are accepted as a fallback for flat posts."""

    workspace_id: str | None = None
    project_id: str | None = None
    params: RunParams | None = None

    # Fallback flat fields (used only if ``params`` is absent).
    # ⚠️ 이 목록은 RunParams 의 필드와 **짝**이다. 플랫폼(external_container)은
    #    envelope 없이 flat 으로 POST 하므로(base.py:188 `json=config.params`),
    #    여기 선언되지 않은 키는 pydantic 이 조용히 버리고 resolve() 가 기본값을
    #    쓴다 — RunParams 에만 추가하면 그 파라미터는 영원히 도달하지 않는다.
    examples: list[ExampleIn] | None = None
    llm_url: str | None = None
    model: str | None = None
    proposer_llm_url: str | None = None
    proposer_model: str | None = None
    raw_task_output: bool | None = None
    api_key: str | None = None
    metric: str | None = None
    vlm: bool | None = None
    holdout_fraction: float | None = None
    rounds: int | None = None
    n_iterations: int | None = None
    n_per_iteration: int | None = None
    seeds_per_iteration: int | None = None
    mipro_auto: str | None = None
    mipro_num_threads: int | None = None
    seed: int | None = None
    sync: bool | None = None

    def resolve(self) -> RunParams:
        """Return effective ``RunParams``, merging top-level fallbacks."""
        if self.params is not None:
            return self.params
        flat = {
            k: v
            for k, v in self.model_dump(exclude_none=True).items()
            if k not in ("workspace_id", "project_id", "params")
        }
        return RunParams(**flat)


class RunResult(BaseModel):
    system_prompt: str
    instruction: str | None
    demos: list[dict[str, Any]]
    n_examples: int
    n_seeds: int
    n_holdout: int
    n_demos: int
    generated: int
    accepted: int
    base_score: float
    final_score: float
    model: str
    metric: str
    history: list[dict[str, Any]]
