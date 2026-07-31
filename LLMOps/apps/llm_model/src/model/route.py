from fastapi import APIRouter, Request, UploadFile, Form, File, Body, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from starlette.background import BackgroundTask
from starlette.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from utils.resource import response, get_user_id, get_auth
from utils.exception.exceptions import *
import model.dto as dto
import model.service as svc
import traceback
import io
import os

model = APIRouter(
    prefix = "/models"
)

TAG_FINE_TUNING = ['FINE_TUNING']
TAG_MODEL = ['MODEL']
TAG_COMMIT_MODEL = ['COMMIT_MODEL']
TAG_OPTION = ['OPTION']

@model.get("/fine-tuning/system-log/download", summary='setting - fine tuning', tags=TAG_FINE_TUNING)
async def get_fine_tuning_system_log_download(model_id: int):
    try:
        res = None
        res = await svc.get_fine_tuning_system_log(model_id=model_id, is_download=True, count=10000)
        return res
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])   


@model.get("/option/download/default-configuration", summary='setting - fine tuning custom config format download', tags=TAG_OPTION)
async def download_default_configuration():
    try:
        # JSON 데이터 생성
        data = {
            "learning_rate" : 5e-5,
            "gradient_accumulation_steps" : 1,
            "num_train_epochs" : 3,
            "cutoff_length" : 512,
            "warmup_steps" : 0,
            "precision": "auto",
            "auto_target_modules": 1,
            "dataset_format": "auto",
            "zero_stage": 1,
            "deepspeed" : {
                        "train_batch_size": "auto",
                        "train_micro_batch_size_per_gpu": "auto",
                        "gradient_accumulation_steps": "auto",
                        "gradient_clipping":"auto",
                        "zero_allow_untested_optimizer": True,
                        "fp16": {
                            "enabled": True,
                            "loss_scale": 0,
                            "loss_scale_window": 1000,
                            "initial_scale_power": 16,
                            "hysteresis": 2,
                            "min_loss_scale": 1
                        },
                        "bf16": {
                            "enabled": False
                        },
                        "zero_optimization": {
                            "stage": 1,
                            "allgather_partitions": True,
                            "allgather_bucket_size": 5e8,
                            "overlap_comm": True,
                            "reduce_scatter": True,
                            "reduce_bucket_size": 5e8,
                            "contiguous_gradients": True,
                            "round_robin_gradients": True
                        }
                    }
        }

        # 데이터를 JSON 문자열로 변환
        json_data = json.dumps(data, ensure_ascii=False, indent=4)

        # 문자열 데이터를 파일처럼 사용 가능한 메모리 버퍼로 변환
        buffer = io.BytesIO(json_data.encode("utf-8"))

        # 클라이언트로 스트리밍 전송
        return StreamingResponse(
            buffer,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=config.json"}
        )

    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])    

@model.get("/fine-tuning/sse-graph/{model_id}", summary='graph - fine tuning', tags=TAG_FINE_TUNING)
async def sse_fine_tuning_graph( model_id : int, request : Request):
    try:
        # 접근 제어(보안 H-3): 소유자 OR 공유 모델의 워크스페이스 멤버만 학습 그래프 구독 가능.
        if not await svc.user_can_access_model(get_user_id(), model_id):
            return response(status=0, message="forbidden", result=[])
        return StreamingResponse(svc.sse_get_fine_tuning_result_graph(model_id=model_id, request=request), media_type="text/event-stream")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@model.get("/fine-tuning/sse-time/{model_id}", summary='time - fine tuning', tags=TAG_FINE_TUNING)
async def sse_fine_tuning_time( model_id : int, request : Request):
    try:
        if not await svc.user_can_access_model(get_user_id(), model_id):
            return response(status=0, message="forbidden", result=[])
        return StreamingResponse(svc.sse_get_fine_tuning_time(model_id=model_id, request=request), media_type="text/event-stream")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])


@model.get("/fine-tuning/sse-status/{model_id}", summary='status - fine tuning', tags=TAG_FINE_TUNING)
async def sse_fine_tuning_status( model_id : int, request : Request):
    try:
        if not await svc.user_can_access_model(get_user_id(), model_id):
            return response(status=0, message="forbidden", result=[])
        return StreamingResponse(svc.sse_get_fine_tuning_status(model_id=model_id, request=request), media_type="text/event-stream")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[]) 
    
