"""데이터 합성 프레임워크 — route (P1, WBS 3.3 / SP-7). 마운트: /api/synthesis/..."""
import traceback

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from utils.resource import response, get_auth, get_user_id

import synthesis.dto as dto
import synthesis.service as svc

synthesis = APIRouter(prefix="/synthesis")


def _current_user():
    """인증 컨텍스트의 (user_id, user_name). 세션/헤더 없으면 (None, None).
    owner 는 클라이언트가 아니라 세션에서 서버 권위적으로 기록(스푸핑 방지)."""
    try:
        user_name, _ = get_auth()
    except Exception:
        return None, None
    try:
        uid = get_user_id()
    except Exception:
        uid = None
    return uid, user_name


@synthesis.get("/healthz")
async def healthz():
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=200, content={"status": "healthy"})


@synthesis.get("/manifests")
async def get_synthesis_manifests():
    """합성 모듈(generate 외부 컨테이너) 목록 — 프로젝트 생성 드롭다운용."""
    try:
        res = await svc.list_manifests()
        return response(status=1, result=res)
    except Exception:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])


@synthesis.get("")
async def get_synthesis_projects(workspace_id: int):
    try:
        res = await svc.get_synthesis_projects(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])


@synthesis.post("", response_model=dto.Response)
async def create_synthesis_project(body: dto.CreateSynthesisProject):
    try:
        # owner 는 세션에서 서버 권위적으로 기록(FE 미전송·스푸핑 방지). 헤더 없으면 보존.
        uid, uname = _current_user()
        if uid is not None:
            body.owner_id = uid
            body.owner_name = uname
        res = await svc.create_synthesis_project(body=body)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message=e.__str__())


@synthesis.get("/{project_id}/status")
async def get_synthesis_status(project_id: int):
    try:
        res = await svc.get_synthesis_status(project_id=project_id)
        return response(status=1, result=res)
    except Exception:
        traceback.print_exc()
        return response(status=0, message="server error")


@synthesis.get("/{project_id}/result")
async def get_synthesis_result(project_id: int):
    try:
        res = await svc.get_synthesis_result(project_id=project_id)
        return response(status=1, result=res)
    except Exception:
        traceback.print_exc()
        return response(status=0, message="server error")


@synthesis.get("/{project_id}/log")
async def get_synthesis_log(project_id: int):
    """생성 실행 실시간 로그(generate pod stdout). FE 폴링."""
    try:
        res = await svc.get_synthesis_log(project_id=project_id)
        return response(status=1, result=res)
    except Exception:
        traceback.print_exc()
        return response(status=0, message="server error")


@synthesis.get("/{project_id}/download")
async def download_synthesis_result(project_id: int):
    """생성 결과 result.jsonl 다운로드."""
    try:
        path = await svc.get_synthesis_result_file(project_id=project_id)
        if not path:
            return JSONResponse(status_code=404, content={"status": 0, "message": "no result file"})
        return FileResponse(
            path, media_type="application/x-ndjson", filename=f"synthesis-{project_id}.jsonl"
        )
    except Exception:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": 0, "message": "server error"})


@synthesis.get("/{project_id}/prompt-candidates")
async def get_prompt_candidates(project_id: int):
    """프롬프트 최적화(LLM1) 후보 — 점수순. P2 mock(고려대 LLM1 수령 시 교체)."""
    try:
        res = await svc.get_prompt_candidates(project_id=project_id)
        return response(status=1, result=res)
    except Exception:
        traceback.print_exc()
        return response(status=0, message="server error")


@synthesis.post("/{project_id}/run", response_model=dto.Response)
async def run_synthesis(project_id: int):
    try:
        res = await svc.run_synthesis(project_id=project_id)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message=e.__str__())


@synthesis.post("/{project_id}/save-dataset", response_model=dto.Response)
async def save_to_dataset(project_id: int, body: dto.SaveDatasetBody):
    """생성 결과 result.jsonl 을 플랫폼 데이터셋으로 등록."""
    try:
        # 데이터셋 소유자 = 저장을 실행한 세션 사용자(없으면 service 에서 프로젝트 owner fallback).
        uid, _ = _current_user()
        res = await svc.save_to_dataset(
            project_id=project_id, dataset_name=body.dataset_name,
            access=body.access, create_user_id=uid,
        )
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message=e.__str__())


@synthesis.post("/{project_id}/prompt-candidates/generate")
async def regenerate_prompt_candidates(project_id: int):
    """'최적화 실행' — 후보 재생성+영속(미결정만 교체, 채택/폐기 이력 보존)."""
    try:
        res = await svc.regenerate_prompt_candidates(project_id=project_id)
        return response(status=1, result=res)
    except Exception:
        traceback.print_exc()
        return response(status=0, message="server error")


@synthesis.post("/{project_id}/candidates/{candidate_id}/adopt", response_model=dto.Response)
async def adopt_candidate(project_id: int, candidate_id: int):
    try:
        res = await svc.adopt_candidate(project_id=project_id, candidate_id=candidate_id)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message=e.__str__())


@synthesis.post("/{project_id}/candidates/{candidate_id}/discard", response_model=dto.Response)
async def discard_candidate(project_id: int, candidate_id: int):
    try:
        res = await svc.discard_candidate(project_id=project_id, candidate_id=candidate_id)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message=e.__str__())


@synthesis.get("/{project_id}")
async def get_synthesis_project(project_id: int):
    try:
        res = await svc.get_synthesis_project_detail(project_id=project_id)
        return response(status=1, result=res)
    except Exception:
        traceback.print_exc()
        return response(status=0, message="server error")


@synthesis.put("/{project_id}", response_model=dto.Response)
async def update_synthesis_project(project_id: int, body: dto.UpdateSynthesisProject):
    try:
        res = await svc.update_synthesis_project(project_id=project_id, body=body)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message=e.__str__())


@synthesis.delete("/{project_id}", response_model=dto.Response)
async def delete_synthesis_project(project_id: int):
    try:
        res = await svc.delete_synthesis_project(project_id=project_id)
        return dto.Response(status=1, result=res)
    except Exception:
        traceback.print_exc()
        return dto.Response(status=0, message="server error")
