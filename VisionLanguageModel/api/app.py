"""
app.py — 에바(Eva) VLM MSA FastAPI 서버 (학습 / 배포 / 추론 통합)

조나단(Jonathan) 플랫폼 MSA 규격 엔드포인트:
    GET  /health              서비스 상태 확인
    GET  /info                서비스 메타정보
    POST /run                 추론 실행 (이미지 + AIS → 텍스트)

에바 확장 엔드포인트 (아크릴과 협의 후 조나단 UI 연동):
    POST /train               학습 시작 (비동기, job_id 반환)
    GET  /train/status        학습 진행 상태 조회
    POST /train/stop          학습 중지
    GET  /models              체크포인트 목록 조회
    POST /deploy              체크포인트 전환 (추론 모델 교체)
"""
from __future__ import annotations

import os
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from model_manager import get_manager, PROMPT_MAP
from train_manager import get_train_manager
from schemas import (
    DeployRequest, DeployResponse,
    HealthResponse,
    InfoResponse,
    ModelsResponse,
    RunRequest, RunResponse, RunResult,
    TrainRequest, TrainResponse,
    TrainStatusResponse, TrainStopResponse,
)

SERVICE_VERSION = "1.0.0"
OUTPUT_TYPES    = list(PROMPT_MAP.keys())


# ── 수명주기 ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    manager = get_manager()
    try:
        print("[Eva] 초기 모델 로드 시작...")
        manager.load()
        print(
            f"[Eva] 모델 로드 완료 — device={manager.device_str}, "
            f"VRAM={manager.vram_used_gb:.1f}GB"
        )
    except Exception:
        print(f"[Eva] 모델 로드 실패 (추론 불가, 다른 엔드포인트는 정상):\n{traceback.format_exc()}")
    yield


app = FastAPI(
    title="Eva VLM MSA API",
    description=(
        "해양 도메인 비전언어모델(에바) 학습·배포·추론 서비스\n"
        "Tango GenAI Platform(조나단) 통합"
    ),
    version=SERVICE_VERSION,
    lifespan=lifespan,
)


# ── 전역 예외 핸들러 ──────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"status": "error", "code": "INTERNAL_ERROR", "message": str(exc)},
    )


# ════════════════════════════════════════════════════════════════════════════════
# 조나단 MSA 표준 엔드포인트
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/health", response_model=HealthResponse, tags=["표준"])
def health_check():
    """서비스 및 모델 로드 상태 확인."""
    m = get_manager()
    if m.is_loading:
        status = "loading"
    elif m.is_loaded:
        status = "healthy"
    else:
        status = "error"

    return HealthResponse(
        status=status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        model_loaded=m.is_loaded,
        device=m.device_str,
        vram_used_gb=m.vram_used_gb,
    )


@app.get("/info", response_model=InfoResponse, tags=["표준"])
def get_info():
    """서비스 메타정보 및 현재 로드된 모델 정보 반환."""
    m = get_manager()
    return InfoResponse(
        name="eva-vlm",
        version=SERVICE_VERSION,
        description=(
            "해양 도메인 특화 Vision-Language Model(에바) 학습·배포·추론 서비스. "
            "선박 카메라 이미지와 AIS 데이터를 입력받아 해상상황묘사 및 "
            "COLREG 기반 항해조력메시지를 생성합니다."
        ),
        capabilities=[
            "maritime-vlm-training",
            "checkpoint-management",
            "maritime-situation-description",
            "navigational-advice",
            "ais-image-fusion",
            "colreg-reasoning",
        ],
        vision_model=m.vision_model_name,
        llm_model=m.llm_model_path,
        checkpoint=m.checkpoint_path,
        output_types=OUTPUT_TYPES,
    )


@app.post("/run", response_model=RunResponse, tags=["표준"])
def run_inference(body: RunRequest):
    """VLM 추론 실행 — 이미지(base64) + AIS 데이터 → 해상상황묘사 / 항해조력메시지."""
    m = get_manager()

    if not m.is_loaded:
        return RunResponse(
            status="error",
            code="SERVICE_UNAVAILABLE",
            message=m.load_error or "모델이 로드되지 않았습니다.",
        )

    p = body.params

    if not p.image_base64:
        return RunResponse(status="error", code="INVALID_PARAMS",
                           message="image_base64 필드가 비어 있습니다.")
    if not p.ais_rows:
        return RunResponse(status="error", code="INVALID_PARAMS",
                           message="ais_rows가 비어 있습니다. 최소 1개 이상 필요합니다.")

    try:
        text, elapsed = m.infer(
            image_base64=p.image_base64,
            ais_rows=p.ais_rows,
            output_type=p.output_type,
            custom_prompt=p.custom_prompt,
            max_new_tokens=p.max_new_tokens,
            repetition_penalty=p.repetition_penalty,
            do_sample=p.do_sample,
        )
    except Exception:
        return RunResponse(
            status="error", code="INTERNAL_ERROR", message=traceback.format_exc()
        )

    return RunResponse(
        status="success",
        result=RunResult(
            output_type=p.output_type,
            text=text,
            inference_time_sec=round(elapsed, 3),
            active_checkpoint=m.checkpoint_path,
        ),
    )


# ════════════════════════════════════════════════════════════════════════════════
# 에바 확장 — 학습 (Training)
# ════════════════════════════════════════════════════════════════════════════════

