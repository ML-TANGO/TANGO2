"""Thin httpx wrapper around fb_external_container's HTTP API.

Encapsulates the s2s contract here so route.py stays focused on the
user-facing SSE/REST shape, and so swapping transports (Kafka, gRPC,
etc.) later only touches this file.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# 서빙/개발 인스턴스 분리 — 플랫폼 ns 는 jfb-settings 의 JF_SYSTEM_NAMESPACE 로 주입된다.
# 미주입 환경에서는 기존 리터럴로 폴백하므로 기존 배포의 동작은 바뀌지 않는다.
_PLATFORM_NAMESPACE = os.environ.get("JF_SYSTEM_NAMESPACE") or "jonathan-system"


class ExternalContainerError(RuntimeError):
    """fb_external_container returned a non-2xx response or was unreachable."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class ExternalContainerClient:
    """Async client for fb_external_container's /api/v1 endpoints."""

    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client

    # ── Manifests ──────────────────────────────────────────────────────

    async def register_manifest(self, manifest_yaml: str) -> dict[str, Any]:
        return await self._post(
            "/api/v1/manifests",
            json={"manifest_yaml": manifest_yaml},
            expected_status=201,
        )

    async def register_hybrid_pair(self, infer_yaml: str, train_yaml: str) -> list[dict[str, Any]]:
        return await self._post(
            "/api/v1/manifests/pair",
            json={
                "manifests": [
                    {"manifest_yaml": infer_yaml},
                    {"manifest_yaml": train_yaml},
                ],
            },
            expected_status=201,
        )

    async def list_manifests(self) -> list[dict[str, Any]]:
        """Pass-through GET /api/v1/manifests on fb_external_container."""
        url = f"{self.base_url}/api/v1/manifests"
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

    async def get_manifest_by_name(self, name: str) -> list[dict[str, Any]]:
        """Pass-through GET /api/v1/manifests/{name}."""
        url = f"{self.base_url}/api/v1/manifests/{name}"
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

    # ── Jobs ───────────────────────────────────────────────────────────

    async def start_job(
        self,
        manifest_name: str,
        manifest_version: str,
        workspace_id: int,
        params: dict[str, Any],
        namespace: str = _PLATFORM_NAMESPACE,
        instance_id: int | None = None,
        instance_count: int | None = None,
        gpu_count: int | None = None,
        platform_model_id: int | None = None,
        output_subdir: str | None = None,
        secrets: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "manifest_name": manifest_name,
            "manifest_version": manifest_version,
            "workspace_id": workspace_id,
            "namespace": namespace,
            "params": params,
        }
        # forward only when caller supplied an override — keeps fb_external_container
        # backward-compatible until SP-Ext.7+ wires up instance scheduling.
        if instance_id is not None:
            payload["instance_id"] = instance_id
        if instance_count is not None:
            payload["instance_count"] = instance_count
        if gpu_count is not None:
            payload["gpu_count"] = gpu_count
        if platform_model_id is not None:
            payload["platform_model_id"] = platform_model_id
        if output_subdir is not None:
            payload["output_subdir"] = output_subdir
        # I6 (SP-3): manifest.secrets.required 값(HF_TOKEN 등). params/env_overrides
        # 와 별도 — fb_external_container 가 redacted 경로로 pod env 주입.
        if secrets:
            payload["secrets"] = secrets
        return await self._post(
            "/api/v1/jobs",
            json=payload,
            expected_status=202,
        )

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
            f"/api/v1/jobs/{job_id}/cancel",
            json=None,
            expected_status=202,
        )

    async def deploy(
        self,
        manifest_name: str,
        manifest_version: str,
        workspace_id: int,
        namespace: str = _PLATFORM_NAMESPACE,
        infer_job_id: str | None = None,
        payload: dict[str, Any] | None = None,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        """Trigger hybrid pair deploy — partner /deploy reload.

        timeout: partner /deploy 는 in-pod 가중치 재로드(1~5분 동기)라 기본 60s 로는
        부족 → 호출측이 상향(예: 체크포인트 서빙 전환 600s)해서 넘긴다.
        """
        body: dict[str, Any] = {
            "manifest_name": manifest_name,
            "manifest_version": manifest_version,
            "workspace_id": workspace_id,
            "namespace": namespace,
            "payload": payload or {},
        }
        if infer_job_id:
            body["infer_job_id"] = infer_job_id
        return await self._post(
            "/api/v1/jobs/deploy",
            json=body,
            expected_status=200,
            timeout=timeout,
        )

    async def run_inference(
        self,
        job_id: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Proxy to /api/v1/jobs/{job_id}/run on a running sync infer pod."""
        return await self._post(
            f"/api/v1/jobs/{job_id}/run",
            json={"params": params},
            expected_status=200,
        )

    # ── Internals ──────────────────────────────────────────────────────

    async def _post(
        self,
        path: str,
        *,
        json: Any,
        expected_status: int,
        timeout: float = 60.0,
    ) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = await self.client.post(url, json=json, timeout=timeout)
        except httpx.HTTPError as e:
            raise ExternalContainerError(0, f"unable to reach {url}: {e}") from e
        if resp.status_code != expected_status:
            raise ExternalContainerError(
                resp.status_code,
                f"fb_external_container returned {resp.status_code} for {path}: {resp.text[:300]}",
            )
        return resp.json() if resp.content else {}
