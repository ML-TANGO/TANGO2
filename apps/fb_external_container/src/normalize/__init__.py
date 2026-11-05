"""Common dto + status enum for external container jobs.

Domain BFFs (apps/llm_model, apps/fb_eval, ...) speak only this dto so that
internal SSE flows and external polling flows share a single shape.
"""

from .dto import (
    ExternalJobConfig,
    ExternalJobError,
    ExternalJobResult,
    ExternalJobStatusUpdate,
)
from .status import (
    ExternalContainerStatus,
    from_partner_string,
    is_terminal,
)

__all__ = [
    "ExternalContainerStatus",
    "ExternalJobConfig",
    "ExternalJobError",
    "ExternalJobResult",
    "ExternalJobStatusUpdate",
    "from_partner_string",
    "is_terminal",
]
