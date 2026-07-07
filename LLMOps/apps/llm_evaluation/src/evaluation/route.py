"""llm_evaluation 라우터 (P1b — benchmark). 플랫폼 envelope response() 준수."""
import traceback

from fastapi import APIRouter, Header
from fastapi.responses import FileResponse, Response

from utils.resource import response

import evaluation.dto as dto
import evaluation.service as svc

evaluations = APIRouter(prefix="/evaluations")

TAG = ["EVALUATION"]


@evaluations.post("/projects", summary="평가 프로젝트 생성(대기)", tags=TAG)
async def create_project(body: dto.EvalProjectCreateBody,
                         jf_user: str = Header(default=None, alias="jf-User")):
    """모델·데이터셋·유형·이름 잠금(P3), status='created'(run 0개, P5). creator=jf-User 헤더."""
    try:
        res = await svc.create_project(
            name=body.name, model_id=body.model_id, dataset_ids=body.dataset_ids,
            eval_type=body.eval_type, creator=jf_user)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/projects", summary="평가 프로젝트 목록(워크스페이스)", tags=TAG)
async def list_projects(workspace_id: int):
    try:
        res = await svc.list_projects(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/projects/{project_id}", summary="평가 프로젝트 상세(+run 목록)", tags=TAG)
async def get_project(project_id: int):
    try:
        res = await svc.get_project(project_id=project_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/projects/{project_id}/compare", summary="프로젝트 내 run 비교", tags=TAG)
async def compare_project_runs(project_id: int):
    try:
        res = await svc.compare_project_runs(project_id=project_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.delete("/projects/{project_id}", summary="평가 프로젝트 삭제", tags=TAG)
async def delete_project(project_id: int):
    try:
        res = await svc.delete_project(project_id=project_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.post("/benchmark", summary="benchmark 평가 런 생성", tags=TAG)
async def run_benchmark(body: dto.BenchmarkRunBody):
    try:
        res = await svc.run_benchmark(
            project_id=body.project_id, metric_set=body.metric_set)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/judges", summary="가용 심판(상용+로컬) 목록", tags=TAG)
async def list_judges():
    try:
        res = await svc.list_judges()
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.post("/judge", summary="LLM-as-a-Judge 런 생성", tags=TAG)
async def run_judge(body: dto.JudgeRunBody):
    try:
        res = await svc.run_judge(
            project_id=body.project_id,
            provider=body.provider, criteria=body.criteria,
            judge_model=body.judge_model, api_key=body.api_key,
            base_url=body.base_url, custom_prompt=body.custom_prompt,
            inference_playground_id=body.inference_playground_id,
        )
        return response(status=1, result=res)
    except Exception as e:
        # ⚠️ str(e) 에 api_key 가 들어가지 않도록 service 에서 키를 메시지에 넣지 않음.
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.post("/expert", summary="전문가 평가 세션 시작", tags=TAG)
async def start_expert(body: dto.ExpertStartBody):
    try:
        res = await svc.start_expert(
            project_id=body.project_id,
            inference_playground_id=body.inference_playground_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/compare", summary="교차모델 비교(전역 best-per-metric)", tags=TAG)
async def compare_models(model_ids: str = ""):
    """model_ids=1,2,3 (콤마구분). 1 세그먼트라 /{model_id}/... param 경로와 충돌 X 지만
    명시 GET 들 앞에 두어 라우팅 의도를 분명히 한다."""
    try:
        ids = []
        for tok in model_ids.split(","):
            tok = tok.strip()
            if tok:
                ids.append(int(tok))    # 비정수 토큰 → ValueError → 422 대신 envelope 0
        res = await svc.compare_models(model_ids=ids)
        return response(status=1, result=res)
    except ValueError as e:
        return response(status=0, message=str(e), result=None)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/{model_id}/results", summary="평가 이력(비교표)", tags=TAG)
async def list_eval_results(model_id: int):
    try:
        res = await svc.list_eval_results(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/{model_id}/{job_id}/result", summary="단건 평가 metrics(poll)", tags=TAG)
async def get_eval_result(model_id: int, job_id: str):
    try:
        res = await svc.get_eval_result(model_id=model_id, job_id=job_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/{model_id}/{job_id}/judge-result", summary="judge 런 결과(poll)", tags=TAG)
async def get_judge_result(model_id: int, job_id: str):
    try:
        res = await svc.get_judge_result(model_id=model_id, job_id=job_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/{model_id}/{job_id}/expert-samples", summary="전문가 채점 샘플+기존채점", tags=TAG)
async def get_expert_samples(model_id: int, job_id: str):
    try:
        res = await svc.get_expert_samples(model_id=model_id, job_id=job_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.post("/{model_id}/{job_id}/expert-rating", summary="전문가 채점 제출(1~5 별점)", tags=TAG)
async def submit_expert_rating(model_id: int, job_id: str, body: dto.ExpertRatingBody,
                               jf_user: str = Header(default=None, alias="jf-User")):
    try:
        res = await svc.submit_expert_rating(
            model_id=model_id, job_id=job_id, sample_idx=body.sample_idx,
            score=body.score, score_json=body.score_json, comment=body.comment,
            rater_user=jf_user)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/{model_id}/{job_id}/expert-result", summary="전문가 평가 진행/결과", tags=TAG)
async def get_expert_result(model_id: int, job_id: str):
    try:
        res = await svc.get_expert_result(model_id=model_id, job_id=job_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.get("/{model_id}/{job_id}/expert-image/{sample_idx}",
                 summary="전문가 샘플 이미지(멀티모달)", tags=TAG)
async def get_expert_image(model_id: int, job_id: str, sample_idx: int):
    """VLM 샘플 이미지를 바이너리로 서빙(envelope 아님). NFS 상대경로 이미지만 — URL 이미지는
    FE 가 직접 렌더. 없거나 검증 실패 → 404(FE 가 플레이스홀더 표시)."""
    try:
        path, media_type = await svc.get_expert_image(
            model_id=model_id, job_id=job_id, sample_idx=sample_idx)
        return FileResponse(path, media_type=media_type)
    except Exception:
        traceback.print_exc()
        return Response(status_code=404)


@evaluations.post("/{model_id}/{job_id}/status", summary="평가 실패/취소 마킹", tags=TAG)
async def update_eval_status(model_id: int, job_id: str, body: dto.EvalStatusBody):
    try:
        res = await svc.mark_eval_status(
            model_id=model_id, job_id=job_id, status=body.status)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@evaluations.delete("/{model_id}/{job_id}", summary="평가 런 삭제(이력 관리)", tags=TAG)
async def delete_eval_run(model_id: int, job_id: str):
    try:
        res = await svc.delete_eval_run(model_id=model_id, job_id=job_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)
