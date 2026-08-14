"""llm_data_pipeline request DTO.

경계에서만 검증한다. 응답은 플랫폼 envelope(`utils.resource.response`)를 그대로 쓰고
result 내부는 dict 로 흘려보낸다 — llm_evaluation 과 같은 방식.
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from data_pipeline.constants import (
    ASSET_STATUSES,
    COORD_REMAP_STEP,
    DATASET_STATES,
    GATE_AXES,
    GEOMETRIC_STEPS,
    PRESETS,
    REVIEW_VERDICTS,
    SPLIT_BY,
    SPLITS,
    STAGES,
    TAXONOMY,
    THRESHOLD_MAX,
    THRESHOLD_MIN,
    TRAIN_FORMATS,
)

_AXIS_KEYS = tuple(a["key"] for a in GATE_AXES)


class DatasetCreateBody(BaseModel):
    """데이터셋 생성. 만들어진 직후는 데이터가 없는 'draft' 이며, 업로드를 해야 시작된다."""

    workspace_id: int = Field(..., ge=1, description="소속 워크스페이스 id")
    name: str = Field(..., min_length=1, max_length=128, description="데이터셋 이름(워크스페이스 내 고유)")
    description: Optional[str] = Field(default=None, max_length=1000)
    preset: str = Field(default=PRESETS[0], description="파이프라인 프리셋: generic|sds_colreg")

    @field_validator("preset")
    @classmethod
    def _validate_preset(cls, v: str) -> str:
        if v not in PRESETS:
            raise ValueError(f"unknown preset: {v}")
        return v


class DatasetUpdateBody(BaseModel):
    """데이터셋 메타 수정. 이름·설명·상태만 바꾼다(파이프라인 구성은 flow 쪽)."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=1000)
    state: Optional[str] = Field(default=None, description="draft|running|active|archived")

    @field_validator("state")
    @classmethod
    def _validate_state(cls, v):
        if v is not None and v not in DATASET_STATES:
            raise ValueError(f"unknown state: {v}")
        return v


class FlowNode(BaseModel):
    """파이프라인 노드 하나.

    steps 는 [기능명, 파라미터표시값] 쌍의 목록이다. 전처리·필터 노드는 여러 기능을
    묶은 그룹이라 steps 가 차고, data/generate/gate 같은 단일 스테이지 노드는 비어 있다.
    """

    kind: str = Field(..., description="data|prep|filter|synth|gate|src|join|calc|gen|out")
    name: str = Field(..., min_length=1, max_length=64)
    steps: List[List[str]] = Field(default_factory=list, description="[[기능명, 파라미터표시값], ...]")
    config: Dict = Field(default_factory=dict, description="노드 파라미터 원본값")


class FlowUpdateBody(BaseModel):
    """파이프라인 노드 체인 저장.

    sds_colreg 프리셋은 노드 구성이 도메인 논리(조인 → 계산 → 생성 순서)에 묶여 있어
    서비스 계층에서 편집을 거부한다. 여기서는 형태만 본다.
    """

    preset: str = Field(..., description="generic|sds_colreg")
    nodes: List[FlowNode] = Field(..., min_length=1)
    # 노드 간 연결. [출발 index, 도착 index] 쌍. 비우면 선형(0→1→2…)으로 본다.
    flow: List[List[int]] = Field(default_factory=list)

    @field_validator("preset")
    @classmethod
    def _validate_preset(cls, v: str) -> str:
        if v not in PRESETS:
            raise ValueError(f"unknown preset: {v}")
        return v


class StageConfigBody(BaseModel):
    """단계 설정 저장 — 전처리 · 필터 공통 입구.

    enabled 는 기능 on/off, params 는 기능별 파라미터. 단계마다 의미 있는 키가 달라
    dict 로 받고 서비스가 해석한다.
    """

    enabled: Dict[str, bool] = Field(default_factory=dict, description="기능명 → 사용 여부")
    params: Dict = Field(default_factory=dict, description="기능 파라미터")


class GenerateConfigBody(BaseModel):
    """생성 단계 설정.

    생성 모델과 심사 모델이 같으면 자기 결과를 자기가 채점하게 되어 맹점이 겹친다.
    그러면 게이트가 통과율만 올릴 뿐 걸러내지 못하므로 여기서 막는다.
    """

    generator_model: str = Field(..., description="생성 모델 id")
    judge_model: str = Field(..., description="심사 모델 id")
    templates: List[str] = Field(default_factory=list, description="선택한 생성 템플릿 key")
    prompt: str = Field(default="", max_length=8000)
    per_image: int = Field(default=3, ge=1, le=20, description="이미지당 생성 수")
    answer_length: str = Field(default="중간", description="짧게|중간|설명형")
    language: str = Field(default="ko", description="ko|en|ko + en")
    hard_negative_pct: int = Field(default=0, ge=0, le=100, description="함정 데이터 비율(%)")
    # 생성 모델 == 심사 모델 검사는 여기서 하지 않는다 — service.judge_model_pairing 이
    # 같은 계열 경고까지 한 곳에서 판정하고, 여기서 또 막으면 422 가 먼저 떨어져
    # 사용자가 그 안내문을 못 본다.


