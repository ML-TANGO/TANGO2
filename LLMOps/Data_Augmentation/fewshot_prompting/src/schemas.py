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


class RunRequest(BaseModel):
    """Tango MSA ``/run`` envelope. ``params`` carries the optimization payload;
    top-level fields are accepted as a fallback for flat posts."""

    workspace_id: str | None = None
    project_id: str | None = None
    params: RunParams | None = None

    # Fallback flat fields (used only if ``params`` is absent).
    examples: list[ExampleIn] | None = None
    llm_url: str | None = None
    model: str | None = None
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


class RunResponse(BaseModel):
    status: str
    result: RunResult | None = None
    message: str | None = None
