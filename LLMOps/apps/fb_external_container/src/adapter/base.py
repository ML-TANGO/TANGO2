"""ExternalAdapter ABC + GenericHTTPAdapter default implementation.

An adapter wraps a single launched container. The lifecycle layer owns
adapter instances per running job; the adapter itself is stateless beyond
the (manifest, service_url, http_client) it holds.

Conventions:
- All endpoint paths come from ``manifest.spec.endpoints``. URL templates
  containing ``{id}`` are substituted via :func:`_substitute_job_id`.
- All HTTP calls go through ``httpx.AsyncClient``. The caller owns the
  client's lifetime (typically a single client per fb_external_container
  process, scoped by FastAPI lifespan).
"""

from __future__ import annotations

import logging
import urllib.parse
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx

from manifest.schema import ExternalContainerManifest
from normalize import (
    ExternalContainerStatus,
    ExternalJobConfig,
    ExternalJobError,
    ExternalJobResult,
    from_partner_string,
    is_terminal,
)

logger = logging.getLogger(__name__)


# ── URL helpers ───────────────────────────────────────────────────────────


def _substitute_job_id(template: str, job_id: str) -> str:
    """Replace ``{id}`` in an endpoint template with a URL-safe job id.

    The schema validator already ensures ``{id}`` is present in
    ``endpoints.jobs`` and ``endpoints.cancel`` when those exist, so this
    just quotes the value defensively in case job_id contains URL-unsafe
    characters.
    """
    return template.replace("{id}", urllib.parse.quote(job_id, safe=""))


def _join_url(base: str, path: str) -> str:
    """Join a base URL with an endpoint path, tolerating either side
    omitting / including the slash separator."""
    if not path:
        return base.rstrip("/")
    if not base:
        return path
    return base.rstrip("/") + "/" + path.lstrip("/")


# ── Adapter ABC ───────────────────────────────────────────────────────────


