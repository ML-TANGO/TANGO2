"""Adapter registry — maps manifest names to their HTTP adapter class.

When SP-Ext.3 lands the manifest registry, this static dict moves into a
DB-backed lookup. The dict shape stays the same so callers don't change.
"""

from typing import Type

from .base import ExternalAdapter, GenericHTTPAdapter
from .etri_vlm import ETRIAdapter
from .fewshot_prompt import FewshotPromptAdapter

# Static registry. Keys match manifest.metadata.name (DNS-1123 enforced by
# the schema). Default fallback is GenericHTTPAdapter — covers partners that
# follow SP-1 v2 §5 verbatim.
ADAPTER_REGISTRY: dict[str, Type[ExternalAdapter]] = {
    "eva-vlm-infer": ETRIAdapter,
    "eva-vlm-train": ETRIAdapter,
    "fewshot-prompt-optimizer": FewshotPromptAdapter,
}


def get_adapter_class(manifest_name: str) -> Type[ExternalAdapter]:
    """Look up the adapter for a manifest, or the generic fallback."""
    return ADAPTER_REGISTRY.get(manifest_name, GenericHTTPAdapter)


__all__ = [
    "ADAPTER_REGISTRY",
    "ETRIAdapter",
    "ExternalAdapter",
    "FewshotPromptAdapter",
    "GenericHTTPAdapter",
    "get_adapter_class",
]
