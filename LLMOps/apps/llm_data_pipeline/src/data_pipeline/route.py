"""llm_data_pipeline 라우터. 플랫폼 envelope response() 준수 — llm_evaluation 과 같은 형태.

Kong ingress 가 `/api/(data-pipelines)(.*)` 로 붙이므로 prefix 는 `/data-pipelines`.
"""
import traceback

from fastapi import APIRouter, Header, Query

from utils.resource import response

import data_pipeline.dto as dto
import data_pipeline.service as svc

data_pipelines = APIRouter(prefix="/data-pipelines")

TAG = ["DATA-PIPELINE"]


# 사용자가 보고 고칠 수 있는 예외 — 이것만 원문을 전한다.
_SAFE_ERRORS = (svc.NotFound, svc.Conflict, ValueError)


def _fail(e):
    """예외를 응답으로 바꾼다.

    NotFound / Conflict / ValueError 는 사용자가 고칠 수 있는 상황이라 메시지를 그대로
    전하고, 그 밖의 예외는 일반 문구로 덮는다. 드라이버 예외를 그대로 흘리면
    `Duplicate entry ... for key 'llm_dp_dataset.uk_dp_dataset_ws_name'` 처럼
    테이블·제약조건명이 응답에 실려 나간다(CWE-209).
    """
    traceback.print_exc()
    if isinstance(e, _SAFE_ERRORS):
        return response(status=0, message=str(e), result=None)
    return response(status=0, message="요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.",
                    result=None)


@data_pipelines.get("/healthz", summary="헬스체크", tags=TAG)
async def healthz():
    return response(status=1, result={"ok": True})


@data_pipelines.get("/meta", summary="화면 공용 상수(축·임계값·프리셋·라이브러리)", tags=TAG)
async def get_meta():
    """FE 가 임계값·유형·기능 목록을 따로 하드코딩하지 않도록 서버가 정본을 내려준다."""
    try:
        return response(status=1, result=svc.get_meta())
    except Exception as e:
        return _fail(e)


# ── 데이터셋 ────────────────────────────────────────────────────────────────
@data_pipelines.get("/datasets", summary="데이터셋 목록(워크스페이스)", tags=TAG)
async def list_datasets(workspace_id: int):
    try:
        return response(status=1, result=await svc.list_datasets(workspace_id=workspace_id))
    except Exception as e:
        return _fail(e)


@data_pipelines.post("/datasets", summary="데이터셋 생성", tags=TAG)
async def create_dataset(body: dto.DatasetCreateBody,
                         jf_user: str = Header(default=None, alias="jf-User")):
    """생성 직후는 데이터가 없는 draft. 프리셋 기본 노드 체인이 함께 만들어진다."""
    try:
        res = await svc.create_dataset(
            workspace_id=body.workspace_id, name=body.name, description=body.description,
            preset=body.preset, create_user=jf_user)
        return response(status=1, result=res)
    except Exception as e:
        return _fail(e)


@data_pipelines.get("/datasets/{dataset_id}", summary="데이터셋 단건", tags=TAG)
async def get_dataset(dataset_id: int):
    try:
        return response(status=1, result=await svc.get_dataset(dataset_id))
    except Exception as e:
        return _fail(e)


@data_pipelines.put("/datasets/{dataset_id}", summary="데이터셋 메타 수정", tags=TAG)
async def update_dataset(dataset_id: int, body: dto.DatasetUpdateBody):
    try:
        res = await svc.update_dataset(
            dataset_id, name=body.name, description=body.description, state=body.state)
        return response(status=1, result=res)
    except Exception as e:
        return _fail(e)


@data_pipelines.delete("/datasets/{dataset_id}", summary="데이터셋 삭제", tags=TAG)
async def delete_dataset(dataset_id: int):
    """자식 행(asset·node·record·review·version)은 FK CASCADE 로 함께 정리된다."""
    try:
        return response(status=1, result=await svc.delete_dataset(dataset_id))
    except Exception as e:
        return _fail(e)


# ── 업로드 ──────────────────────────────────────────────────────────────────
@data_pipelines.get("/datasets/{dataset_id}/assets", summary="업로드 목록 + 요약 + 실패", tags=TAG)
async def get_assets(dataset_id: int,
                     limit: int = Query(default=100, ge=1, le=1000),
                     offset: int = Query(default=0, ge=0)):
    try:
        res = await svc.get_assets(dataset_id, limit=limit, offset=offset)
        return response(status=1, result=res)
    except Exception as e:
        return _fail(e)


