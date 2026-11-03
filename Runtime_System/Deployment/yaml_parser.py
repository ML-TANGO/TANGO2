"""
yaml_parser.py
==============
모델 배포 파이프라인 설정 YAML(deploy.yaml) 파서 / 검증기 / 실행계획 해석기.

v2 변경점 (실제 구현과 스키마 정렬):
  - input_torchscript → input_model + input_format 으로 교체
    (하위호환: input_torchscript 가 있으면 경고와 함께 input_model 로 승격)
  - quant_method 허용값을 optimizer.py 구현과 일치시킴 (awq/gptq/rtn/none)
    smoothquant/bitsandbytes 는 '미구현'으로 분리해 명확한 에러를 낸다
  - ENGINE_SPECS: target_engine → 필요 모델 포맷 / 허용 양자화 제약 테이블 추가
    (llama.cpp 는 GGUF 자체 양자화를 쓰므로 awq/gptq 산출물을 먹지 못한다 등)
  - pruning_info 는 아직 미구현 → 지정 시 '무시됨' 경고
  - resolve_plan(): 검증된 설정 → pipeline.py 가 그대로 실행할 수 있는 Plan 으로 변환

구성 섹션:
  - input_model / input_format : 입력 모델 경로와 포맷
  - code_generation            : 타겟 엔진 / 서비스 / 코딩 정보
  - image_build                : 컨테이너/배포 빌드 정보
  - optimization               : 캘리브레이션 / 프루닝 / 양자화
  - prompt_engineering         : 프롬프트 설정
  - RAG                        : RAG 설정

사용 예:
    from yaml_parser import DeployConfig
    cfg = DeployConfig.from_yaml("deploy.yaml")
    errors, warnings = cfg.validate()
    plan = cfg.resolve_plan()

CLI:
    python yaml_parser.py deploy.yaml            # 파싱 + 검증
    python yaml_parser.py deploy.yaml --strict   # 경고도 에러 처리
    python yaml_parser.py deploy.yaml --plan     # 해석된 실행 계획 출력
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML이 필요합니다: pip install pyyaml")


# ---------------------------------------------------------------------------
# 허용 값(enum) 정의
# ---------------------------------------------------------------------------
INPUT_FORMATS = {"pytorch", "safetensors"}
MODEL_FORMATS = {"pytorch", "safetensors", "gguf", "onnx"}

SERVICE_TYPES = {"sds", "sdf", "sdm"}
DEPLOY_METHODS = {"k8s", "k3s", "docker", "raw"}
TARGET_ARCHS = {"x86", "arm"}
STORAGE_CLASSES = {"local", "minio", "nfs", "aws"}
INVOKE_TIMES = {"period", "event", "user"}
SAVE_PRECISIONS = {"f16", "bf16", "f32"}

# 양자화 — optimizer.py 가 실제로 구현한 것과 아직 아닌 것을 분리한다.
QUANT_IMPLEMENTED = {"awq", "gptq", "rtn", "fp8", "nvfp4"}
QUANT_PLANNED = {"smoothquant", "bitsandbytes"}
QUANT_METHODS = QUANT_IMPLEMENTED | QUANT_PLANNED | {"none"}
QUANT_BITS = {4, 8}                 # 16 = 양자화 안 함 → none 으로 정규화
GROUP_SIZES = {-1, 64, 128}
CALIB_REQUIRED = {"awq", "gptq", "fp8", "nvfp4"}   # 캘리브레이션이 필수인 방식

# NVIDIA ModelOpt 경유 방식 — bits/group_size/zero_point 를 설정으로 받지 않는다.
#   FP8   : per-tensor scaling, Hopper(sm89) 이상
#   NVFP4 : block size 16 고정, Blackwell(sm100) 이상
MODELOPT_METHODS = {"fp8", "nvfp4"}
MODELOPT_IMPLIED_BITS = {"fp8": 8, "nvfp4": 4}

# 프루닝 (pruner.py 구현)
PRUNING_METHODS = {"structural", "unstructural", "wanda"}
PRUNING_IMPLEMENTED = {"structural", "unstructural", "wanda"}
PRUNING_CALIB_REQUIRED = {"wanda"}      # 활성 통계가 필요한 방식
PRUNING_SCOPES = {"layer", "global"}

# GGUF 자체 양자화 타입(llama.cpp 경로에서 save_precision/quant 대체)
GGUF_OUTTYPES = {"f32", "f16", "bf16", "q8_0", "auto"}


@dataclass(frozen=True)
class EngineSpec:
    """target_engine 이 요구하는 산출물 포맷과 양자화 제약."""
    model_format: str                 # 이 엔진이 로드하는 최종 포맷
    quant_methods: frozenset          # 이 엔진 경로에서 허용되는 quant_method
    implemented: bool                 # 파이프라인이 끝까지 만들어 줄 수 있는가
    note: str = ""


ENGINE_SPECS: dict[str, EngineSpec] = {
    # vLLM: AWQ/GPTQ 체크포인트를 그대로 로드한다.
    "vllm": EngineSpec(
        model_format="safetensors",
        quant_methods=frozenset({"none", "awq", "gptq", "rtn"}),
        implemented=True,
    ),
    # llama.cpp: 가중치 양자화를 GGUF 자체 타입(q8_0 등)으로 처리한다.
    #   AWQ/GPTQ 로 팩된 체크포인트는 convert_hf_to_gguf.py 가 읽지 못한다.
    "llama.cpp": EngineSpec(
        model_format="gguf",
        quant_methods=frozenset({"none", "rtn"}),
        implemented=True,
        note="가중치 양자화는 optimization.gguf_outtype(q8_0 등)으로 지정하세요. "
             "AWQ/GPTQ 체크포인트는 GGUF 변환 대상이 아닙니다.",
    ),
    # TensorRT-LLM: TRT 엔진 백엔드가 제거되어 PyTorch 백엔드만 남았다.
    #   엔진 빌드 단계가 없고 HF 체크포인트를 그대로 로드하므로 vllm 과 거의 같다.
    #   다른 점은 양자화 경로뿐 — ModelOpt 로 내보낸 체크포인트를 쓴다.
    "trtllm": EngineSpec(
        model_format="safetensors",
        quant_methods=frozenset({"none", "fp8", "nvfp4"}),
        implemented=True,
        note="양자화는 NVIDIA ModelOpt(fp8/nvfp4)를 사용합니다. "
             "AWQ/GPTQ 체크포인트를 쓰려면 target_engine=vllm 을 검토하세요.",
    ),

    # TensorRT: 인코더 전용(CLIP, ViT, 임베딩). ONNX 까지는 만들지만
    #   engine(.plan) 빌드 단계는 아직 없다.
    #   양자화는 .plan 빌드 시점의 INT8 캘리브레이션이 담당하므로 사전 양자화를
    #   받지 않는다. RTN fake-quant 를 거쳐 ONNX 로 내보내면 크기는 그대로인데
    #   정확도만 잃는다.
    "tensorrt": EngineSpec(
        model_format="onnx",
        quant_methods=frozenset({"none"}),
        implemented=False,
        note="ONNX export 까지만 수행합니다. .plan(engine) 빌드 단계는 아직 미구현입니다. "
             "양자화는 .plan 빌드 시 INT8 캘리브레이션으로 처리하세요. "
             "LLM 이 아니라 인코더 전용 모델을 위한 경로입니다.",
    ),
    # PyTorch 직접 실행
    "pytorch": EngineSpec(
        model_format="safetensors",
        quant_methods=frozenset({"none", "rtn"}),
        implemented=True,
    ),
}
TARGET_ENGINES = set(ENGINE_SPECS)


def _as_bool(v: Any) -> Optional[bool]:
    """yes/no/true/false/bool → bool 변환. 변환 불가 시 None."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"yes", "true", "y", "1"}:
            return True
        if s in {"no", "false", "n", "0"}:
            return False
    return None


