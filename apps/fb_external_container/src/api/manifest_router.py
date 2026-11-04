"""Manifest registration endpoints.

SP-Ext.2 ships this as a stub. SP-Ext.3 fills in the DB-backed CRUD —
the request/response shapes here are the contract that SP-Ext.3 must
honour, so it lives in this skeleton rather than waiting.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from manifest import (
    ExternalContainerManifest,
    HybridPairValidationError,
    ManifestRegistry,
    ManifestValidationError,
    RegistryConflictError,
    validate_hybrid_pair,
    validate_manifest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def get_registry(request: Request) -> ManifestRegistry:
    """Active registry implementation (DB or in-memory fallback).

    Exposed as a top-level dependency so test code can ``app.dependency_overrides``
    it the same way ``job_router.get_registry`` is overridden.
    """
    return request.app.state.registry


class ManifestEnvelope(BaseModel):
    """Single manifest registration request body."""

    manifest_yaml: str = Field(min_length=1, description="Raw YAML — apiVersion=tango.acryl.ai/v1")


class HybridPairEnvelope(BaseModel):
    """Pair registration body — both halves at once.

    SP-1 v2 §1.1: paired manifests must agree on service_family,
    contract_version, image identity, and the (infer + workload) shape.
    Registering as a pair lets us enforce that atomically.
    """

    manifests: List[ManifestEnvelope] = Field(min_length=2, max_length=2)


class ManifestStored(BaseModel):
    """Response surface for a registered manifest.

    ``description`` / ``default_params`` / ``is_active`` are surfaced for
    the BFF list/detail endpoints. Manifests have no native ``default_params``
    field today (SP-1 v2 spec): we expose ``{}`` so the frontend can render
    the form pre-fill area without crashing, and partner-shipped defaults
    can be added later without breaking the contract. ``is_active`` is
    ``True`` while the row is in the registry table; deletion = inactive.
    """

    model_config = ConfigDict(protected_namespaces=())

    name: str
    version: str
    job_type: str
    execution_mode: str
    image: str
    service_family: Optional[str] = None
    contract_version: Optional[str] = None
    description: Optional[str] = None
    default_params: Dict[str, Any] = Field(default_factory=dict)
    # 선택 — 다단계 학습 레시피(SP-10). spec.recipe 직렬화(없으면 None).
    recipe: Optional[Dict[str, Any]] = None
    is_active: bool = True


def _parse_and_validate(raw_yaml: str) -> ExternalContainerManifest:
    try:
        manifest = ExternalContainerManifest.model_validate_yaml(raw_yaml)
    except (yaml.YAMLError, ValueError) as e:
        raise HTTPException(status_code=422, detail=f"manifest YAML invalid: {e}") from e
    try:
        validate_manifest(manifest)
    except ManifestValidationError as e:
        raise HTTPException(status_code=422, detail={"errors": e.errors}) from e
    return manifest


def _to_response(manifest: ExternalContainerManifest) -> ManifestStored:
    spec = manifest.spec
    return ManifestStored(
        name=manifest.metadata.name,
        version=manifest.metadata.version,
        job_type=spec.job_type,
        execution_mode=spec.execution_mode,
        image=spec.image,
        service_family=spec.service_family,
        contract_version=spec.contract_version,
        description=manifest.metadata.description,
        default_params={},  # 현재 manifest schema 에 default_params 없음 — TODO partner default 채워지면 spec.inputs.params.default 등에서 추출
        recipe=spec.recipe.model_dump() if spec.recipe else None,
        is_active=True,
    )


@router.post(
    "",
    response_model=ManifestStored,
    status_code=status.HTTP_201_CREATED,
)
async def register_manifest(
    envelope: ManifestEnvelope,
    registry: ManifestRegistry = Depends(get_registry),
) -> ManifestStored:
    """Register a single manifest. Persists to MariaDB if configured."""
    manifest = _parse_and_validate(envelope.manifest_yaml)
    try:
        await registry.add(manifest, envelope.manifest_yaml)
    except RegistryConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return _to_response(manifest)


@router.post(
    "/pair",
    response_model=List[ManifestStored],
    status_code=status.HTTP_201_CREATED,
)
async def register_hybrid_pair(
    envelope: HybridPairEnvelope,
    registry: ManifestRegistry = Depends(get_registry),
) -> List[ManifestStored]:
    """Register two paired manifests atomically with cross-manifest checks."""
    parsed = [_parse_and_validate(item.manifest_yaml) for item in envelope.manifests]
    try:
        validate_hybrid_pair(parsed[0], parsed[1])
    except HybridPairValidationError as e:
        raise HTTPException(status_code=422, detail={"errors": e.errors}) from e
    try:
        await registry.add_pair(
            parsed[0], envelope.manifests[0].manifest_yaml,
            parsed[1], envelope.manifests[1].manifest_yaml,
        )
    except RegistryConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return [_to_response(m) for m in parsed]


@router.get(
    "",
    response_model=List[ManifestStored],
)
async def list_manifests(
    registry: ManifestRegistry = Depends(get_registry),
) -> List[ManifestStored]:
    """List all registered manifests (operator + BFF surface)."""
    rows = await registry.list_all()
    return [
        ManifestStored(
            name=r.name,
            version=r.version,
            job_type=r.job_type,
            execution_mode=r.execution_mode,
            image=r.image,
            service_family=r.service_family,
            contract_version=r.contract_version,
            description=r.description,
            default_params={},
            is_active=True,
        )
        for r in rows
    ]


@router.get(
    "/{name}",
    response_model=List[ManifestStored],
)
async def get_manifest_by_name(
    name: str,
    registry: ManifestRegistry = Depends(get_registry),
) -> List[ManifestStored]:
    """Return every registered version for ``name``.

    Frontend uses this to populate the version dropdown + per-version
    defaults on the SDS-VLM 학습 시작 page. 404 if no versions registered.
    """
    rows = [r for r in await registry.list_all() if r.name == name]
    if not rows:
        raise HTTPException(status_code=404, detail=f"manifest {name!r} not found")
    # 버전별 full manifest 를 가져와 spec.recipe(다단계 학습 레시피, SP-10)를 함께
    # surface. raw_json 재파싱이라 추가 컬럼/마이그레이션 불필요. recipe 없는
    # manifest 는 None — FE 가 기존 단일 launch 경로로 fallback.
    out: List[ManifestStored] = []
    for r in rows:
        # per-version 격리: 한 버전의 raw_json 손상/transient DB 오류가 전체 엔드포인트
        # 를 500 내지 않도록 recipe=None 으로 폴백(나머지 버전은 정상 반환).
        try:
            manifest = await registry.get(r.name, r.version)
            recipe = (
                manifest.spec.recipe.model_dump()
                if manifest and manifest.spec.recipe
                else None
            )
        except Exception:
            logger.warning(
                "get_manifest_by_name: failed to load recipe for %s@%s; recipe=None",
                r.name, r.version,
            )
            recipe = None
        out.append(
            ManifestStored(
                name=r.name,
                version=r.version,
                job_type=r.job_type,
                execution_mode=r.execution_mode,
                image=r.image,
                service_family=r.service_family,
                contract_version=r.contract_version,
                description=r.description,
                default_params={},
                recipe=recipe,
                is_active=True,
            )
        )
    return out


@router.get(
    "/{name}/{version}/paired",
    response_model=ManifestStored,
)
async def get_paired_manifest(
    name: str,
    version: str,
    registry: ManifestRegistry = Depends(get_registry),
) -> ManifestStored:
    """Return the paired manifest registered with the same pair_id.

    codex Med-2: playground/service.py 가 ``-train`` → ``-infer`` + 버전을
    hardcode 했었음. 그 대신 train manifest 의 pair_id 로 paired inference
    manifest 를 lookup. 다른 partner / 다른 version 에서도 동작.

    404 if (name, version) 가 unknown 이거나 pair_id 가 None (paired 등록
    안 됨) 이거나 pair partner 가 다른 row 에 없음.
    """
    rows = await registry.list_all()
    target = next(
        (r for r in rows if r.name == name and r.version == version),
        None,
    )
    if target is None:
        raise HTTPException(
            status_code=404, detail=f"manifest {name}@{version} not found"
        )
    if target.pair_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"manifest {name}@{version} has no pair_id (not registered as paired)",
        )
    paired = next(
        (
            r for r in rows
            if r.pair_id == target.pair_id and not (r.name == name and r.version == version)
        ),
        None,
    )
    if paired is None:
        raise HTTPException(
            status_code=404,
            detail=f"pair partner for {name}@{version} (pair_id={target.pair_id}) not found",
        )
    return ManifestStored(
        name=paired.name,
        version=paired.version,
        job_type=paired.job_type,
        execution_mode=paired.execution_mode,
        image=paired.image,
        service_family=paired.service_family,
        contract_version=paired.contract_version,
        description=paired.description,
        default_params={},
        is_active=True,
    )


@router.delete(
    "/{name}/{version}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_manifest(
    name: str,
    version: str,
    registry: ManifestRegistry = Depends(get_registry),
) -> Response:
    removed = await registry.remove(name, version)
    if not removed:
        raise HTTPException(status_code=404, detail=f"manifest {name}@{version} not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
