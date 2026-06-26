from fastapi import APIRouter, Query, Request, UploadFile, Form, File, Body, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.responses import RedirectResponse
from pydantic import Field
from typing import Literal
import traceback
from utils.resource import response, get_user_id, get_auth
from utils.exception.exceptions import *
from utils import TYPE
import pipeline.dto as dto
import pipeline.service as svc

pipeline = APIRouter(
    prefix = "/pipelines"
)


@pipeline.get("/history/detail/{pipeline_history_id}")
async def get_pipeline_histories(pipeline_history_id : int):
    try:
        res = None
        res = await svc.get_pipeline_history(pipeline_history_id=pipeline_history_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error")

@pipeline.get("/task/system-log/download")
async def get_task_system_log_download(
    task_id: int
):
    try:
        res = None
        res = await svc.get_pipeline_task_system_log(task_id=task_id, is_download=True, count=10000)
        return res
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[]) 

   
@pipeline.get("/option/items")
async def get_option_task_items(
    workspace_id: int, 
    task_type: Literal["project", "deployment", "preprocessing"] = Query(...)
):
    try:
        res = None
        res = await svc.get_task_items(workspace_id=workspace_id, task_type=task_type)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@pipeline.get("/option/datasets")
async def get_option_datasets(
    workspace_id: int
):
    try:
        res = None
        res = await svc.get_datasets(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@pipeline.get("/option/images")
async def get_option_images(workspace_id: int):
    try:
        res = None
        res = await svc.get_images(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@pipeline.get("/option/generation-manifests")
async def get_option_generation_manifests():
    """생성형 파이프라인 노드용 외부 컨테이너 manifest 목록 (job_type=generate). WBS 1.2"""
    try:
        res = await svc.get_generation_manifests()
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@pipeline.get("/option/llm-models")
async def get_option_llm_models(workspace_id: int):
    """GenAI 통합 파이프라인 finetuning/quantize 노드용 워크스페이스 LLM 모델 목록."""
    try:
        res = await svc.get_llm_models(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@pipeline.get("/option/run-code")
async def get_option_run_codes(
    task_item_id: int, 
    task_type : Literal["project", "deployment", "preprocessing"] = Query(...)
):
    try:
        res = None
        res = await svc.get_run_code(task_item_id=task_item_id, task_type=task_type)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])    

@pipeline.get("/task/system-log")
async def get_task_system_log(
    task_id: int
):
    try:
        res = None
        res = await svc.get_pipeline_task_system_log(task_id=task_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])    


@pipeline.put("/bookmark")
async def set_pipeline_bookmark(pipeline_id : int = Body(...)):
    try:
        res = None
        user_id = get_user_id()
        res = await svc.set_bookmark_pipeline(pipeline_id=pipeline_id, header_user_id=user_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])

@pipeline.post("/task", response_model=dto.Response)
async def create_pipeline_task(body : dto.CreatePipelineTask):
    try:
        res = None
        res = await svc.create_pipeline_task(task_item_id=body.task_item_id, task_type=body.task_type, pipeline_id=body.pipeline_id, task_item_type=body.task_item_type, project_training_type=body.project_training_type, built_in_params=body.built_in_params, dataset_data_path=body.dataset_data_path,
                                             run_code=body.run_code, parameter=body.parameter, image_id=body.image_id, gpu_count=body.gpu_count,
                                             x_index=body.x_index, y_index=body.y_index)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message=e.__str__(), result=[])

@pipeline.put("/task", response_model=dto.Response)
async def update_pipeline_task_position(body : dto.UpdatePipelineTaskPosition ):
    try:
        res = None
        res = await svc.update_pipeline_task_position(task_id=body.task_id, x_index=body.x_index, x_position=body.x_position, y_index=body.y_index)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error", result=[])
    

@pipeline.delete("/task", response_model=dto.Response)
async def delete_pipelines_task(task_id : int = Body(...)):
    try:
        res = None
        res = await svc.delete_pipeline_task(task_id=task_id)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error", result=[])     


@pipeline.put("/graph", response_model=dto.Response)
async def update_pipeline_graph(body : dto.UpdateTaskGraph):
    try:
        res = None
        res = await svc.update_pipeline_graph(pipeline_id=body.pipeline_id, predecessor_task=body.predecessor_task, successor_task=body.successor_task)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error", result=[])
    
@pipeline.post("/run", response_model=dto.Response)
async def run_pipeline(pipeline_id : int = Body(...)):
    try:
        res = None
        user_id = get_user_id()
        res, _ = await svc.start_pipeline(pipeline_id=pipeline_id, start_user_id=user_id)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error", result=[])