def _norm(v: Any) -> Any:
    """문자열 enum 값을 소문자로 정규화."""
    return v.lower() if isinstance(v, str) else v


def detect_input_format(model_dir: str) -> Optional[str]:
    """모델 폴더의 가중치 확장자로 input_format 을 추정. 실패 시 None."""
    from pathlib import Path
    p = Path(model_dir)
    if not p.is_dir():
        return None
    if any(p.glob("*.safetensors")):
        return "safetensors"
    if any(p.glob("*.bin")) or any(p.glob("*.pth")) or any(p.glob("*.pt")):
        return "pytorch"
    return None


def _build(cls, data: Optional[dict]):
    """dict → dataclass 변환 (정의되지 않은 키는 extra에 보관)."""
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(f"{cls.__name__}: dict가 필요하지만 {type(data).__name__} 수신")
    known = {f.name for f in fields(cls)}
    kwargs, extra = {}, {}
    for k, v in data.items():
        if k in known:
            kwargs[k] = v
        else:
            extra[k] = v
    obj = cls(**kwargs)
    if extra and hasattr(obj, "extra"):
        obj.extra = extra
    return obj


class ConfigError(Exception):
    """설정 파일 구조/타입 오류."""


# ---------------------------------------------------------------------------
# code_generation
# ---------------------------------------------------------------------------
@dataclass
class ServiceSpec:
    invoke_time: Optional[str] = None          # period / event / user
    service_ip: Optional[str] = None
    service_port: Optional[int] = None
    service_shared_folder: Optional[str] = None
    extra: dict = field(default_factory=dict)  # sds 카메라, sdf 센서 등 타입별 자유 항목


