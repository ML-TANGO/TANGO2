"""llm_data_pipeline 라우터. 플랫폼 envelope response() 준수 — llm_evaluation 과 같은 형태.

Kong ingress 가 `/api/(data-pipelines)(.*)` 로 붙이므로 prefix 는 `/data-pipelines`.
"""
import traceback

import mimetypes

from fastapi import APIRouter, Header, Query
from fastapi.responses import FileResponse, JSONResponse

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
@data_pipelines.get("/source-datasets", summary="소스로 고를 수 있는 데이터셋", tags=TAG)
async def list_source_datasets(workspace_id: int,
                               jf_user: str = Header(default=None, alias="Jf-User")):
    """원본이 들어 있는 기존 데이터셋 목록. `path` 를 그대로 sources 에 넣으면 된다.

    파이프라인이 산출물을 쌓는 작업 데이터셋은 빠진다 — 자기 출력을 자기 입력으로
    고를 수 있으면 안 된다.
    """
    try:
        return response(status=1,
                        result=await svc.list_source_datasets(workspace_id, jf_user))
    except Exception as e:
        return _fail(e)


@data_pipelines.get("/source-datasets/{dataset_id}/folders", summary="소스 데이터셋의 폴더", tags=TAG)
async def list_source_folders(dataset_id: int, workspace_id: int,
                              jf_user: str = Header(default=None, alias="Jf-User")):
    """폴더까지 좁혀 읽을 수 있게. 첫 항목은 전체(루트)."""
    try:
        return response(status=1,
                        result=await svc.list_source_folders(workspace_id, dataset_id, jf_user))
    except Exception as e:
        return _fail(e)


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


# ── 실행 이력 ───────────────────────────────────────────────────────────────
@data_pipelines.get("/datasets/{dataset_id}/runs", summary="노드 실행 이력", tags=TAG)
async def list_runs(dataset_id: int,
                    node_index: int = Query(default=None, description="특정 노드만"),
                    limit: int = Query(default=50, ge=1, le=500)):
    """최신순. 노드 잡은 비동기라 실행 직후에는 running 으로 보이고, 리콘사일러가
    산출물을 확인하면 done/failed 로 바뀐다."""
    try:
        return response(status=1, result=await svc.list_runs(
            dataset_id, node_index=node_index, limit=limit))
    except Exception as e:
        return _fail(e)


# 주의: 이 경로는 아래 `/runs/{run_id}` 보다 **먼저** 선언해야 한다. 순서가 바뀌면
# FastAPI 가 "compare" 를 run_id 로 받아 "실행을 찾을 수 없습니다: compare" 가 된다.
@data_pipelines.get("/datasets/{dataset_id}/runs/compare", summary="두 실행 A/B 비교", tags=TAG)
async def compare_runs(dataset_id: int,
                       a: str = Query(description="기준 실행 run_id"),
                       b: str = Query(description="비교 대상 run_id")):
    """설정 차이 · 단계별 funnel 차이 · 카운트 증감. 같은 노드의 실행끼리만 비교한다."""
    try:
        return response(status=1, result=await svc.compare_runs(dataset_id, a, b))
    except Exception as e:
        return _fail(e)


@data_pipelines.get("/datasets/{dataset_id}/runs/{run_id}", summary="실행 상세(+단계별 funnel)", tags=TAG)
async def get_run(dataset_id: int, run_id: str):
    """노드 안에서 단계별로 몇 건이 들어가 몇 건이 남았는지(funnel)까지 준다."""
    try:
        return response(status=1, result=await svc.get_run(dataset_id, run_id))
    except Exception as e:
        return _fail(e)


@data_pipelines.get("/datasets/{dataset_id}/runs/{run_id}/preview",
                    summary="산출물 미리보기(통과 · 제외)", tags=TAG)
async def preview_run(dataset_id: int, run_id: str,
                      kind: str = Query(default="passed", description="passed|dropped"),
                      limit: int = Query(default=50, ge=1, le=200),
                      offset: int = Query(default=0, ge=0)):
    """노드 드로어의 '통과' · '제외' 열. '입력' 열은 상류 실행의 통과분이므로
    같은 엔드포인트를 상류 run_id 로 한 번 더 부르면 된다."""
    try:
        return response(status=1, result=await svc.preview_run(
            dataset_id, run_id, kind=kind, limit=limit, offset=offset))
    except Exception as e:
        return _fail(e)


@data_pipelines.get("/datasets/{dataset_id}/runs/{run_id}/thumb/{asset_id}",
                    summary="산출물 썸네일(image/jpeg)", tags=TAG)
async def run_thumb(dataset_id: int, run_id: str, asset_id: str):
    """썸네일 바이트. 봉투(JSON) 대신 이미지로 내려가야 <img src> 로 바로 걸린다.

    노드는 앞부분 일부만 썸네일로 만든다(전량이면 용량이 터진다). 없는 자산은 404 이며,
    미리보기 응답의 has_thumb 로 미리 걸러진다.
    """
    try:
        path = await svc.run_thumb_path(dataset_id, run_id, asset_id)
        return FileResponse(path, media_type="image/jpeg")
    except svc.NotFound as e:
        return JSONResponse(status_code=404, content={"status": 0, "message": str(e)})
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


