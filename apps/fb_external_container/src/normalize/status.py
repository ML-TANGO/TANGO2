"""External container lifecycle status enum + partner-string normalization.

SP-1 v2 §5.4 defines the canonical status set for `/jobs/{id}` responses:
``running | completed | failed | cancelled``. We add ``pending`` for the
window between helm install and pod readiness — that span is platform-owned,
not partner-owned, so it never appears in a partner response.
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class ExternalContainerStatus(str, Enum):
    """Canonical lifecycle status for external container jobs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Partner strings observed in the wild, normalized into the canonical enum.
# Lowercase keys so the lookup is case-insensitive.
_PARTNER_ALIAS: dict[str, ExternalContainerStatus] = {
    # canonical
    "pending": ExternalContainerStatus.PENDING,
    "running": ExternalContainerStatus.RUNNING,
    "completed": ExternalContainerStatus.COMPLETED,
    "failed": ExternalContainerStatus.FAILED,
    "cancelled": ExternalContainerStatus.CANCELLED,
    # ETRI SDS-VLM
    "queued": ExternalContainerStatus.PENDING,
    "started": ExternalContainerStatus.RUNNING,
    "in_progress": ExternalContainerStatus.RUNNING,
    "training": ExternalContainerStatus.RUNNING,
    "finished": ExternalContainerStatus.COMPLETED,
    "succeeded": ExternalContainerStatus.COMPLETED,
    "success": ExternalContainerStatus.COMPLETED,
    "error": ExternalContainerStatus.FAILED,
    "errored": ExternalContainerStatus.FAILED,
    "stopped": ExternalContainerStatus.CANCELLED,
    "canceled": ExternalContainerStatus.CANCELLED,
    "aborted": ExternalContainerStatus.CANCELLED,
}

_TERMINAL_STATES: frozenset[ExternalContainerStatus] = frozenset(
    {
        ExternalContainerStatus.COMPLETED,
        ExternalContainerStatus.FAILED,
        ExternalContainerStatus.CANCELLED,
    }
)


def is_terminal(status: ExternalContainerStatus) -> bool:
    """True if the status is a lifecycle endpoint (poller should stop)."""
    return status in _TERMINAL_STATES


def from_partner_string(raw: str | None) -> ExternalContainerStatus:
    """Translate a partner status string to the canonical enum.

    Unknown values fall back to ``RUNNING`` — a deliberately conservative
    choice so we keep polling rather than declaring a phantom terminal state.
    """
    if not raw:
        return ExternalContainerStatus.RUNNING
    key = raw.strip().lower()
    if key in _PARTNER_ALIAS:
        return _PARTNER_ALIAS[key]
    logger.warning(
        "Unrecognised partner status %r — defaulting to RUNNING. "
        "Add an alias to _PARTNER_ALIAS if this is a stable partner value.",
        raw,
    )
    return ExternalContainerStatus.RUNNING