@data_pipelines.post("/datasets/{dataset_id}/assets", summary="원본 데이터 등록", tags=TAG)
async def register_assets(dataset_id: int, body: dto.AssetRegisterBody):
    """드라이브(기존 데이터셋)에서 고른 원본을 이 파이프라인에 등록한다.

    파일 자체를 여기로 올리지 않는다 — 원본 적재는 데이터셋이 하고, 여기는 참조만 받는다.
    """
    try:
        rows = [(a.name, a.path, a.kind, a.size_bytes, a.status, a.fail_reason)
                for a in body.assets]
        return response(status=1, result=await svc.register_assets(dataset_id, rows))
    except Exception as e:
        return _fail(e)


# ── 파이프라인 노드 ─────────────────────────────────────────────────────────
@data_pipelines.get("/datasets/{dataset_id}/flow", summary="파이프라인 노드 체인", tags=TAG)
async def get_flow(dataset_id: int):
    """노드마다 입력/출력 타입과 경고(좌표 깨짐·재심사 필요)가 함께 붙어 온다."""
    try:
        return response(status=1, result=await svc.get_flow(dataset_id))
    except Exception as e:
        return _fail(e)


@data_pipelines.put("/datasets/{dataset_id}/flow", summary="파이프라인 노드 체인 저장", tags=TAG)
async def replace_flow(dataset_id: int, body: dto.FlowUpdateBody):
    """전체 교체. 해양 COLREG 프리셋은 구성 고정이라 서비스 계층이 거부한다."""
    try:
        res = await svc.replace_flow(
            dataset_id, preset=body.preset, nodes=body.nodes, flow=body.flow)
        return response(status=1, result=res)
    except Exception as e:
        return _fail(e)


# ── 단계 설정 ───────────────────────────────────────────────────────────────
@data_pipelines.get("/datasets/{dataset_id}/stages/{stage}", summary="단계 설정 조회", tags=TAG)
async def get_stage(dataset_id: int, stage: str):
    try:
        dto.validate_stage(stage)
        return response(status=1, result=await svc.get_stage(dataset_id, stage))
    except Exception as e:
        return _fail(e)


@data_pipelines.post("/datasets/{dataset_id}/stages/{stage}/run", summary="단계 실행", tags=TAG)
async def run_stage(dataset_id: int, stage: str, body: dto.StageRunBody,
                    jf_user: str = Header(default=None, alias="Jf-User")):
    """노드 하나를 잡으로 띄운다.

    dry_run 이면 표본만 돌려 `_preview/` 에 남기고 이력에 안 남긴다 — 사용자가 기능을
    껐다 켜며 결과를 비교하는 경로다. 전량 실행은 `_runs/{run_id}/` 로 간다.
    """
    try:
        dto.validate_stage(stage)
        res = await svc.run_stage(dataset_id, stage, dry_run=body.dry_run,
                                  sample_size=body.sample_size, jf_user=jf_user)
        return response(status=1, result=res)
    except Exception as e:
        return _fail(e)


@data_pipelines.put("/datasets/{dataset_id}/stages/preprocess", summary="전처리 설정 저장", tags=TAG)
async def save_preprocess(dataset_id: int, body: dto.StageConfigBody):
    try:
        res = await svc.save_stage(dataset_id, "preprocess", body.model_dump())
        return response(status=1, result=res)
    except Exception as e:
        return _fail(e)


@data_pipelines.put("/datasets/{dataset_id}/stages/filter", summary="필터 설정 저장", tags=TAG)
async def save_filter(dataset_id: int, body: dto.StageConfigBody):
    try:
        res = await svc.save_stage(dataset_id, "filter", body.model_dump())
        return response(status=1, result=res)
    except Exception as e:
        return _fail(e)


@data_pipelines.put("/datasets/{dataset_id}/stages/generate", summary="생성 설정 저장", tags=TAG)
async def save_generate(dataset_id: int, body: dto.GenerateConfigBody):
    """생성 모델과 심사 모델이 같으면 DTO 단계에서 이미 거부된다(자가심사 차단).
    같은 계열이면 막지는 않고 경고만 함께 돌려준다."""
    try:
        pairing = svc.judge_model_pairing(body.generator_model, body.judge_model)
        if pairing["level"] in ("blocked", "error"):
            return response(status=0, message=pairing["message"], result=None)
        res = await svc.save_stage(dataset_id, "generate", body.model_dump())
        res["pairing"] = pairing
        return response(status=1, result=res)
    except Exception as e:
        return _fail(e)


