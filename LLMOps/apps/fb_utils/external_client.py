"""Thin httpx client for calling fb_external_container BFF.

Pattern mirrors apps/llm_model/src/external/proxy.py but kept separate to
preserve import boundaries between llm_playground and llm_model services.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from utils import settings

logger = logging.getLogger(__name__)

_http_client: Optional[httpx.AsyncClient] = None
_lock: Optional[asyncio.Lock] = None

# fb_external_container 의 manifest 스키마 `JobType` 닫힌집합 리터럴
# (apps/fb_external_container/src/manifest/schema.py:
#  Literal["train", "evaluate", "preprocess", "convert", "infer", "generate"]).
# 별 서비스라 import 경계를 넘어 가져올 수 없어 값만 복제한다 — BFF 쪽 리터럴이
# 바뀌면 여기도 같이 고쳐야 한다.
# ⚠️ 호출부에서 문자열을 다시 하드코딩하지 말고 이 상수를 쓸 것. 과거
# service.py 가 `job_type == "inference"` 로 비교해(스키마 값은 "infer")
# paired infer manifest 전환이 영구 dead branch 였고, 그 결과 배포가 조용히
# train manifest 로 pod 를 띄웠다.
MANIFEST_JOB_TYPE_INFER = "infer"


class ExternalInferError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


async def _client() -> httpx.AsyncClient:
    global _http_client, _lock
    if _lock is None:
        _lock = asyncio.Lock()
    async with _lock:
        if _http_client is None or _http_client.is_closed:
            _http_client = httpx.AsyncClient(timeout=1800.0)
    return _http_client


async def close_external_client() -> None:
    """Lifespan shutdown hook — release socket pool cleanly."""
    global _http_client
    c = _http_client
    _http_client = None
    if c is not None and not c.is_closed:
        try:
            await c.aclose()
        except Exception:
            logger.exception("close_external_client failed")


def _base_url() -> str:
    return settings.FB_EXTERNAL_CONTAINER_URL.rstrip("/")


async def _post(path: str, *, json: Any, expected: int) -> Any:
    url = f"{_base_url()}{path}"
    c = await _client()
    try:
        r = await c.post(url, json=json, timeout=1800.0)
    except httpx.HTTPError as e:
        raise ExternalInferError(0, f"unreachable {url}: {e}") from e
    if r.status_code != expected:
        raise ExternalInferError(
            r.status_code,
            f"BFF {path} returned {r.status_code}: {r.text[:300]}",
        )
    return r.json() if r.content else {}


async def _get(path: str, *, expected: int = 200) -> Any:
    url = f"{_base_url()}{path}"
    c = await _client()
    try:
        r = await c.get(url, timeout=5.0)
    except httpx.HTTPError as e:
        raise ExternalInferError(0, f"unreachable {url}: {e}") from e
    if r.status_code != expected:
        raise ExternalInferError(
            r.status_code,
            f"BFF {path} returned {r.status_code}: {r.text[:300]}",
        )
    return r.json() if r.content else {}


async def get_job_status(job_id: str) -> dict[str, Any]:
    """GET /api/v1/jobs/{job_id} — pod_ready, helm_release, partner_job_id 등 포함."""
    return await _get(f"/api/v1/jobs/{job_id}")


async def get_paired_manifest(
    name: str, version: str,
) -> dict[str, Any] | None:
    """GET /api/v1/manifests/{name}/{version}/paired.

    codex Med-2: train manifest 의 pair_id 로 등록된 inference manifest 를
    lookup. 404 면 paired 등록이 안 됐다는 뜻 — None 반환. 호출자는 이걸
    fallback 신호로 쓰면 안 된다(배포는 infer manifest 없이는 성립하지 않는다).
    """
    try:
        return await _get(f"/api/v1/manifests/{name}/{version}/paired")
    except ExternalInferError as e:
        if getattr(e, "status_code", 0) == 404:
            return None
        raise


async def start_infer_job(
    manifest_name: str,
    manifest_version: str,
    workspace_id: int,
    platform_model_id: int,
    params: dict[str, Any],
    gpu_count: int = 1,
    namespace: str = settings.SYSTEM_NAMESPACE,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Launch a partner pod via fb_external_container /api/v1/jobs.

    env_overrides — manifest spec.env 위에 덮어쓰기. launch 시점에 결정되는
    동적 env (예: EVA_CHECKPOINT_PATH = model.latest_commit name).
    """
    body: dict[str, Any] = {
        "manifest_name": manifest_name,
        "manifest_version": manifest_version,
        "workspace_id": workspace_id,
        "platform_model_id": platform_model_id,
        "gpu_count": gpu_count,
        "params": params,
        "namespace": namespace,
    }
    if env_overrides:
        body["env_overrides"] = env_overrides
    return await _post("/api/v1/jobs", json=body, expected=202)


async def cancel_infer_job(job_id: str) -> dict[str, Any]:
    return await _post(
        f"/api/v1/jobs/{job_id}/cancel",
        json=None,
        expected=202,
    )


async def run_inference(job_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Sync inference — POST /api/v1/jobs/{job_id}/run body {params: {...}}."""
    return await _post(
        f"/api/v1/jobs/{job_id}/run",
        json={"params": params},
        expected=200,
    )
