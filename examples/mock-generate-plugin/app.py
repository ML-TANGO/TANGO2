"""
mock-generate-plugin — 생성형 데이터 파이프라인(WBS 1.1 / v0.4 3.3) BE 스캐폴드용
mock 외부 컨테이너. 고려대 LLM1/LLM2(프롬프트·데이터 생성) 모듈 **수령 전**에
파이프라인 end-to-end(생성 노드 → 전처리 → 학습)를 검증하기 위한 고정 출력 컨테이너.

SP-1 외부 컨테이너 규약을 그대로 따른다(hello-plugin fork):
  - 표준 endpoint: /health /live /info /run /jobs/{id} /jobs/{id}/cancel
  - async lifecycle: /run 202 + job_id → 플랫폼이 /jobs/{id} polling
  - 출력: /output/result.jsonl = VLM instruction 데이터(image+instruction+output)
    (고려대 그림12-14 스키마). 고려대 컨테이너 도착 시 이 파일을 교체(동일 계약).

자세한 계약: ../hello-plugin/external-container-spec.md
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse

# ── 플랫폼 주입 env (spec §3.2) ──
JF_ITEM_ID        = os.environ.get("JF_ITEM_ID", "local")
JF_JOB_TYPE       = os.environ.get("JF_JOB_TYPE", "generate")
JF_EXECUTION_MODE = os.environ.get("JF_EXECUTION_MODE", "async")
JF_PARAMS_PATH    = os.environ.get("JF_PARAMS_PATH", "/input/params.json")
JF_OUTPUT_PATH    = os.environ.get("JF_OUTPUT_PATH", "/output")
JF_PORT           = int(os.environ.get("JF_PORT", "8000"))

NAME    = "mock-generate"
VERSION = "1.0.0"

CAPABILITIES = {
    "supported_models": [],
    "min_gpu_memory_gb": None,
    "estimated_startup_seconds": 10,
    "estimated_duration_seconds": 30,
    "timeout_seconds": 600,
}

app = FastAPI(title=NAME, version=VERSION)

_jobs: Dict[str, Dict[str, Any]] = {}


def _emit(event: str, **fields: Any) -> None:
    line = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), **fields}
    print(json.dumps(line, ensure_ascii=False), flush=True)


def _redact(params: dict) -> list[str]:
    return sorted(params.keys()) if isinstance(params, dict) else []


def _load_params(body_params: Optional[dict]) -> dict:
    if body_params:
        return body_params
    try:
        with open(JF_PARAMS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"malformed or unreadable {JF_PARAMS_PATH}: {exc}") from exc


# ── 표준 endpoint (SP-1 규약 — hello-plugin 과 동일) ──

@app.get("/health", tags=["표준"])
async def health():
    return JSONResponse(status_code=200, content={"status": "ready"})


@app.get("/live", tags=["표준"])
async def live():
    return JSONResponse(status_code=200, content={"status": "alive"})


@app.get("/info", tags=["표준"])
async def info():
    return {
        "name": NAME,
        "version": VERSION,
        "execution_mode": JF_EXECUTION_MODE,
        "job_type": JF_JOB_TYPE,
        "spec_api_version": "tango.acryl.ai/v1",
        **CAPABILITIES,
    }


@app.post("/run", tags=["표준"])
async def run(body: Optional[dict] = Body(default=None)):
    body = body or {}
    raw = body["params"] if isinstance(body.get("params"), dict) else body
    try:
        params = _load_params(raw)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={
            "status": "error", "code": "E_PARAMS_INVALID", "message": str(exc)})

    if any(j["status"] == "running" for j in _jobs.values()):
        return JSONResponse(status_code=429, content={
            "status": "error", "code": "E_BUSY", "message": "a job is already running"})

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"status": "running", "progress": 0.0, "result": None,
                     "error": None, "cancel": False, "task": None}
    _jobs[job_id]["task"] = asyncio.create_task(_run_job(job_id, params))
    _emit("log", level="info", message="generation job started", job_id=job_id,
          item_id=JF_ITEM_ID, param_keys=_redact(params))
    return JSONResponse(status_code=202, content={
        "status": "running", "job_id": job_id, "message": "accepted"})


@app.get("/jobs/{job_id}", tags=["표준"])
async def job_status(job_id: str):
    j = _jobs.get(job_id)
    if j is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "E_JOB_NOT_FOUND", "message": f"unknown job_id {job_id}"})
    return {
        "job_id": job_id,
        "status": j["status"],
        "progress": j["progress"],
        "result": j["result"],
        "error": j["error"],
    }


@app.post("/jobs/{job_id}/cancel", tags=["표준"])
async def job_cancel(job_id: str):
    j = _jobs.get(job_id)
    if j is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "E_JOB_NOT_FOUND", "message": f"unknown job_id {job_id}"})
    if j["status"] != "running":
        return {"job_id": job_id, "status": j["status"]}
    j["cancel"] = True
    return {"job_id": job_id, "status": "cancelling"}


# ── mock 생성 작업 — 고려대 LLM1/LLM2 컨테이너 도착 시 이 함수만 교체 ──

async def _run_job(job_id: str, params: dict) -> None:
    """VLM instruction 데이터(image+instruction+output) jsonl 을 고정 생성.
    실제 컨테이너는 메타프롬프트→프롬프트/인스트럭션(LLM1) + 데이터 생성(LLM2)."""
    j = _jobs[job_id]
    try:
        count = int(params.get("count", 10))
        count = max(0, min(count, 10000))  # mock 상한 — 출력 볼륨 소진 방지
        instruction = str(params.get("instruction", "이 이미지를 설명하시오."))
        image_prefix = str(params.get("image_prefix", "images/sample"))
        os.makedirs(JF_OUTPUT_PATH, exist_ok=True)

        out_path = os.path.join(JF_OUTPUT_PATH, "result.jsonl")
        with open(out_path, "w", encoding="utf-8") as f:
            for i in range(1, count + 1):
                if j["cancel"]:
                    j["status"] = "cancelled"
                    _emit("log", level="info", message="generation cancelled", job_id=job_id, step=i)
                    return
                # VLM instruction 레코드 (고려대 그림12-14 스키마)
                record = {
                    "image": f"{image_prefix}_{i}.jpg",
                    "instruction": instruction,
                    "output": f"[mock] 생성된 설명 {i} (item={JF_ITEM_ID})",
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                j["progress"] = round(i / count, 4)
                _emit("progress", job_id=job_id, step=i, total=count,
                      percent=round(j["progress"] * 100, 2))
                await asyncio.sleep(0.2)  # ← 실제 생성 연산으로 교체

        result = {"records": count, "output_file": "result.jsonl", "item_id": JF_ITEM_ID}
        with open(os.path.join(JF_OUTPUT_PATH, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump({"records": count, "status": "ok"}, f)

        j["result"] = result
        j["progress"] = 1.0
        j["status"] = "completed"
        _emit("log", level="info", message="generation completed", job_id=job_id, records=count)

    except Exception as exc:
        j["status"] = "failed"
        j["error"] = {"code": "E_GENERATE_FAILED", "message": str(exc), "fatal": True}
        _emit("error", job_id=job_id, code="E_GENERATE_FAILED", message=str(exc), fatal=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=JF_PORT)
