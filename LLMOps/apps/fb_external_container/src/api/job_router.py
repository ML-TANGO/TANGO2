"""Job lifecycle endpoints — backed by launch.JobTracker (SP-Ext.8).

The dto shapes here are the contract for domain BFFs (SP-Ext.9). The
in-memory JobTracker behind these endpoints is replaced by a DB-backed
implementation in SP-Ext.3 without changing the request/response shapes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from datetime import datetime
from typing import Optional

from exceptions import NotFoundError
from launch import JobTracker
from manifest import ManifestRegistry
from normalize import ExternalJobResult

router = APIRouter()


class ExternalJobDetail(BaseModel):
    """Full job snapshot for the domain BFF.

    The domain BFF (e.g. apps/llm_model) needs more than the partner-agnostic
    `ExternalJobResult` carries — manifest metadata, partner job id, timing,
    helm release, raw params — so it can derive percent / remaining_time /
    `fine_tuning_status` payloads that match the platform's internal LLM
    fine-tuning SSE schema.
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    job_id: str
    manifest_name: str
    manifest_version: str
    workspace_id: int
    namespace: str
    helm_release: str
    pod_name: str
    service_url: str
    partner_job_id: Optional[str] = None
    started_at: datetime
    timeout_seconds: int
    params: dict
    result: ExternalJobResult
    # platform-side metadata — auto commit hook + sse-graph NFS path 추론용
    platform_model_id: Optional[int] = None
    output_subdir: Optional[str] = None
    # Partner pod readiness — partner /health 200 OK 면 True. infer pod model
    # load 가 끝나 추론 가능한지 도메인 BFF (llm_playground) 가 Test 버튼 활성화
    # 게이트로 사용. health 호출 실패 시 False (보수적 — 504 차단 우선).
    pod_ready: bool = False


# ── Request / response models ────────────────────────────────────────────


class StartJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    manifest_name: str = Field(min_length=1)
    manifest_version: str = Field(min_length=1)
    workspace_id: int = Field(ge=1)
    # Defaults to the platform namespace; callers running multi-namespace
    # workloads override this per request.
    namespace: str = Field(default="jonathan-system", min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    # Optional resource override — frontend FINETUNING_SETTING 모달이 보낸
    # instance/gpu 선택값. None 이면 manifest.spec.resources default 가 그대로
    # helm install 에 쓰인다.
    instance_id: Optional[int] = None
    instance_count: Optional[int] = None
    gpu_count: Optional[int] = None
    # Auto commit hook target — terminal=COMPLETED 시 BFF 가 받아서 commit_model
    # row 생성. None 이면 hook skip (수동 호출만 가능).
    # output_subdir 는 partner 가 결과를 쓰는 /output/<여기>/ 폴더 이름.
    platform_model_id: Optional[int] = None
    output_subdir: Optional[str] = None
    # manifest spec.env 의 dynamic override — playground infer 의 dynamic
    # EVA_CHECKPOINT_PATH (model.latest_commit) 같이 launch 시점에만 결정되는 값.
    # helm chart pod.yaml 이 spec.env + env_overrides 를 merge 해서 pod 에 주입.
    env_overrides: Optional[dict[str, str]] = None


class StartJobResponse(BaseModel):
    job_id: str
    helm_release: str


class CancelResponse(BaseModel):
    job_id: str
    cancelled: bool


# ── Dependencies ─────────────────────────────────────────────────────────


def get_tracker(request: Request) -> JobTracker:
    tracker = getattr(request.app.state, "job_tracker", None)
    if tracker is None:
        raise HTTPException(status_code=503, detail="job tracker not initialised")
    return tracker


def get_registry(request: Request) -> ManifestRegistry:
    registry = getattr(request.app.state, "registry", None)
    if registry is None:
        raise HTTPException(status_code=503, detail="manifest registry not initialised")
    return registry


# ── Routes ───────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=StartJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_job(
    req: StartJobRequest,
    tracker: JobTracker = Depends(get_tracker),
    registry: ManifestRegistry = Depends(get_registry),
) -> StartJobResponse:
    """Launch an external container workload."""
    manifest = await registry.get(req.manifest_name, req.manifest_version)
    if manifest is None:
        raise NotFoundError(
            f"manifest {req.manifest_name}@{req.manifest_version} is not registered; "
            "POST /api/v1/manifests first"
        )
    job_id = await tracker.start(
        manifest,
        req.workspace_id,
        req.params,
        req.namespace,
        instance_id=req.instance_id,
        instance_count=req.instance_count,
        gpu_count=req.gpu_count,
        platform_model_id=req.platform_model_id,
        output_subdir=req.output_subdir,
        env_overrides=req.env_overrides,
    )
    record = tracker.get(job_id)
    return StartJobResponse(
        job_id=job_id,
        helm_release=record.helm_release if record else "",
    )