@pipeline.post("/stop", response_model=dto.Response)
async def stop_pipeline(pipeline_id : int = Body(...)):
    try:
        res = None
        res = await svc.stop_pipeline(pipeline_id=pipeline_id)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error", result=[])


@pipeline.put("/retraining", response_model=dto.Response)
async def update_pipeline_retraining_setting(body : dto.UpdateRetrainingSetting):
    try:
        res = None
        res = await svc.update_retraining_setting(pipeline_id=body.pipeline_id, retraining_type=body.retraining_type, retraining_unit=body.retraining_unit, retraining_value=body.retraining_value)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error", result=[])


@pipeline.put("/dataset", response_model=dto.Response)
async def update_pipeline_dataset(pipeline_id : int = Body(...), dataset_id : int = Body(...)):
    try:
        res = None
        res = await svc.update_pipeline_dataset(pipeline_id=pipeline_id, dataset_id=dataset_id)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error", result=[])
    
    
@pipeline.put("/add-serial", response_model=dto.Response)
async def add_pipeline_task_serial(
    pipeline_id : int = Body(...), 
    task_type: str = Body(...), 
    y_index_base : int = Body(...)
    ):
    try:
        res = None
        res = await svc.add_pipeline_task_serial(pipeline_id=pipeline_id, task_type=task_type, y_index_base=y_index_base)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error", result=[])

@pipeline.put("/delete-serial", response_model=dto.Response)
async def delete_pipeline_task_serial(
    pipeline_id : int = Body(...), 
    task_type: str = Body(...), 
    y_index_base : int = Body(...)
    ):
    try:
        res = None
        res = await svc.delete_pipeline_task_serial(pipeline_id=pipeline_id, task_type=task_type, y_index_base=y_index_base)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error", result=[])

@pipeline.get("/healthz")
async def healthz():
    try:
        await svc.check_healthz()
        return JSONResponse(status_code=200, content={"status": "healthy"})
    except:
        return JSONResponse(status_code=500, content={"status": "not healthy"})    

@pipeline.get("/setting/{pipeline_id}", response_model=dto.PipelineResponse)
async def get_pipeline_setting(pipeline_id : int):
    try:
        res = None
        res = await svc.get_pipeline_setting(pipeline_id=pipeline_id)
        return dto.PipelineResponse(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error")

@pipeline.get("/info/{pipeline_id}", response_model=dto.PipelineInfoResponse)
async def get_pipeline_info(pipeline_id : int):
    try:
        res = None
        res = await svc.get_pipeline_detail(pipeline_id=pipeline_id)
        return dto.PipelineInfoResponse(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error")
    
@pipeline.get("/history/{pipeline_id}", response_model=dto.PipelineHistoryResponse)
async def get_pipeline_histories(pipeline_id : int):
    try:
        res = None
        res = await svc.get_pipeline_histories(pipeline_id=pipeline_id)
        # print(res)
        return dto.PipelineHistoryResponse(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error")

@pipeline.put("", response_model=dto.Response)
async def update_pipelines(body : dto.PipelineUpdate):
    try:
        res = None
        res = await svc.update_pipeline(pipeline_id=body.pipeline_id, description=body.description, access=body.access, owner_id = body.owner_id, users_id = body.users_id)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error")

@pipeline.get("", response_model=dto.PipelinesResponse)
async def get_pipelines(workspace_id : int):
    try:
        res = None
        user_id = get_user_id()
        res = await svc.get_pipelines(workspace_id=workspace_id, header_user_id = user_id )

        return dto.PipelinesResponse(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error")

@pipeline.post("", response_model=dto.Response)
async def create_pipeline(body : dto.CreatePipeline):
    try:
        res = None
        user_id = get_user_id()
        res = await svc.create_pipeline(description=body.description, workspace_id=body.workspace_id, access=body.access, 
                                        owner_id=body.owner_id,name=body.name, create_user_id=user_id, users_id=body.users_id, 
                                        type=body.type, built_in_type=body.built_in_type, built_in_sub_type=body.built_in_sub_type, 
                                        built_in_specification=body.built_in_specification, built_in_data_type=body.built_in_data_type, built_in_preprocessing_list=body.built_in_preprocessing_list)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message=e.__str__())
    
@pipeline.delete("", response_model=dto.Response)
async def delete_pipelines(pipeline_id : int = Body(...)):
    try:
        res = None
        res = await svc.delete_pipeline(pipeline_id=pipeline_id)
        return dto.Response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return dto.Response(status=0, message="server error") 