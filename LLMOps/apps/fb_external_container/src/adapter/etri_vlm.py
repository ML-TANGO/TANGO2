"""Adapter for ETRI SDS-VLM (eva-vlm-{infer,train}).

ETRI deviates from SP-1 v2 in two known ways the platform must absorb
(see docs/superpowers/reviews/2026-05-12-ETRI-SDS-VLM-API-review.md):

1. ``/train`` returns ``{"id": "..."}`` (key is ``id`` not ``job_id``).
2. Error responses currently return HTTP 200 with ``status: "ERROR"`` and
   an ``error_message`` string field. ETRI patches this in v1.0.1 — we
   tolerate both shapes so the adapter keeps working across versions.
"""

from __future__ import annotations

from typing import Any, Optional

import logging
import urllib.parse
from typing import Any, Optional

import httpx

from normalize import (
    ExternalContainerStatus,
    ExternalJobConfig,
    ExternalJobError,
    ExternalJobResult,
    from_partner_string,
)

from .base import (  # type: ignore[attr-defined]
    GenericHTTPAdapter,
    _build_error,
    _coerce_progress,
    _join_url,
    _substitute_job_id,
)

logger = logging.getLogger(__name__)


class _ETRIRequestError(RuntimeError):
    """ETRI returned HTTP 200 but the body indicated failure (Tier 1 bug)."""


