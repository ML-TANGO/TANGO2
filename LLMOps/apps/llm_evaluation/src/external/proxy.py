"""Thin httpx wrapper around fb_external_container's /api/v1 job API.

llm_model.external.proxy 와 동일 계약(s2s) — 평가 오케스트레이션이 job_type=evaluate
컨테이너를 런치/폴링/취소하는 데 필요한 부분만(start/get/cancel). 앱 간 결합 회피용
경량 사본(범용 httpx 래퍼, llm_model 특화 로직 없음).
"""
from __future__ import annotations

import os
from typing import Any

import httpx

# 서빙/개발 인스턴스 분리 — 플랫폼 ns 는 jfb-settings 의 JF_SYSTEM_NAMESPACE 로 주입된다.
# 미주입 환경에서는 기존 리터럴로 폴백하므로 기존 배포의 동작은 바뀌지 않는다.
_PLATFORM_NAMESPACE = os.environ.get("JF_SYSTEM_NAMESPACE") or "jonathan-system"


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
        namespace: str = _PLATFORM_NAMESPACE,
        gpu_count: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "manifest_name": manifest_name,
            "manifest_version": manifest_version,
            "workspace_id": workspace_id,
            "namespace": namespace,
            "params": params,
        }
        # 자원 오버라이드. **키를 빼는 것과 0 을 넣는 것은 다르다** — 수신측
        # (fb_external_container lifecycle)이 `gpu_count is not None` 으로 판정해
        # 없으면 manifest.spec.resources.gpu 를 그대로 쓰고, 0 이면 GPU 를 요청하지
        # 않는다. 그래서 여기서도 falsy 가 아니라 None 으로 걸러야 0 이 살아남는다.
        if gpu_count is not None:
            payload["gpu_count"] = int(gpu_count)
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
