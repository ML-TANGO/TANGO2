"""evaluate-logickor-judge — LogicKor 심판 채점 + 집계 컨테이너 (SP-1 계약, GPU).

LogicKor 파이프라인 `generate → **evaluate(심판)** → **score(집계)**` 두 단계를 한 런에
수행한다. 입력은 미채점 생성물(evaluator 를 거치지 않은 generator 산출 jsonl)이고,
출력은 심판 점수가 박힌 evaluated jsonl + 플랫폼 벤치마크 계약 metrics.json 이다.

evaluate-logickor(CPU, 집계 전용)와의 관계
  - 그쪽은 "이미 채점된 산출물"을 집계만 한다(GPU 0). GPU 없이 계약·화면·이력을 먼저
    세우기 위한 경로였다.
  - 이쪽은 채점 자체를 수행한다. 집계 로직(scoring.py)은 **같은 파일을 공유**하므로
    두 경로의 점수 정의가 갈라지지 않는다.
  - 플랫폼은 LOGICKOR_MANIFEST_NAME env 로 어느 쪽을 쓸지 고른다(코드 변경 없음).

⚠️ 생성(generate) 단계는 아직 포함하지 않는다 — 대상 모델 가중치를 받아야 하고 GPU 에
   생성모델+심판모델을 순차로 올려야 해서 별 증분으로 둔다.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse

import scoring

# ── 플랫폼 주입 env (SP-1 §3.2) ──
JF_ITEM_ID        = os.environ.get("JF_ITEM_ID", "local")
JF_JOB_TYPE       = os.environ.get("JF_JOB_TYPE", "evaluate")
JF_EXECUTION_MODE = os.environ.get("JF_EXECUTION_MODE", "async")
JF_PARAMS_PATH    = os.environ.get("JF_PARAMS_PATH", "/input/params.json")
JF_DATASET_ROOT   = os.environ.get("JF_DATASET_ROOT", "/dataset")
JF_DATASET_NAME   = os.environ.get("JF_DATASET_NAME", "").strip()
JF_OUTPUT_PATH    = os.environ.get("JF_OUTPUT_PATH", "/output")
JF_TOTAL_GPU      = os.environ.get("JF_TOTAL_GPU", "1")
JF_PORT           = int(os.environ.get("JF_PORT", "8000"))

NAME = "evaluate-logickor-judge"
VERSION = "0.1.0"

# 심판 모델 로드가 수 분, 채점이 파일당 수 분이라 mock/집계기와 시간 규모가 다르다.
CAPABILITIES = {
    "supported_models": [],
    "min_gpu_memory_gb": 24,
    "estimated_startup_seconds": 240,
    "estimated_duration_seconds": 1800,
    "timeout_seconds": 10800,
}

app = FastAPI(title=NAME, version=VERSION)
_jobs: Dict[str, Dict[str, Any]] = {}


def _emit(event: str, **fields: Any) -> None:
    print(json.dumps({"event": event,
                      "timestamp": datetime.now(timezone.utc).isoformat(),
                      **fields}, ensure_ascii=False), flush=True)


def _load_params(body_params: Optional[dict]) -> dict:
    if body_params:
        return body_params
    try:
        with open(JF_PARAMS_PATH, "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        return loaded if isinstance(loaded, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"params.json is not valid JSON: {exc}") from exc


def _resolve_metric(params: dict) -> str:
    for item in (params.get("benchmarks") or []):
        if isinstance(item, dict) and item.get("benchmark") == scoring.BENCHMARK_ID:
            m = str(item.get("metric") or "").strip()
            if m in scoring.SUPPORTED_METRICS:
                return m
    m = str(params.get("metric") or "").strip()
    return m if m in scoring.SUPPORTED_METRICS else scoring.DEFAULT_METRIC


def _resolve_input_root(params: dict) -> str:
    """생성물이 담긴 루트. 마운트된 데이터셋 안으로 한정(evaluate-logickor 동일 규약)."""
    root = JF_DATASET_ROOT
    if JF_DATASET_NAME:
        scoped = os.path.join(JF_DATASET_ROOT, JF_DATASET_NAME)
        if os.path.isdir(scoped):
            root = scoped
    subdir = str(params.get("generated_subdir") or "").strip().strip("/")
    if subdir:
        if ".." in subdir or os.path.isabs(subdir):
            raise ValueError("generated_subdir must be a relative path without '..'")
        candidate = os.path.join(root, subdir)
        if os.path.commonpath([os.path.realpath(candidate), os.path.realpath(root)]) \
                != os.path.realpath(root):
            raise ValueError("generated_subdir escapes the dataset root")
        root = candidate
    return root


def _gpu_devices() -> str:
    """컨테이너에 보이는 GPU 인덱스. 플랫폼이 device 를 격리해 넣어주므로 0..n-1 이다."""
    try:
        n = max(1, int(float(JF_TOTAL_GPU)))
    except (TypeError, ValueError):
        n = 1
    return ",".join(str(i) for i in range(n))


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
        "name": NAME, "version": VERSION,
        "execution_mode": JF_EXECUTION_MODE, "job_type": JF_JOB_TYPE,
        "spec_api_version": "tango.acryl.ai/v1",
        "benchmarks": [scoring.BENCHMARK_ID],
        "metrics": list(scoring.SUPPORTED_METRICS),
        "recommended_metric": {scoring.BENCHMARK_ID: scoring.DEFAULT_METRIC},
        "mock": False,
        "stage": "judge+score",
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
    _emit("log", level="info", message="logickor judge job started", job_id=job_id,
          item_id=JF_ITEM_ID, gpu=_gpu_devices())
    return JSONResponse(status_code=202, content={
        "status": "running", "job_id": job_id, "message": "accepted"})


@app.get("/jobs/{job_id}", tags=["표준"])
async def job_status(job_id: str):
    j = _jobs.get(job_id)
    if j is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "E_JOB_NOT_FOUND",
            "message": f"unknown job_id {job_id}"})
    return {"job_id": job_id, "status": j["status"], "progress": j["progress"],
            "result": j["result"], "error": j["error"]}


@app.post("/jobs/{job_id}/cancel", tags=["표준"])
async def job_cancel(job_id: str):
    j = _jobs.get(job_id)
    if j is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "E_JOB_NOT_FOUND",
            "message": f"unknown job_id {job_id}"})
    if j["status"] != "running":
        return {"job_id": job_id, "status": j["status"]}
    j["cancel"] = True
    return {"job_id": job_id, "status": "cancelling"}


# ── 채점 + 집계 잡 ──

async def _run_job(job_id: str, params: dict) -> None:
    j = _jobs[job_id]
    try:
        import judge  # vLLM 임포트가 무거워 잡 시작 시점에 로드한다.

        metric = _resolve_metric(params)
        in_root = _resolve_input_root(params)
        evaluated_dir = os.path.join(JF_OUTPUT_PATH, "evaluated")

        judge_model = str(params.get("judge_model") or judge.DEFAULT_JUDGE_MODEL).strip()
        model_len = int(params.get("judge_model_len") or 8192)
        max_out = int(params.get("judge_max_output_tokens") or 1024)
        # HF 토큰은 params 로 받되 로그·산출물에 절대 싣지 않는다.
        hf_token = params.get("hf_token") or os.environ.get("HF_TOKEN") or None

        def progress(p: float, msg: str) -> None:
            if j["cancel"]:
                raise asyncio.CancelledError
            j["progress"] = round(p, 3)
            _emit("log", level="info", message=msg, job_id=job_id, progress=j["progress"])

        # vLLM 은 동기·블로킹이라 이벤트 루프를 막지 않도록 스레드로 넘긴다
        # (안 넘기면 /jobs 폴링과 /health 가 채점 내내 응답하지 않아 플랫폼이 죽은 줄 안다).
        stats = await asyncio.to_thread(
            judge.run_judge, in_root, evaluated_dir, judge_model,
            _gpu_devices(), model_len, max_out, hf_token, progress)

        if j["cancel"]:
            raise asyncio.CancelledError

        agg = scoring.aggregate(scoring.iter_records(
            [os.path.join(dp, f) for dp, _, fs in os.walk(evaluated_dir)
             for f in fs if f.endswith(".jsonl")]))
        if agg is None:
            raise ValueError("채점 후에도 집계할 행이 없다 — 심판 출력 파싱을 확인하라")

        metrics = scoring.build_metrics(agg, metric, params.get("datasets") or [])
        metrics["source_files"] = stats["outputs"]
        metrics["judge"] = {
            "model": stats["judge_model"], "files": stats["files"],
            "judged": stats["judged"],
            # 점수 파싱 실패(0점 처리) 개수 — 조용히 평균을 끌어내리므로 반드시 노출한다.
            "unscored": stats["unscored"],
            # 형식 불량으로 아예 제외된 행 수 — 조용한 누락을 결과에 남긴다.
            "skipped": stats["skipped"],
        }
        metrics["_meta"] = {"name": NAME, "version": VERSION, "item_id": JF_ITEM_ID}

        os.makedirs(JF_OUTPUT_PATH, exist_ok=True)
        with open(os.path.join(JF_OUTPUT_PATH, "metrics.json"), "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, ensure_ascii=False, indent=2, allow_nan=False)

        j["result"] = {"metrics": metrics, "output_dir": JF_OUTPUT_PATH}
        j["progress"] = 1.0
        j["status"] = "succeeded"
        _emit("log", level="info", message="logickor judge+score finished", job_id=job_id,
              overall=agg["overall"], count=agg["count"], unscored=stats["unscored"])
    except asyncio.CancelledError:
        j["status"] = "cancelled"
        _emit("log", level="warn", message="logickor judge cancelled", job_id=job_id)
    except Exception as exc:  # noqa: BLE001
        j["status"] = "failed"
        j["error"] = {"code": "E_JUDGE_FAILED", "message": str(exc)}
        _emit("log", level="error", message="logickor judge failed",
              job_id=job_id, error=str(exc))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=JF_PORT)
