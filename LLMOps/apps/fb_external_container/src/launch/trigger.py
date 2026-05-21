"""fb_scheduler s2s wrapper for external container helm operations.

fb_scheduler exposes ``POST /external/launch`` and ``POST /external/uninstall``
on its existing health_app FastAPI. This module is the only place that
knows about that HTTP contract — JobTracker calls SchedulerClient methods,
not raw HTTP.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class SchedulerError(RuntimeError):
    """fb_scheduler returned a non-2xx response or could not be reached."""


class SchedulerClient:
    """Thin async wrapper over the fb_scheduler external endpoints."""

    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client

    async def launch(self, pod_info_dict: dict[str, Any]) -> dict[str, Any]:
        """POST /external/launch — fb_scheduler runs helm install."""
        url = f"{self.base_url}/external/launch"
        try:
            resp = await self.client.post(url, json=pod_info_dict, timeout=60.0)
        except httpx.HTTPError as e:
            raise SchedulerError(f"unable to reach fb_scheduler at {url}: {e}") from e
        if resp.status_code >= 400:
            raise SchedulerError(
                f"fb_scheduler returned {resp.status_code} for /external/launch: "
                f"{resp.text[:500]}"
            )
        return resp.json() if resp.content else {}

    async def uninstall(self, helm_release: str, namespace: str) -> dict[str, Any]:
        """POST /external/uninstall — fb_scheduler runs helm uninstall."""
        url = f"{self.base_url}/external/uninstall"
        try:
            resp = await self.client.post(
                url,
                json={"helm_release": helm_release, "namespace": namespace},
                timeout=30.0,
            )
        except httpx.HTTPError as e:
            raise SchedulerError(f"unable to reach fb_scheduler at {url}: {e}") from e
        if resp.status_code >= 400:
            raise SchedulerError(
                f"fb_scheduler returned {resp.status_code} for /external/uninstall: "
                f"{resp.text[:500]}"
            )
        return resp.json() if resp.content else {}