@model.get("/fine-tuning/train-log", summary='log - fine tuning', tags=TAG_FINE_TUNING)
async def sse_fine_tuning_log(model_id : int):
    try:
        res = await svc.get_fine_tuning_result_logs(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])  

@model.get("/{model_id}/checkpoints", summary='list training checkpoints', tags=TAG_FINE_TUNING)
async def list_model_checkpoints(model_id: int):
    """학습 step별 체크포인트(어댑터) 레지스트리 — step·epoch·loss·grad·eval·크기·시각·best."""
    try:
        # 접근 제어(H-3): 소유자 OR 공유 모델 워크스페이스 멤버만.
        if not await svc.user_can_access_model(get_user_id(), model_id):
            return response(status=0, message="forbidden", result={"list": []})
        res = await svc.list_checkpoints(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result={"list": []})


@model.delete("/{model_id}/checkpoints/{step}", summary='delete a training checkpoint', tags=TAG_FINE_TUNING)
async def delete_model_checkpoint(model_id: int, step: int):
    """체크포인트 삭제 — step:int(경로 allowlist), active 중 차단·경로봉쇄는 서비스에서."""
    try:
        if not await svc.user_can_access_model(get_user_id(), model_id):
            return response(status=0, message="forbidden", result=False)
        res = await svc.delete_checkpoint(model_id=model_id, step=step)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=False)


@model.get("/{model_id}/commit-models/{commit_id}/checkpoints", summary='list commit checkpoints', tags=TAG_COMMIT_MODEL)
async def list_commit_model_checkpoints(model_id: int, commit_id: int):
    """커밋(버전)에 귀속된 체크포인트 스냅샷 레지스트리(Phase 2-C) — 커밋 시 commit_checkpoints/<commit>
    로 보존된 어댑터를 step·epoch·loss·grad·eval·크기·시각·best 로 나열. commit 이 model 소속인지 검증."""
    try:
        if not await svc.user_can_access_model(get_user_id(), model_id):
            return response(status=0, message="forbidden", result={"list": []})
        res = await svc.list_commit_checkpoints(model_id=model_id, commit_id=commit_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result={"list": []})


@model.delete("/{model_id}/commit-models/{commit_id}/checkpoints/{step}", summary='delete a commit checkpoint', tags=TAG_COMMIT_MODEL)
async def delete_commit_model_checkpoint(model_id: int, commit_id: int, step: int):
    """커밋 스냅샷에서 체크포인트 삭제(Phase 2-C) — step:int(allowlist), 경로봉쇄는 서비스에서.
    커밋 frozen 이라 active-gate 불요."""
    try:
        if not await svc.user_can_access_model(get_user_id(), model_id):
            return response(status=0, message="forbidden", result=False)
        res = await svc.delete_commit_checkpoint(model_id=model_id, commit_id=commit_id, step=step)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        # 큐레이션된 검증 메시지만 노출(promote 라우트와 동일 처리), 예기치 못한 예외는 generic.
        _m = str(e)
        _um = _m[len("Error:"):].strip() if _m.startswith("Error:") else "server error"
        return response(status=0, message=_um, result=False)


@model.post("/{model_id}/commit-models/{commit_id}/checkpoints/{step}/promote", summary='promote a commit checkpoint to a new version', tags=TAG_COMMIT_MODEL)
async def promote_commit_model_checkpoint(model_id: int, commit_id: int, step: int):
    """커밋의 step 체크포인트를 새 버전 `<commit>-step<step>` 으로 promote(Phase 2-C, 수동 best 적용).
    LoRA cat 델타 산술로 재머지(base 스냅샷 불요). 비파괴(새 커밋 생성, 서빙 미변경). step:int allowlist,
    user_can_access_model 게이트, commit_status RUNNING 중 거부는 서비스에서."""
    try:
        if not await svc.user_can_access_model(get_user_id(), model_id):
            return response(status=0, message="forbidden", result=False)
        res = await svc.promote_commit_checkpoint(model_id=model_id, commit_id=commit_id, step=step, create_user_id=get_user_id())
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        # 큐레이션된 사용자 검증 메시지("Error: ...", 예: 중복/이미-best/step없음)는 그대로 노출, 예기치 못한
        # 예외는 generic(내부 노출 방지). 검증 실패가 "server error" 로 뭉개져 원인 안 보이던 문제 해소.
        _m = str(e)
        _um = _m[len("Error:"):].strip() if _m.startswith("Error:") else "server error"
        return response(status=0, message=_um, result=False)


