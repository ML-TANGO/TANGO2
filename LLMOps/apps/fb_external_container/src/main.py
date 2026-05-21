"""fb_external_container FastAPI bootstrap.

Lifespan owns:
- ``app.state.partner_http`` — single shared httpx.AsyncClient for all
  adapter calls. Adapters take a client; we own the connection pool.
- ``app.state.db_pool`` — placeholder until SP-Ext.3 lands.

Mirrors the apps/fb_user `def main()` factory pattern so the same
``uvicorn --factory main:main`` run.sh invocation works.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import health, job_router, manifest_router
from config import get_settings
from exceptions import register_exception_handlers
from launch import JobTracker, SchedulerClient
from manifest import (
    InMemoryManifestRegistry,
    MariaDBManifestRegistry,
)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    logger.info(
        "fb_external_container starting (scheduler=%s, poll_interval=%.1fs)",
        settings.fb_scheduler_url, settings.poll_interval_seconds,
    )

    # Single shared client — partner pods are inside the cluster, no proxy.
    app.state.partner_http = httpx.AsyncClient(
        timeout=settings.partner_http_timeout_seconds,
    )

    # Best-effort DB pool init. If env vars are missing or connection fails,
    # degrade to in-memory registry so dev / SP-Ext.10 mock work continues.
    app.state.db_pool = await _try_init_db_pool(settings, logger)
    if app.state.db_pool is not None:
        app.state.registry = MariaDBManifestRegistry(app.state.db_pool)
        logger.info("manifest registry: MariaDB persistence active")
    else:
        app.state.registry = InMemoryManifestRegistry()
        logger.warning(
            "manifest registry: in-memory fallback active "
            "(set db_host/db_user/db_password env to enable MariaDB)"
        )

    scheduler_client = SchedulerClient(
        base_url=settings.fb_scheduler_url,
        client=app.state.partner_http,
    )
    app.state.job_tracker = JobTracker(
        scheduler=scheduler_client,
        http_client=app.state.partner_http,
        poll_interval=settings.poll_interval_seconds,
    )

    try:
        yield
    finally:
        await app.state.job_tracker.shutdown()
        await app.state.partner_http.aclose()
        if app.state.db_pool is not None:
            app.state.db_pool.close()
            await app.state.db_pool.wait_closed()
        logger.info("fb_external_container shutdown complete")


async def _try_init_db_pool(settings, logger):
    """Best-effort aiomysql pool. Returns None on any failure."""
    if not settings.db_password and settings.db_host in ("localhost", "127.0.0.1"):
        # Local dev with no DB password set — treat as "no DB configured".
        logger.info("DB env not configured; manifest registry will use in-memory fallback")
        return None
    try:
        import aiomysql  # lazy import — only needed when DB is configured
        return await aiomysql.create_pool(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            db=settings.db_name,
            minsize=1,
            maxsize=5,
            autocommit=False,
        )
    except Exception as e:
        logger.warning(
            "aiomysql pool init failed (%s); falling back to in-memory registry",
            e,
        )
        return None


def main() -> FastAPI:
    """Factory for `uvicorn --factory main:main`."""
    app = FastAPI(
        title="fb_external_container",
        version="0.1.0",
        description="Common infrastructure for external partner container hosting (SP-1 v2).",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(manifest_router.router, prefix="/api/v1/manifests", tags=["manifest"])
    app.include_router(job_router.router, prefix="/api/v1/jobs", tags=["job"])

    return app


# When run as `uvicorn main:app` (without --factory) some tools expect
# `app` at module level. Build it eagerly here too.
app = main()
