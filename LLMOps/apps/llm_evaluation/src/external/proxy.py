"""Thin httpx wrapper around fb_external_container's /api/v1 job API.

llm_model.external.proxy 와 동일 계약(s2s) — 평가 오케스트레이션이 job_type=evaluate
컨테이너를 런치/폴링/취소하는 데 필요한 부분만(start/get/cancel). 앱 간 결합 회피용
경량 사본(범용 httpx 래퍼, llm_model 특화 로직 없음).
"""
from __future__ import annotations

from typing import Any

import httpx


class ExternalContainerError(RuntimeError):
    """fb_external_container returned a non-expected response or was unreachable."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class ExternalContainerClient:
    """Async client for fb_external_container's /api/v1 job endpoints."""

    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client

    async def start_job(
        self,
        manifest_name: str,
        manifest_version: str,
        workspace_id: int,
        params: dict[str, Any],
        namespace: str = "jonathan-system",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "manifest_name": manifest_name,
            "manifest_version": manifest_version,
            "workspace_id": workspace_id,
            "namespace": namespace,
            "params": params,
        }
        return await self._post("/api/v1/jobs", json=payload, expected_status=202)

    async def get_job(self, job_id: str) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/jobs/{job_id}"
        try:
            resp = await self.client.get(url, timeout=15.0)
        except httpx.HTTPError as e:
            raise ExternalContainerError(0, f"unable to reach {url}: {e}") from e
        if resp.status_code >= 400:
            raise ExternalContainerError(
                resp.status_code,
                f"fb_external_container returned {resp.status_code}: {resp.text[:300]}",
            )
        return resp.json()

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        return await self._post(
            f"/api/v1/jobs/{job_id}/cancel", json=None, expected_status=202)

    async def _post(self, path: str, *, json: Any, expected_status: int) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = await self.client.post(url, json=json, timeout=60.0)
        except httpx.HTTPError as e:
            raise ExternalContainerError(0, f"unable to reach {url}: {e}") from e
        if resp.status_code != expected_status:
            raise ExternalContainerError(
                resp.status_code,
                f"fb_external_container returned {resp.status_code} for {path}: {resp.text[:300]}",
            )
        return resp.json() if resp.content else {}