@router.get(
    "/{job_id}",
    response_model=ExternalJobDetail,
)
async def get_job_status(
    job_id: str,
    tracker: JobTracker = Depends(get_tracker),
) -> ExternalJobDetail:
    """Return a full job snapshot — manifest metadata + current result.

    Domain BFFs use this to derive their own status / progress / log
    payloads in the format their frontend already speaks (e.g. the
    `fine_tuning_status` shape used by apps/llm_model's existing SSE).
    """
    record = tracker.get(job_id)
    if record is None:
        raise NotFoundError(f"job {job_id} not found")
    # codex Med-1: 매 호출마다 partner /health probe 하면 partner_http 의
    # 300s timeout 때문에 느린/멈춘 partner 가 status 호출 자체를 stall 시킨다
    # (playground 의 5s timeout → "installing" 표시). poll loop 이 이미
    # readiness 를 record.pod_ready 로 추적 중이라 그대로 사용.
    pod_ready = record.pod_ready
    return ExternalJobDetail(
        job_id=record.job_id,
        manifest_name=record.manifest.metadata.name,
        manifest_version=record.manifest.metadata.version,
        workspace_id=record.workspace_id,
        namespace=record.namespace,
        helm_release=record.helm_release,
        pod_name=record.pod_name,
        service_url=record.service_url,
        partner_job_id=record.partner_job_id,
        started_at=record.started_at,
        timeout_seconds=record.timeout_seconds,
        params=record.params,
        result=record.result,
        platform_model_id=record.platform_model_id,
        output_subdir=record.output_subdir,
        pod_ready=pod_ready,
    )


class RunInferenceRequest(BaseModel):
    """Sync infer call on a running pod — params는 partner-specific schema."""
    model_config = ConfigDict(extra="forbid", protected_namespaces=())
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/{job_id}/run", status_code=status.HTTP_200_OK)
async def run_inference(
    job_id: str,
    req: RunInferenceRequest,
    tracker: JobTracker = Depends(get_tracker),
) -> dict[str, Any]:
    """Proxy a sync inference call to a running infer pod.

    long-running sync infer pod 가 한 번 startup load 한 모델로 매번 즉시
    응답. /deploy 와 별도 endpoint — checkpoint swap 안 일어남.
    """
    from adapter import get_adapter_class

    record = tracker.get(job_id)
    if record is None:
        raise NotFoundError(f"job {job_id} not found")
    if record.manifest.spec.execution_mode != "sync":
        raise HTTPException(
            status_code=400,
            detail=f"job {job_id} execution_mode={record.manifest.spec.execution_mode} (sync only)",
        )
    AdapterCls = get_adapter_class(record.manifest.metadata.name)
    adapter = AdapterCls(record.manifest, record.service_url, tracker.http_client)
    try:
        body = await adapter.run_sync(req.params)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"partner /run call failed: {e}")
    return body if isinstance(body, dict) else {"raw": body}