@dataclass
class ServiceInfo:
    service_type: Optional[str] = None         # sds / sdf / sdm
    spec: Any = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.spec, dict) or self.spec is None:
            self.spec = _build(ServiceSpec, self.spec)


@dataclass
class SdfAction:
    lib_path: Optional[str] = None
    entry_point: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class CodingInfo:
    sdf_action: Any = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.sdf_action, dict) or self.sdf_action is None:
            self.sdf_action = _build(SdfAction, self.sdf_action)


@dataclass
class CodeGeneration:
    target_engine: Optional[str] = None        # vllm / tensorrt / pytorch / llama.cpp
    service_info: Any = None
    coding_info: Any = None
    use_triton: Any = None                     # yes / no
    use_optimization: Any = None
    use_prompt_engineering: Any = None
    use_RAG: Any = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.service_info, dict) or self.service_info is None:
            self.service_info = _build(ServiceInfo, self.service_info)
        if isinstance(self.coding_info, dict) or self.coding_info is None:
            self.coding_info = _build(CodingInfo, self.coding_info)


# ---------------------------------------------------------------------------
# image_build
# ---------------------------------------------------------------------------
@dataclass
class BuildInfo:
    app_name: Optional[str] = None
    image_file: Optional[str] = None
    target_arch: Optional[str] = None          # x86 / arm
    replicas_num: Optional[int] = None
    target_ip: Optional[str] = None
    target_port: Optional[int] = None
    mount_volume: Optional[str] = None
    storage_class: Optional[str] = None        # local / minio / nfs / aws
    extra: dict = field(default_factory=dict)


@dataclass
class ImageBuild:
    deploy_method: Optional[str] = None        # k8s / k3s / docker / raw
    build_info: Any = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.build_info, dict) or self.build_info is None:
            self.build_info = _build(BuildInfo, self.build_info)


# ---------------------------------------------------------------------------
# optimization
# ---------------------------------------------------------------------------
@dataclass
class CalibrationInfo:                          # awq / gptq용
    dataset_path: Optional[str] = None
    sample_sentence_number: Optional[int] = None
    max_len_tokens_per_sentence: Optional[int] = None
    tokenizer_path: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class PruningInfo:
    pruning_method: Optional[str] = None        # structural / unstructural / wanda
    sparsity_ratio: Any = None                  # "50%" 또는 0.5
    target_layers: Any = None                   # all 또는 ["model.layers.10", ...]
    nm_pattern: Optional[str] = None            # "2:4" 등 semi-structured (선택)
    scope: Optional[str] = None                 # layer / global (선택)
    extra: dict = field(default_factory=dict)

    def sparsity(self) -> Optional[float]:
        """'50%' / 50 / 0.5 → 0.5 로 정규화."""
        v = self.sparsity_ratio
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip().rstrip("%")
            try:
                v = float(v)
            except ValueError:
                return None
        if isinstance(v, (int, float)):
            return v / 100.0 if v > 1 else float(v)
        return None


@dataclass
class GptqParam:
    damping_factor: Optional[float] = None
    act_order: Any = None
    desc_act: Any = None
    extra: dict = field(default_factory=dict)

    def effective_act_order(self) -> bool:
        """act_order 와 desc_act 는 같은 뜻 — 둘 중 지정된 값을 쓴다."""
        for v in (self.act_order, self.desc_act):
            b = _as_bool(v)
            if b is not None:
                return b
        return False


