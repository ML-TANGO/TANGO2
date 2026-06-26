"""ExternalContainerManifest pydantic schema.

1:1 mapping of examples/hello-plugin/external-container-spec.md §6 manifest YAML.

apiVersion=tango.acryl.ai/v1 / kind=ExternalContainer.

Self-consistency rules (per manifest) live in validator.py. Hybrid pair
consistency rules (across two manifests sharing a service_family) also
live in validator.py.

Pydantic v2 syntax. `extra="forbid"` is enforced everywhere so partner
typos surface at registration time rather than at launch.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ── Type aliases (closed sets per SP-1 v2 §6) ─────────────────────────────

JobType = Literal["train", "evaluate", "preprocess", "convert", "infer", "generate"]
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


# ── Training recipe (SP-10 도메인 카드 → 프리셋) ──────────────────────────
#
# 선택 필드. 다단계 학습 컨테이너(예: SDS = CLIP+LLM 4-Phase)가 단계별 프리셋을
# 선언하면, 플랫폼이 학습 화면에 "가로 phase 카드 파이프라인"으로 렌더하고 각
# phase 의 ``params`` 를 /run 에 그대로 POST 한다. ``chain_from`` 은 직전 phase 의
# /output 을 이 phase 입력으로 잇는다(플랫폼이 reserved param 으로 주입).
# 단일 phase 컨테이너는 recipe 를 생략하면 기존 단일 launch 경로 그대로 동작.


class RecipePhase(_StrictBase):
    id: Annotated[str, Field(min_length=1, max_length=63)]
    label: Annotated[str, Field(min_length=1)]
    description: Optional[str] = None
    # 이 phase 를 /run 으로 실행할 때 보낼 프리셋 params (사용자가 UI 에서 편집 가능).
    params: Dict[str, Any] = Field(default_factory=dict)
    # 직전 phase id — 그 phase 의 /output 체크포인트를 이 phase 입력으로 체이닝.
    chain_from: Optional[str] = None
    # 체이닝 입력 매핑 — {param_key: template}. template 의 `{checkpoint_name}`
    # 토큰이 chain_from phase 의 커밋 이름으로 치환되어 해당 param 으로 들어간다.
    # 예: {"resume_lora_path": "/models/checkpoints/{checkpoint_name}"}.
    # 플랫폼이 launch 시 `_base_model={name: <model>}` 도 함께 주입해 그 모델의
    # commit_models 를 /models/checkpoints 로 mount(pod.yaml). chain_from 필수.
    chain_inputs: Optional[Dict[str, str]] = None
    # 선택 단계(예: Phase 4-GAA) — UI 에서 기본 off 토글로 노출.
    optional: bool = False

    @field_validator("id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9_-]*$", v):
            raise ValueError(
                f"recipe phase id must be a slug [a-z0-9_-]; got {v!r}"
            )
        return v


class Recipe(_StrictBase):
    label: Optional[str] = None
    phases: Annotated[List[RecipePhase], Field(min_length=1)]

    @model_validator(mode="after")
    def _check_phase_graph(self) -> "Recipe":
        ids = [p.id for p in self.phases]
        if len(ids) != len(set(ids)):
            raise ValueError("recipe phase ids must be unique")
        seen: set[str] = set()
        for p in self.phases:
            if p.chain_from is not None:
                if p.chain_from not in ids:
                    raise ValueError(
                        f"phase {p.id!r} chain_from={p.chain_from!r} references unknown phase id"
                    )
                if p.chain_from not in seen:
                    raise ValueError(
                        f"phase {p.id!r} chain_from={p.chain_from!r} must reference an earlier phase"
                    )
            if p.chain_inputs and not p.chain_from:
                raise ValueError(
                    f"phase {p.id!r} declares chain_inputs but no chain_from"
                )
            if p.chain_inputs:
                # 예약 키 금지 — chain_inputs 로 _base_model/_dataset/
                # _built_in_checkpoint 를 덮어쓰면 플랫폼 mount 주입을 무력화한다.
                _reserved = {"_base_model", "_dataset", "_built_in_checkpoint"}
                _bad = sorted(_reserved & set(p.chain_inputs.keys()))
                if _bad:
                    raise ValueError(
                        f"phase {p.id!r} chain_inputs must not set reserved keys {_bad}"
                    )
            seen.add(p.id)
        return self


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

    # 선택 — 다단계 학습 레시피(SP-10 도메인 카드/프리셋). 생략 시 단일 launch.
    recipe: Optional[Recipe] = None

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