@data_pipelines.put("/datasets/{dataset_id}/stages/data", summary="데이터 소스(마운트) 저장", tags=TAG)
async def save_data(dataset_id: int, body: dto.StageConfigBody):
    """데이터 노드는 실행되지 않는다 — 원본을 어디서 읽을지(sources)만 담는다.

    실제로 그 경로를 읽는 것은 전처리 노드이고, 실행 시점에 여기 값을 물려받는다.
    이 저장이 없으면 화면에서 고른 소스가 사라지고, 노드는 /datasets 전체를 훑는다.
    """
    try:
        return response(status=1, result=await svc.save_stage(dataset_id, "data", body.model_dump()))
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


# 해양 COLREG 수집·조인 단계. 저장 바디는 전처리·필터와 같은 모양(소스 · 기능 on/off ·
# 파라미터)이라 StageConfigBody 를 그대로 쓴다. 단계마다 경로를 따로 두는 것은 이 라우터의
# 기존 방식(스테이지별 명시 엔드포인트)을 따른 것이다.
@data_pipelines.put("/datasets/{dataset_id}/stages/sds_video", summary="항해 영상 수집 설정 저장", tags=TAG)
async def save_sds_video(dataset_id: int, body: dto.StageConfigBody):
    try:
        res = await svc.save_stage(dataset_id, "sds_video", body.model_dump())
        return response(status=1, result=res)
    except Exception as e:
        return _fail(e)


@data_pipelines.put("/datasets/{dataset_id}/stages/sds_ais", summary="AIS 로그 수집 설정 저장", tags=TAG)
async def save_sds_ais(dataset_id: int, body: dto.StageConfigBody):
    try:
        res = await svc.save_stage(dataset_id, "sds_ais", body.model_dump())
        return response(status=1, result=res)
    except Exception as e:
        return _fail(e)


@data_pipelines.put("/datasets/{dataset_id}/stages/sds_join", summary="조인 설정 저장", tags=TAG)
async def save_sds_join(dataset_id: int, body: dto.StageConfigBody):
    try:
        res = await svc.save_stage(dataset_id, "sds_join", body.model_dump())
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


@data_pipelines.get("/datasets/{dataset_id}/records/{record_id}/image",
                    summary="레코드 원본 이미지(image/*)", tags=TAG)
async def record_image(dataset_id: int, record_id: int):
    """검수 화면이 <img src> 로 바로 거는 원본 이미지.

    썸네일(`/runs/{run_id}/thumb/{asset_id}`)과 다른 경로인 이유는 service 쪽 주석에
    있다 — 요약하면 썸네일은 일부만 있고, 레코드의 asset_ref 는 경로라서 그 엔드포인트에
    넣을 수 없다.
    """
    try:
        path = await svc.record_image_path(dataset_id, record_id)
        return FileResponse(path, media_type=mimetypes.guess_type(path)[0] or "image/jpeg")
    except svc.NotFound as e:
        return JSONResponse(status_code=404, content={"status": 0, "message": str(e)})
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


# ── 생성·심사 서빙(자동 배포·회수) ──────────────────────────────────────────
@data_pipelines.get("/datasets/{dataset_id}/servings", summary="이 파이프라인이 쥔 서빙 현황", tags=TAG)
async def list_servings(dataset_id: int):
    """역할별 배포 상태와 노드가 쓸 주소. GPU 를 무엇이 물고 있는지 여기서 확인한다."""
    try:
        return response(status=1, result=await svc.list_servings(dataset_id))
    except Exception as e:
        return _fail(e)


@data_pipelines.post("/datasets/{dataset_id}/servings/{role}", summary="서빙 준비(자동 배포)", tags=TAG)
async def start_serving(dataset_id: int, role: str,
                        wait: bool = Query(default=False,
                                           description="true 면 준비될 때까지 기다린다(s2s·점검용). "
                                                        "기본은 시작만 하고 즉시 반환."),
                        jf_user: str = Header(default=None, alias="jf-User")):
    """단계 설정에서 고른 모델을 띄운다. 자원이 모자라면 **띄우기 전에** 사유와 함께 거절된다."""
    try:
        if wait:
            return response(status=1, result=await svc.ensure_serving(dataset_id, role, jf_user))
        return response(status=1, result=await svc.start_serving(dataset_id, role, jf_user))
    except Exception as e:
        return _fail(e)


@data_pipelines.delete("/datasets/{dataset_id}/servings", summary="서빙 회수", tags=TAG)
async def release_serving(dataset_id: int,
                          role: str = Query(default=None, description="생략하면 전부"),
                          jf_user: str = Header(default=None, alias="jf-User")):
    """지금 내린다. 리콘사일러의 유휴 회수를 기다리지 않고 GPU 를 즉시 돌려받는 경로."""
    try:
        return response(status=1, result=await svc.release_serving(dataset_id, role, jf_user))
    except Exception as e:
        return _fail(e)
