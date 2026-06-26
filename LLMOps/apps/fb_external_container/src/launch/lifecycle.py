"""External job lifecycle — adapter polling + (optional) DB-backed persistence.

JobTracker owns three things per running job:
1. A JobRecord with the current normalized status.
2. An asyncio polling Task that drives the partner adapter through the
   pod-ready → start_job → poll → terminal sequence.
3. The teardown path (scheduler.uninstall + task cancel) so terminal
   states release K8s resources.

SP-Ext.3: a ``JobStateRepository`` can be wired in via ``__init__`` to
persist active records (insert at start, update on transitions, delete at
terminal). When ``repository`` is None the tracker falls back to in-memory
only (dev / mock mode). The in-memory ``self._jobs`` dict remains the
authoritative runtime view; DB is a write-through mirror for recovery.
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
from exceptions import ValidationError
from manifest.schema import ExternalContainerManifest
from normalize import (
    ExternalContainerStatus,
    ExternalJobConfig,
    ExternalJobError,
    ExternalJobResult,
    is_terminal,
)

from .repository import JobStateRepository, JobStateSnapshot
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
    env_overrides: dict[str, str] | None = None,
    platform_model_id: int | None = None,
    instance_id: int | None = None,
    secrets: dict[str, str] | None = None,
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

    # 경로 안전성(defense-in-depth): base_model.name / built_in_checkpoint.name 은
    # pod.yaml subPath(models/<name>/..., built_in_checkpoint/<name>)로 그대로
    # 들어간다. 직접 API 호출자가 traversal 값을 넣어 다른 워크스페이스 디렉토리를
    # mount 하지 못하게 단일 path 세그먼트만 허용(`/`·`\`·`..`·leading-dot 거부).
    # K8s subPath 도 `..` 를 거부하지만 버전 의존이라 백엔드에서 명시 차단.
    for _rk, _rv in (("_base_model", base_model), ("_built_in_checkpoint", built_in)):
        _nm = str(_rv.get("name", "")) if isinstance(_rv, dict) else ""
        if _nm and (
            "/" in _nm or "\\" in _nm or "\x00" in _nm
            or _nm in (".", "..") or _nm.startswith(".")
        ):
            raise ValidationError(
                f"{_rk}.name must be a single path-safe segment; got {_nm!r}"
            )

    # I6 (SP-3): secrets passthrough. manifest 가 secrets.required 로 선언한 자격증명
    # 이름 × 운영자가 launch 시 넘긴 값을 매핑해 pod env 로 주입한다.
    # required 인데 값이 안 넘어오면 명시적 실패(미입력 컨테이너가 런타임에 알 수 없는
    # 이유로 죽는 것 방지). manifest 가 required:[] 면(현 전 manifest) 변화 없음.
    #
    # SECURITY (SP-3 codex CRITICAL 하드닝 완료): secret 값은 평문 env 로 렌더되지
    # 않는다. fb_scheduler(external_run._ensure_external_secret)가 helm install 전에
    # helm 밖 K8s Secret 을 만들고, pod.yaml 은 valueFrom.secretKeyRef 로 참조한다.
    # → 값이 PodSpec / Helm release manifest·history 에 평문으로 남지 않음(at-rest 차단).
    # 여기서는 required × 운영자 입력 매핑 + 미입력 검증만 한다(값 전달은 그대로).
    secrets_in = secrets or {}
    required_secrets = list(spec.secrets.required or [])
    missing = [name for name in required_secrets if not secrets_in.get(name)]
    if missing:
        # ValidationError(AppError) → 422 + logger.error(no traceback). 누락된
        # secret 이름만 메시지에 들어가고(값 아님) FE 가 user-error 로 구분 가능.
        raise ValidationError(
            f"manifest {manifest.metadata.name!r} requires secrets {missing} "
            "but no value was provided at launch"
        )
    # required 에 선언된 것만 통과(선언 안 된 임의 secret 주입 차단).
    effective_secrets = {
        name: str(secrets_in[name]) for name in required_secrets if name in secrets_in
    }

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
            # fb_monitoring 의 insert_gpu_usage 가 pod_type='fine_tuning'
            # 분기에서 label_model_id 를 access. 없으면 KeyError 로 workspace.
            # SP-Ext.4 M6: platform_model_id 없을 때 ""(빈 문자열) 로 두면
            # fb_dashboard 의 model_pod 루프가 workspace_pods[fine_tuning][""]
            # 단일 키를 동시 train 끼리 덮어써 GPU/리소스 합산 누락. job_id
            # fallback 으로 unique 키 보장 (dashboard 는 이 키로 per-pod 집계만
            # 하고 model 이름 lookup 실패는 graceful skip). 실무상 train 은
            # 항상 platform_model_id 가 있으나 방어적 처리.
            "model_id": str(platform_model_id) if platform_model_id else job_id,
            # SP-Ext.4 Codex #1 fix: external infer pod 이 chart 에서
            # pod_type=deployment 로 매핑되는데 monitoring_service.py:2116
            # 가 workspace_pods[DEPLOYMENT_TYPE][label_deployment_id]
            # [label_deployment_worker_id] indexing → 두 라벨 없으면 KeyError
            # workspace_usage tick 전체 crash. internal deployment_llm 의
            # _label.tpl 의 labels.deployment template 와 동형 (deployment_id +
            # deployment_worker_id 모두 박음). external 은 deployment 개념이
            # 없으니 job_id 와 pod_name 으로 unique key 구성.
            "deployment_id": job_id,
            "deployment_worker_id": pod_name,
            # PROJECT 분기 (line 1720~) 의 label_project_id / project_item_id /
            # work_func_type 도 같은 위험 — external 은 project 분기 안 타니까
            # (chart 가 pod_type 을 deployment/fine_tuning/tool 셋으로만 매핑)
            # 빈 값으로 박을 필요 없음.
            # SP-Ext.4 instance graph fix: frontend FINETUNING_SETTING 모달이
            # 보낸 instance_id 를 label 로 전달 → fb_dashboard 의
            # get_workspace_instance_used 가 instance_status[instance_id]
            # [fine_tuning][model_id] 로 attribute → instance 그래프에 external
            # 학습 표시 (workspace resource bar 와 일치). None 이면 fb_scheduler
            # 가 allocated node 로 fallback 해석 (단일 instance workspace).
            "instance_id": str(instance_id) if instance_id else "",
        },
        "env": dict(spec.env or {}),
        "env_overrides": dict(env_overrides or {}),
        "secrets": effective_secrets,
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
    # codex Med-1: partner /health 가 한 번이라도 200 응답한 적 있는지.
    # poll loop 의 _wait_until_ready 가 True 로 set. 이후 GET /jobs/{id}
    # 가 매 호출마다 비싼 partner /health probe (timeout 300s 가능) 안 함.
    pod_ready: bool = False

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
        repository: Optional[JobStateRepository] = None,
    ) -> None:
        self.scheduler = scheduler
        self.http_client = http_client
        self.poll_interval = poll_interval
        # SP-Ext.3: None 이면 in-memory only (dev / mock). 실 운영은 lifespan
        # 이 aiomysql pool 로 repository 를 만들어 주입.
        self.repository = repository
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
        env_overrides: dict[str, str] | None = None,
        secrets: dict[str, str] | None = None,
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
            env_overrides=env_overrides,
            platform_model_id=platform_model_id,
            instance_id=instance_id,
            secrets=secrets,
        )

        # codex #73-(a): provisional row 먼저 — scheduler.launch 와
        # _repo_insert 사이의 crash 가 helm release 를 orphan 으로 만들지
        # 않도록 순서 뒤집기. crash 가 launch 도 못 부르고 죽으면 row 만
        # 남고 (recovery 가 helm release 없음 → drop) helm 은 만들어진 적
        # 없음. launch 후 crash 면 row + release 둘 다 있음 → recovery 가
        # polling 재개. 두 케이스 모두 일관된 invariant: row 가 있으면
        # release 도 (있어야) 있다 — 또는 곧 cleanup 된다.
        async with self._lock:
            self._jobs[job_id] = record
        await self._repo_insert(record)

        try:
            await self.scheduler.launch(pod_info_dict)
        except SchedulerError as e:
            logger.error("scheduler launch failed for %s: %s", job_id, e)
            record.update_result(
                status=ExternalContainerStatus.FAILED,
                error=ExternalJobError(code="E_SCHEDULER_LAUNCH", message=str(e)),
            )
            # provisional row 정리 — helm release 도 못 만들어졌으니
            # recovery 가 잡을 게 없다. row 만 지움.
            await self._repo_delete(record)
            return job_id

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
        """Cancel every poll task; preserve partner pods + DB rows.

        SP-Ext.3: BFF 의 graceful 종료 (rollout / SIGTERM) 시 in-flight 한
        partner job 의 ``helm release`` 와 ``external_job_state`` row 를
        ``_cleanup`` 하지 않는다. 다음 BFF process 의 ``startup_recovery()``
        가 그 row 로 polling 재개해야 함. ``_cleanup`` 호출은 SP-Ext.3 이전의
        의도된 동작이었지만, recovery 도입 후 정상 종료 시 cleanup 은
        recovery 자체를 무력화한다.

        Hard crash (kill -9, OOM, node 죽음) 의 경우 이 shutdown 가 못
        호출돼도 row 가 남아 자동 recovery 됨 — invariant 동일.
        """
        active = [
            r for r in self._jobs.values()
            if r.poll_task is not None and not r.poll_task.done()
        ]
        if not active:
            return

        for record in active:
            record.poll_task.cancel()

        poll_tasks = [r.poll_task for r in active]
        try:
            await asyncio.wait_for(
                asyncio.gather(*poll_tasks, return_exceptions=True),
                timeout=drain_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "shutdown timed out after %.1fs while cancelling %d poll task(s)",
                drain_seconds, len(active),
            )

        logger.info(
            "shutdown: %d active job(s) preserved for recovery "
            "(helm release + DB row left in place)",
            len(active),
        )

    # ── Polling task ────────────────────────────────────────────────────

    async def _poll_loop(self, job_id: str) -> None:
        record = self._jobs[job_id]
        AdapterCls = get_adapter_class(record.manifest.metadata.name)
        adapter = AdapterCls(record.manifest, record.service_url, self.http_client)
        # SP-Ext.3 (Codex review): startup recovery 후에도 timeout 의미 유지.
        # started_at 으로부터의 elapsed 를 빼서 남은 시간만 새 deadline 으로.
        # 첫 launch 시엔 elapsed ≈ 0 이라 timeout_seconds 와 사실상 동일.
        elapsed = (_utcnow() - record.started_at).total_seconds()
        remaining = max(0.0, record.timeout_seconds - elapsed)
        deadline = time.monotonic() + remaining

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
                record.pod_ready = True
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
        # SP-Ext.3: recovery 후 이미 start_job 통과한 record 면 partner_job_id
        # 가 채워져 있다. 중복 호출은 partner 가 새 job 만들거나 409 반환.
        # 그냥 RUNNING 표시 유지하고 polling 으로 직행.
        if record.partner_job_id:
            record.update_result(status=ExternalContainerStatus.RUNNING)
            logger.info(
                "skipping start_job for %s — partner_job_id already set (%s); "
                "startup recovery path",
                record.job_id, record.partner_job_id,
            )
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
            # SP-Ext.3: partner id 와 status 변경을 persist. _drive_until_terminal
            # 안 매 poll 마다 update 하지는 않음 (DB write 부담) — status 가
            # transition 될 때만 persist 한다.
            await self._repo_update_partner(record)
            await self._repo_update_status(record)
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
        # SP-Ext.4 H4: pod 이 죽었는데(crash/삭제/node 이탈) DB row 만 남은 경우
        # — 특히 startup_recovery 가 K8s 존재 확인 없이 무조건 poll 재개하므로
        # — 기존엔 get_status 실패를 무한 backoff 하며 full timeout(학습은
        # 200000s)까지 bu;방치했다 (DB active / Redis free / K8s 없음 3중 불일치).
        # 연속 실패가 임계치를 넘으면 pod 소실로 간주, 즉시 FAILED + cleanup
        # 하여 orphan helm/GPU/row 를 회수한다. 일시적 blip 은 임계치 미만에서
        # 성공 시 카운터 리셋되어 false-drop 없음.
        consecutive_failures = 0
        max_consecutive_failures = 12  # ~12 * poll_interval 연속 unreachable
        while time.monotonic() < deadline:
            await asyncio.sleep(self.poll_interval)
            try:
                r = await adapter.get_status(record.partner_job_id)
            except Exception:
                consecutive_failures += 1
                logger.warning(
                    "poll failed for %s (%d/%d consecutive); backing off",
                    record.job_id, consecutive_failures, max_consecutive_failures,
                )
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(
                        "job %s unreachable for %d consecutive polls — pod "
                        "presumed gone; marking FAILED + cleanup",
                        record.job_id, consecutive_failures,
                    )
                    await self._cleanup(
                        record,
                        ExternalContainerStatus.FAILED,
                        error=ExternalJobError(
                            code="E_POD_UNREACHABLE",
                            message=(
                                f"partner job {record.partner_job_id} unreachable "
                                f"for {consecutive_failures} consecutive polls"
                            ),
                        ),
                    )
                    return
                await asyncio.sleep(self.poll_interval)
                continue
            consecutive_failures = 0  # 성공 시 리셋 — transient blip false-drop 방지
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
        # SP-Ext.4 M7: job_type 명시 게이트 추가. commit 은 학습 산출물 대상
        # 이므로 train/batch 만 — infer(deployment) 가 우연히 COMPLETED +
        # platform_model_id 를 갖더라도 commit 오발 방지. (현재 infer 는
        # CANCELLED 로만 종료돼 COMPLETED 게이트에 안 걸리지만 방어적 명시.)
        if (
            terminal_status is ExternalContainerStatus.COMPLETED
            and record.manifest.spec.job_type in ("train", "batch")
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

        # SP-Ext.3: terminal 도달 — row 삭제 (active 만 남기는 invariant).
        # uninstall 결과와 무관하게 항상 시도. delete 실패는 log 만, helm
        # release 가 이미 빠진 상태라 orphan row 는 다음 BFF startup 의
        # recovery 에서 "K8s 에 release 없음" 으로 정리되도록 추후 설계.
        await self._repo_delete(record)

    # ── SP-Ext.3 repository helpers (best-effort, never raise) ──────────

    def _db_persist(self, record: JobRecord) -> bool:
        """이 record 를 external_job_state 에 persist 할지 여부.

        SP-Ext.4 C3: sync infer (execution_mode=sync) 는 Kong ingress 로
        노출되는 long-running 서빙 pod 으로, async 학습과 달리 terminal 전이가
        없다. 이전엔 sync 도 _repo_insert 로 'pending' row 를 박았지만
        RUNNING/terminal 전이가 없어 row 가 영구 pending 으로 잔존했고,
        startup_recovery 가 매 BFF restart 마다 그 row 를 부활시켜 무의미한
        polling task 를 누적시켰다 (+ pod 죽어도 orphan helm/GPU).
        sync 는 in-memory 로만 추적한다 — BFF restart 후 추적 상실은 허용
        (infer pod 은 Kong 으로 독립 서빙되며, 중지는 명시 cancel / helm
        uninstall). async (train/batch) 만 persist + recovery 대상.
        """
        if self.repository is None:
            return False
        if record.manifest.spec.execution_mode == "sync":
            return False
        return True

    async def _repo_insert(self, record: JobRecord) -> None:
        if not self._db_persist(record):
            return
        try:
            await self.repository.insert(
                job_id=record.job_id,
                model_id=record.platform_model_id,
                workspace_id=record.workspace_id,
                manifest_name=record.manifest.metadata.name,
                manifest_version=record.manifest.metadata.version,
                manifest_json=record.manifest.model_dump_json(),
                namespace=record.namespace,
                pod_name=record.pod_name,
                helm_release=record.helm_release,
                service_url=record.service_url,
                timeout_seconds=record.timeout_seconds,
                params_json=json.dumps(record.params),
                # ExternalContainerStatus(str, Enum) 의 mix-in str 이 Python
                # 3.11+ 에서 'ExternalContainerStatus.RUNNING' 형식으로 떨어질
                # 위험이 있어 .value 로 명시 (recovery 의 enum 복원 호환).
                status=record.result.status.value,
                started_at=record.started_at,
                effective_gpu=record.effective_gpu,
                output_subdir=record.output_subdir,
            )
        except Exception:
            logger.exception(
                "JobStateRepository.insert failed for %s — in-memory tracking "
                "continues, but BFF restart will not recover this job",
                record.job_id,
            )

    async def _repo_update_status(self, record: JobRecord) -> None:
        if not self._db_persist(record):
            return
        try:
            await self.repository.update_status(
                record.job_id, record.result.status.value,
            )
        except Exception:
            logger.exception(
                "JobStateRepository.update_status failed for %s",
                record.job_id,
            )

    async def _repo_update_partner(self, record: JobRecord) -> None:
        if not self._db_persist(record) or not record.partner_job_id:
            return
        try:
            await self.repository.update_partner_job_id(
                record.job_id, record.partner_job_id,
            )
        except Exception:
            logger.exception(
                "JobStateRepository.update_partner_job_id failed for %s",
                record.job_id,
            )

    async def _repo_delete(self, record: JobRecord) -> None:
        if not self._db_persist(record):
            return
        try:
            await self.repository.delete(record.job_id)
        except Exception:
            logger.exception(
                "JobStateRepository.delete failed for %s — orphan row may "
                "remain; next BFF startup should clean it up",
                record.job_id,
            )

    # ── SP-Ext.3 startup recovery ───────────────────────────────────────

    async def startup_recovery(self) -> int:
        """Reattach polling tasks to in-flight partner jobs after BFF restart.

        Lifespan 의 startup 단계에서 1회 호출. repository 가 가진 모든 active
        snapshot 을 JobRecord 로 재구성해 ``self._jobs`` 에 등록하고
        ``_poll_loop`` 를 재시작한다.

        Returns 복원된 job 수. repository 가 None 이거나 list_active 실패 시 0.

        Idempotent: 이미 ``self._jobs`` 에 있는 job_id 는 skip. 같은 BFF
        프로세스 안에서 두 번 호출되더라도 중복 polling task 안 만듦.
        """
        if self.repository is None:
            return 0
        try:
            snapshots = await self.repository.list_active()
        except Exception:
            logger.exception(
                "JobStateRepository.list_active failed — startup recovery skipped"
            )
            return 0
        if not snapshots:
            logger.info("startup recovery: no active jobs to restore")
            return 0

        logger.info(
            "startup recovery: attempting to restore %d active job(s)",
            len(snapshots),
        )
        recovered = 0
        for snap in snapshots:
            try:
                record = self._snapshot_to_record(snap)
            except Exception:
                logger.exception(
                    "snapshot → JobRecord reconstruction failed for job %s "
                    "(manifest_version=%s); leaving DB row in place for "
                    "operator inspection",
                    snap.job_id, snap.manifest_version,
                )
                continue
            async with self._lock:
                if snap.job_id in self._jobs:
                    logger.debug(
                        "skipping recovery of %s — already in self._jobs",
                        snap.job_id,
                    )
                    continue
                self._jobs[snap.job_id] = record
            record.poll_task = asyncio.create_task(self._poll_loop(snap.job_id))
            recovered += 1
            logger.info(
                "recovered job %s (partner=%s, prev_status=%s, helm=%s)",
                snap.job_id, snap.partner_job_id, snap.status, snap.helm_release,
            )
        logger.info(
            "startup recovery: %d/%d job(s) restored",
            recovered, len(snapshots),
        )
        return recovered

    def _snapshot_to_record(self, snap: JobStateSnapshot) -> JobRecord:
        """Rebuild JobRecord from a persisted snapshot.

        Pydantic manifest 는 ``model_validate`` 로 재구성. status string 은
        enum 으로 복원. started_at 은 MariaDB naive UTC datetime 이라 UTC
        tz-aware 로 정정 (lifecycle 내부 _utcnow() 와 비교 가능하게).
        """
        manifest = ExternalContainerManifest.model_validate(snap.manifest_dict)

        try:
            status = ExternalContainerStatus(snap.status)
        except ValueError:
            logger.warning(
                "unknown status %r for recovered job %s; falling back to PENDING",
                snap.status, snap.job_id,
            )
            status = ExternalContainerStatus.PENDING

        started_at = snap.started_at
        if started_at is not None and started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)

        record = JobRecord(
            job_id=snap.job_id,
            manifest=manifest,
            workspace_id=snap.workspace_id,
            namespace=snap.namespace,
            pod_name=snap.pod_name,
            helm_release=snap.helm_release,
            service_url=snap.service_url,
            timeout_seconds=snap.timeout_seconds,
            params=snap.params_dict,
            started_at=started_at if started_at is not None else _utcnow(),
            partner_job_id=snap.partner_job_id,
            platform_model_id=snap.model_id,
            output_subdir=snap.output_subdir,
            effective_gpu=snap.effective_gpu or 0,
        )
        record.result = ExternalJobResult(job_id=snap.job_id, status=status)
        return record

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
