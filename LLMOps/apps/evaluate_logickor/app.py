"""evaluate-logickor — LogicKor 채점 집계 컨테이너 (SP-1 계약).

LogicKor 파이프라인 `clean→train→generate→evaluate→score` 중 **score 단계만** 수행한다.
입력은 ETRI evaluator.py 가 이미 채점해 둔 jsonl(문항별 심판 점수)이고, 출력은 플랫폼
벤치마크 계약 metrics(대표 스칼라 + 영역×턴 격자)다.

왜 집계만 떼어 컨테이너로 두는가
  - 생성·심판 단계는 GPU 와 transformers 5.5.4 / vllm 핀이 필요해 플랫폼 기본 의존성
    (transformers>=4.52.4,<5.0.0)과 충돌한다. 집계는 순수 파이썬이라 그 충돌과 무관하고
    CPU 만으로 돈다 → 계약·화면·이력을 GPU 없이 먼저 확정할 수 있다.
  - 생성·심판이 붙는 시점에도 이 집계 로직(scoring.py)은 그대로 재사용된다.

⚠️ 이 컨테이너는 모델을 돌리지 않는다. 점수는 입력 jsonl 에 이미 들어있는 심판 점수이며,
   그 심판이 누구였는지는 이 단계에서 알 수 없다(생성·심판 단계의 책임).
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
JF_PORT           = int(os.environ.get("JF_PORT", "8000"))

NAME = "evaluate-logickor"
VERSION = "0.1.0"

CAPABILITIES = {
    "supported_models": [],      # 모델을 로드하지 않는다(집계 전용).
    "min_gpu_memory_gb": None,
    "estimated_startup_seconds": 5,
    "estimated_duration_seconds": 15,
    "timeout_seconds": 600,
}

app = FastAPI(title=NAME, version=VERSION)

_jobs: Dict[str, Dict[str, Any]] = {}


def _emit(event: str, **fields: Any) -> None:
    """구조화 로그 1줄 — 플랫폼 로그 수집기가 파싱한다."""
    print(json.dumps({"event": event,
                      "timestamp": datetime.now(timezone.utc).isoformat(),
                      **fields}, ensure_ascii=False), flush=True)


def _load_params(body_params: Optional[dict]) -> dict:
    """요청 body 의 params 우선, 없으면 플랫폼이 떨어뜨린 params.json."""
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
    """params.benchmarks 에서 logickor 의 지표를 뽑는다. 없으면 기본(judge_overall).

    플랫폼은 benchmarks:[{benchmark, metric}] 로 보낸다. metric 은 "어느 축을 대표
    스칼라로 쓸지"만 고르며(전체/1턴/2턴) 전체 결과는 무엇을 골라도 함께 산출된다.
    """
    for item in (params.get("benchmarks") or []):
        if isinstance(item, dict) and item.get("benchmark") == scoring.BENCHMARK_ID:
            metric = str(item.get("metric") or "").strip()
            if metric in scoring.SUPPORTED_METRICS:
                return metric
    metric = str(params.get("metric") or "").strip()
    return metric if metric in scoring.SUPPORTED_METRICS else scoring.DEFAULT_METRIC


def _resolve_input_root(params: dict) -> str:
    """채점 jsonl 을 찾을 루트. 플랫폼이 마운트한 데이터셋 안으로 한정한다.

    JF_DATASET_NAME 이 있으면 그 하위로 스코프를 좁혀(다른 데이터셋 잠식 방지)
    apps/evaluate 와 동일한 규약을 따른다. params.evaluated_subdir 로 데이터셋 안의
    하위 경로만 더 지정할 수 있다(경로 조작은 거부).
    """
    root = JF_DATASET_ROOT
    if JF_DATASET_NAME:
        scoped = os.path.join(JF_DATASET_ROOT, JF_DATASET_NAME)
        if os.path.isdir(scoped):
            root = scoped

    subdir = str(params.get("evaluated_subdir") or "").strip().strip("/")
    if subdir:
        if ".." in subdir or os.path.isabs(subdir):
            raise ValueError("evaluated_subdir must be a relative path without '..'")
        candidate = os.path.join(root, subdir)
        # realpath 로 최종 위치가 루트 밖으로 나가지 않는지 확인(심볼릭 링크 우회 차단).
        if os.path.commonpath([os.path.realpath(candidate), os.path.realpath(root)]) \
                != os.path.realpath(root):
            raise ValueError("evaluated_subdir escapes the dataset root")
        root = candidate
    return root


def _resolve_datasets(params: dict) -> List[str]:
    ds = params.get("datasets")
    if isinstance(ds, list) and ds:
        return [str(d) for d in ds]
    return [JF_DATASET_NAME] if JF_DATASET_NAME else []


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
        "benchmarks": [scoring.BENCHMARK_ID],
        "metrics": list(scoring.SUPPORTED_METRICS),
        "recommended_metric": {scoring.BENCHMARK_ID: scoring.DEFAULT_METRIC},
        "mock": False,
        "stage": "score",  # 생성·심판은 이 컨테이너 밖(별 단계)
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
    _emit("log", level="info", message="logickor scoring job started",
          job_id=job_id, item_id=JF_ITEM_ID, datasets=_resolve_datasets(params))
    return JSONResponse(status_code=202, content={
        "status": "running", "job_id": job_id, "message": "accepted"})


@app.get("/jobs/{job_id}", tags=["표준"])
async def job_status(job_id: str):
    j = _jobs.get(job_id)
    if j is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "E_JOB_NOT_FOUND",
            "message": f"unknown job_id {job_id}"})
    return {
        "job_id": job_id, "status": j["status"], "progress": j["progress"],
        "result": j["result"], "error": j["error"],
    }


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


# ── 집계 잡 ──

async def _run_job(job_id: str, params: dict) -> None:
    j = _jobs[job_id]
    try:
        metric = _resolve_metric(params)
        root = _resolve_input_root(params)
        paths = scoring.resolve_paths(root)
        if not paths:
            raise FileNotFoundError(
                f"no *.jsonl under {root} — 채점 완료된 evaluator 산출물이 필요하다")

        j["progress"] = 0.3
        if j["cancel"]:
            raise asyncio.CancelledError

        # 집계는 CPU 바운드이지만 42문항 × 파일수 규모라 수십 ms 다 — 스레드로 넘기지 않는다.
        agg = scoring.aggregate(scoring.iter_records(paths))
        if agg is None:
            raise ValueError(
                "채점 필드(query_single/query_multi)가 있는 행이 없다 — generator 원본"
                " 산출물을 넘긴 것은 아닌지 확인하라(evaluator 를 거친 파일이 필요)")

        j["progress"] = 0.8
        if j["cancel"]:
            raise asyncio.CancelledError

        metrics = scoring.build_metrics(agg, metric, _resolve_datasets(params))
        metrics["source_files"] = [os.path.relpath(p, root) for p in paths]
        metrics["_meta"] = {"name": NAME, "version": VERSION, "item_id": JF_ITEM_ID}

        # NFS 산출물 영속화 — 플랫폼이 컨테이너 정리 후 metrics.json 으로 eval_result 를
        # 지연 마감하므로, 잡 결과 dict 와 별개로 파일을 반드시 남겨야 한다.
        os.makedirs(JF_OUTPUT_PATH, exist_ok=True)
        out = os.path.join(JF_OUTPUT_PATH, "metrics.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, ensure_ascii=False, indent=2, allow_nan=False)

        j["result"] = {"metrics": metrics, "output_dir": JF_OUTPUT_PATH}
        j["progress"] = 1.0
        j["status"] = "succeeded"
        _emit("log", level="info", message="logickor scoring finished", job_id=job_id,
              files=len(paths), count=agg["count"], metric=metric,
              overall=agg["overall"])
    except asyncio.CancelledError:
        j["status"] = "cancelled"
        _emit("log", level="warn", message="logickor scoring cancelled", job_id=job_id)
    except Exception as exc:  # noqa: BLE001 — 잡 실패를 status 로 노출해야 한다
        j["status"] = "failed"
        j["error"] = {"code": "E_SCORING_FAILED", "message": str(exc)}
        _emit("log", level="error", message="logickor scoring failed",
              job_id=job_id, error=str(exc))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=JF_PORT)