# ── SDS(external) 체크포인트 관리 (P1) — commit-scoped 내부 체크포인트와 별개로,
# external 모델의 per-step 체크포인트를 모델레벨 flat 목록으로. 서비스가 NFS 직독. ──
@model.get("/{model_id}/external-checkpoints", summary='list SDS/external checkpoints (flat)', tags=TAG_COMMIT_MODEL)
async def list_external_model_checkpoints(model_id: int):
    """SDS(external) 모델의 per-step 체크포인트 flat 목록(P1) — 커밋들의 commit_models/<c>/checkpoint-<step>/
    를 loss/grad/크기/시각/phase 태그/best 로 나열. 컨테이너 아닌 플랫폼 NFS 직독."""
    try:
        if not await svc.user_can_access_model(get_user_id(), model_id):
            return response(status=0, message="forbidden", result={"list": []})
        res = await svc.list_external_checkpoints(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result={"list": []})


@model.delete("/{model_id}/external-checkpoints/{commit_id}/{step}", summary='delete a SDS/external checkpoint', tags=TAG_COMMIT_MODEL)
async def delete_external_model_checkpoint(model_id: int, commit_id: int, step: int):
    """SDS 체크포인트 삭제 — step:int(allowlist), 경로봉쇄·best 보호는 서비스에서."""
    try:
        if not await svc.user_can_access_model(get_user_id(), model_id):
            return response(status=0, message="forbidden", result=False)
        res = await svc.delete_external_checkpoint(model_id=model_id, commit_id=commit_id, step=step)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        _m = str(e)
        _um = _m[len("Error:"):].strip() if _m.startswith("Error:") else "server error"
        return response(status=0, message=_um, result=False)


@model.post("/{model_id}/external-checkpoints/{commit_id}/{step}/best", summary='set a SDS/external checkpoint as best', tags=TAG_COMMIT_MODEL)
async def set_external_model_best_checkpoint(model_id: int, commit_id: int, step: int):
    """SDS 체크포인트 best 지정(P1: 모델레벨 마커). 실제 서빙 전환은 P2. step:int allowlist,
    경로봉쇄·commit↔model 소속 검증은 서비스에서."""
    try:
        if not await svc.user_can_access_model(get_user_id(), model_id):
            return response(status=0, message="forbidden", result=False)
        res = await svc.set_external_best_checkpoint(model_id=model_id, commit_id=commit_id, step=step)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        _m = str(e)
        _um = _m[len("Error:"):].strip() if _m.startswith("Error:") else "server error"
        return response(status=0, message=_um, result=False)


@model.post("/{model_id}/external-checkpoints/serve-best", summary='serve the best SDS/external checkpoint (P2)', tags=TAG_COMMIT_MODEL)
async def serve_external_model_best_checkpoint(model_id: int):
    """P2: best 로 지정된 SDS 체크포인트를 실행 중 infer pod 에 in-pod 로드해 서빙 전환.
    phase 게이트(projector 거부)·경로봉쇄·full envelope 구성·재로드 타임아웃(600s)은 서비스에서.
    동기 호출(재로드 1~5분) — FE 는 스피너로 응답 대기."""
    try:
        if not await svc.user_can_access_model(get_user_id(), model_id):
            return response(status=0, message="forbidden", result=False)
        res = await svc.serve_external_best_checkpoint(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        _m = str(e)
        _um = _m[len("Error:"):].strip() if _m.startswith("Error:") else "server error"
        return response(status=0, message=_um, result=False)


@model.get("/fine-tuning/system-log", summary='log - fine tuning', tags=TAG_FINE_TUNING)
async def get_fine_tuning_system_log(model_id: int):
    try:
        res = None
        res = await svc.get_fine_tuning_system_log(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])   

