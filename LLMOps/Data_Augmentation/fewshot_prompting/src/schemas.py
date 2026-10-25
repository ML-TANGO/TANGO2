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
    """One few-shot example. ``image`` (a ``data:image/...`` URI or an http(s)
    URL) is used only when ``vlm`` is true; the text path ignores it."""

    query: str
    response: str
    image: str | None = None


class RunParams(BaseModel):
    """Optimization parameters (the meaningful body of ``/run``)."""

    examples: list[ExampleIn] = Field(default_factory=list)
    # Optional validation examples (same shape as ``examples``). When given, every
    # optimization decision is scored on them; they never enter the prompt, and
    # leave-one-out scoring / holdout_fraction are not used.
    validation: list[ExampleIn] = Field(default_factory=list)
    # OpenAI-compatible base URL of the served task/generation/reflection model,
    # e.g. "http://my-vllm-svc:8000/v1". Required.
    llm_url: str | None = None
    # Model id. If omitted, auto-detected from ``{llm_url}/models``.
    model: str | None = None
    api_key: str = "EMPTY"
    # Metric for holdout scoring: "spice", "token_f1" or "bert_score"
    # (multilingual; model set by env BERTSCORE_MODEL). Omitted: "spice", or
    # "token_f1" when the example responses are Korean (SPICE parses English
    # only). An explicit value is always honored.
    metric: str | None = None
    # VLM: show each example's image to the task LM while optimizing (llm_url
    # must serve a vision model). Off by default — text (query, response) only.
    vlm: bool = False
    # Share of the examples held out for scoring only (never in the prompt; see
    # optimizer.task.split_examples). 0 (default): no split — every example is
    # both a demo candidate and a scoring example, scored with its own demo left
    # out (leave-one-out). Ignored when ``validation`` is given.
    holdout_fraction: float = 0.0
    # False: no optimization — return the default instruction + every given
    # example as the system prompt right away (no LLM calls, no scores).
    optimize: bool = True
    # Optimization knobs (sensible defaults; override per request if needed).
    rounds: int = 1
    n_iterations: int = 6
    n_per_iteration: int = 3
    seeds_per_iteration: int = 4
    # Data augmentation: ``feedback`` critiques and revises every synthetic
    # demo with textual feedback (textgrad) before the score gate decides on it.
    feedback: bool = True
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
    examples: list[ExampleIn] | None = None
    validation: list[ExampleIn] | None = None
    llm_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    metric: str | None = None
    vlm: bool | None = None
    holdout_fraction: float | None = None
    optimize: bool | None = None
    rounds: int | None = None
    n_iterations: int | None = None
    n_per_iteration: int | None = None
    seeds_per_iteration: int | None = None
    feedback: bool | None = None
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
    base_score: float | None  # None when optimize=false
    final_score: float | None
    model: str
    metric: str  # metric actually used; differs from the request only on fallback
    history: list[dict[str, Any]]
    warnings: list[str] = Field(default_factory=list)