class ETRIAdapter(GenericHTTPAdapter):
    """ETRI SDS-VLM eva-vlm-{infer,train} response normalization."""

    # ETRI 응답이 job id 를 "id" 키로 보냄 (SP-1 v2 §5.3 은 "job_id" 권장).
    _PARTNER_ID_KEYS: tuple[str, ...] = ("job_id", "id", "training_id")

    _ETRI_ERROR_STATUSES: frozenset[str] = frozenset(
        {"error", "errored", "failed", "fail"}
    )

    def _extract_partner_job_id(self, body: dict, platform_job_id: str) -> str:
        # Top-level keys first.
        for key in self._PARTNER_ID_KEYS:
            if body.get(key):
                return str(body[key])
        # ETRI v1.0.0 actually nests it under `result.job_id`
        # (TrainResponse.result is a dict — confirmed against /openapi.json).
        result = body.get("result")
        if isinstance(result, dict):
            for key in self._PARTNER_ID_KEYS:
                if result.get(key):
                    return str(result[key])
        return platform_job_id

    @staticmethod
    def _detect_etri_error(body: dict) -> Optional[ExternalJobError]:
        """SP-Ext review MEDIUM #B — start_job and cancel must also absorb
        ETRI's Tier 1 quirk (HTTP 200 + ``status: ERROR``). _build_result
        already handles get_status; this static helper covers the other
        endpoints without duplicating the body-shape knowledge."""
        raw_status = body.get("status") or body.get("state")
        if not isinstance(raw_status, str):
            return None
        if raw_status.strip().lower() not in ETRIAdapter._ETRI_ERROR_STATUSES:
            return None
        err = body.get("error")
        msg = (
            (err.get("message") if isinstance(err, dict) else None)
            or (err if isinstance(err, str) else None)
            or body.get("error_message")
            or body.get("message")
            or "ETRI returned a failure status without a message"
        )
        code = (
            err.get("code") if isinstance(err, dict) and err.get("code")
            else "E_ETRI_ERROR"
        )
        return ExternalJobError(code=str(code), message=str(msg))

    async def start_job(self, config: ExternalJobConfig) -> str:
        """POST /train (or whatever endpoints.run resolves to).

        ETRI v1.0.0 의 ``/train`` body schema 는
        ``{"workspace_id": int, "project_id": str, "params": {...}}`` 요구
        (FastAPI ValidationError 로 422 응답). config.params 만 raw 로 보내면
        매칭 실패하므로 envelope 으로 감싸 전달한다. project_id 는 platform
        job_id 를 그대로 사용 (ETRI 입장에선 partner-side id, 우리 record 의
        partner_job_id 와 별도).

        ETRI v1.0.0 sometimes returns HTTP 200 + ``status: ERROR`` instead of
        a 4xx response (Tier 1 bug). We surface that as an exception so the
        lifecycle layer routes the job to FAILED via ``_start_partner_job``
        rather than entering the polling loop with a stale id.
        """
        url = _join_url(self.service_url, self._endpoint("run"))
        # ETRI schemas.py TrainRequest: workspace_id/project_id 가 모두 `str`.
        # platform 의 workspace_id 는 int 라 명시 변환 필수 (그 외엔 422).
        envelope = {
            "workspace_id": str(config.workspace_id),
            "project_id": str(config.job_id),
            "params": config.params or {},
        }
        resp = await self.client.post(url, json=envelope)
        resp.raise_for_status()
        body = resp.json() if resp.content else {}
        etri_error = self._detect_etri_error(body)
        if etri_error is not None:
            raise _ETRIRequestError(
                f"{etri_error.code}: {etri_error.message}"
            )
        return self._extract_partner_job_id(body, config.job_id)

    async def run_sync(self, params: dict[str, Any]) -> dict[str, Any]:
        """ETRI /run — RunRequest envelope `{workspace_id, project_id, params}`.

        partner code (`/app/app.py:131`) 의 `run_inference(body: RunRequest)`
        가 envelope 안 params 만 사용. workspace_id / project_id 는 ETRI 측
        식별자라 우리는 dummy 로 채워 보냄.
        ETRI Tier 1 quirk (HTTP 200 + status:"error") 흡수.
        """
        url = _join_url(self.service_url, self._endpoint("run"))
        envelope = {
            "workspace_id": "0",
            "project_id": "bff-inference",
            "params": params or {},
        }
        resp = await self.client.post(url, json=envelope)
        resp.raise_for_status()
        body = resp.json() if resp.content else {}
        etri_error = self._detect_etri_error(body)
        if etri_error is not None:
            raise _ETRIRequestError(f"{etri_error.code}: {etri_error.message}")
        return body

    async def deploy(self, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """POST /deploy — ETRI eva-vlm-infer 가 새 checkpoint 를 reload.

        Hybrid pair flow: eva-vlm-train → commit_model 생성 → 사용자가
        infer pod 의 /deploy 를 호출하면 partner 가 LoRA adapter + projector
        를 swap. 동기 endpoint — body 는 partner 가 정의 (예: checkpoint
        경로, model_id, 또는 빈 body 로 latest 자동 선택).

        ETRI Tier 1 quirk (HTTP 200 + status:ERROR) 흡수.
        """
        endpoints = self.manifest.spec.endpoints or {}
        path = endpoints.get("deploy")
        if not path:
            raise NotImplementedError(
                f"manifest {self.manifest.metadata.name!r} has no deploy endpoint"
            )
        url = _join_url(self.service_url, path)
        resp = await self.client.post(url, json=dict(payload or {}))
        resp.raise_for_status()
        body = resp.json() if resp.content else {}
        etri_error = self._detect_etri_error(body)
        if etri_error is not None:
            raise _ETRIRequestError(f"{etri_error.code}: {etri_error.message}")
        return body

    async def cancel(self, job_id: str) -> bool:
        """POST /train/stop?job_id={id} — tolerate the same Tier 1 quirk."""
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
        if resp.status_code != 200:
            return False
        body = resp.json() if resp.content else {}
        if self._detect_etri_error(body) is not None:
            # Partner refused — leave the job alive so the timeout path picks
            # it up. Returning True would mislead the caller.
            logger.info(
                "ETRI cancel rejected for %s: %s", job_id, body.get("error_message"),
            )
            return False
        return True

    def _build_result(self, job_id: str, body: dict) -> ExternalJobResult:
        """Normalize ETRI ``/train/status?job_id=X`` body.

        Known ETRI shape::

            {
              "id": "...",
              "status": "RUNNING|FINISHED|ERROR|STOPPED",
              "progress": 0.5 | 50,           # may be 0..1 or 0..100
              "current_step": 1234,
              "total_steps": 5000,
              "metrics": {...},               # FINISHED only
              "error_message": "..."          # ERROR only, HTTP still 200
            }
        """
        status_str = body.get("status") or body.get("state")
        status = _etri_status(status_str)

        progress = _coerce_progress(body.get("progress"))
        # Fallback: derive progress from current_step / total_steps if the
        # partner didn't compute it (ETRI sometimes omits the field early on).
        if progress is None:
            cur = body.get("current_step")
            tot = body.get("total_steps")
            try:
                if cur is not None and tot:
                    progress = max(0.0, min(1.0, float(cur) / float(tot)))
            except (TypeError, ValueError, ZeroDivisionError):
                progress = None

        # ETRI surfaces successful payload via "metrics"/"result"/"output"
        # depending on the route. Take the first dict we find, then merge in
        # the top-level ETRI scalars (current_step, total_steps, current_loss,
        # elapsed_sec, phase) so domain BFFs (apps/llm_model) can compute
        # progress / remaining_time without re-calling the partner pod.
        result_payload: Optional[dict[str, Any]] = None
        for key in ("result", "metrics", "output"):
            val = body.get(key)
            if isinstance(val, dict):
                result_payload = dict(val)
                break

        # wandb_url/wandb_run_url/tracking_url: reserved experiment-tracking run
        # URL keys. ETRI surfaces these at the top level (like the scalars), so
        # merge them into result_payload — the BFF (_extract_tracking_url) then
        # validates + forwards to the FE as a W&B link.
        etri_scalars = {
            k: body.get(k)
            for k in ("current_step", "total_steps", "current_loss",
                      "elapsed_sec", "phase", "output_dir",
                      "wandb_url", "wandb_run_url", "tracking_url")
            if body.get(k) is not None
        }
        if etri_scalars:
            if result_payload is None:
                result_payload = etri_scalars
            else:
                result_payload = {**result_payload, **etri_scalars}

        error = _normalize_etri_error(body, status)

        return ExternalJobResult(
            job_id=job_id,
            status=status,
            progress=progress,
            result=result_payload,
            error=error,
        )


# ── ETRI status normalization ────────────────────────────────────────────


def _etri_status(raw: Any) -> ExternalContainerStatus:
    """ETRI status strings → canonical enum.

    Falls through to the generic alias table for anything not explicitly
    mapped here. We keep the explicit table for ETRI-specific values so a
    future schema change is loud (mismatch surfaces as PENDING here, not as
    a silent RUNNING from the generic fallback).
    """
    if not isinstance(raw, str):
        return ExternalContainerStatus.RUNNING
    key = raw.strip().lower()
    table = {
        "running": ExternalContainerStatus.RUNNING,
        "finished": ExternalContainerStatus.COMPLETED,
        "completed": ExternalContainerStatus.COMPLETED,
        "error": ExternalContainerStatus.FAILED,
        "failed": ExternalContainerStatus.FAILED,
        "stopped": ExternalContainerStatus.CANCELLED,
        "cancelled": ExternalContainerStatus.CANCELLED,
        "queued": ExternalContainerStatus.PENDING,
        "pending": ExternalContainerStatus.PENDING,
    }
    if key in table:
        return table[key]
    return from_partner_string(raw)


def _normalize_etri_error(
    body: dict,
    status: ExternalContainerStatus,
) -> Optional[ExternalJobError]:
    """ETRI surfaces errors via either ``error`` (dict) or ``error_message`` (str).

    When status is FAILED we always synthesize an error envelope so the
    BFF has something to show, even if ETRI omitted both fields.
    """
    err = body.get("error")
    msg = body.get("error_message")
    if isinstance(err, dict):
        return ExternalJobError(
            code=str(err.get("code") or "E_ETRI_ERROR"),
            message=str(err.get("message") or msg or "ETRI partner error"),
            fatal=bool(err.get("fatal", True)),
        )
    if isinstance(err, str) and err:
        return ExternalJobError(code="E_ETRI_ERROR", message=err)
    if msg:
        return ExternalJobError(code="E_ETRI_ERROR", message=str(msg))
    if status is ExternalContainerStatus.FAILED:
        return ExternalJobError(
            code="E_ETRI_UNKNOWN",
            message="ETRI reported FAILED status without an error_message",
        )
    return None