@model.post("/fine-tuning/stop", summary='stop - fine tuning', tags=TAG_FINE_TUNING)
async def stop_model_fine_tuning(model_id : int=Body(...)):
    try:
        res = None
        res, message = await svc.stop_fine_tuning(model_id=model_id)
        return response(status=1, result=res, message=message)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])   

@model.post("/fine-tuning/run", summary='run - fine tuning', tags=TAG_FINE_TUNING)
async def run_model_fine_tuning(body: dto.PostFineTuningRun):
    try:
        res = None
        res = await svc.running_fine_tuning(model_id=body.model_id, model_dataset_id=body.model_dataset_id, instance_count=body.instance_count,\
            instance_id=body.instance_id, gpu_count=body.gpu_count, fine_tuning_config=body.fine_tuning_config)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])  


@model.get("/fine-tuning/summary", summary='get - fine tuning', tags=TAG_FINE_TUNING)
async def get_model_fine_tuning_summary(model_id: int):
    try:
        # ModelDetailPage 가 진입 시 처음 호출하는 엔드포인트 → 상세 진입 게이트.
        # FE 는 message=='forbidden' 를 보고 목록으로 되돌린다(직접 URL 진입 방어).
        if not await svc.user_can_access_model(get_user_id(), model_id):
            return response(status=0, message="forbidden", result=None)
        res = None
        res = await svc.get_model_summary(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@model.get("/{model_id}/fine-tuning/status", summary='internal FT status (s2s poll)', tags=TAG_FINE_TUNING)
async def get_model_fine_tuning_status(model_id: int):
    # GenAI 통합 파이프라인 런타임 전용 s2s 폴링 엔드포인트 — get_auth 없음(s2s OK).
    # latest_fine_tuning_status 만 반환(경량). 사용자 UI 는 sse-status 사용.
    try:
        res = await svc.get_fine_tuning_status(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=None)

@model.get("/option/datasets",summary='setting - fine tuning', tags=TAG_OPTION)
async def get_datasets(workspace_id : int, is_mine : bool = False, dataset_name : str = None):
    try:
        res = None
        # TODO 
        # 추후 수정
        if is_mine:
            create_user_id = 2
        else:
            create_user_id = None
        res = await svc.get_dataset_list(workspace_id=workspace_id, create_user_id=create_user_id, dataset_name=dataset_name)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])


@model.get("/option/models",summary='setting - fine tuning', tags=TAG_OPTION)
async def get_datasets(workspace_id : int, search: str = None, is_mine : bool = False):
    try:
        res = None
        # TODO 
        # 추후 수정
        user_id = get_user_id()
        
        res = await svc.get_models_option(workspace_id=workspace_id, model_name=search, header_user_id=user_id, is_mine=is_mine)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@model.get("/option/commit-models",summary='setting - fine tuning', tags=TAG_OPTION)
async def get_datasets(model_id : int, search: str = None):
    try:
        res = None
        res = await svc.get_commit_models_option(model_id=model_id, commit_name=search)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])


@model.get("/option/instances",summary='setting - fine tuning', tags=TAG_OPTION)
async def get_instances(workspace_id : int):
    try:
        res = None
        res = await svc.get_instance_list(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@model.post("/option/huggingface-models",summary='setting - model', tags=TAG_OPTION)
async def get_models_by_huggingface(body : dto.PostHuggingface):
    try:
        res = None
        res = await svc.get_models_by_huggingface(model_name=body.model_name, huggingface_token=body.huggingface_token, private=body.private, model_kind=body.model_kind)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])  

@model.post("/option/huggingface-token-check",summary='setting - model', tags=TAG_OPTION)
async def check_huggingface_token(huggingface_token : str = Body(...)):
    try:
        res = None
        res = await svc.check_model_access(token=huggingface_token)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])


@model.get("/option/dataset-files",summary='setting - fine tuning', tags=TAG_OPTION)
async def get_dataset_files(dataset_id : int, search : str = None):
    """dataset file 상세 조회"""
    try:
        user_id = get_user_id()
        res = await svc.get_dataset_files_and_folders(dataset_id=dataset_id, search_user_id=user_id, search=search) 
        return response(result=res, status =1)
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e)) 
@model.post("/option/add-dataset", summary='setting - fine tuning', tags=TAG_OPTION)
async def get_model(body : dto.AddDataset):
    try:
        res = None
        res = await svc.add_dataset(model_id=body.model_id, dataset_id=body.dataset_id, training_data_path=body.training_data_path)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])
    