class GateConfigBody(BaseModel):
    """VLM 심사 임계값 저장. 4축 전부 지정해야 하고 허용 범위를 벗어나면 거부한다."""

    thresholds: Dict[str, float] = Field(..., description="축 key → 임계값(0~1)")
    max_regenerate: int = Field(default=3, ge=0, le=10, description="미달 레코드 재생성 최대 횟수")

    @field_validator("thresholds")
    @classmethod
    def _validate_thresholds(cls, v: Dict[str, float]) -> Dict[str, float]:
        missing = [k for k in _AXIS_KEYS if k not in v]
        if missing:
            raise ValueError(f"missing threshold axes: {missing}")
        for k, val in v.items():
            if k not in _AXIS_KEYS:
                raise ValueError(f"unknown axis: {k}")
            if not (THRESHOLD_MIN <= float(val) <= THRESHOLD_MAX):
                raise ValueError(f"threshold out of range [{THRESHOLD_MIN}, {THRESHOLD_MAX}]: {k}={val}")
        return v


class AssetItem(BaseModel):
    """등록할 원본 하나. 파일을 업로드받는 것이 아니라 드라이브의 참조를 받는다."""

    name: str = Field(..., min_length=1, max_length=255)
    path: Optional[str] = Field(default=None, max_length=1024)
    kind: Optional[str] = Field(default=None, max_length=32)
    size_bytes: Optional[int] = Field(default=None, ge=0)
    status: str = Field(default="registered", description="registered|duplicate|failed")
    fail_reason: Optional[str] = Field(default=None, max_length=255)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        if v not in ASSET_STATUSES:
            raise ValueError(f"unknown asset status: {v}")
        return v


class AssetRegisterBody(BaseModel):
    assets: List[AssetItem] = Field(..., min_length=1, max_length=5000)


class StageRunBody(BaseModel):
    """단계 실행 요청. dry_run 이면 소규모 표본만 돌려 미리보기를 만든다.

    TODO(2차): 실행 라우트는 아직 없다. 실제 전처리·생성·심사는 외부 컨테이너
    (fb_external_container) 디스패치가 필요하고 그 배선이 2차 범위라, 지금 라우트를
    열면 아무 일도 안 하면서 성공을 돌려주게 된다. 계약은 설계 문서에도 2차로 표기.
    """

    dry_run: bool = Field(default=False, description="소규모 표본 실행")
    sample_size: int = Field(default=10, ge=1, le=100, description="dry_run 표본 수")


class ReviewBody(BaseModel):
    """사람 검수 판정.

    'edited' 는 질문·답을 고쳐서 승인한 경우라 수정본이 반드시 있어야 한다.
    'rejected' 는 왜 버렸는지 남겨야 나중에 생성 프롬프트를 고칠 근거가 된다.
    """

    verdict: str = Field(..., description="approved|edited|rejected")
    taxonomy: Optional[str] = Field(default=None, description="오류 유형")
    edited_question: Optional[str] = Field(default=None, max_length=4000)
    edited_answer: Optional[str] = Field(default=None, max_length=8000)

    @field_validator("verdict")
    @classmethod
    def _validate_verdict(cls, v: str) -> str:
        if v not in REVIEW_VERDICTS:
            raise ValueError(f"unknown verdict: {v}")
        return v

    @field_validator("taxonomy")
    @classmethod
    def _validate_taxonomy(cls, v):
        if v not in (None, "") and v not in TAXONOMY:
            raise ValueError(f"unknown taxonomy: {v}")
        return v


class VersionCreateBody(BaseModel):
    """데이터셋 버전(릴리스) 생성 — 구성·분할을 확정해 스냅샷을 남긴다.

    분할 비율은 합이 0 이면 나눌 수 없으므로 최소 하나는 0 보다 커야 한다.
    """

    version: str = Field(..., min_length=1, max_length=32, description="예: v0.4.0")
    mix: Dict[str, int] = Field(default_factory=dict, description="데이터 유형 → 가중치")
    split: Dict[str, int] = Field(default_factory=dict, description="train|validation|test → 비율")
    split_by: str = Field(default=SPLIT_BY[0], description="분리 기준")

    @field_validator("split")
    @classmethod
    def _validate_split(cls, v: Dict[str, int]) -> Dict[str, int]:
        if not v:
            return v
        unknown = [k for k in v if k not in SPLITS]
        if unknown:
            raise ValueError(f"unknown split keys: {unknown}")
        if sum(v.values()) <= 0:
            raise ValueError("split 합이 0 입니다 — 최소 하나는 0 보다 커야 합니다")
        return v

    @field_validator("split_by")
    @classmethod
    def _validate_split_by(cls, v: str) -> str:
        if v not in SPLIT_BY:
            raise ValueError(f"unknown split_by: {v}")
        return v


class VerifyFormatBody(BaseModel):
    """학습 형식 미리 검사 — 실제 학습 코드가 읽을 수 있는지 데이터셋 생성 전에 본다."""

    formats: List[str] = Field(default_factory=lambda: list(TRAIN_FORMATS))

    @field_validator("formats")
    @classmethod
    def _validate_formats(cls, v: List[str]) -> List[str]:
        unknown = [f for f in v if f not in TRAIN_FORMATS]
        if unknown:
            raise ValueError(f"unknown formats: {unknown}")
        return v


def validate_stage(stage: str) -> str:
    """스테이지 이름은 경로 파라미터로 오므로 라우트에서 이 헬퍼로 검증한다."""
    if stage not in STAGES:
        raise ValueError(f"unknown stage: {stage}")
    return stage


def needs_coord_remap(step_names) -> bool:
    """기하 변형이 걸렸는데 좌표 보정이 빠졌는지 본다. 빠지면 bbox 가 원본 기준으로
    남아 이미지와 어긋난다."""
    has_geom = any(s in GEOMETRIC_STEPS for s in step_names)
    return has_geom and COORD_REMAP_STEP not in step_names
