"""llm_evaluation 라우터 (P1b — benchmark). 플랫폼 envelope response() 준수."""
import traceback

from fastapi import APIRouter, Header

from utils.resource import response

import evaluation.dto as dto
import evaluation.service as svc

evaluations = APIRouter(prefix="/evaluations")

TAG = ["EVALUATION"]


@evaluations.post("/benchmark", summary="benchmark 평가 런 생성", tags=TAG)
async def run_benchmark(body: dto.BenchmarkRunBody):
    try:
        res = await svc.run_benchmark(
            model_id=body.model_id, dataset_ids=body.dataset_ids,
            metric_set=body.metric_set,
        )
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
            model_id=body.model_id, dataset_ids=body.dataset_ids,
            provider=body.provider, criteria=body.criteria,
            judge_model=body.judge_model, api_key=body.api_key,
            base_url=body.base_url, custom_prompt=body.custom_prompt,
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
            model_id=body.model_id, dataset_ids=body.dataset_ids)
        return response(status=1, result=res)
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


@evaluations.post("/{model_id}/{job_id}/expert-rating", summary="전문가 채점 제출(O/X)", tags=TAG)
async def submit_expert_rating(model_id: int, job_id: str, body: dto.ExpertRatingBody,
                               jf_user: str = Header(default=None, alias="jf-User")):
    try:
        res = await svc.submit_expert_rating(
            model_id=model_id, job_id=job_id, sample_idx=body.sample_idx,
            verdict=body.verdict, comment=body.comment, rater_user=jf_user)
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


@evaluations.post("/{model_id}/{job_id}/status", summary="평가 실패/취소 마킹", tags=TAG)
async def update_eval_status(model_id: int, job_id: str, body: dto.EvalStatusBody):
    try:
        res = await svc.mark_eval_status(
            model_id=model_id, job_id=job_id, status=body.status)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)