@model.get("/option/model-update", summary='setting - fine tuning', tags=TAG_OPTION)
async def get_model_update(model_id : int):
    try:
        res = None
        res = await svc.get_model_update(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])


@model.post("/option/upload-configuration", summary='setting - fine tuning', tags=TAG_OPTION)
async def upload_configuration(file: UploadFile = File(...), model_id : int = Form(...) ):
    try:
        res = None
        # res = await svc.add_dataset(model_id=body.model_id, dataset_id=body.dataset_id, training_data_path=body.training_data_path)
        res = await svc.upload_fine_tuning_configuration(file=file, model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])    
@model.delete("/option/model-dataset", summary='setting - fine tuning', tags=TAG_OPTION)
async def delete_model_dataset(model_dataset_id : int):
    try:
        res = None
        res = await svc.delete_model_dataset(model_dataset_id=model_dataset_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])
    
@model.delete("/option/model-configuration", summary='setting - fine tuning', tags=TAG_OPTION)
async def delete_model_configuration(model_config_id : int):
    try:
        res = None
        res = await svc.delete_model_configuration(model_config_id=model_config_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@model.get("/option/user",summary='setting - fine tuning', tags=TAG_OPTION)
async def get_users(workspace_id : int):
    try:
        res = None
        res = await svc.get_workspace_user(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@model.get("/commit-models/{commit_model_id}", summary='get - fine tuning', tags=TAG_COMMIT_MODEL)
async def get_model_commit_list(commit_model_id: int):
    try:
        res = None
        res = await svc.get_commit_model(commit_model_id=commit_model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])    
    
@model.post("/commit-models/load", summary='setting - fine tuning', tags=TAG_FINE_TUNING)
async def load_model_commit(commit_model_id: int = Body(...)):
    try:
        res = None
        res = await svc.load_commit_model(commit_model_id=commit_model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[]) 
    

@model.put("/bookmark",summary='list - model', tags=TAG_MODEL)
async def set_model_bookmark(model_id : int = Body(...)):
    try:
        res = None
        user_id = get_user_id()
        res = await svc.set_bookmark_model(model_id=model_id, header_user_id=user_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])



    
@model.get("/fine-tuning", summary='get - fine tuning', tags=TAG_FINE_TUNING)
async def get_model_fine_tuning(model_id: int):
    try:
        res = None
        res = await svc.get_model_fine_tuning(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])   
    


@model.get("/commit-models", summary='get - fine tuning', tags=TAG_COMMIT_MODEL)
async def get_model_commit_list(model_id: int):
    try:
        res = None
        res = await svc.get_commit_models(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[]) 
    


    
@model.post("/commit-models", summary='create - fine tuning', tags=TAG_COMMIT_MODEL)
async def create_model_commit(body : dto.PostModelCommit):
    try:
        res = None
        # cr = CustomResource()
        user_id = get_user_id()
        res = await svc.create_commit_model(model_id=body.model_id, commit_name=body.commit_name, commit_message=body.commit_message, create_user_id=user_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])
    
    
@model.get("/healthz")
async def healthz():
    try:
        await svc.check_healthz()
        return JSONResponse(status_code=200, content={"status": "healthy"})
    except:
        return JSONResponse(status_code=500, content={"status": "not healthy"})

    
# @model.post("/shorten")
# async def shorten_url(request: dto.URLRequest):
#     # 고유한 ID를 생성하여 단축된 URL로 사용
#     try:
#         res = None
#         # cr = CustomResource()
#         res = await svc.shorten_url(original_url=request.original_url)
#         return response(status=1, result=res)
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="server error", result=[])
 
@model.put("/detail",summary='update - model', tags=TAG_MODEL)
async def delete_model(model_id: int = Body(...), description: str = Body(...)):
    try:
        res = None
        res = await svc.update_model_description(model_id=model_id, description=description)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=None)
    
# @model.get("/{short_id}")
# async def redirect_url(short_id: str):
#     # 단축된 URL을 통해 원본 URL로 리디렉션
#     try:
#         res = None
#         # cr = CustomResource()
#         res = await svc.get_origin_url(short_id=short_id)
#         if res is None:
#             raise HTTPException(status_code=404, detail="URL not found")
#         return RedirectResponse(url=res["original_url"])
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="server error", result=[])
    
