"""llm_evaluation 라우터 (P1b — benchmark). 플랫폼 envelope response() 준수."""
import traceback

from fastapi import APIRouter

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


@evaluations.post("/{model_id}/{job_id}/status", summary="평가 실패/취소 마킹", tags=TAG)
async def update_eval_status(model_id: int, job_id: str, body: dto.EvalStatusBody):
    try:
        res = await svc.mark_eval_status(
            model_id=model_id, job_id=job_id, status=body.status)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)
