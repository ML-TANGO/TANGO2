"""External job lifecycle — in-memory tracking + adapter polling.

JobTracker owns three things per running job:
1. A JobRecord with the current normalized status.
2. An asyncio polling Task that drives the partner adapter through the
   pod-ready → start_job → poll → terminal sequence.
3. The teardown path (scheduler.uninstall + task cancel) so terminal
   states release K8s resources.

State is in-memory only — SP-Ext.3 replaces ``self._jobs`` with a
DB-backed table without changing this interface.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from adapter import get_adapter_class
from manifest.schema import ExternalContainerManifest
from normalize import (
    ExternalContainerStatus,
    ExternalJobConfig,
    ExternalJobError,
    ExternalJobResult,
    is_terminal,
)

from .trigger import SchedulerClient, SchedulerError

logger = logging.getLogger(__name__)


# ── Naming helpers ────────────────────────────────────────────────────────

# Helm release / pod / service URLs follow the chart's convention. K8s caps
# release names at 53 chars; manifest names are DNS-1123 and at most 63
# chars (schema enforces), so we slice the job_id to keep the suffix short.

_JOB_ID_SLICE = 8


def _build_helm_release(manifest_name: str, job_id: str) -> str:
    return f"ext-{manifest_name}-{job_id[:_JOB_ID_SLICE]}"


def _build_pod_name(manifest_name: str, job_id: str) -> str:
    return f"{_build_helm_release(manifest_name, job_id)}-0"


def _build_service_url(pod_name: str, namespace: str, port: int) -> str:
    """In-cluster ClusterIP DNS — matches chart templates/service.yaml.

    Chart 의 service 가 ``port: 80 → targetPort: spec.port`` 패턴이라
    (platform convention: 모든 jfb svc 가 :80 으로 통일) host:port 는 항상
    ``svc-name:80`` 이다. ``port`` 인자는 호환 위해 남기되 무시한다.
    """
    return f"http://{pod_name}-svc.{namespace}.svc.cluster.local:80"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── ExternalPodInfo dict builder ──────────────────────────────────────────

# Reserved keys lifted out of `params` into the chart's `inputs.*` slots.
# Anything else stays inside `params_json` and lands at /input/params.json.
_RESERVED_DATASET_KEY = "_dataset"          # {"name": str, "access": str}
_RESERVED_BASE_MODEL_KEY = "_base_model"    # {"name": str}
_RESERVED_BUILTIN_KEY = "_built_in_checkpoint"  # {"name": str}


def _pop_reserved(params: dict[str, Any], key: str) -> dict[str, Any]:
    val = params.pop(key, None)
    if isinstance(val, dict):
        return val
    return {}


_PLATFORM_DEFAULT_NAMESPACE = "jonathan-system"


def _resolve_namespace(
    spec_workspace_scope: str,
    namespace: str,
    workspace_id: int,
) -> str:
    """Workspace 격리 namespace 자동 결정.

    Platform convention: ``workspace_scope='per-workspace'`` 인 manifest 는
    ``jonathan-system-{workspace_id}`` namespace 안에서 실행되고, 그 namespace
    의 PVC (``jonathan-system-{workspace_id}-{main,data}-pvc``) 를 mount 한다.
    helm pod.yaml 의 ``claimName: {{ .Values.namespace }}-{main,data}-pvc``
    가 이 patterns 에 그대로 매핑된다.

    Frontend 가 default 'jonathan-system' 을 보내면 backend 가 workspace
    격리 namespace 로 교체. 사용자가 명시적으로 다른 namespace (예: admin
    cross-workspace) 를 보내면 그대로 사용.
    """
    if spec_workspace_scope != "per-workspace":
        return namespace
    if namespace == _PLATFORM_DEFAULT_NAMESPACE or not namespace:
        return f"{_PLATFORM_DEFAULT_NAMESPACE}-{workspace_id}"
    return namespace


def _build_pod_info_dict(
    manifest: ExternalContainerManifest,
    workspace_id: int,
    job_id: str,
    raw_params: dict[str, Any],
    namespace: str,
    gpu_count_override: int | None = None,
) -> dict[str, Any]:
    """Build the JSON body that fb_scheduler's /external/launch expects.

    Shape matches apps/fb_scheduler/src/scheduler/dto.py:ExternalPodInfo.

    ``gpu_count_override`` (frontend 의 FINETUNING_SETTING 모달이 보낸 값)
    이 주어지면 manifest.spec.resources.gpu 대신 사용된다. None 이면 manifest
    default 가 그대로 helm install 의 resources.limits."nvidia.com/gpu" 로 쓰임.
    """
    spec = manifest.spec
    pod_name = _build_pod_name(manifest.metadata.name, job_id)
    helm_release = _build_helm_release(manifest.metadata.name, job_id)
    # caller (JobTracker.start) 가 이미 _resolve_namespace 적용한 effective
    # namespace 를 넘기지만, 재진입/테스트 위해 안전한 idempotent 호출.
    effective_namespace = _resolve_namespace(
        spec.workspace_scope, namespace, workspace_id
    )

    # Mutate a copy so caller's params dict is untouched downstream.
    params = dict(raw_params)
    dataset = _pop_reserved(params, _RESERVED_DATASET_KEY)
    base_model = _pop_reserved(params, _RESERVED_BASE_MODEL_KEY)
    built_in = _pop_reserved(params, _RESERVED_BUILTIN_KEY)

    effective_gpu = (
        gpu_count_override
        if gpu_count_override is not None
        else spec.resources.gpu
    )

    return {
        "namespace": effective_namespace,
        "pod_name": pod_name,
        "helm_release": helm_release,
        "manifest": {
            "name": manifest.metadata.name,
            "version": manifest.metadata.version,
            "provider": manifest.metadata.provider or manifest.metadata.vendor,
            "service_family": spec.service_family or "",
            "contract_version": spec.contract_version or "",
        },
        "image": spec.image,
        "image_digest": spec.image_digest or "",
        "job_type": spec.job_type,
        "execution_mode": spec.execution_mode,
        "port": spec.port,
        "workspace_scope": spec.workspace_scope,
        "resources": {
            "cpu": spec.resources.cpu,
            "memory": spec.resources.memory,
            "gpu": effective_gpu,
            "gpu_memory": spec.resources.gpu_memory or "",
        },
        "inputs": {
            "dataset": {
                "name": str(dataset.get("name", "")),
                "access": str(dataset.get("access", "")),
            },
            "base_model": {"name": str(base_model.get("name", ""))},
            "built_in_checkpoint": {"name": str(built_in.get("name", ""))},
            "params_json": json.dumps(params),
        },
        "endpoints": dict(spec.endpoints or {}),
        "capabilities": {
            "estimated_startup_seconds": spec.capabilities.estimated_startup_seconds or 300,
            "estimated_duration_seconds": spec.capabilities.estimated_duration_seconds or 0,
            "timeout_seconds": spec.capabilities.timeout_seconds or 0,
        },
        # securityContext / ingress / labels / env / secrets / jf_env defer
        # to chart defaults; SP-Ext.3 fills partner-defined env/secrets from
        # the persisted manifest. Ingress is enabled for sync (user-facing).
        "ingress": {"enabled": spec.execution_mode == "sync"},
        "labels": {
            "workspace_id": str(workspace_id),
            "job_id": job_id,
        },
        "env": dict(spec.env or {}),
        "secrets": {},
        "jf_env": {
            "JF_ITEM_ID": job_id,
            "JF_HOST": f"workspace-{workspace_id}",
            "JF_POD_NAME": pod_name,
            "JF_JOB_TYPE": spec.job_type,
            "JF_EXECUTION_MODE": spec.execution_mode,
            "JF_PORT": str(spec.port),
            "JF_DATASET_NAME": str(dataset.get("name", "")),
            "JF_MODEL_NAME": str(base_model.get("name", "")),
            "JF_TOTAL_GPU": effective_gpu,
        },
    }


# ── Records ───────────────────────────────────────────────────────────────


@dataclass
class JobRecord:
    job_id: str
    manifest: ExternalContainerManifest
    workspace_id: int
    namespace: str
    pod_name: str
    helm_release: str
    service_url: str
    timeout_seconds: int
    params: dict[str, Any]
    started_at: datetime = field(default_factory=_utcnow)
    partner_job_id: Optional[str] = None
    result: ExternalJobResult = field(
        default_factory=lambda: ExternalJobResult(
            job_id="_pending_",
            status=ExternalContainerStatus.PENDING,
        )
    )
    poll_task: Optional[asyncio.Task] = None
    # Auto commit hook payload — caller (BFF) supplied. None 이면 hook skip.
    platform_model_id: Optional[int] = None
    output_subdir: Optional[str] = None
    # Idempotent guard — _cleanup 이 여러 분기에서 호출되니까 1회만 발사.
    auto_commit_fired: bool = False
    # GPU 수 (auto commit metadata 용; manifest default 또는 override).
    effective_gpu: int = 0

    def update_result(self, **fields: Any) -> None:
        # Pydantic models are immutable by convention; replace, don't mutate.
        self.result = self.result.model_copy(update={**fields, "updated_at": _utcnow()})


# ── Tracker ───────────────────────────────────────────────────────────────


class JobTracker:
    """In-memory job state + supervisor for polling tasks."""

    def __init__(
        self,
        scheduler: SchedulerClient,
        http_client: httpx.AsyncClient,
        poll_interval: float = 5.0,
    ) -> None:
        self.scheduler = scheduler
        self.http_client = http_client
        self.poll_interval = poll_interval
        self._jobs: dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()

    # ── Public API ──────────────────────────────────────────────────────

    def get(self, job_id: str) -> Optional[JobRecord]:
        return self._jobs.get(job_id)

    def all(self) -> list[JobRecord]:
        return list(self._jobs.values())

    async def start(
        self,
        manifest: ExternalContainerManifest,
        workspace_id: int,
        params: dict[str, Any],
        namespace: str,
        instance_id: int | None = None,
        instance_count: int | None = None,
        gpu_count: int | None = None,
        platform_model_id: int | None = None,
        output_subdir: str | None = None,
    ) -> str:
        """Launch an external container and start the polling task.

        Returns the platform job_id immediately (the partner job id, if any,
        is discovered later in the polling loop's start_job phase).

        ``instance_id`` / ``instance_count`` / ``gpu_count`` 는 frontend 의
        FINETUNING_SETTING 모달이 보낸 자원 선택값. ``gpu_count`` 만 현재
        helm resources override 에 쓰이고, instance_id/count 는 SP-Ext.7+
        (instance 스케줄링) 도입 전까지는 기록용으로 record.params 에 남는다.
        """
        job_id = uuid.uuid4().hex
        # workspace_scope 가 per-workspace 면 platform convention 에 따라
        # `jonathan-system-{workspace_id}` namespace 안에서 실행 (PVC 매핑이
        # 그 namespace 에 맞춰져 있다). record / service_url / pod_info dict
        # 모두 같은 effective_namespace 를 보아야 모니터링/uninstall 일관성.
        effective_namespace = _resolve_namespace(
            manifest.spec.workspace_scope, namespace, workspace_id
        )
        pod_name = _build_pod_name(manifest.metadata.name, job_id)
        helm_release = _build_helm_release(manifest.metadata.name, job_id)
        service_url = _build_service_url(pod_name, effective_namespace, manifest.spec.port)
        timeout_seconds = _resolve_timeout(manifest)

        effective_gpu = (
            gpu_count if gpu_count is not None else manifest.spec.resources.gpu
        )
        record = JobRecord(
            job_id=job_id,
            manifest=manifest,
            workspace_id=workspace_id,
            namespace=effective_namespace,
            pod_name=pod_name,
            helm_release=helm_release,
            service_url=service_url,
            timeout_seconds=timeout_seconds,
            params=dict(params),
            platform_model_id=platform_model_id,
            output_subdir=output_subdir,
            effective_gpu=effective_gpu,
        )
        record.result = ExternalJobResult(
            job_id=job_id,
            status=ExternalContainerStatus.PENDING,
        )

        pod_info_dict = _build_pod_info_dict(
            manifest, workspace_id, job_id, params, namespace,
            gpu_count_override=gpu_count,
        )

        try:
            await self.scheduler.launch(pod_info_dict)
        except SchedulerError as e:
            logger.error("scheduler launch failed for %s: %s", job_id, e)
            record.update_result(
                status=ExternalContainerStatus.FAILED,
                error=ExternalJobError(code="E_SCHEDULER_LAUNCH", message=str(e)),
            )
            async with self._lock:
                self._jobs[job_id] = record
            return job_id

        async with self._lock:
            self._jobs[job_id] = record

        record.poll_task = asyncio.create_task(self._poll_loop(job_id))
        return job_id

    async def cancel(self, job_id: str) -> bool:
        """Request cancellation. Returns False if the job is unknown."""
        record = self._jobs.get(job_id)
        if record is None:
            return False
        if record.poll_task and not record.poll_task.done():
            record.poll_task.cancel()
        # Try partner cancel only if we already have a partner id.
        if record.partner_job_id:
            AdapterCls = get_adapter_class(record.manifest.metadata.name)
            adapter = AdapterCls(record.manifest, record.service_url, self.http_client)
            try:
                await adapter.cancel(record.partner_job_id)
            except Exception:
                logger.exception("partner cancel failed for %s", job_id)
        await self._cleanup(record, ExternalContainerStatus.CANCELLED)
        return True

    async def shutdown(self, drain_seconds: float = 10.0) -> None:
        """Cancel every running poll task and run their cleanup before
        returning to the lifespan's `finally` block.

        SP-Ext review MEDIUM #C4: ``_poll_loop`` only re-raises on
        ``CancelledError`` — it does not run ``_cleanup`` from the cancel
        path. So cancelling poll tasks alone leaves helm releases up. We
        kick off ``_cleanup`` directly here, in parallel to cancelling the
        poll task, then await both. ``_cleanup`` is idempotent
        (``scheduler.uninstall`` treats "release not found" as success), so
        racing with the poll loop's own terminal cleanup is safe.
        """
        active = [
            r for r in self._jobs.values()
            if r.poll_task is not None and not r.poll_task.done()
        ]
        if not active:
            return

        cleanup_tasks = [
            asyncio.create_task(
                self._cleanup(record, ExternalContainerStatus.CANCELLED)
            )
            for record in active
        ]
        for record in active:
            record.poll_task.cancel()

        all_tasks = [r.poll_task for r in active] + cleanup_tasks
        try:
            await asyncio.wait_for(
                asyncio.gather(*all_tasks, return_exceptions=True),
                timeout=drain_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "shutdown timed out after %.1fs while draining %d poll tasks; "
                "some helm releases may need manual cleanup",
                drain_seconds, len(active),
            )

    # ── Polling task ────────────────────────────────────────────────────

    async def _poll_loop(self, job_id: str) -> None:
        record = self._jobs[job_id]
        AdapterCls = get_adapter_class(record.manifest.metadata.name)
        adapter = AdapterCls(record.manifest, record.service_url, self.http_client)
        deadline = time.monotonic() + record.timeout_seconds

        try:
            await self._wait_until_ready(record, adapter, deadline)
            if record.result.status in (
                ExternalContainerStatus.FAILED,
                ExternalContainerStatus.CANCELLED,
            ):
                return

            await self._start_partner_job(record, adapter)
            if record.result.status is ExternalContainerStatus.FAILED:
                return

            await self._drive_until_terminal(record, adapter, deadline)
        except asyncio.CancelledError:
            logger.info("poll loop for %s cancelled", job_id)
            raise
        except Exception:
            logger.exception("poll loop for %s crashed", job_id)
            await self._cleanup(
                record,
                ExternalContainerStatus.FAILED,
                error=ExternalJobError(
                    code="E_POLL_LOOP_CRASH",
                    message="poll loop crashed — see fb_external_container logs",
                ),
            )

    async def _wait_until_ready(
        self,
        record: JobRecord,
        adapter,
        deadline: float,
    ) -> None:
        record.update_result(status=ExternalContainerStatus.PENDING)
        # Skip readiness probing entirely for batch (no HTTP server).
        if record.manifest.spec.execution_mode == "batch":
            return
        while time.monotonic() < deadline:
            await asyncio.sleep(self.poll_interval)
            try:
                healthy = await adapter.health()
            except Exception as e:
                logger.debug("health probe error for %s: %s", record.job_id, e)
                continue
            if healthy:
                logger.info("pod %s is ready", record.job_id)
                return
        # Startup timeout.
        await self._cleanup(
            record,
            ExternalContainerStatus.FAILED,
            error=ExternalJobError(
                code="E_STARTUP_TIMEOUT",
                message=f"pod not ready within {record.timeout_seconds}s",
            ),
        )

    async def _start_partner_job(self, record: JobRecord, adapter) -> None:
        # sync containers serve /run on demand — no separate start_job phase.
        if record.manifest.spec.execution_mode == "sync":
            record.update_result(status=ExternalContainerStatus.RUNNING)
            return
        config = ExternalJobConfig(
            manifest_name=record.manifest.metadata.name,
            manifest_version=record.manifest.metadata.version,
            workspace_id=record.workspace_id,
            job_id=record.job_id,
            params=record.params,
        )
        try:
            partner_id = await adapter.start_job(config)
            record.partner_job_id = partner_id
            record.update_result(status=ExternalContainerStatus.RUNNING)
            logger.info(
                "started partner job %s for platform %s",
                partner_id, record.job_id,
            )
        except Exception as e:
            logger.exception("start_job failed for %s", record.job_id)
            await self._cleanup(
                record,
                ExternalContainerStatus.FAILED,
                error=ExternalJobError(code="E_START_FAILED", message=str(e)),
            )

    async def _drive_until_terminal(
        self,
        record: JobRecord,
        adapter,
        deadline: float,
    ) -> None:
        # sync / batch don't have a /jobs/{id} loop to poll.
        if record.manifest.spec.execution_mode != "async":
            return
        # SP-Ext review MEDIUM #L5: guard against entering the poll loop
        # without a partner job id. _start_partner_job calls _cleanup on
        # failure, but the caller doesn't short-circuit on FAILED status —
        # without this guard we'd pass None into adapter.get_status and
        # blow up on urllib.parse.quote(None).
        if not record.partner_job_id:
            logger.debug(
                "skipping poll loop for %s — no partner_job_id (start_job likely failed)",
                record.job_id,
            )
            return
        while time.monotonic() < deadline:
            await asyncio.sleep(self.poll_interval)
            try:
                r = await adapter.get_status(record.partner_job_id)
            except Exception:
                logger.exception("poll failed for %s; backing off", record.job_id)
                await asyncio.sleep(self.poll_interval)
                continue
            record.result = r
            if is_terminal(r.status):
                logger.info(
                    "job %s reached terminal status %s",
                    record.job_id, r.status,
                )
                await self._cleanup(record, r.status, result_override=r)
                return

        # Runtime timeout — try to cancel the partner job, then mark FAILED.
        logger.warning(
            "job %s exceeded %ds timeout", record.job_id, record.timeout_seconds,
        )
        try:
            await adapter.cancel(record.partner_job_id)
        except Exception:
            logger.exception("timeout cancel failed for %s", record.job_id)
        await self._cleanup(
            record,
            ExternalContainerStatus.FAILED,
            error=ExternalJobError(
                code="E_RUNTIME_TIMEOUT",
                message=f"job exceeded {record.timeout_seconds}s timeout",
            ),
        )

    # ── Cleanup ─────────────────────────────────────────────────────────

    async def _cleanup(
        self,
        record: JobRecord,
        terminal_status: ExternalContainerStatus,
        result_override: Optional[ExternalJobResult] = None,
        error: Optional[ExternalJobError] = None,
    ) -> None:
        """Settle the JobRecord to a terminal state and helm uninstall."""
        if result_override is not None:
            record.result = result_override.model_copy(
                update={"updated_at": _utcnow()}
            )
        else:
            record.update_result(status=terminal_status, error=error)

        # Auto commit hook — terminal=COMPLETED 인데 BFF 가 platform_model_id +
        # output_subdir 를 같이 보냈으면 commit_model row 자동 생성. helm
        # uninstall 보다 *먼저* 시도해야 partner pod NFS 결과물이 아직 살아
        # 있다 (혹시 pod 가 임시 emptyDir 일 때 안전). 단 idempotent —
        # auto_commit_fired guard 로 1회만.
        if (
            terminal_status is ExternalContainerStatus.COMPLETED
            and not record.auto_commit_fired
            and record.platform_model_id
            and record.output_subdir
        ):
            record.auto_commit_fired = True
            try:
                await self._maybe_auto_commit(record)
            except Exception:
                # auto commit 실패가 helm uninstall 막아서 좀비 release 만들면
                # 안 된다. log + 진행. 운영자가 수동 commit 폴백.
                logger.exception(
                    "auto commit hook failed for job %s (model_id=%s); helm "
                    "uninstall 진행",
                    record.job_id, record.platform_model_id,
                )

        try:
            await self.scheduler.uninstall(record.helm_release, record.namespace)
        except SchedulerError as e:
            logger.error(
                "scheduler uninstall failed for %s (%s): %s",
                record.job_id, record.helm_release, e,
            )

    # ── Auto commit hook ────────────────────────────────────────────────

    async def _maybe_auto_commit(self, record: JobRecord) -> None:
        """Call llm_model BFF /api/models/{model_id}/external-commit.

        BFF 가 NFS file move + commit_model row insert + model.latest_commit_id
        update 처리. 우리는 partner metadata 만 합성해서 forward.
        """
        # Lazy import — config 의 settings 사용. circular import 회피.
        from config import get_settings

        settings = get_settings()
        bff_url = settings.llm_model_bff_url.rstrip("/")
        url = f"{bff_url}/api/models/{record.platform_model_id}/external-commit"

        meta = self._build_partner_metadata(record)
        body = {
            "job_id": record.job_id,
            "output_subdir": record.output_subdir,
            "partner_metadata": meta,
            # commit_name / commit_message 는 BFF default 사용.
        }
        logger.info(
            "auto commit hook → POST %s (job=%s, model_id=%s, output_subdir=%s)",
            url, record.job_id, record.platform_model_id, record.output_subdir,
        )
        resp = await self.http_client.post(url, json=body, timeout=60.0)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"BFF external-commit returned {resp.status_code}: {resp.text[:300]}"
            )
        # BFF envelope: 200 OK 라도 body.status != 1 이면 실패.
        try:
            data = resp.json()
        except Exception:
            raise RuntimeError(f"BFF external-commit non-JSON body: {resp.text[:300]}")
        if data.get("status") != 1:
            raise RuntimeError(
                f"BFF external-commit returned status={data.get('status')} "
                f"message={data.get('message')}"
            )
        logger.info(
            "auto commit hook ok — job=%s, model_id=%s, commit=%s",
            record.job_id, record.platform_model_id,
            (data.get("result") or {}).get("commit_name"),
        )

    def _build_partner_metadata(self, record: JobRecord) -> dict[str, Any]:
        """fine_tuning_config JSON column 에 들어갈 enriched metadata.

        manifest 정보 + 사용자 params (reserved key 제외) + 학습 결과
        (current_step, total_steps, elapsed_sec, output_dir) + GPU 등.
        """
        spec = record.manifest.spec
        meta_section = record.manifest.metadata

        # ETRIAdapter._build_result 이 raw partner scalars 를 result.result 에
        # 그대로 merge 하니까 거기서 학습 통계 추출.
        result_inner = {}
        if record.result and record.result.result:
            inner = record.result.result
            if isinstance(inner, dict):
                result_inner = inner

        # params 에서 reserved key (_dataset / _base_model / _built_in_checkpoint)
        # 만 제외하고 나머지는 그대로 보존. (operator 가 어떤 hyperparams 로
        # 학습했는지 commit detail 에서 보고 싶을 거다.)
        params_clean = {
            k: v for k, v in record.params.items()
            if k not in (
                _RESERVED_DATASET_KEY,
                _RESERVED_BASE_MODEL_KEY,
                _RESERVED_BUILTIN_KEY,
            )
        }

        return {
            "manifest_name": meta_section.name,
            "manifest_version": meta_section.version,
            "manifest_provider": meta_section.provider or meta_section.vendor or "",
            "service_family": spec.service_family or "",
            "contract_version": spec.contract_version or "",
            "params": params_clean,
            "result": {
                "partner_job_id": record.partner_job_id,
                "status": str(record.result.status) if record.result else "",
                "current_step": result_inner.get("current_step"),
                "total_steps": result_inner.get("total_steps"),
                "elapsed_sec": result_inner.get("elapsed_sec"),
                "output_dir": result_inner.get("output_dir"),
            },
            "runtime": {
                "started_at": record.started_at.isoformat(),
                "timeout_seconds": record.timeout_seconds,
                "namespace": record.namespace,
                "helm_release": record.helm_release,
                "pod_name": record.pod_name,
                "gpu_count": record.effective_gpu,
            },
        }


def _resolve_timeout(manifest: ExternalContainerManifest) -> int:
    """SP-1 v2 §6: timeout_seconds, fallback to estimated_duration_seconds * 3."""
    caps = manifest.spec.capabilities
    if caps.timeout_seconds:
        return caps.timeout_seconds
    if caps.estimated_duration_seconds:
        return caps.estimated_duration_seconds * 3
    # Last resort — 30 minutes. Inference cold-start aside, no partner job
    # should run unbounded by default.
    return 1800