@model.get("",summary='list or single - model', tags=TAG_MODEL)
async def get_models(workspace_id: int=None, model_id: int=None):
    try:
        res = None
        user_id = get_user_id()
        # ?model_id=N → 단건 조회 (frontend ModelDetailPage 가 training_type
        # 분기를 위해 사용). workspace_id 만 주면 list 응답.
        # 목록(list)은 게이트하지 않는다 — 비공개 모델도 카드로는 보이고 진입만 막는
        # 제품 규칙(2026-07-27). 단건 조회는 상세 진입 경로라 게이트한다.
        if model_id is not None:
            if not await svc.user_can_access_model(user_id, model_id):
                return response(status=0, message="forbidden", result=None)
            res = await svc.get_model_summary(model_id=model_id)
        else:
            res = await svc.get_models(workspace_id=workspace_id, header_user_id=user_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=None)
    
@model.post("/{model_id}/ingest-checkpoint", summary='admin - ingest custom checkpoint (3.6)', tags=TAG_MODEL)
async def ingest_checkpoint(model_id: int, body: dto.IngestCheckpointBody, background: BackgroundTasks):
    """운영자 전용 — 기관 제공 커스텀 체크포인트를 by-reference 로 탑재(3.6).
    사용자 self-service 업로드 아님. 큰 pull 대비 background 실행 → 202, 완료는
    commit 목록(`GET /models/commit-models`) 폴링으로 확인."""
    # admin 게이트는 try 밖 — HTTPException(403)이 except 에서 500 으로 변질되지 않게.
    username, _ = get_auth()
    if username != 'admin':
        raise HTTPException(status_code=403, detail="admin only — operator-mediated ingestion")
    try:
        background.add_task(
            svc.ingest_external_checkpoint_safe,
            workspace_id=body.workspace_id,
            model_id=model_id,
            target_manifest_name=body.target_manifest_name,
            target_manifest_version=body.target_manifest_version,
            ref_type=body.ref_type,
            ref=body.ref,
            token=body.token,
            commit_name=body.commit_name,
            description=body.description,
            metadata=body.metadata,
        )
        return response(status=1, message="ingestion started", result={"accepted": True})
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=None)


@model.post("",summary='create - model', tags=TAG_MODEL)
async def create_models(body: dto.PostModel):
    try:
        res = None
        user_id = get_user_id()
        if body.create_user_id == 0:
            body.create_user_id = user_id
        res = await svc.create_model(
            workspace_id=body.workspace_id,
            model_name=body.model_name,
            description=body.description,
            huggingface_model_id=body.huggingface_model_id,
            users_id=body.users_id,
            commit_model_id=body.commit_model_id,
            huggingface_token=body.huggingface_token,
            create_user_id=body.create_user_id,
            private=body.private,
            access=body.access,
            training_type=body.training_type or 'internal',
            external_manifest_name=body.external_manifest_name,
            external_manifest_version=body.external_manifest_version,
            domain=body.domain,
            load_type=body.load_type,
        )
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=None)


class _ExternalJobBindBody(BaseModel):
    """Body for PATCH /models/{model_id}/external-job — links a freshly
    launched partner job_id back onto the model row so the detail page can
    reuse the existing SSE/log endpoints (which key off job_id).
    """
    model_config = {"protected_namespaces": ()}
    external_job_id: str


@model.patch("/{model_id}/external-job", summary='bind external job to model', tags=TAG_MODEL)
async def bind_external_job(model_id: int, body: _ExternalJobBindBody):
    try:
        await svc.bind_external_job(model_id=model_id, external_job_id=body.external_job_id)
        return response(status=1, result={"model_id": model_id, "external_job_id": body.external_job_id})
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=None)


class _ExternalCommitBody(BaseModel):
    """Body for POST /models/{model_id}/external-commit — 학습 종료 후 결과물을
    internal LLM 의 commit_model 패턴으로 통합한다.
    """
    model_config = {"protected_namespaces": ()}
    job_id: str
    output_subdir: str   # /output/<여기>/ — 학습 시 사용자가 지정한 checkpoint name
    partner_metadata: Optional[dict] = None
    commit_name: Optional[str] = None      # default: <output_subdir>-<job_id[:8]>
    commit_message: Optional[str] = None


