"""
schemas.py — 에바(Eva) MSA API Pydantic 요청/응답 모델

엔드포인트별 스키마:
  /health          HealthResponse
  /info            InfoResponse
  /run             RunRequest → RunResponse          (추론)
  /train           TrainRequest → TrainResponse      (학습 시작)
  /train/status    TrainStatusResponse               (학습 진행 조회)
  /train/stop      TrainStopResponse                 (학습 중지)
  /models          ModelsResponse                    (체크포인트 목록)
  /deploy          DeployRequest → DeployResponse    (체크포인트 전환)
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ── 공통 ──────────────────────────────────────────────────────────────────────

class AISRow(BaseModel):
    ship_id:     int
    my_ship:     int    = Field(description="1=자선(own vessel), 0=타선(nearby vessel)")
    latitude:    float
    longitude:   float
    knot:        float
    heading:     float
    length:      int
    width:       int
    draft:       int
    bbox_x:      Optional[float] = None
    bbox_y:      Optional[float] = None
    bbox_width:  Optional[float] = None
    bbox_height: Optional[float] = None
    timestamp:   Optional[str]   = None


OutputType = Literal[
    "영문 해상상황묘사",
    "한글 해상상황묘사",
    "영문 항해조력메시지",
    "한글 항해조력메시지",
    "간결 항해조력메시지",
]

TrainingPhase = Literal["projector", "lora", "lora_marine", "lora_sds"]
TrainScenario = Literal["en", "ko", "ko_compact"]
TrainStatus   = Literal["pending", "running", "completed", "failed", "stopped"]


# ══════════════════════════════════════════════════════════════════════════════
# /health
# ══════════════════════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    status:       Literal["healthy", "loading", "error"]
    timestamp:    str
    model_loaded: bool
    device:       Optional[str]   = None
    vram_used_gb: Optional[float] = None


# ══════════════════════════════════════════════════════════════════════════════
# /info
# ══════════════════════════════════════════════════════════════════════════════

class InfoResponse(BaseModel):
    name:         str
    version:      str
    description:  str
    capabilities: List[str]
    vision_model: Optional[str] = None
    llm_model:    Optional[str] = None
    checkpoint:   Optional[str] = None
    output_types: List[str]     = []


# ══════════════════════════════════════════════════════════════════════════════
# /run  (추론)
# ══════════════════════════════════════════════════════════════════════════════

class RunParams(BaseModel):
    image_base64:       str          = Field(description="base64 인코딩된 PNG/JPG 이미지")
    ais_rows:           List[AISRow] = Field(description="선박 AIS 데이터 행 목록")
    output_type:        OutputType   = "영문 해상상황묘사"
    custom_prompt:      Optional[str] = Field(None, description="직접 지정 프롬프트 (없으면 output_type 기본값 사용)")
    max_new_tokens:     int           = 512
    repetition_penalty: float         = 1.1
    do_sample:          bool          = False


class RunRequest(BaseModel):
    workspace_id: str
    project_id:   str
    params:       RunParams


class RunResult(BaseModel):
    output_type:        str
    text:               str
    inference_time_sec: float
    active_checkpoint:  Optional[str] = None


class RunResponse(BaseModel):
    status:  Literal["success", "error"]
    result:  Optional[RunResult] = None
    code:    Optional[str]       = None
    message: Optional[str]       = None


# ══════════════════════════════════════════════════════════════════════════════
# /train  (학습)
# ══════════════════════════════════════════════════════════════════════════════

class TrainParams(BaseModel):
    phase: TrainingPhase = Field(
        description=(
            "학습 단계. "
            "projector=Phase1(프로젝터 사전학습), "
            "lora=Phase2a(CC3M LoRA), "
            "lora_marine=Phase2b(해양 텍스트 계속학습), "
            "lora_sds=Phase3(SDS 도메인 특화)"
        )
    )

    # 공통 경로 설정 (NFS 마운트 경로 기준)
    llm_model_path:       str   = Field(description="베이스 LLM 모델 경로 (NFS)")
    output_checkpoint_name: str = Field(description="저장할 체크포인트 디렉토리 이름")

    # Phase 1/2a/3 공통 (이미지+텍스트 학습)
    data_path:    Optional[str]  = Field(None, description="학습 데이터 JSON 파일 경로")
    image_dir:    Optional[str]  = Field(None, description="이미지 디렉토리 경로")

    # Phase 1/2a/3 선택
    projector_path:    Optional[str]  = Field(None, description="기존 projector.bin 경로 (Phase2a/3)")
    resume_lora_path:  Optional[str]  = Field(None, description="이어받을 LoRA 체크포인트 경로 (Phase2b/3)")

    # Phase 2b (lora_marine) — 텍스트 전용
    marine_data_path: Optional[str] = Field(None, description="해양 텍스트 데이터 경로 (Parquet, Phase2b)")

    # Phase 3 (lora_sds) 시나리오 선택
    sds_scenario: Optional[TrainScenario] = Field(None, description="SDS 시나리오 (Phase3 전용)")

    # 하이퍼파라미터 (미입력 시 각 Phase 기본값 사용)
    num_epochs:         Optional[int]   = None
    batch_size:         Optional[int]   = None
    grad_accum:         Optional[int]   = None
    learning_rate:      Optional[float] = None
    lora_r:             Optional[int]   = None
    lora_alpha:         Optional[int]   = None
    max_steps:          Optional[int]   = None

    # DeepSpeed ZeRO stage
    zero_stage: int = 2


class TrainRequest(BaseModel):
    workspace_id: str
    project_id:   str
    params:       TrainParams


class TrainResponse(BaseModel):
    status:  Literal["success", "error"]
    result:  Optional[dict] = None   # {"job_id": str, "message": str}
    code:    Optional[str]  = None
    message: Optional[str]  = None


class TrainStatusResponse(BaseModel):
    job_id:          str
    status:          TrainStatus
    phase:           Optional[str]   = None
    progress_pct:    Optional[float] = None   # 0~100
    current_step:    Optional[int]   = None
    total_steps:     Optional[int]   = None
    current_loss:    Optional[float] = None
    elapsed_sec:     Optional[float] = None
    output_dir:      Optional[str]   = None
    message:         Optional[str]   = None
    error:           Optional[str]   = None


class TrainStopResponse(BaseModel):
    status:  Literal["success", "error"]
    job_id:  Optional[str] = None
    message: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# /models  (체크포인트 목록)
# ══════════════════════════════════════════════════════════════════════════════

class CheckpointInfo(BaseModel):
    name:        str
    path:        str
    has_lora:    bool
    size_mb:     Optional[float] = None
    created_at:  Optional[str]   = None
    is_active:   bool = False


class ModelsResponse(BaseModel):
    checkpoints_root: str
    checkpoints:      List[CheckpointInfo]
    active_checkpoint: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# /deploy  (체크포인트 전환)
# ══════════════════════════════════════════════════════════════════════════════

class DeployParams(BaseModel):
    checkpoint_name: str = Field(
        description="로드할 체크포인트 디렉토리 이름 (/models/checkpoints/ 하위)"
    )
    vision_model_name: Optional[str] = Field(
        None,
        description="비전 모델 변경 시 지정 (기본: 현재 로드된 값 유지)"
    )
    llm_model_path: Optional[str] = Field(
        None,
        description="LLM 모델 변경 시 지정 (기본: 현재 로드된 값 유지)"
    )


class DeployRequest(BaseModel):
    workspace_id: str
    project_id:   str
    params:       DeployParams


class DeployResponse(BaseModel):
    status:           Literal["success", "error"]
    checkpoint_path:  Optional[str]   = None
    device:           Optional[str]   = None
    vram_used_gb:     Optional[float] = None
    code:             Optional[str]   = None
    message:          Optional[str]   = None
