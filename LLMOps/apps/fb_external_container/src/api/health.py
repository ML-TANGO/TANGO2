"""Health / readiness routes.

K8s probes from the helm chart hit these (matching the SP-1 v2 §5.2
semantics we enforce on partner pods). DB readiness is only checked when
the pool is up; until SP-Ext.3 lands the readiness probe degrades to a
plain liveness check.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready", response_model=None)
async def ready(request: Request) -> dict | JSONResponse:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        # SP-Ext.3 not wired yet — be honest about partial readiness.
        return {"status": "ready", "db": "not-configured"}
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
        return {"status": "ready", "db": "ok"}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "not-ready", "db": "error", "detail": str(exc)},
        )