@model.post("/{model_id}/external-commit", summary='commit external training artifacts', tags=TAG_MODEL)
async def commit_external_artifacts(model_id: int, body: _ExternalCommitBody):
    try:
        res = await svc.commit_external_artifacts(
            model_id=model_id,
            job_id=body.job_id,
            output_subdir=body.output_subdir,
            partner_metadata=body.partner_metadata,
            commit_name=body.commit_name,
            commit_message=body.commit_message,
        )
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


class _QuantizeBody(BaseModel):
    """Body for POST /models/{model_id}/quantize — 학습 완료 모델을 GGUF 로
    양자화하는 convert job 을 띄운다 (SP-4 / 3.9, 명시 버튼 트리거).
    target_quant 는 UI 의 Q4/Q5/Q6 에 대응 (q4/q5/q6).
    """
    model_config = {"protected_namespaces": ()}
    target_quant: str = Field(..., pattern="^q[456]$")
    target_device: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9_\- ]{1,64}$")
    prune: bool = False  # 4.7 placeholder — 실제 프루닝은 엣지 컨테이너 도착 시.


@model.get("/quantize/devices", summary='device → recommended quantization map', tags=TAG_MODEL)
async def quantize_device_recommendations():
    # 4.5 — device 선택 시 권장 Q 배지/자동제안용. 모델 비의존(정적 매핑).
    return response(status=1, result=svc.get_quantize_device_recommendations())


