"""ExternalContainerManifest pydantic schema.

1:1 mapping of docs/external-container-spec.md §6 manifest YAML.

apiVersion=tango.acryl.ai/v1 / kind=ExternalContainer.

Self-consistency rules (per manifest) live in validator.py. Hybrid pair
consistency rules (across two manifests sharing a service_family) also
live in validator.py.

Pydantic v2 syntax. `extra="forbid"` is enforced everywhere so partner
typos surface at registration time rather than at launch.
"""

from __future__ import annotations

import re
from typing import Annotated, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Type aliases (closed sets per SP-1 v2 §6) ─────────────────────────────

JobType = Literal["train", "evaluate", "preprocess", "convert", "infer"]
ExecutionMode = Literal["sync", "async", "batch"]
WorkspaceScope = Literal["per-workspace", "shared"]
AcceleratorT = Literal["nvidia", "hailo", "rocm"]

# free-form endpoint map — SP-1 v2 §5.4 allows partner-defined URL templates
# (e.g. ETRI uses /train/status?job_id={id}). Validator enforces required
# keys per execution_mode.
EndpointMap = Dict[str, str]


# ── Regex for resource amounts (Kubernetes quantity subset) ───────────────

_K8S_MEMORY = re.compile(r"^\d+(?:\.\d+)?(Ki|Mi|Gi|Ti|K|M|G|T)?$")
_K8S_CPU = re.compile(r"^\d+(?:\.\d+)?m?$")


