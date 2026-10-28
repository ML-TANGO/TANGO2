"""External partner container BFF for the model domain.

Wraps fb_external_container's HTTP API so users hitting the model UI see
a single shape regardless of whether the underlying job is internal LLM
fine-tuning or a partner-supplied container (SP-Ext.2-8).
"""

from .proxy import ExternalContainerClient, ExternalContainerError
from .route import close_external_client, external

__all__ = [
    "ExternalContainerClient",
    "ExternalContainerError",
    "close_external_client",
    "external",
]