@model.post("/{model_id}/quantize", summary='quantize model → GGUF convert job', tags=TAG_MODEL)
async def quantize_model(model_id: int, body: _QuantizeBody):
    try:
        res = await svc.quantize_model(
            model_id=model_id,
            target_quant=body.target_quant,
            target_device=body.target_device,
            prune=body.prune,
        )
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@model.get("/{model_id}/quantize/lineage", summary='quantization lineage (history)', tags=TAG_MODEL)
async def quantize_lineage(model_id: int):
    # 4.6 — 원본 모델의 양자화 이력(원본+양자화 파라미터) 조회.
    try:
        res = await svc.list_quantize_lineage(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


class _LineageStatusBody(BaseModel):
    model_config = {"protected_namespaces": ()}
    status: str = Field(..., pattern="^(failed|cancelled)$")


@model.post("/{model_id}/quantize/{job_id}/lineage-status", summary='mark lineage failed/cancelled', tags=TAG_MODEL)
async def update_quantize_lineage_status(model_id: int, job_id: str, body: _LineageStatusBody):
    # 4.6 — convert 실패/취소를 이력에 반영(FE terminal 감지 시). 완료는 package 조회가 마감.
    try:
        res = await svc.mark_quantize_lineage(model_id=model_id, job_id=job_id, status=body.status)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@model.get("/{model_id}/quantize/{job_id}/package", summary='list porting package files', tags=TAG_MODEL)
async def list_quantize_package(model_id: int, job_id: str):
    try:
        res = await svc.list_quantize_package(model_id=model_id, job_id=job_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@model.get("/{model_id}/quantize/{job_id}/package/download", summary='download porting package (zip | ?file=)', tags=TAG_MODEL)
async def download_quantize_package(model_id: int, job_id: str, file: Optional[str] = None):
    try:
        path, filename, media = await svc.get_quantize_package_path(
            model_id=model_id, job_id=job_id, filename=file,
        )
    except ValueError as e:
        # 잘못된 filename/job_id (경로조작 등) → 400. (FE 는 blob 다운로드라 에러
        # JSON 을 200 으로 주면 파일로 저장돼버림 → HTTP 에러로 올려 catch 되게.)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=404, detail=str(e))
    # zip 은 임시파일 → 전송 후 삭제. 단일 파일(gguf 등)은 NFS 원본이라 삭제 X.
    background = None
    if media == "application/zip":
        background = BackgroundTask(lambda p=path: os.path.exists(p) and os.remove(p))
    return FileResponse(path, media_type=media, filename=filename, background=background)


class _RegisterServableBody(BaseModel):
    """Body for POST /models/{model_id}/quantize/{job_id}/register-servable — [멀티엔진
    Phase 2 C-B] 양자화 GGUF 를 llama.cpp 직접 서빙용 commit 모델로 등록. model_name
    은 helm --set/NFS 세그먼트에 들어가므로 route 단에서도 allowlist(service 재검증과 이중)."""
    model_config = {"protected_namespaces": ()}
    model_name: str = Field(..., pattern=r"^[A-Za-z0-9._-]{1,50}$")
    commit_name: Optional[str] = None
    commit_message: Optional[str] = None


@model.post("/{model_id}/quantize/{job_id}/register-servable", summary='register quantized GGUF as llama.cpp-servable commit model', tags=TAG_MODEL)
async def register_quantized_servable(model_id: int, job_id: str, body: _RegisterServableBody):
    try:
        res = await svc.register_quantized_servable(
            model_id=model_id, job_id=job_id,
            model_name=body.model_name,
            commit_name=body.commit_name,
            commit_message=body.commit_message,
        )
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


# ── SP-5 자동평가 (v0.4 3.8) ──────────────────────────────────────────────

_EVAL_ALLOWED_METRICS = {"bleu", "rouge", "perplexity"}


class _EvaluateBody(BaseModel):
    """Body for POST /models/{model_id}/evaluate — 학습 완료 모델을 평가 데이터셋으로
    채점하는 evaluate job 을 띄운다 (SP-5 / 3.8, 명시 버튼 트리거)."""
    model_config = {"protected_namespaces": ()}
    dataset_id: int = Field(..., gt=0)
    metric_set: Optional[List[str]] = Field(default=None)
    max_samples: Optional[int] = Field(default=None, gt=0, le=1000)

    @field_validator("metric_set")
    @classmethod
    def _check_metrics(cls, v):
        if v is None:
            return v
        bad = [m for m in v if m not in _EVAL_ALLOWED_METRICS]
        if bad:
            raise ValueError(f"unknown metric(s): {bad} (allowed: {sorted(_EVAL_ALLOWED_METRICS)})")
        return v


@model.post("/{model_id}/evaluate", summary='evaluate model → evaluate job (자체 메트릭)', tags=TAG_MODEL)
async def evaluate_model(model_id: int, body: _EvaluateBody):
    try:
        res = await svc.evaluate_model(
            model_id=model_id, dataset_id=body.dataset_id,
            metric_set=body.metric_set, max_samples=body.max_samples,
        )
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@model.get("/{model_id}/evaluate/results", summary='evaluation results (비교표 + best)', tags=TAG_MODEL)
async def list_eval_results(model_id: int):
    # ⑪ — 모델의 평가 이력 + 메트릭별 best 마킹(비교표). SDM 도메인 키 자유 노출.
    try:
        res = await svc.list_eval_results(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@model.get("/{model_id}/evaluate/{job_id}/result", summary='single evaluate job metrics (poll)', tags=TAG_MODEL)
async def get_eval_result(model_id: int, job_id: str):
    # FE 폴링 — metrics.json 준비되면 ready=True + eval_result lazy 마감.
    try:
        res = await svc.get_eval_result(model_id=model_id, job_id=job_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


class _EvalStatusBody(BaseModel):
    model_config = {"protected_namespaces": ()}
    status: str = Field(..., pattern="^(failed|cancelled)$")


@model.post("/{model_id}/evaluate/{job_id}/status", summary='mark eval failed/cancelled', tags=TAG_MODEL)
async def update_eval_status(model_id: int, job_id: str, body: _EvalStatusBody):
    # FE terminal(failed/cancelled) 감지 시 호출. 완료는 result 조회가 lazy 마감.
    try:
        res = await svc.mark_eval_status(model_id=model_id, job_id=job_id, status=body.status)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@model.delete("",summary='delete - model', tags=TAG_MODEL)
async def delete_model(model_id: int):
    try:
        res = None
        res = await svc.delete_model(model_id=model_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=None)
    
@model.put("",summary='put - model', tags=TAG_MODEL)
async def update_model(body: dto.PutModel):
    try:
        res = None
        res = await svc.update_model(model_id=body.model_id, description=body.description,  access=body.access, user_list=body.user_list, create_user_id=body.create_user_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=None)