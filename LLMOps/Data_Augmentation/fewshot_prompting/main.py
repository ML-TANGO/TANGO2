"""Few-Shot Prompt Optimization service (Tango MSA backend).

Receives few-shot examples and an LLM url over REST and returns a single
optimized **system prompt (text)** — the instruction + curated few-shot demos
produced by the optimizer in ``src/optimizer/`` (DSPy MIPROv2 + a
textual-gradient harvest loop).

Endpoints follow the Tango MSA contract
(``LLMOps/docs/Tango MSA 서비스 Docker 이미지 빌드 가이드.md``); the async
``/run`` -> ``/status`` split is the guide's recommended pattern for jobs that
exceed the platform's 60 s sync timeout (API guide: ``README.md``):

  GET  /health  — liveness probe
  GET  /info    — service name / version / capabilities
  POST /run     — submit an optimization job -> {job_id} (params.sync=true
                  runs inline and returns {system_prompt, ...} directly)
  GET  /status  — poll a job: ?job_id=... -> pending/running/completed/failed

Run locally:  python main.py   (or: uvicorn main:app --host 0.0.0.0 --port 30000)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.jobs import JobStore
from src.schemas import RunRequest
from src.service import optimize_system_prompt, validate_params

SERVICE_NAME = "fewshot-prompt-optimizer"
SERVICE_VERSION = "1.0.0"
PORT = int(os.environ.get("PORT", "30000"))

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)
JOBS = JobStore()


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Tango MSA error envelope (탑재 가이드 5.3/5.4): status/code/message."""
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "code": code, "message": message},
    )


@app.exception_handler(RequestValidationError)
def on_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Fold FastAPI's 422 {"detail": [...]} into the guide's 400 INVALID_PARAMS shape.
    problems = "; ".join(
        f"{'.'.join(str(p) for p in err['loc'] if p != 'body')}: {err['msg']}"
        for err in exc.errors()
    )
    return _error_response(400, "INVALID_PARAMS", problems or "invalid request body")


@app.get("/health")
def health_check() -> dict:
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/info")
def get_info() -> dict:
    return {
        "name": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "description": (
            "Optimizes few-shot examples + instruction into a system prompt "
            "(DSPy MIPROv2 + a textual-gradient harvest loop)."
        ),
        "capabilities": [
            "fewshot_optimization",
            "system_prompt_generation",
            "vlm_ready",
            "async_run",
        ],
    }


@app.post("/run")
def run_service(request: RunRequest):
    try:
        params = request.resolve()
        validate_params(params)  # fail fast at submit time
    except ValueError as e:
        return _error_response(400, "INVALID_PARAMS", str(e))

    if params.sync:
        try:
            result = optimize_system_prompt(params)
            return {"status": "success", "result": result.model_dump()}
        except ValueError as e:
            return _error_response(400, "INVALID_PARAMS", str(e))
        except Exception as e:  # noqa: BLE001 — surface the failure to the caller
            return _error_response(500, "INTERNAL_ERROR", f"{type(e).__name__}: {e}")

    job = JOBS.submit(lambda set_progress: optimize_system_prompt(params, progress_cb=set_progress))
    return {"status": "success", "result": {"job_id": job.job_id, "job_status": job.status}}


@app.get("/status")
def get_status(job_id: str | None = None):
    if not job_id:
        return _error_response(400, "INVALID_PARAMS", "query parameter 'job_id' is required")
    job = JOBS.get(job_id)
    if job is None:
        return _error_response(404, "NOT_FOUND", f"unknown job_id: {job_id} (never existed, or expired)")
    body: dict = {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }
    if job.status == "completed":
        body["result"] = job.result
    elif job.status == "failed":
        body["code"] = job.error_code
        body["message"] = job.error_message
    return {k: v for k, v in body.items() if v is not None}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