@app.post("/train", response_model=TrainResponse, tags=["학습"])
async def start_training(body: TrainRequest):
    """
    에바 VLM 학습을 비동기로 시작한다.

    phase 선택:
    - `projector`   : Phase 1 — 프로젝터 사전학습 (CLIP+LLM 고정)
    - `lora`        : Phase 2a — CC3M LoRA 파인튜닝
    - `lora_marine` : Phase 2b — 해양 텍스트 계속학습 (이미지 없음)
    - `lora_sds`    : Phase 3 — SDS 도메인 특화 LoRA

    즉시 `job_id`를 반환하며, 진행 상황은 `GET /train/status?job_id=<id>`로 확인한다.
    """
    tm = get_train_manager()
    try:
        job_id = await tm.start(body.params)
    except RuntimeError as e:
        return TrainResponse(
            status="error", code="RESOURCE_EXHAUSTED", message=str(e)
        )
    except Exception:
        return TrainResponse(
            status="error", code="INTERNAL_ERROR", message=traceback.format_exc()
        )

    return TrainResponse(
        status="success",
        result={
            "job_id": job_id,
            "message": (
                f"Phase '{body.params.phase}' 학습이 시작됐습니다. "
                f"GET /train/status?job_id={job_id} 로 진행 상황을 확인하세요."
            ),
        },
    )


@app.get("/train/status", response_model=TrainStatusResponse, tags=["학습"])
def train_status(job_id: str = Query(..., description="학습 job_id")):
    """학습 작업의 현재 진행 상태를 반환한다."""
    tm  = get_train_manager()
    job = tm.get_job(job_id)
    if job is None:
        return TrainStatusResponse(
            job_id=job_id,
            status="failed",
            message=f"job_id '{job_id}'를 찾을 수 없습니다.",
        )

    return TrainStatusResponse(
        job_id=job.job_id,
        status=job.status,
        phase=job.phase,
        progress_pct=job.progress_pct,
        current_step=job.current_step,
        total_steps=job.total_steps if job.total_steps > 0 else None,
        current_loss=job.current_loss,
        elapsed_sec=round(job.elapsed_sec, 1) if job.elapsed_sec else None,
        output_dir=job.output_dir,
        error=job.error,
    )


@app.post("/train/stop", response_model=TrainStopResponse, tags=["학습"])
async def stop_training(job_id: str = Query(..., description="중지할 학습 job_id")):
    """실행 중인 학습 작업을 중지한다."""
    tm = get_train_manager()
    try:
        await tm.stop(job_id)
    except KeyError as e:
        return TrainStopResponse(
            status="error", message=str(e)
        )
    except RuntimeError as e:
        return TrainStopResponse(
            status="error", job_id=job_id, message=str(e)
        )
    except Exception:
        return TrainStopResponse(
            status="error", job_id=job_id, message=traceback.format_exc()
        )

    return TrainStopResponse(
        status="success",
        job_id=job_id,
        message="학습 작업이 중지됐습니다.",
    )


# ════════════════════════════════════════════════════════════════════════════════
# 에바 확장 — 배포 (Deployment / Checkpoint Management)
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/models", response_model=ModelsResponse, tags=["배포"])
def list_models():
    """
    NFS 체크포인트 루트를 스캔하여 사용 가능한 체크포인트 목록을 반환한다.
    각 항목에는 LoRA 포함 여부, 크기, 현재 활성 여부가 포함된다.
    """
    m    = get_manager()
    root = os.environ.get("EVA_CHECKPOINTS_ROOT", "/models/checkpoints")

    try:
        checkpoints = m.list_checkpoints()
    except Exception:
        checkpoints = []

    return ModelsResponse(
        checkpoints_root=root,
        checkpoints=checkpoints,
        active_checkpoint=m.checkpoint_path,
    )


@app.post("/deploy", response_model=DeployResponse, tags=["배포"])
def deploy_checkpoint(body: DeployRequest):
    """
    지정한 체크포인트를 추론 엔진에 로드한다 (실시간 모델 교체).

    - 기존 모델을 GPU에서 해제한 뒤 새 체크포인트를 로드한다.
    - 로드 중에는 `/health` 응답이 `"loading"` 상태가 된다.
    - 로드 완료 후 `/run` 추론이 새 체크포인트로 동작한다.

    주의: 로드 시간이 1~5분 소요될 수 있으므로 동기 응답 타임아웃을 충분히 설정해야 한다.
    """
    m = get_manager()
    p = body.params

    if not p.checkpoint_name:
        return DeployResponse(
            status="error", code="INVALID_PARAMS",
            message="checkpoint_name이 비어 있습니다.",
        )

    try:
        m.switch_checkpoint(
            checkpoint_name=p.checkpoint_name,
            vision_model_name=p.vision_model_name,
            llm_model_path=p.llm_model_path,
        )
    except FileNotFoundError as e:
        return DeployResponse(
            status="error", code="NOT_FOUND", message=str(e)
        )
    except Exception:
        return DeployResponse(
            status="error", code="INTERNAL_ERROR", message=traceback.format_exc()
        )

    return DeployResponse(
        status="success",
        checkpoint_path=m.checkpoint_path,
        device=m.device_str,
        vram_used_gb=m.vram_used_gb,
        message=f"체크포인트 '{p.checkpoint_name}' 로드 완료.",
    )


# ── 개발용 직접 실행 ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=False,
    )
