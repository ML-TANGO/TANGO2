"""
hello-plugin — Tango 외부 컨테이너 인터페이스(SP-1 v1) 최소 템플릿.

이 파일 하나로 규약의 핵심을 모두 보여준다:
  - 표준 HTTP endpoint: /health(readiness) /live(liveness) /info /run
    /jobs/{id}(async status) /jobs/{id}/cancel
  - async 작업 lifecycle: /run 이 202 + job_id 반환 → 플랫폼이 /jobs/{id} polling
  - 입력 규약: /run body = params dict (플랫폼이 raw dict 로 POST) — 없으면
    /input/params.json fallback (batch/local)
  - 출력 규약: /output 파일 + stdout JSON Lines(실시간 progress/error, spec §4.2)
  - 플랫폼 주입 env: JF_* (spec §3.2)

협력기관은 이 파일을 fork 한 뒤 `_run_job()` 내부의 데모 로직만 자기 작업으로
교체하면 된다. endpoint/규약 구조는 그대로 둔다.

자세한 계약: external-container-spec.md
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

# ── 플랫폼 주입 env (spec §3.2) — 정적 metadata 만, 동적 파라미터는 params 로 ──
JF_ITEM_ID        = os.environ.get("JF_ITEM_ID", "local")
JF_JOB_TYPE       = os.environ.get("JF_JOB_TYPE", "preprocess")
JF_EXECUTION_MODE = os.environ.get("JF_EXECUTION_MODE", "async")
JF_PARAMS_PATH    = os.environ.get("JF_PARAMS_PATH", "/input/params.json")
JF_OUTPUT_PATH    = os.environ.get("JF_OUTPUT_PATH", "/output")
JF_PORT           = int(os.environ.get("JF_PORT", "8000"))

NAME    = "hello-plugin"
VERSION = "1.0.0"

# /info 가 반영할 capabilities (spec §5.1). manifest.yaml 의 capabilities 와 일치시킬 것.
CAPABILITIES = {
    "supported_models": [],
    "min_gpu_memory_gb": None,
    "estimated_startup_seconds": 10,
    "estimated_duration_seconds": 30,
    "timeout_seconds": 300,
}

app = FastAPI(title=NAME, version=VERSION)

# in-memory job store. 이 템플릿은 동시 1개 작업만 받는다(아래 /run 의 busy guard).
# task 객체는 GC 방지를 위해 보관 — 단, JSON 응답엔 절대 넣지 않는다(키 projection).
_jobs: Dict[str, Dict[str, Any]] = {}


def _emit(event: str, **fields: Any) -> None:
    """stdout JSON Lines (spec §4.2). 플랫폼이 한 줄씩 파싱해 실시간 표시.
    spec §4.2 의 event type 만 사용: progress / metric / log / error.
    PYTHONUNBUFFERED=1 + flush 로 버퍼링 없이 흘려보낸다."""
    line = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), **fields}
    print(json.dumps(line, ensure_ascii=False), flush=True)


def _redact(params: dict) -> list[str]:
    """stdout 로그에 파라미터 '값'을 남기지 않는다(프롬프트/경로/실수로 넣은 비밀 유출 방지).
    값 대신 key 목록만 로깅."""
    return sorted(params.keys()) if isinstance(params, dict) else []


def _load_params(body_params: Optional[dict]) -> dict:
    """params 우선순위: /run body(raw dict) > /input/params.json (spec §3.3).
    환경변수는 동적 파라미터 transport 로 쓰지 않는다(고정 metadata 전용).

    malformed JSON 은 조용히 {} 로 삼키지 않고 fail-fast 한다(spec §4.3 사용자 에러).
    파일 미주입(FileNotFoundError)은 HTTP 컨테이너의 정상 경로라 {} 반환."""
    if body_params:
        return body_params
    try:
        with open(JF_PARAMS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}                       # /run body 로 받는 HTTP 컨테이너는 파일이 없을 수 있음
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"malformed or unreadable {JF_PARAMS_PATH}: {exc}") from exc


# ── 표준 endpoint ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["표준"])
async def health():
    """readiness — 트래픽 받을 준비됐는지. (spec §5.2)
    모델 로딩이 필요한 컨테이너면 로딩 중 503 {"status":"loading"} 반환할 것.
    이 데모는 로딩이 없어 즉시 ready."""
    return JSONResponse(status_code=200, content={"status": "ready"})


@app.get("/live", tags=["표준"])
async def live():
    """liveness — 모델 로드와 무관하게 process alive 만. (spec §5.2)
    cold-start(모델 로딩) 동안 /health 는 503 이어도 /live 는 200 이라야
    K8s livenessProbe 가 로딩 중 pod 를 죽이지 않는다."""
    return JSONResponse(status_code=200, content={"status": "alive"})


@app.get("/info", tags=["표준"])
async def info():
    """manifest metadata + capabilities 와 일관되게 반환. (spec §5.1)
    플랫폼이 launch 후 introspection 검증한다 — manifest 와 불일치 시 실패 처리."""
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
    """async 작업 시작 → 202 Accepted + job_id. (spec §5.3 async)

    body 규약: 플랫폼 generic adapter 는 **params dict 를 그대로 POST** 한다
    (envelope `{"params":{}}` 아님 — fb_external_container GenericHTTPAdapter).
    forward-compat 으로 envelope 도 허용: body 에 dict 인 "params" 키가 있으면 그걸 사용.
    sync 컨테이너라면 여기서 200 + 결과를 바로 반환한다(execution_mode=sync)."""
    body = body or {}
    raw = body["params"] if isinstance(body.get("params"), dict) else body
    try:
        params = _load_params(raw)
    except ValueError as exc:                          # malformed params → fail-fast 400
        return JSONResponse(status_code=400, content={
            "status": "error", "code": "E_PARAMS_INVALID", "message": str(exc)})

    # busy guard — 이 템플릿은 한 번에 한 작업만 (플랫폼은 보통 pod 당 1 작업).
    if any(j["status"] == "running" for j in _jobs.values()):
        return JSONResponse(status_code=429, content={
            "status": "error", "code": "E_BUSY", "message": "a job is already running"})

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"status": "running", "progress": 0.0, "result": None,
                     "error": None, "cancel": False, "task": None}
    # task 참조 보관 — 안 하면 GC 가 실행 중 태스크를 거둬갈 수 있음.
    _jobs[job_id]["task"] = asyncio.create_task(_run_job(job_id, params))
    _emit("log", level="info", message="job started", job_id=job_id,
          item_id=JF_ITEM_ID, param_keys=_redact(params))   # 값은 안 남김(redacted)
    return JSONResponse(status_code=202, content={
        "status": "running", "job_id": job_id, "message": "accepted"})


@app.get("/jobs/{job_id}", tags=["표준"])
async def job_status(job_id: str):
    """async 작업 상태. (spec §5.4) 없으면 404 + 표준 에러 envelope."""
    j = _jobs.get(job_id)
    if j is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "E_JOB_NOT_FOUND", "message": f"unknown job_id {job_id}"})
    return {
        "job_id": job_id,
        "status": j["status"],          # running | completed | failed | cancelled
        "progress": j["progress"],      # 0.0 ~ 1.0
        "result": j["result"],
        "error": j["error"],            # null 또는 {"code","message","fatal"} 객체 (spec §5.4/§8)
    }


@app.post("/jobs/{job_id}/cancel", tags=["표준"])
async def job_cancel(job_id: str):
    """async 작업 취소 요청. (spec §5.5)
    주의: 이 데모는 협조적(cooperative) 취소 — 다음 step 경계에서 멈춘다.
    blocking 작업(예: 단일 호출로 오래 걸리는 ML 연산)을 취소하려면 subprocess/thread
    로 실행하고 SIGTERM/kill 로 실제 중단해야 한다(단순 flag 로는 부족)."""
    j = _jobs.get(job_id)
    if j is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "E_JOB_NOT_FOUND", "message": f"unknown job_id {job_id}"})
    if j["status"] != "running":                       # 이미 종료된 작업은 idempotent
        return {"job_id": job_id, "status": j["status"]}
    j["cancel"] = True
    return {"job_id": job_id, "status": "cancelling"}


# ── 데모 작업 (협력기관은 이 함수 내부만 교체) ────────────────────────────────

async def _run_job(job_id: str, params: dict) -> None:
    """params.steps 만큼 진행하며 progress 갱신 + /output 산출물 작성.
    실제 컨테이너는 여기서 학습/추론/전처리 등 자기 작업을 수행한다."""
    j = _jobs[job_id]
    try:
        name  = str(params.get("name", "world"))
        steps = int(params.get("steps", 5))
        # /output 은 플랫폼이 미리 mount(PVC). exist_ok=True 라 mount 위 no-op.
        # readOnlyRootFilesystem 환경에선 mount 된 /output·/tmp 외엔 write 금지.
        os.makedirs(JF_OUTPUT_PATH, exist_ok=True)

        for i in range(1, steps + 1):
            if j["cancel"]:
                j["status"] = "cancelled"
                _emit("log", level="info", message="job cancelled", job_id=job_id, step=i)
                return
            await asyncio.sleep(1)                      # ← 실제 작업으로 교체
            j["progress"] = round(i / steps, 4)
            # spec §4.2: progress 이벤트는 percent(0~100), key 이름도 "percent".
            _emit("progress", job_id=job_id, step=i, total=steps,
                  percent=round(j["progress"] * 100, 2))

        result = {"greeting": f"hello, {name}!", "steps": steps, "item_id": JF_ITEM_ID}
        # 출력 규약 (spec §4.1): /output 아래에 산출물 작성
        with open(os.path.join(JF_OUTPUT_PATH, "result.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        with open(os.path.join(JF_OUTPUT_PATH, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump({"steps_done": steps, "status": "ok"}, f)

        j["result"] = result
        j["progress"] = 1.0
        j["status"] = "completed"
        _emit("log", level="info", message="job completed", job_id=job_id)

    except Exception as exc:                            # 모든 실패는 표준 에러 코드로 (spec §8)
        j["status"] = "failed"
        j["error"] = {"code": "E_HELLO_FAILED", "message": str(exc), "fatal": True}
        _emit("error", job_id=job_id, code="E_HELLO_FAILED", message=str(exc), fatal=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=JF_PORT)
