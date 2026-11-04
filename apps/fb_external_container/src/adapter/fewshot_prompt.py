"""Adapter for ETRI fewshot-prompt-optimizer.

The container follows SP-1 v2 §5 except for **one** deviation the platform must
absorb: ``POST /run`` nests the job id inside a Tango MSA success envelope
instead of returning it at the top level.

    {"status": "success", "result": {"job_id": "job-…", "job_status": "pending"}}

``GenericHTTPAdapter._extract_partner_job_id`` only reads ``body["job_id"]`` and
falls back to the *platform* job id — which would make us poll an id the container
never issued: a permanent failure with no error surfaced anywhere. Overriding that
single hook is the whole adapter.

Everything else already lines up and needs no code here:
  * ``GET /status?job_id=`` — declared as ``endpoints.jobs: "/status?job_id={id}"``
    in the manifest; ``_substitute_job_id`` handles the ``{id}`` template
    (contract §5.4 permits partner-specific URL conventions).
  * ``progress`` 0..100 — ``_coerce_progress`` accepts 0..1 or 0..100.
  * ``status: "pending"`` — already in the canonical enum.
  * ``/status`` body puts ``status``/``progress``/``result`` at the top level, so
    ``_build_result`` maps it as-is.
  * ``/run`` answers HTTP 200 (spec suggests 202) — ``raise_for_status`` passes.

No ``/cancel`` endpoint exists, so ``cancel()`` is the inherited logged no-op;
surface "cancel unsupported" in the UI rather than pretending it worked.
"""

from __future__ import annotations

import logging

from normalize import ExternalJobError, ExternalJobResult

from .base import GenericHTTPAdapter

logger = logging.getLogger(__name__)

# Failure messages can carry a full optimizer exception line; keep them bounded
# so a partner cannot blow up the job record.
_MAX_ERROR_MESSAGE = 2000


class FewshotPromptAdapter(GenericHTTPAdapter):
    """fewshot-prompt-optimizer — unwraps the ``/run`` success envelope and the
    non-standard failure shape."""

    def _extract_partner_job_id(self, body: dict, platform_job_id: str) -> str:
        result = body.get("result")
        if isinstance(result, dict) and result.get("job_id"):
            return str(result["job_id"])
        # Top-level job_id (spec shape) or platform-id fallback.
        logger.debug(
            "fewshot-prompt-optimizer /run response had no result.job_id; "
            "falling back to generic extraction (keys=%s)", list(body)
        )
        return super()._extract_partner_job_id(body, platform_job_id)

    def _build_result(self, job_id: str, body: dict) -> ExternalJobResult:
        """Map the container's failure shape onto the platform error object.

        On failure the container does NOT emit SP-1 v2 §5.4's ``error`` object —
        it puts ``code``/``message`` at the top level instead::

            {"job_id": "...", "status": "failed", "progress": 15,
             "code": "INTERNAL_ERROR", "message": "TypeError: ..."}

        ``GenericHTTPAdapter._build_result`` only reads ``body["error"]``, so the
        reason was dropped entirely and the job surfaced as ``status=FAILED,
        error=null`` — with no traceback in the container log either, because its
        JobStore catches the exception into ``error_message`` instead of raising
        (jobs.py). That combination makes every optimizer failure undiagnosable,
        so translate it here.
        """
        result = super()._build_result(job_id, body)
        if result.error is not None:
            return result
        message = body.get("message")
        code = body.get("code")
        if not message and not code:
            return result
        return result.model_copy(
            update={
                "error": ExternalJobError(
                    code=str(code or "E_PARTNER_ERROR"),
                    message=str(
                        message or "partner reported failure without a message"
                    )[:_MAX_ERROR_MESSAGE],
                )
            }
        )
