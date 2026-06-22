"""Few-Shot Prompt Optimization service (Tango MSA backend).

Receives few-shot examples and an LLM url over REST and returns a single
optimized **system prompt (text)** — the instruction + curated few-shot demos
produced by the optimizer in ``src/optimizer/`` (DSPy MIPROv2 + a
textual-gradient harvest loop).

Endpoints follow the Tango MSA contract
(``LLMOps/docs/Tango MSA 서비스 Docker 이미지 빌드 가이드.md``):

  GET  /health  — liveness probe
  GET  /info    — service name / version / capabilities
  POST /run     — optimize: {examples, llm_url, ...} -> {system_prompt, ...}

Run locally:  python main.py   (or: uvicorn main:app --host 0.0.0.0 --port 30000)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import FastAPI

from src.schemas import RunRequest, RunResponse
from src.service import optimize_system_prompt

SERVICE_NAME = "fewshot-prompt-optimizer"
SERVICE_VERSION = "1.0.0"
PORT = int(os.environ.get("PORT", "30000"))

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)


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
        "capabilities": ["fewshot_optimization", "system_prompt_generation", "vlm_ready"],
    }


@app.post("/run", response_model=RunResponse)
def run_service(request: RunRequest) -> RunResponse:
    try:
        params = request.resolve()
        result = optimize_system_prompt(params)
        return RunResponse(status="success", result=result)
    except ValueError as e:
        # Client-side problem (bad/missing input): report, don't 500.
        return RunResponse(status="error", message=str(e))
    except Exception as e:  # noqa: BLE001 — surface the failure to the caller
        return RunResponse(status="error", message=f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