@dataclass
class QuantInfo:
    quant_method: Optional[str] = None          # awq / gptq / rtn / none
    bits: Optional[int] = None                  # 4 / 8
    group_size: Optional[int] = None            # -1 / 64 / 128
    zero_point: Any = None                      # true=asymmetric, false=symmetric
    gptq_param: Any = None
    smoothquant_alpha: Optional[float] = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.gptq_param, dict) or self.gptq_param is None:
            self.gptq_param = _build(GptqParam, self.gptq_param)

    def method(self) -> str:
        """정규화된 quant_method. 미지정/16bit 는 'none'."""
        m = _norm(self.quant_method) or "none"
        if self.bits == 16:
            return "none"
        return m


@dataclass
class Optimization:
    calibration_info: Any = None
    pruning_info: Any = None
    quant_info: Any = None
    save_precision: Optional[str] = None        # f16 / bf16 / f32
    gguf_outtype: Optional[str] = None          # llama.cpp 경로 전용 (f16 / q8_0 ...)
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.calibration_info, dict) or self.calibration_info is None:
            self.calibration_info = _build(CalibrationInfo, self.calibration_info)
        if isinstance(self.pruning_info, dict) or self.pruning_info is None:
            self.pruning_info = _build(PruningInfo, self.pruning_info)
        if isinstance(self.quant_info, dict) or self.quant_info is None:
            self.quant_info = _build(QuantInfo, self.quant_info)


# ---------------------------------------------------------------------------
# prompt_engineering / RAG
# ---------------------------------------------------------------------------
@dataclass
class PromptEngineering:
    prompt_method: Optional[str] = None         # every query / once / etc
    prompt_file: Optional[str] = None
    prompt_info: Any = None
    extra: dict = field(default_factory=dict)


@dataclass
class RagInfo:
    input_source: Optional[str] = None
    chunk_policy: Any = None
    embedding_model: Optional[str] = None
    vector_db_file: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class Rag:
    RAG_method: Optional[str] = None
    RAG_info: Any = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.RAG_info, dict) or self.RAG_info is None:
            self.RAG_info = _build(RagInfo, self.RAG_info)


# ---------------------------------------------------------------------------
# 실행 계획 — validate() 통과 후 pipeline.py 가 소비하는 구조체
# ---------------------------------------------------------------------------
@dataclass
class QuantPlan:
    method: str                        # awq / gptq / rtn ("none"이면 QuantPlan 자체가 None)
    bits: int
    group_size: int
    zero_point: bool
    dataset_path: Optional[str] = None
    num_samples: int = 512
    max_len: int = 2048
    damping: float = 0.01
    act_order: bool = False


@dataclass
class PrunePlan:
    method: str                        # structural / unstructural / wanda
    sparsity: float
    target_layers: Any = None
    nm_pattern: Optional[str] = None
    dataset_path: Optional[str] = None
    num_samples: int = 128
    max_len: int = 2048