@router.post(
    "/{job_id}/cancel",
    response_model=CancelResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def cancel_job(
    job_id: str,
    tracker: JobTracker = Depends(get_tracker),
) -> CancelResponse:
    """Request cancellation. Final state appears via /jobs/{id}."""
    ok = await tracker.cancel(job_id)
    if not ok:
        raise NotFoundError(f"job {job_id} not found")
    return CancelResponse(job_id=job_id, cancelled=True)


# ── Deploy (hybrid pair — train → infer reload) ──────────────────────────


class DeployRequest(BaseModel):
    """Hybrid pair 의 infer manifest 에 /deploy 호출 (e.g. eva-vlm-train 학습
    완료 → eva-vlm-infer pod 가 새 checkpoint reload).

    target manifest 의 long-running infer pod 을 식별하기 위해
    manifest_name + manifest_version + workspace_id + namespace 를 받음.
    JobTracker 의 job_id 와 분리 — infer pod 은 사용자가 별도 launch 한
    long-running 인스턴스.
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    manifest_name: str = Field(min_length=1)
    manifest_version: str = Field(min_length=1)
    workspace_id: int = Field(ge=1)
    namespace: str = Field(default="jonathan-system", min_length=1)
    # infer pod 의 job_id (lifecycle.JobRecord 의 platform job_id). 없으면
    # tracker 에서 service_family 기준으로 paired infer job 자동 매칭 시도.
    infer_job_id: Optional[str] = None
    # partner /deploy body — checkpoint path / commit name 등 partner-specific.
    payload: dict[str, Any] = Field(default_factory=dict)


class DeployResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())
    manifest_name: str
    manifest_version: str
    infer_job_id: Optional[str]
    service_url: Optional[str]
    response: dict[str, Any]


@router.post(
    "/deploy",
    response_model=DeployResponse,
    status_code=status.HTTP_200_OK,
)
async def deploy_external(
    req: DeployRequest,
    tracker: JobTracker = Depends(get_tracker),
    registry: ManifestRegistry = Depends(get_registry),
) -> DeployResponse:
    """Hybrid pair deploy — target infer pod 의 /deploy 호출."""
    from adapter import get_adapter_class  # local import — 순환 방지

    manifest = await registry.get(req.manifest_name, req.manifest_version)
    if manifest is None:
        raise NotFoundError(
            f"manifest {req.manifest_name}@{req.manifest_version} not registered"
        )

    # service URL 결정: 사용자가 infer_job_id 줬으면 tracker 에서 그 record 의
    # service_url 사용. 아니면 paired infer job 자동 매칭. 둘 다 없으면 error
    # (infer pod 안 떠있음).
    infer_record = None
    if req.infer_job_id:
        infer_record = tracker.get(req.infer_job_id)
        if infer_record is None:
            raise NotFoundError(f"infer job {req.infer_job_id} not found")
    else:
        # paired: 같은 service_family + manifest_name 의 가장 최근 running job.
        family = manifest.spec.service_family
        for rec in tracker.all():
            if (
                rec.manifest.metadata.name == req.manifest_name
                and rec.manifest.metadata.version == req.manifest_version
            ):
                infer_record = rec
                break
            if (
                family
                and rec.manifest.spec.service_family == family
                and rec.manifest.spec.job_type == "infer"
            ):
                infer_record = rec
                break
        if infer_record is None:
            raise NotFoundError(
                f"no active infer pod found for {req.manifest_name}@"
                f"{req.manifest_version} (service_family={family})"
            )

    AdapterCls = get_adapter_class(manifest.metadata.name)
    adapter = AdapterCls(manifest, infer_record.service_url, tracker.http_client)
    try:
        body = await adapter.deploy(req.payload)
    except NotImplementedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"partner /deploy call failed: {e}",
        )
    return DeployResponse(
        manifest_name=manifest.metadata.name,
        manifest_version=manifest.metadata.version,
        infer_job_id=infer_record.job_id,
        service_url=infer_record.service_url,
        response=body if isinstance(body, dict) else {"raw": body},
    )
