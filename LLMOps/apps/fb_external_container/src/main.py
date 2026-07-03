"""fb_external_container FastAPI bootstrap.

Lifespan owns:
- ``app.state.partner_http`` — single shared httpx.AsyncClient for all
  adapter calls. Adapters take a client; we own the connection pool.
- ``app.state.db_pool`` — placeholder until SP-Ext.3 lands.

Mirrors the apps/fb_user `def main()` factory pattern so the same
``uvicorn --factory main:main`` run.sh invocation works.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import health, job_router, manifest_router
from config import get_settings
from exceptions import register_exception_handlers
from launch import JobStateRepository, JobTracker, SchedulerClient
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

    # Start on the in-memory registry so the lifespan finishes *fast* and
    # /health returns 200 immediately — the liveness probe has no DB
    # dependency. Blocking the lifespan to wait for MariaDB would starve the
    # probe and get the pod killed (~90s) into a CrashLoop. Instead we connect
    # in the background and upgrade to the MariaDB registry once the DB is
    # reachable; the registry is fully lazy (per-request queries) so the swap
    # is instant and needs no reload step. This is what makes the manifests
    # auto-recover after a node reboot where this pod races ahead of galera.
    app.state.db_pool = None
    app.state.registry = InMemoryManifestRegistry()
    app.state.db_init_task = None

    scheduler_client = SchedulerClient(
        base_url=settings.fb_scheduler_url,
        client=app.state.partner_http,
    )
    app.state.job_tracker = JobTracker(
        scheduler=scheduler_client,
        http_client=app.state.partner_http,
        poll_interval=settings.poll_interval_seconds,
        repository=None,
    )

    if not _db_configured(settings):
        logger.info(
            "DB env not configured; manifest registry stays in-memory "
            "(set db_host/db_user/db_password to enable MariaDB; "
            "BFF restart will NOT recover in-flight jobs)"
        )
    else:
        # One fast attempt covers the common case (MariaDB already up, e.g. a
        # plain pod restart). On failure — typically a node reboot where this
        # pod races ahead of MariaDB-galera — hand off to a background retry so
        # startup still completes now and the registry upgrades later.
        try:
            pool = await _open_pool(settings)
        except Exception as e:
            logger.warning(
                "initial DB connect failed (%s); serving with in-memory "
                "registry and retrying MariaDB in the background",
                e,
            )
            app.state.db_init_task = asyncio.create_task(
                _db_init_background(app, settings, logger)
            )
        else:
            await _wire_db(app, pool, logger)

    try:
        yield
    finally:
        task = app.state.db_init_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await app.state.job_tracker.shutdown()
        await app.state.partner_http.aclose()
        if app.state.db_pool is not None:
            app.state.db_pool.close()
            await app.state.db_pool.wait_closed()
        logger.info("fb_external_container shutdown complete")


def _db_configured(settings) -> bool:
    """False for local dev with no DB (localhost + empty password)."""
    return not (
        not settings.db_password
        and settings.db_host in ("localhost", "127.0.0.1")
    )


async def _open_pool(settings):
    """Open a single aiomysql pool. Raises on failure; caller owns any retry.

    ``connect_timeout`` is mandatory here: aiomysql defaults it to None, so
    without it a dropped SYN (reboot Service pointing at a not-yet-ready pod)
    would hang the connect for the OS TCP timeout and stall the whole retry.
    """
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
        connect_timeout=settings.db_connect_timeout_seconds,
    )


async def _wire_db(app, pool, logger) -> None:
    """Attach a live pool: upgrade registry + job repository, run recovery.

    Safe to call from the lifespan or from the background task. Assigning
    ``app.state.registry`` is atomic under the GIL and the MariaDB registry
    queries the table on every request, so concurrent lookups never observe
    torn state during the swap.
    """
    app.state.db_pool = pool
    app.state.registry = MariaDBManifestRegistry(pool)
    # SP-Ext.3: same pool drives the job state persistence.
    app.state.job_tracker.repository = JobStateRepository(pool)
    logger.info(
        "MariaDB persistence active (manifest registry + job state repository)"
    )
    # Restore in-flight jobs left behind by the previous BFF process.
    # Best-effort — any failure logs and yields to normal operation.
    try:
        recovered = await app.state.job_tracker.startup_recovery()
        if recovered:
            logger.info(
                "SP-Ext.3 startup recovery restored %d in-flight job(s)",
                recovered,
            )
    except Exception:
        logger.exception(
            "SP-Ext.3 startup recovery raised — continuing with cold start"
        )


async def _db_init_background(app, settings, logger) -> None:
    """Retry MariaDB with capped backoff, then upgrade the registry in place.

    Runs as a lifespan-owned task so the app serves immediately while a
    slow-to-boot MariaDB (node reboot / galera quorum) comes up. Gives up after
    ``db_init_max_attempts`` and leaves the in-memory registry in place; a later
    natural restart (or a manual re-register) recovers from there.
    """
    attempts = max(1, settings.db_init_max_attempts)
    delay = max(0.0, settings.db_init_backoff_base_seconds)
    cap = max(delay, settings.db_init_backoff_cap_seconds)

    for attempt in range(1, attempts + 1):
        await asyncio.sleep(delay)
        try:
            pool = await _open_pool(settings)
        except Exception as e:
            next_delay = min(cap, delay * 2)
            if attempt >= attempts:
                logger.warning(
                    "background DB connect gave up after %d attempt(s) (%s); "
                    "staying on in-memory registry",
                    attempt, e,
                )
                return
            logger.warning(
                "background DB connect attempt %d/%d failed (%s); "
                "retrying in %.1fs",
                attempt, attempts, e, next_delay,
            )
            delay = next_delay
            continue
        await _wire_db(app, pool, logger)
        logger.info(
            "background DB init succeeded on attempt %d; manifest registry "
            "upgraded to MariaDB (external-container jobs now resolvable)",
            attempt,
        )
        return


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