@dataclass
class Plan:
    """deploy.yaml 을 실행 가능한 단계 목록으로 해석한 결과."""
    input_model: str
    input_format: str                  # pytorch / safetensors
    target_engine: str
    output_format: str                 # 엔진이 요구하는 최종 포맷
    engine_implemented: bool
    quant: Optional[QuantPlan] = None
    gguf_outtype: str = "f16"
    save_precision: Optional[str] = None
    prune: Optional["PrunePlan"] = None
    stages: list = field(default_factory=list)

    def describe(self) -> str:
        lines = [
            f"입력      : {self.input_model} ({self.input_format})",
            f"타겟 엔진 : {self.target_engine} → 산출 포맷 {self.output_format}"
            + ("" if self.engine_implemented else "  [엔진 빌드 단계 미구현]"),
        ]
        if self.prune:
            p = self.prune
            detail = (f"nm_pattern={p.nm_pattern}" if p.nm_pattern
                      else f"sparsity={p.sparsity:.0%}")
            lines.append(f"프루닝    : {p.method}, {detail}"
                         + (f", calib={p.dataset_path}" if p.dataset_path else ""))
        else:
            lines.append("프루닝    : 없음")
        if self.quant:
            q = self.quant
            if q.method in MODELOPT_METHODS:
                # bits/group_size/zero_point 를 방식이 고정하므로 표시하지 않는다
                detail = f"{q.method} (ModelOpt, {q.bits}bit 고정)"
            else:
                detail = (f"{q.method} {q.bits}bit, group_size={q.group_size}, "
                          f"{'asymmetric' if q.zero_point else 'symmetric'}")
            lines.append("양자화    : " + detail
                         + (f", calib={q.dataset_path}" if q.dataset_path else ""))
        else:
            lines.append("양자화    : 없음")
        if self.output_format == "gguf":
            lines.append(f"GGUF dtype: {self.gguf_outtype}")
        lines.append(f"실행 단계 : {' → '.join(self.stages)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 최상위 설정
# ---------------------------------------------------------------------------
@dataclass
class DeployConfig:
    input_model: Optional[str] = None
    input_format: Optional[str] = None          # pytorch / safetensors
    input_torchscript: Optional[str] = None     # deprecated (하위호환)
    code_generation: Any = None
    image_build: Any = None
    optimization: Any = None
    prompt_engineering: Any = None
    RAG: Any = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.code_generation, dict) or self.code_generation is None:
            self.code_generation = _build(CodeGeneration, self.code_generation)
        if isinstance(self.image_build, dict) or self.image_build is None:
            self.image_build = _build(ImageBuild, self.image_build)
        if isinstance(self.optimization, dict) or self.optimization is None:
            self.optimization = _build(Optimization, self.optimization)
        if isinstance(self.prompt_engineering, dict) or self.prompt_engineering is None:
            self.prompt_engineering = _build(PromptEngineering, self.prompt_engineering)
        if isinstance(self.RAG, dict) or self.RAG is None:
            self.RAG = _build(Rag, self.RAG)

    # ---------------- 로딩 ----------------
    @classmethod
    def from_yaml(cls, path: str) -> "DeployConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ConfigError("최상위 YAML은 매핑(dict)이어야 합니다.")
        return _build(cls, data)

    @classmethod
    def from_string(cls, text: str) -> "DeployConfig":
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ConfigError("최상위 YAML은 매핑(dict)이어야 합니다.")
        return _build(cls, data)

    # ---------------- 검증 ----------------
    def validate(self) -> tuple[list[str], list[str]]:
        """(errors, warnings) 반환."""
        errors: list[str] = []
        warnings: list[str] = []

        def check_enum(value, allowed, path, required=False):
            if value is None:
                if required:
                    errors.append(f"{path}: 필수 값이 비어 있습니다.")
                return
            if _norm(value) not in allowed:
                errors.append(
                    f"{path}: '{value}' 는 허용 값 {sorted(map(str, allowed))} 에 없습니다.")

        # ── 입력 모델 ────────────────────────────────────────────────
        if not self.input_model and self.input_torchscript:
            warnings.append(
                "input_torchscript: 더 이상 쓰지 않는 키입니다. "
                "input_model + input_format 으로 바꾸세요 (이번에는 input_model 로 대신 사용).")
            self.input_model = self.input_torchscript
        if not self.input_model:
            errors.append("input_model: 입력 모델 폴더 경로가 필요합니다.")
        if not self.input_format and self.input_model:
            detected = detect_input_format(self.input_model)
            if detected:
                warnings.append(
                    f"input_format: 미지정 → 폴더 내용으로 '{detected}' 자동 감지. "
                    f"명시적으로 적어두는 편이 안전합니다.")
                self.input_format = detected
            else:
                errors.append(
                    "input_format: 필수 값이 비어 있고 자동 감지도 실패했습니다 "
                    f"(가능: {sorted(INPUT_FORMATS)}).")
        else:
            check_enum(self.input_format, INPUT_FORMATS, "input_format", required=True)

        # ── code_generation ─────────────────────────────────────────
        cg = self.code_generation
        check_enum(cg.target_engine, TARGET_ENGINES, "code_generation.target_engine",
                   required=True)
        check_enum(cg.service_info.service_type, SERVICE_TYPES,
                   "code_generation.service_info.service_type")
        it = cg.service_info.spec.invoke_time
        if it is not None:
            check_enum(it, INVOKE_TIMES, "code_generation.service_info.spec.invoke_time")

        for name in ("use_triton", "use_optimization", "use_prompt_engineering", "use_RAG"):
            raw = getattr(cg, name)
            if raw is not None and _as_bool(raw) is None:
                errors.append(f"code_generation.{name}: '{raw}' 는 yes/no 값이어야 합니다.")

        engine = _norm(cg.target_engine)
        spec = ENGINE_SPECS.get(engine)
        if spec and not spec.implemented:
            warnings.append(
                f"code_generation.target_engine={engine}: {spec.note}")

        # ── image_build ─────────────────────────────────────────────
        ib = self.image_build
        check_enum(ib.deploy_method, DEPLOY_METHODS, "image_build.deploy_method",
                   required=True)
        bi = ib.build_info
        check_enum(bi.target_arch, TARGET_ARCHS, "image_build.build_info.target_arch")
        check_enum(bi.storage_class, STORAGE_CLASSES, "image_build.build_info.storage_class")
        if bi.replicas_num is not None and (
                not isinstance(bi.replicas_num, int) or bi.replicas_num < 1):
            errors.append("image_build.build_info.replicas_num: 1 이상의 정수여야 합니다.")
        if bi.target_port is not None and not (
                isinstance(bi.target_port, int) and 1 <= bi.target_port <= 65535):
            errors.append("image_build.build_info.target_port: 1~65535 범위의 정수여야 합니다.")

        # ── optimization ────────────────────────────────────────────
        use_opt = _as_bool(cg.use_optimization)
        opt = self.optimization
        qi = opt.quant_info
        qm = qi.method()

        if use_opt:
            check_enum(opt.save_precision, SAVE_PRECISIONS, "optimization.save_precision")
            if opt.gguf_outtype is not None:
                check_enum(opt.gguf_outtype, GGUF_OUTTYPES, "optimization.gguf_outtype")

            check_enum(qi.quant_method, QUANT_METHODS,
                       "optimization.quant_info.quant_method")
            if qm in QUANT_PLANNED:
                errors.append(
                    f"optimization.quant_info.quant_method='{qm}': 아직 구현되지 않았습니다. "
                    f"현재 사용 가능: {sorted(QUANT_IMPLEMENTED)}")
            if qi.bits == 16:
                warnings.append(
                    "optimization.quant_info.bits=16: 양자화 없음(none)으로 처리합니다.")
            elif qm in MODELOPT_METHODS:
                # bits/group_size/zero_point 는 방식이 결정한다 — 설정으로 못 바꾼다
                implied = MODELOPT_IMPLIED_BITS[qm]
                if qi.bits is not None and qi.bits != implied:
                    warnings.append(
                        f"optimization.quant_info.bits={qi.bits}: {qm} 는 "
                        f"{implied}bit 로 고정입니다. 지정 값은 무시됩니다.")
                if qi.group_size is not None:
                    detail = ("블록 크기 16 고정" if qm == "nvfp4"
                              else "per-tensor scaling")
                    warnings.append(
                        f"optimization.quant_info.group_size: {qm} 는 {detail}이라 "
                        f"무시됩니다.")
                if _as_bool(qi.zero_point):
                    warnings.append(
                        "optimization.quant_info.zero_point: "
                        f"{qm} 는 symmetric 고정이라 무시됩니다.")
            elif qm in QUANT_IMPLEMENTED:
                if qi.bits is None:
                    warnings.append(
                        "optimization.quant_info.bits: 미지정 → 기본값 4bit 를 사용합니다.")
                elif qi.bits not in QUANT_BITS:
                    errors.append(
                        f"optimization.quant_info.bits: {qi.bits} 는 허용 값 "
                        f"{sorted(QUANT_BITS)} 에 없습니다 (16 = 양자화 없음).")

            if (qm not in MODELOPT_METHODS and qi.group_size is not None
                    and qi.group_size not in GROUP_SIZES):
                warnings.append(
                    f"optimization.quant_info.group_size: {qi.group_size} "
                    f"(일반적인 값은 {sorted(GROUP_SIZES)})")

            # 엔진 ↔ 양자화 방식 호환성
            # (미구현 방식은 위에서 이미 에러를 냈으므로 중복 보고하지 않는다)
            if spec and qm not in QUANT_PLANNED and qm not in spec.quant_methods:
                msg = (f"optimization.quant_info.quant_method='{qm}' 는 "
                       f"target_engine='{engine}' 경로에서 쓸 수 없습니다 "
                       f"(허용: {sorted(spec.quant_methods)}).")
                if spec.note:
                    msg += " " + spec.note
                errors.append(msg)

            # 캘리브레이션
            if qm in CALIB_REQUIRED:
                ci = opt.calibration_info
                if not ci.dataset_path:
                    errors.append(
                        f"optimization.calibration_info.dataset_path: "
                        f"{qm} 양자화에는 필수입니다.")
            if qm == "gptq" and qi.gptq_param.damping_factor is None:
                warnings.append(
                    "optimization.quant_info.gptq_param.damping_factor: "
                    "GPTQ 사용 시 지정을 권장합니다 (기본 0.01).")
            if qm != "gptq" and any(
                v is not None for v in (qi.gptq_param.damping_factor,
                                        qi.gptq_param.act_order,
                                        qi.gptq_param.desc_act)):
                warnings.append(
                    "optimization.quant_info.gptq_param: GPTQ가 아니므로 무시됩니다.")
            if qm != "smoothquant" and qi.smoothquant_alpha is not None:
                warnings.append(
                    "optimization.quant_info.smoothquant_alpha: "
                    "smoothquant가 아니므로 무시됩니다.")

            # 프루닝
            pi = opt.pruning_info
            if pi.pruning_method is not None:
                pm = _norm(pi.pruning_method)
                check_enum(pi.pruning_method, PRUNING_METHODS,
                           "optimization.pruning_info.pruning_method")
                if pi.scope is not None:
                    check_enum(pi.scope, PRUNING_SCOPES,
                               "optimization.pruning_info.scope")

                # nm_pattern 을 쓰면 sparsity 는 패턴이 결정한다
                if pi.nm_pattern:
                    if pm != "unstructural":
                        errors.append(
                            f"optimization.pruning_info.nm_pattern: "
                            f"unstructural 에서만 쓸 수 있습니다 (현재 {pm}).")
                    else:
                        try:
                            n, m = (int(x) for x in str(pi.nm_pattern).split(":"))
                            if not (0 < n < m):
                                raise ValueError
                        except Exception:
                            errors.append(
                                f"optimization.pruning_info.nm_pattern: "
                                f"'{pi.nm_pattern}' 는 'n:m' 형식이어야 합니다 "
                                f"(0 < n < m, 예: '2:4').")
                    if pi.sparsity_ratio is not None:
                        warnings.append(
                            "optimization.pruning_info.sparsity_ratio: "
                            "nm_pattern 이 지정되어 무시됩니다.")
                else:
                    sp = pi.sparsity()
                    if sp is None:
                        errors.append(
                            "optimization.pruning_info.sparsity_ratio: "
                            "숫자 또는 'xx%' 형식이어야 합니다.")
                    elif not (0.0 < sp < 1.0):
                        errors.append(
                            f"optimization.pruning_info.sparsity_ratio: "
                            f"0~100% 사이여야 합니다 (현재 {sp:.0%}).")
                    elif pm == "structural" and sp > 0.5:
                        warnings.append(
                            f"optimization.pruning_info.sparsity_ratio={sp:.0%}: "
                            f"structural 은 출력 채널을 통째로 없애므로 "
                            f"50% 를 넘기면 정확도 손실이 급격히 커집니다.")

                if pm in PRUNING_CALIB_REQUIRED and not opt.calibration_info.dataset_path:
                    errors.append(
                        f"optimization.calibration_info.dataset_path: "
                        f"{pm} 프루닝에는 필수입니다.")
        elif use_opt is False and qi.method() != "none":
            warnings.append(
                "use_optimization=no 이지만 optimization 섹션이 채워져 있어 무시됩니다.")

        # ── prompt_engineering ──────────────────────────────────────
        if _as_bool(cg.use_prompt_engineering):
            pe = self.prompt_engineering
            if not pe.prompt_method and not pe.prompt_file:
                errors.append(
                    "prompt_engineering: use_prompt_engineering=yes 이므로 "
                    "prompt_method 또는 prompt_file이 필요합니다.")

        # ── RAG ─────────────────────────────────────────────────────
        if _as_bool(cg.use_RAG):
            ri = self.RAG.RAG_info
            if not ri.embedding_model:
                errors.append("RAG.RAG_info.embedding_model: use_RAG=yes 이므로 필수입니다.")
            if not ri.input_source:
                errors.append("RAG.RAG_info.input_source: use_RAG=yes 이므로 필수입니다.")

        # ── 알 수 없는 키 경고 ──────────────────────────────────────
        def walk(obj, path):
            if is_dataclass(obj):
                ex = getattr(obj, "extra", None)
                if ex:
                    for k in ex:
                        warnings.append(f"{path}.{k}: 정의되지 않은 키입니다 (extra에 보관됨).")
                for f in fields(obj):
                    if f.name != "extra":
                        walk(getattr(obj, f.name), f"{path}.{f.name}")

        walk(self, "config")
        return errors, warnings

    # ---------------- 실행 계획 해석 ----------------
    def resolve_plan(self) -> Plan:
        """검증을 통과한 설정을 pipeline.py 가 실행할 Plan 으로 변환.
        validate() 로 에러가 없음을 먼저 확인한 뒤 호출할 것."""
        cg = self.code_generation
        opt = self.optimization
        qi = opt.quant_info
        engine = _norm(cg.target_engine)
        spec = ENGINE_SPECS[engine]

        use_opt = bool(_as_bool(cg.use_optimization))
        qm = qi.method() if use_opt else "none"

        quant = None
        if qm in QUANT_IMPLEMENTED:
            ci = opt.calibration_info
            quant = QuantPlan(
                method=qm,
                bits=(MODELOPT_IMPLIED_BITS[qm] if qm in MODELOPT_METHODS
                      else (qi.bits or 4)),
                group_size=qi.group_size if qi.group_size is not None else 128,
                zero_point=bool(_as_bool(qi.zero_point)),
                dataset_path=ci.dataset_path,
                num_samples=ci.sample_sentence_number or 512,
                max_len=ci.max_len_tokens_per_sentence or 2048,
                damping=(qi.gptq_param.damping_factor
                         if qi.gptq_param.damping_factor is not None else 0.01),
                act_order=qi.gptq_param.effective_act_order(),
            )

        prune = None
        pi = opt.pruning_info
        if use_opt and pi.pruning_method:
            ci = opt.calibration_info
            prune = PrunePlan(
                method=_norm(pi.pruning_method),
                sparsity=pi.sparsity() or 0.5,
                target_layers=pi.target_layers,
                nm_pattern=pi.nm_pattern,
                dataset_path=ci.dataset_path,
                num_samples=ci.sample_sentence_number or 128,
                max_len=ci.max_len_tokens_per_sentence or 2048,
            )

        # GGUF dtype: 명시값 → save_precision → f16
        gguf_outtype = _norm(opt.gguf_outtype) or _norm(opt.save_precision) or "f16"
        if gguf_outtype not in GGUF_OUTTYPES:
            gguf_outtype = "f16"

        # 실행 단계 구성
        stages: list[str] = ["validate"]
        if prune:
            stages.append("prune")
        if quant:
            stages.append("quantize")
        in_fmt = _norm(self.input_format)
        out_fmt = spec.model_format
        # convert 는 항상 수행한다. 입력==출력이어도 model_converter 가
        # '해당 포맷 실행에 필요한 파일만' 골라 복사해 주므로 산출물 정리 효과가 있다.
        stages += ["convert", "codegen", "image_build"]

        return Plan(
            input_model=self.input_model,
            input_format=in_fmt,
            target_engine=engine,
            output_format=out_fmt,
            engine_implemented=spec.implemented,
            quant=quant,
            gguf_outtype=gguf_outtype,
            save_precision=_norm(opt.save_precision),
            prune=prune,
            stages=stages,
        )

    # ---------------- 직렬화 ----------------
    def to_dict(self) -> dict:
        def conv(obj):
            if is_dataclass(obj):
                out = {}
                for f in fields(obj):
                    v = conv(getattr(obj, f.name))
                    if f.name == "extra":
                        if v:
                            out.update(v)
                    elif v is not None:
                        out[f.name] = v
                return out or None
            if isinstance(obj, dict):
                return {k: conv(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [conv(v) for v in obj]
            return obj
        return conv(self) or {}

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.to_dict(), allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="배포 설정 YAML 파서/검증기")
    ap.add_argument("yaml_path", help="설정 YAML 파일 경로")
    ap.add_argument("--strict", action="store_true", help="경고도 에러로 처리")
    ap.add_argument("--dump", action="store_true", help="정규화된 설정을 YAML로 출력")
    ap.add_argument("--plan", action="store_true", help="해석된 실행 계획을 출력")
    args = ap.parse_args()

    try:
        cfg = DeployConfig.from_yaml(args.yaml_path)
    except (ConfigError, yaml.YAMLError, OSError) as e:
        print(f"[FATAL] 파일을 읽을 수 없습니다: {e}", file=sys.stderr)
        return 2

    errors, warnings = cfg.validate()
    for w in warnings:
        print(f"[WARN ] {w}")
    for e in errors:
        print(f"[ERROR] {e}")

    if args.dump:
        print("\n--- 정규화된 설정 ---")
        print(cfg.to_yaml())

    if errors or (args.strict and warnings):
        print(f"\n검증 실패: 에러 {len(errors)}건, 경고 {len(warnings)}건")
        return 1

    print(f"\n검증 통과 (경고 {len(warnings)}건)")

    if args.plan:
        print("\n--- 실행 계획 ---")
        print(cfg.resolve_plan().describe())
    return 0


if __name__ == "__main__":
    sys.exit(main())