@data_pipelines.put("/datasets/{dataset_id}/stages/gate", summary="심사 임계값 저장", tags=TAG)
async def save_gate(dataset_id: int, body: dto.GateConfigBody):
    try:
        res = await svc.save_stage(dataset_id, "gate", body.model_dump())
        return response(status=1, result=res)
    except Exception as e:
        return _fail(e)


@data_pipelines.get("/datasets/{dataset_id}/gate-summary", summary="게이트 통과율 · 축별 미달", tags=TAG)
async def gate_summary(dataset_id: int):
    try:
        return response(status=1, result=await svc.get_gate_summary(dataset_id))
    except Exception as e:
        return _fail(e)


# ── 검수 ────────────────────────────────────────────────────────────────────
@data_pipelines.get("/datasets/{dataset_id}/records", summary="검수 큐", tags=TAG)
async def list_records(dataset_id: int,
                       order: str = Query(default="score_asc", description="score_asc|random|taxonomy"),
                       taxonomy: str = Query(default=None),
                       review_state: str = Query(default=None),
                       limit: int = Query(default=50, ge=1, le=500),
                       offset: int = Query(default=0, ge=0)):
    """기본 정렬이 점수 낮은 순인 이유: 사람 시간이 비싸므로 위험한 것부터 본다."""
    try:
        res = await svc.list_records(dataset_id, order=order, taxonomy=taxonomy,
                                     review_state=review_state, limit=limit, offset=offset)
        return response(status=1, result=res)
    except Exception as e:
        return _fail(e)


@data_pipelines.get("/datasets/{dataset_id}/records/{record_key}",
                    summary="레코드 상세 — 사람이 읽는 키로 조회", tags=TAG)
async def get_record_by_key(dataset_id: int, record_key: str):
    """화면 URL 이 vdf-0009855 같은 키를 쓰므로 그 경로로도 열어 둔다."""
    try:
        return response(status=1, result=await svc.get_record_by_key(dataset_id, record_key))
    except Exception as e:
        return _fail(e)


@data_pipelines.get("/records/{record_id}", summary="레코드 상세(+판정 이력)", tags=TAG)
async def get_record(record_id: int):
    try:
        return response(status=1, result=await svc.get_record(record_id))
    except Exception as e:
        return _fail(e)


@data_pipelines.post("/records/{record_id}/review", summary="사람 검수 판정", tags=TAG)
async def review_record(record_id: int, body: dto.ReviewBody,
                        jf_user: str = Header(default=None, alias="jf-User")):
    """판정은 이력으로 쌓인다. '수정 후 승인'이면 본문이 수정본으로 교체된다."""
    try:
        res = await svc.review_record(
            record_id, verdict=body.verdict, taxonomy=body.taxonomy,
            edited_question=body.edited_question, edited_answer=body.edited_answer,
            reviewer=jf_user)
        return response(status=1, result=res)
    except Exception as e:
        return _fail(e)


# ── 분포 분석 ───────────────────────────────────────────────────────────────
@data_pipelines.get("/datasets/{dataset_id}/coverage", summary="데이터 유형별 분포 · 판정", tags=TAG)
async def get_coverage(dataset_id: int):
    """레코드 수와 원본 수를 함께 준다 — 둘을 봐야 업로드 문제인지 생성 문제인지 갈린다."""
    try:
        return response(status=1, result=await svc.get_coverage(dataset_id))
    except Exception as e:
        return _fail(e)


# ── 구성 · 버전 ─────────────────────────────────────────────────────────────
@data_pipelines.post("/datasets/{dataset_id}/verify-format", summary="학습 형식 미리 검사", tags=TAG)
async def verify_format(dataset_id: int, body: dto.VerifyFormatBody):
    """데이터셋을 만들기 전에 실제 학습 코드가 읽을 수 있는지 본다."""
    try:
        return response(status=1, result=await svc.verify_format(dataset_id, body.formats))
    except Exception as e:
        return _fail(e)


@data_pipelines.get("/datasets/{dataset_id}/versions", summary="버전 이력(+직전 대비 증감)", tags=TAG)
async def list_versions(dataset_id: int):
    try:
        return response(status=1, result=await svc.list_versions(dataset_id))
    except Exception as e:
        return _fail(e)


@data_pipelines.post("/datasets/{dataset_id}/versions", summary="버전 생성(릴리스)", tags=TAG)
async def create_version(dataset_id: int, body: dto.VersionCreateBody):
    try:
        res = await svc.create_version(
            dataset_id, version=body.version, mix=body.mix,
            split=body.split, split_by=body.split_by)
        return response(status=1, result=res)
    except Exception as e:
        return _fail(e)
