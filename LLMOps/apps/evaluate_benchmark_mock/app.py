"""evaluate-benchmark-mock — 벤치마크 평가 mock 컨테이너 (llm_evaluation P1a).

목적: 정식 벤치마크 평가 컨테이너(고려대 plugin / 실측)가 탑재되기 전, **오케스트레이션
+ FE e2e 를 테스트**하기 위한 mock. 모델을 실제로 돌리지 않고 "벤치마크 → 메트릭" 매핑
(예: ARC→Accuracy, KoBEST→F1)에 대해 **결정적(hash 기반) 그럴듯한 점수**를 반환한다.

설계:
  - SP-1 외부 컨테이너 계약을 그대로 따른다(apps/evaluate 와 동형) → fb_external_container
    런치/정리/eval_result 영속화 와이어링 변경 없이 동작. 정식 컨테이너는 manifest 교체로 대체.
  - 모델 로드/데이터셋 파싱 안 함(mock) → torch/transformers 의존 0, slim 베이스, path-traversal
    표면 없음(데이터셋은 이름만 인지, 내용 미열람).
  - 점수는 sha256(benchmark::metric) 기반 결정적 → 같은 입력 → 같은 점수(데모/테스트 안정).
  - 벤치마크(9)·메트릭(8)·권장 매핑은 llm_evaluation BE constants + FE benchmarks.js 와 id 일치.

⚠️ MOCK: 실제 평가 아님. 정식 메트릭은 apps/evaluate(실측 기본) / 고려대 plugin(정밀)로 라우팅.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse

# ── 플랫폼 주입 env (SP-1 §3.2) ──
JF_ITEM_ID        = os.environ.get("JF_ITEM_ID", "local")
JF_JOB_TYPE       = os.environ.get("JF_JOB_TYPE", "evaluate")
JF_EXECUTION_MODE = os.environ.get("JF_EXECUTION_MODE", "async")
JF_PARAMS_PATH    = os.environ.get("JF_PARAMS_PATH", "/input/params.json")
JF_DATASET_NAME   = os.environ.get("JF_DATASET_NAME", "").strip()
JF_OUTPUT_PATH    = os.environ.get("JF_OUTPUT_PATH", "/output")
JF_PORT           = int(os.environ.get("JF_PORT", "8000"))

NAME    = "evaluate-benchmark-mock"
VERSION = "0.2.0"

# 벤치마크 정본(9) — id = llm_evaluation constants.BENCHMARK_IDS + FE benchmarks.js 일치.
_BENCHMARK_IDS = [
    "arc", "kobest", "mmlu", "hellaswag", "winogrande",
    "gsm8k", "truthfulqa", "boolq", "humaneval",
]

# 메트릭 정본(8) — 벤치마크와 분리된 채점 방식. id = constants.METRIC_IDS + FE benchmarkMetrics.js.
_METRIC_IDS = [
    "accuracy", "f1", "acc_norm", "bleu", "rouge", "meteor", "cider", "spice",
]

# 벤치마크별 권장 메트릭(생략 시 채택) — constants.BENCHMARK_RECOMMENDED_METRIC 와 일치.
_RECOMMENDED_METRIC = {
    "arc": "accuracy", "kobest": "f1", "mmlu": "accuracy", "hellaswag": "acc_norm",
    "winogrande": "accuracy", "gsm8k": "accuracy", "truthfulqa": "accuracy",
    "boolq": "accuracy", "humaneval": "accuracy",
}

CAPABILITIES = {
    "supported_models": [],
    "min_gpu_memory_gb": None,
    "estimated_startup_seconds": 5,
    "estimated_duration_seconds": 10,
    "timeout_seconds": 300,
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


def _mock_score(benchmark: str, metric: str) -> float:
    """sha256(benchmark::metric) → [52.0, 95.0] 결정적 점수(0~100 스케일, 그럴듯)."""
    h = hashlib.sha256(f"{benchmark}::{metric}".encode("utf-8")).hexdigest()
    frac = int(h[:8], 16) / 0xFFFFFFFF
    return round(52.0 + frac * 43.0, 2)


def _resolve_benchmarks(params: dict) -> List[Dict[str, str]]:
    """params.benchmarks(list of {benchmark, metric}) 정규화 — 생략/빈값이면 전체 벤치마크를
    권장 메트릭으로. unknown id·벤치마크 중복 제거(런당 벤치마크 1행)."""
    raw = params.get("benchmarks")
    pairs: List[Dict[str, str]] = []
    seen = set()
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            b = str(item.get("benchmark", "")).strip()
            m = str(item.get("metric", "")).strip()
            if b not in _BENCHMARK_IDS or m not in _METRIC_IDS or b in seen:
                continue
            seen.add(b)
            pairs.append({"benchmark": b, "metric": m})
    if not pairs:
        pairs = [{"benchmark": b, "metric": _RECOMMENDED_METRIC[b]} for b in _BENCHMARK_IDS]
    return pairs


def _resolve_datasets(params: dict) -> List[str]:
    ds = params.get("datasets")
    if isinstance(ds, str):
        ds = [d.strip() for d in ds.split(",") if d.strip()]
    if not ds:
        ds = [JF_DATASET_NAME] if JF_DATASET_NAME else ["default"]
    return [str(d) for d in ds]


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
        "benchmarks": list(_BENCHMARK_IDS),
        "metrics": list(_METRIC_IDS),
        "recommended_metric": dict(_RECOMMENDED_METRIC),
        "mock": True,
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
    _emit("log", level="info", message="benchmark(mock) job started", job_id=job_id,
          item_id=JF_ITEM_ID, benchmarks=_resolve_benchmarks(params),
          datasets=_resolve_datasets(params))
    return JSONResponse(status_code=202, content={
        "status": "running", "job_id": job_id, "message": "accepted"})


@app.get("/jobs/{job_id}", tags=["표준"])
async def job_status(job_id: str):
    j = _jobs.get(job_id)
    if j is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "E_JOB_NOT_FOUND", "message": f"unknown job_id {job_id}"})
    return {
        "job_id": job_id, "status": j["status"], "progress": j["progress"],
        "result": j["result"], "error": j["error"],
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


# ── mock 평가 잡 ──

class _Cancelled(Exception):
    pass


def _build_metrics(params: dict) -> dict:
    """벤치마크→메트릭 매핑을 결정적 점수로 채점. averages 는 벤치마크→점수(이력 비교
    flatten 소스), results 는 FE 결과 뷰가 직접 렌더할 [{benchmark, metric, score}] 목록."""
    pairs = _resolve_benchmarks(params)
    datasets = _resolve_datasets(params)
    results = [
        {"benchmark": p["benchmark"], "metric": p["metric"],
         "score": _mock_score(p["benchmark"], p["metric"])}
        for p in pairs
    ]
    return {
        "mode": "benchmark",
        "mock": True,
        "results": results,                                     # [{benchmark, metric, score}]
        "averages": {r["benchmark"]: r["score"] for r in results},  # {benchmark: score}
        "benchmark_set": [p["benchmark"] for p in pairs],
        "metric_map": {p["benchmark"]: p["metric"] for p in pairs},  # {benchmark: metric}
        "datasets": datasets,                                   # 마운트된 데이터셋명(맥락)
        "_meta": {"name": NAME, "version": VERSION, "item_id": JF_ITEM_ID},
    }


async def _run_job(job_id: str, params: dict) -> None:
    j = _jobs[job_id]
    try:
        os.makedirs(JF_OUTPUT_PATH, exist_ok=True)
        pairs = _resolve_benchmarks(params)

        # 진행률 시뮬 — 벤치마크당 짧게(async/poll 플로우 테스트용, 총 ~2s).
        for i, p in enumerate(pairs):
            if j["cancel"]:
                raise _Cancelled()
            await asyncio.sleep(min(2.0 / max(len(pairs), 1), 1.0))
            if j["cancel"]:  # sleep 직후 재확인 — 마지막 sleep 중 취소 race 방지.
                raise _Cancelled()
            j["progress"] = round((i + 1) / len(pairs), 4)
            _emit("progress", job_id=job_id, percent=round(j["progress"] * 100, 1),
                  message=f"scoring {p['benchmark']} ({p['metric']})")

        if j["cancel"]:  # build/write 직전 최종 확인 — 취소 후 metrics.json 생성 방지.
            raise _Cancelled()
        metrics = _build_metrics(params)

        # NFS 산출물 영속화 — 플랫폼이 cleanup 후 metrics.json 으로 eval_result lazy 마감.
        with open(os.path.join(JF_OUTPUT_PATH, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2, allow_nan=False)

        j["result"] = {"metrics": metrics, "output_dir": JF_OUTPUT_PATH}
        j["progress"] = 1.0
        j["status"] = "completed"
        _emit("log", level="info", message="benchmark(mock) completed", job_id=job_id)

    except _Cancelled:
        j["status"] = "cancelled"
        _emit("log", level="info", message="benchmark(mock) cancelled", job_id=job_id)
        _clean_output()
    except Exception as exc:  # noqa: BLE001 — 잡 실패는 status=failed 로 보고(컨테이너 계약).
        j["status"] = "failed"
        j["error"] = {"code": "E_EVAL_FAILED", "message": str(exc), "fatal": True}
        _emit("error", job_id=job_id, code="E_EVAL_FAILED", message=str(exc), fatal=True)
        _clean_output()


def _clean_output() -> None:
    """실패/취소 시 부분 산출물 정리 — 플랫폼이 ready 로 오인하지 않게. 심링크 건너뜀."""
    try:
        out_real = os.path.realpath(JF_OUTPUT_PATH)
        for fn in os.listdir(JF_OUTPUT_PATH):
            fp = os.path.join(JF_OUTPUT_PATH, fn)
            if os.path.islink(fp):
                continue
            if os.path.isfile(fp) and os.path.realpath(fp).startswith(out_real + os.sep):
                os.remove(fp)
    except OSError:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=JF_PORT)
