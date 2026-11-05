"""Job-level dto shared between adapters, lifecycle, and domain BFF.

SP-1 v2 §5.4 prescribes the shape of `/jobs/{id}` responses. This module
mirrors that shape exactly so adapters can return a plain `ExternalJobResult`
and the rest of the platform doesn't see partner specifics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .status import ExternalContainerStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _StrictBase(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


# ── Error envelope (SP-1 v2 §4.2 stdout event=error + §8 errors.yaml) ────


class ExternalJobError(_StrictBase):
    """Partner-reported error normalized into the platform schema."""

    code: str = Field(min_length=1)
    message: str
    fatal: bool = True


# ── Job configuration (platform → adapter) ────────────────────────────────


class ExternalJobConfig(_StrictBase):
    """Input to ``ExternalAdapter.start_job``."""

    manifest_name: str
    manifest_version: str
    workspace_id: int
    job_id: str
    params: dict[str, Any] = Field(default_factory=dict)


# ── Job result (adapter → platform → BFF) ─────────────────────────────────


class ExternalJobResult(_StrictBase):
    """Normalized `/jobs/{id}` response, used everywhere downstream."""

    job_id: str
    status: ExternalContainerStatus
    # 0.0 .. 1.0. None when partner cannot report progress (e.g. inference
    # serving has no fractional progress concept).
    progress: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    # Partner-defined result payload on COMPLETED (metrics, output paths, ...)
    result: Optional[dict[str, Any]] = None
    error: Optional[ExternalJobError] = None
    # Pod-relative timestamps. updated_at is required for SSE delta detection.
    started_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=_utcnow)


# ── Status update event (SSE/stream) ──────────────────────────────────────


class ExternalJobStatusUpdate(_StrictBase):
    """A single SSE event emitted by the lifecycle poller.

    The poller batches partner state into either a status transition,
    a progress tick, a metric value, or a free-form log line. BFFs map this
    to the SSE event shape they already speak for internal LLM training.
    """

    job_id: str
    status: Optional[ExternalContainerStatus] = None
    progress: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    step: Optional[int] = None
    log_level: Optional[str] = None
    log_message: Optional[str] = None
    error: Optional[ExternalJobError] = None
    emitted_at: datetime = Field(default_factory=_utcnow)