class _StrictBase(BaseModel):
    """Common strict config for all sub-models.

    `protected_namespaces=()` clears pydantic's default `model_` reservation
    so partner-facing field names like `model_artifact_format` are allowed.
    fb_scheduler's dto.py applies the same opt-out for FineTuningLabel.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        protected_namespaces=(),
    )


# ── Metadata ──────────────────────────────────────────────────────────────


class Metadata(_StrictBase):
    name: Annotated[str, Field(min_length=1, max_length=63)]
    version: Annotated[str, Field(min_length=1)]
    vendor: Annotated[str, Field(min_length=1)]
    contact: Annotated[str, Field(min_length=1)]
    provider: Optional[str] = None
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _name_dns1123(cls, v: str) -> str:
        # K8s release name compatibility (lowercase alphanumerics + hyphens).
        if not re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", v):
            raise ValueError(
                "metadata.name must be DNS-1123 compatible "
                "(lowercase alphanumerics and hyphens only)"
            )
        return v


# ── Resources ─────────────────────────────────────────────────────────────


class Resources(_StrictBase):
    cpu: str
    memory: str
    gpu: int = 0
    gpu_memory: Optional[str] = None
    accelerator: AcceleratorT = "nvidia"

    @field_validator("cpu")
    @classmethod
    def _cpu_quantity(cls, v: str) -> str:
        if not _K8S_CPU.match(v):
            raise ValueError(
                f"resources.cpu must be a Kubernetes CPU quantity (e.g. '4', '500m'); got {v!r}"
            )
        return v

    @field_validator("memory")
    @classmethod
    def _memory_quantity(cls, v: str) -> str:
        if not _K8S_MEMORY.match(v):
            raise ValueError(
                f"resources.memory must be a Kubernetes memory quantity (e.g. '16Gi'); got {v!r}"
            )
        return v

    @field_validator("gpu_memory")
    @classmethod
    def _gpu_memory_quantity(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _K8S_MEMORY.match(v):
            raise ValueError(
                f"resources.gpu_memory must be a Kubernetes memory quantity; got {v!r}"
            )
        return v

    @field_validator("gpu")
    @classmethod
    def _gpu_range(cls, v: int) -> int:
        if not 0 <= v <= 8:
            raise ValueError(f"resources.gpu must be 0..8 (per-pod cap); got {v}")
        return v


# ── Inputs / Outputs ──────────────────────────────────────────────────────


class InputRequirement(_StrictBase):
    required: bool


class Inputs(_StrictBase):
    dataset: Optional[InputRequirement] = None
    base_model: Optional[InputRequirement] = None
    params: Optional[InputRequirement] = None


class Outputs(_StrictBase):
    metrics: bool = False
    model: bool = False
    dataset: bool = False
    artifacts: bool = False


# ── Secrets / Network ─────────────────────────────────────────────────────


class Secrets(_StrictBase):
    required: List[str] = Field(default_factory=list)

    @field_validator("required")
    @classmethod
    def _secret_name_shape(cls, v: List[str]) -> List[str]:
        for name in v:
            if not re.match(r"^[A-Z][A-Z0-9_]*$", name):
                raise ValueError(
                    f"secrets.required entries must be SCREAMING_SNAKE_CASE env names; got {name!r}"
                )
        return v


class Network(_StrictBase):
    egress_whitelist: List[str] = Field(default_factory=list)


# ── Capabilities ──────────────────────────────────────────────────────────


class Capabilities(_StrictBase):
    supported_models: List[str] = Field(default_factory=list)
    min_gpu_memory_gb: Optional[int] = None
    estimated_startup_seconds: Optional[int] = Field(default=None, ge=1)
    estimated_duration_seconds: Optional[int] = Field(default=None, ge=1)
    timeout_seconds: Optional[int] = Field(default=None, ge=1)


# ── Spec ──────────────────────────────────────────────────────────────────


class Spec(_StrictBase):
    # Image and classification
    image: Annotated[str, Field(min_length=1)]
    image_digest: Optional[str] = None
    job_type: JobType
    execution_mode: ExecutionMode
    port: int = Field(default=8000, ge=1, le=65535)
    workspace_scope: WorkspaceScope = "per-workspace"

    # Resources
    resources: Resources

    # Inputs / outputs / secrets / network
    inputs: Inputs = Field(default_factory=Inputs)
    outputs: Outputs = Field(default_factory=Outputs)
    secrets: Secrets = Field(default_factory=Secrets)
    network: Network = Field(default_factory=Network)

    # Partner-defined static env (e.g. EVA_CHECKPOINTS_ROOT=/output 으로
    # ETRI 의 hardcoded "/models/checkpoints" default 를 우리 mount 와 매핑).
    # helm pod.yaml 의 `.Values.env` range 로 그대로 forward. workspace 별
    # 동적 값은 jf_env 로 처리되며 여기는 manifest 전역 default 만 명시.
    env: dict[str, str] = Field(default_factory=dict)

    # HTTP endpoints (None or empty {} for batch)
    endpoints: Optional[EndpointMap] = None

    # Capability declaration
    capabilities: Capabilities = Field(default_factory=Capabilities)

    # Hybrid pair shared metadata (optional; required when partner ships paired manifests)
    service_family: Optional[str] = None
    contract_version: Optional[str] = None
    model_artifact_format: Optional[str] = None
    checkpoint_namespace: Optional[str] = None

    @field_validator("image_digest")
    @classmethod
    def _digest_shape(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^sha256:[0-9a-f]{64}$", v):
            raise ValueError(
                f"spec.image_digest must be 'sha256:<64-hex>' when provided; got {v!r}"
            )
        return v


# ── Top-level manifest ────────────────────────────────────────────────────


class ExternalContainerManifest(_StrictBase):
    apiVersion: Literal["tango.acryl.ai/v1"]
    kind: Literal["ExternalContainer"]
    metadata: Metadata
    spec: Spec

    @classmethod
    def model_validate_yaml(cls, raw: str) -> "ExternalContainerManifest":
        """Parse and validate a YAML document.

        Importing yaml lazily keeps schema.py importable in contexts that
        don't need YAML parsing (the registry layer can hand us a dict).
        """
        import yaml  # local import — avoid hard dependency at module import

        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            raise ValueError("manifest YAML must be a mapping at the top level")
        return cls.model_validate(data)