class ExternalAdapter(ABC):
    """Base class for partner-specific HTTP adapters.

    Sub-classes override only the response-shape mappings; the HTTP layer
    is shared in :class:`GenericHTTPAdapter`.
    """

    def __init__(
        self,
        manifest: ExternalContainerManifest,
        service_url: str,
        client: httpx.AsyncClient,
    ) -> None:
        self.manifest = manifest
        self.service_url = service_url.rstrip("/")
        self.client = client

    # ── HTTP path resolution ─────────────────────────────────────────────

    def _endpoint(self, key: str) -> str:
        """Return the partner-defined URL path for an endpoint key."""
        endpoints = self.manifest.spec.endpoints or {}
        path = endpoints.get(key)
        if not path:
            raise KeyError(
                f"manifest {self.manifest.metadata.name!r} has no endpoint "
                f"{key!r} (declared keys: {list(endpoints)})"
            )
        return path

    # ── Public surface — must be implemented per partner ─────────────────

    @abstractmethod
    async def info(self) -> dict[str, Any]:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...

    @abstractmethod
    async def start_job(self, config: ExternalJobConfig) -> str:
        """POST partner's run endpoint with ``config.params``.

        Returns the partner-side job id. Caller stores the mapping
        (platform job_id ↔ partner job_id) so subsequent polls use the
        correct id.
        """

    @abstractmethod
    async def get_status(self, job_id: str) -> ExternalJobResult:
        ...

    @abstractmethod
    async def cancel(self, job_id: str) -> bool:
        ...

    async def run_sync(self, params: dict[str, Any]) -> dict[str, Any]:
        """Sync inference call — POST manifest.endpoints.run with params body.

        Unlike `start_job` (async — returns partner_job_id for polling), this
        forwards the response body directly. Used by long-running sync infer
        pods where each request is independent and resolves within seconds.
        Partners override if their /run body envelope differs.
        """
        url = _join_url(self.service_url, self._endpoint("run"))
        resp = await self.client.post(url, json=params)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    async def deploy(self, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Optional: trigger partner's deploy/reload endpoint.

        Used by hybrid pairs (e.g. eva-vlm-train → eva-vlm-infer) where the
        infer pod needs to swap to a freshly-committed checkpoint without
        image re-deploy. Partners that do not declare `endpoints.deploy`
        cause this to raise ``NotImplementedError`` — callers decide
        whether to log+skip or surface to the user.
        """
        endpoints = self.manifest.spec.endpoints or {}
        path = endpoints.get("deploy")
        if not path:
            raise NotImplementedError(
                f"manifest {self.manifest.metadata.name!r} has no deploy endpoint"
            )
        url = _join_url(self.service_url, path)
        body = dict(payload or {})
        resp = await self.client.post(url, json=body)
        resp.raise_for_status()
        return resp.json() if resp.content else {}


# ── Default implementation (SP-1 v2 spec-compliant partners) ──────────────


class GenericHTTPAdapter(ExternalAdapter):
    """Reference adapter for partners that follow SP-1 v2 §5 verbatim.

    - ``POST /run`` returns ``{"job_id": "..."}`` (async) or the result
      directly (sync).
    - ``GET /jobs/{id}`` returns ``{status, progress, result, error}``.
    - ``POST /jobs/{id}/cancel`` returns 200 on accepted cancel.

    Sub-classes override the small `_extract_*` hooks to absorb partner
    deviations without re-implementing HTTP plumbing.
    """

    async def info(self) -> dict[str, Any]:
        url = _join_url(self.service_url, self._endpoint("info"))
        resp = await self.client.get(url)
        resp.raise_for_status()
        return resp.json()

    async def health(self) -> bool:
        url = _join_url(self.service_url, self._endpoint("health"))
        try:
            resp = await self.client.get(url)
        except httpx.HTTPError as e:
            logger.debug("health probe to %s failed: %s", url, e)
            return False
        return resp.status_code == 200

    async def start_job(self, config: ExternalJobConfig) -> str:
        url = _join_url(self.service_url, self._endpoint("run"))
        resp = await self.client.post(url, json=config.params)
        resp.raise_for_status()
        body = resp.json() if resp.content else {}
        partner_job_id = self._extract_partner_job_id(body, config.job_id)
        return partner_job_id

    async def get_status(self, job_id: str) -> ExternalJobResult:
        template = self._endpoint("jobs")
        url = _join_url(self.service_url, _substitute_job_id(template, job_id))
        resp = await self.client.get(url)
        # Partners that ship HTTP 200 for errors (SP-1 v2 §11 ETRI Tier 1
        # bug) still surface the failure via the body's ``status`` field —
        # _build_result handles both paths.
        if resp.status_code >= 400:
            logger.debug(
                "%s returned %d for %s; building FAILED result",
                self.manifest.metadata.name, resp.status_code, url,
            )
            return ExternalJobResult(
                job_id=job_id,
                status=ExternalContainerStatus.FAILED,
                error=ExternalJobError(
                    code="E_HTTP_ERROR",
                    message=f"partner returned HTTP {resp.status_code}",
                ),
            )
        body = resp.json() if resp.content else {}
        return self._build_result(job_id, body)

    async def cancel(self, job_id: str) -> bool:
        endpoints = self.manifest.spec.endpoints or {}
        template = endpoints.get("cancel")
        if not template:
            logger.info(
                "manifest %r does not declare a cancel endpoint; cancel is a no-op",
                self.manifest.metadata.name,
            )
            return False
        url = _join_url(self.service_url, _substitute_job_id(template, job_id))
        try:
            resp = await self.client.post(url)
        except httpx.HTTPError as e:
            logger.warning("cancel %s failed: %s", url, e)
            return False
        return resp.status_code == 200

    # ── Per-partner hooks (override in subclass) ─────────────────────────

    def _extract_partner_job_id(self, body: dict, platform_job_id: str) -> str:
        """Default: take ``job_id`` from response body; fall back to platform id."""
        return str(body.get("job_id") or platform_job_id)

    def _build_result(self, job_id: str, body: dict) -> ExternalJobResult:
        """Map an SP-1 v2 §5.4-shaped body into ExternalJobResult."""
        raw_status = body.get("status")
        status = from_partner_string(raw_status if isinstance(raw_status, str) else None)
        return ExternalJobResult(
            job_id=job_id,
            status=status,
            progress=_coerce_progress(body.get("progress")),
            result=body.get("result") if isinstance(body.get("result"), dict) else None,
            error=_build_error(body.get("error")),
        )


# ── Helpers ───────────────────────────────────────────────────────────────


def _coerce_progress(raw: Any) -> Optional[float]:
    """Accept either 0..1 float or 0..100 percent integers."""
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v > 1.0:
        v = v / 100.0
    return max(0.0, min(1.0, v))


def _build_error(raw: Any) -> Optional[ExternalJobError]:
    """Map partner error envelope into ExternalJobError, or None."""
    if not raw:
        return None
    if isinstance(raw, str):
        return ExternalJobError(code="E_PARTNER_ERROR", message=raw)
    if isinstance(raw, dict):
        return ExternalJobError(
            code=str(raw.get("code") or "E_PARTNER_ERROR"),
            message=str(raw.get("message") or "unspecified partner error"),
            fatal=bool(raw.get("fatal", True)),
        )
    return ExternalJobError(code="E_PARTNER_ERROR", message=str(raw))


__all__ = [
    "ExternalAdapter",
    "GenericHTTPAdapter",
    "is_terminal",
    "_substitute_job_id",
    "_join_url",
]
