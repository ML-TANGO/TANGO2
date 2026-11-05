"""
mock-convert-plugin — 양자화·포팅(SP-4 / v0.4 3.9) convert 컨테이너 mock.

플랫폼 소유 llama.cpp convert 컨테이너의 **mock**. 실제 llama.cpp(convert_hf_to_gguf
+ quantize) 이미지 도착 전, 플랫폼 측 convert job 와이어링(학습 후 양자화→포팅 패키지
다운로드)을 end-to-end 검증하기 위한 고정 출력 컨테이너.

SP-1 외부 컨테이너 규약을 그대로 따른다(hello-plugin/mock-generate fork):
  - 표준 endpoint: /health /live /info /run /jobs/{id} /jobs/{id}/cancel
  - job_type: convert, execution_mode: batch (학습 후 1회성 변환)
  - 입력: merged 모델(/model) + params(/input/params.json: target_quant 등)
  - 출력: /output 에 포팅 패키지 — model.gguf + inference.py + run.sh +
    config.json + metadata.json (⑬ 코드수정 UI 없음, 패키지 다운로드만)

실제 컨테이너 도착 시 _run_job 의 변환 로직만 교체(나머지 계약 동일).
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
JF_JOB_TYPE       = os.environ.get("JF_JOB_TYPE", "convert")
JF_EXECUTION_MODE = os.environ.get("JF_EXECUTION_MODE", "async")
JF_PARAMS_PATH    = os.environ.get("JF_PARAMS_PATH", "/input/params.json")
JF_MODEL_PATH     = os.environ.get("JF_MODEL_PATH", "/model")
JF_OUTPUT_PATH    = os.environ.get("JF_OUTPUT_PATH", "/output")
JF_PORT           = int(os.environ.get("JF_PORT", "8000"))

NAME    = "mock-convert"
VERSION = "1.0.0"

# 타겟 양자화 → 근사 압축비(mock 산출 크기 계산용)
_QUANT_RATIO = {"q4": 0.28, "q5": 0.34, "q6": 0.40, "q8": 0.53, "f16": 1.0}

CAPABILITIES = {
    "supported_models": [],
    "min_gpu_memory_gb": None,
    "estimated_startup_seconds": 10,
    "estimated_duration_seconds": 40,
    "timeout_seconds": 1800,
}

app = FastAPI(title=NAME, version=VERSION)

_jobs: Dict[str, Dict[str, Any]] = {}


def _emit(event: str, **fields: Any) -> None:
    line = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), **fields}
    print(json.dumps(line, ensure_ascii=False), flush=True)


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


# ── 표준 endpoint (SP-1 규약) ──

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
    _emit("log", level="info", message="convert job started", job_id=job_id,
          item_id=JF_ITEM_ID, target_quant=params.get("target_quant", "q5"))
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


# ── mock 변환 — 실제 llama.cpp(convert_hf_to_gguf + quantize) 도착 시 이 함수만 교체 ──

_INFERENCE_PY = '''\
# 포팅 패키지 — llama.cpp GGUF 추론 예시 (자동 생성, 코드 수정 UI 없음 / ⑬)
import sys
from llama_cpp import Llama
llm = Llama(model_path="model.gguf", n_ctx=2048)
print(llm(sys.argv[1] if len(sys.argv) > 1 else "Hello", max_tokens=128)["choices"][0]["text"])
'''

_RUN_SH = '''\
#!/usr/bin/env bash
# 타겟 디바이스에서 실행: pip install llama-cpp-python && python inference.py "프롬프트"
set -e
pip install --quiet llama-cpp-python
python inference.py "$@"
'''


async def _run_job(job_id: str, params: dict) -> None:
    """merged 모델 → GGUF + 포팅 패키지(고정 산출). 실제 컨테이너는 llama.cpp 변환."""
    j = _jobs[job_id]
    try:
        target_quant = str(params.get("target_quant", "q5")).lower()
        model_name = str(params.get("model_name", "model"))
        ratio = _QUANT_RATIO.get(target_quant, 0.34)
        os.makedirs(JF_OUTPUT_PATH, exist_ok=True)

        # 입력 merged 모델 크기 추정(없으면 기본값) — mock GGUF 크기 산출용.
        src_bytes = 0
        try:
            for root, _, files in os.walk(JF_MODEL_PATH):
                for fn in files:
                    src_bytes += os.path.getsize(os.path.join(root, fn))
        except Exception:
            pass
        if src_bytes <= 0:
            src_bytes = 1_500_000_000  # 기본 1.5GB 가정(mock)
        gguf_bytes = int(src_bytes * ratio)

        steps = ["load merged model", f"convert to GGUF ({target_quant})", "write package"]
        for i, step in enumerate(steps, 1):
            if j["cancel"]:
                j["status"] = "cancelled"
                _emit("log", level="info", message="convert cancelled", job_id=job_id, step=step)
                return
            _emit("progress", job_id=job_id, step=i, total=len(steps),
                  percent=round(i / len(steps) * 100, 1), message=step)
            j["progress"] = round(i / len(steps), 4)
            await asyncio.sleep(1.0)  # ← 실제 변환 연산으로 교체

        # 포팅 패키지 산출 (⑬ 다운로드만 — 코드 수정 UI 없음)
        gguf_name = f"{model_name}.{target_quant}.gguf"
        gguf_path = os.path.join(JF_OUTPUT_PATH, gguf_name)
        with open(gguf_path, "wb") as f:
            f.write(b"GGUF\x00mock")  # mock 헤더(실제 변환 시 진짜 GGUF)
            f.truncate(max(len(b"GGUF\x00mock"), gguf_bytes // 1000))  # mock: 1/1000 축소 기록
        with open(os.path.join(JF_OUTPUT_PATH, "inference.py"), "w", encoding="utf-8") as f:
            f.write(_INFERENCE_PY)
        with open(os.path.join(JF_OUTPUT_PATH, "run.sh"), "w", encoding="utf-8") as f:
            f.write(_RUN_SH)
        config = {"model_file": gguf_name, "quantization": target_quant, "n_ctx": 2048,
                  "source_model": model_name}
        with open(os.path.join(JF_OUTPUT_PATH, "config.json"), "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        metadata = {
            "name": NAME, "version": VERSION, "job_id": job_id, "item_id": JF_ITEM_ID,
            "target_quant": target_quant, "source_bytes": src_bytes, "gguf_bytes": gguf_bytes,
            "files": [gguf_name, "inference.py", "run.sh", "config.json", "metadata.json"],
        }
        with open(os.path.join(JF_OUTPUT_PATH, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        j["result"] = {
            "gguf_file": gguf_name,
            "gguf_bytes": gguf_bytes,
            "target_quant": target_quant,
            "package_files": metadata["files"],
            "output_dir": JF_OUTPUT_PATH,
        }
        j["progress"] = 1.0
        j["status"] = "completed"
        _emit("log", level="info", message="convert completed", job_id=job_id,
              gguf_file=gguf_name, gguf_bytes=gguf_bytes)

    except Exception as exc:
        j["status"] = "failed"
        j["error"] = {"code": "E_CONVERT_FAILED", "message": str(exc), "fatal": True}
        _emit("error", job_id=job_id, code="E_CONVERT_FAILED", message=str(exc), fatal=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=JF_PORT)
