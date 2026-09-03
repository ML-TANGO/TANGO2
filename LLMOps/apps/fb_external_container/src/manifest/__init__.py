"""External container manifest schema and validation.

Spec: examples/hello-plugin/external-container-spec.md (SP-1 v2)
ADR:  docs/adr/0003-external-service-onboarding-pattern.md (v2)
"""

from .registry import (
    InMemoryManifestRegistry,
    ManifestRegistry,
    ManifestRow,
    MariaDBManifestRegistry,
    RegistryConflictError,
)
from .schema import (
    AcceleratorT,
    Capabilities,
    EndpointMap,
    ExecutionMode,
    ExternalContainerManifest,
    InputRequirement,
    Inputs,
    JobType,
    Metadata,
    Network,
    Outputs,
    Resources,
    Secrets,
    Spec,
    WorkspaceScope,
)
from .seed import seed_manifests
from .validator import (
    HybridPairValidationError,
    ManifestValidationError,
    validate_hybrid_pair,
    validate_manifest,
)

__all__ = [
    "AcceleratorT",
    "Capabilities",
    "EndpointMap",
    "ExecutionMode",
    "ExternalContainerManifest",
    "HybridPairValidationError",
    "InMemoryManifestRegistry",
    "InputRequirement",
    "Inputs",
    "JobType",
    "ManifestRegistry",
    "ManifestRow",
    "ManifestValidationError",
    "MariaDBManifestRegistry",
    "Metadata",
    "Network",
    "Outputs",
    "RegistryConflictError",
    "Resources",
    "Secrets",
    "seed_manifests",
    "Spec",
    "WorkspaceScope",
    "validate_hybrid_pair",
    "validate_manifest",
]
