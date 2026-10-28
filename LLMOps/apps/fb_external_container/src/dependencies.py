"""FastAPI dependency factories.

Resources owned by the FastAPI lifespan (httpx client, DB pool) are read
from ``request.app.state``. SP-Ext.3 (manifest registry) and SP-Ext.8
(lifecycle poller) inject these into their routers via ``Depends(...)``.
"""

from __future__ import annotations

import httpx
from fastapi import Request


async def get_http_client(request: Request) -> httpx.AsyncClient:
    """Shared httpx client used by adapters to talk to partner pods."""
    return request.app.state.partner_http


async def get_db_pool(request: Request):
    """Shared MariaDB connection pool.

    SP-Ext.3 wires this up once the manifest registry table lands. Until
    then the attribute may be ``None`` — callers that need it should fail
    explicitly rather than dereference None silently.
    """
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        from exceptions import ServiceError  # local import — avoid cycle
        raise ServiceError("db_pool not initialised (SP-Ext.3 not yet wired)")
    return pool
