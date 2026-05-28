from fastapi import APIRouter, Depends, BackgroundTasks, Header, Body
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional
import traceback
from utils.resource import response
from utils import TYPE
from option import service as svc
from option import dto
import urllib.parse
# from utils.msa_db import db_user

TAG_LIST = ['List']
TAG_MODEL = ['MODEL']
TAG_ANALYZER = ['ANALYZER']
TAG_COMMON = ['COMMON']
TAG_PREPROCESSING = ['PREPROCESSING']
TAG_PROJECT = ['PROJECT']
TAG_PIPELINE = ['PIPELINE']
TAG_DEPLOYMENT = ['DEPLOYMENT']
TAG_FINE_TUNING = ['FINE_TUNING']


options = APIRouter(
    prefix = "/options"
)

from utils.redis import get_redis_client_async
from utils.redis_key import WORKSPACE_PODS_STATUS
@options.get("/healthz")
async def healthz():
    try:
        redis_client = await get_redis_client_async()
        await redis_client.hgetall(WORKSPACE_PODS_STATUS)
    
        return JSONResponse(status_code=200, content={"status": "healthy"})
    except:
        return JSONResponse(status_code=500, content={"status": "not healthy"})

# Jonathan Intelligence (built-in-models)
@options.get("/built-in-model/category/models", summary='빌트인 모델 조회: 카테고리 - 모델', tags=TAG_COMMON)
async def get_built_in_models(category : str):
    try:
        res = await svc.get_built_in_models(category)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])  

@options.get("/built-in-model/category", summary='빌트인 모델 조회: 카테고리', tags=TAG_COMMON)
async def get_categories_by_built_in_model():
    try:
        res = svc.get_built_in_model_category()
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])  
    
@options.get("/built-in-model/training", summary='빌트인 모델 조회: 학습에서 불러오기 - 학습', tags=TAG_COMMON)
async def get_project_by_built_in_model(workspace_id: int):
    try:
        res = await svc.get_built_in_models_project(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])  

# huggingface
@options.get("/huggingface/category", summary='허깅페이스 조회: 카테고리', tags=TAG_COMMON)
async def get_categories_by_model():
    try:
        res = await svc.get_categories_by_model()
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])  

@options.post("/huggingface/models", summary='허깅페이스 조회: 카테고리 - 모델', tags=TAG_COMMON)
async def get_models_by_huggingface(body : dto.HuggingfaceModelInput):
    try:
        res = None
        res = await svc.get_models_by_huggingface(model_name=body.model_name, task=body.task, huggingface_token=body.huggingface_token, private=body.private)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

@options.get("/huggingface/training", summary='허깅페이스 조회: 학습에서 불러오기 - 학습', tags=TAG_COMMON)
async def get_project_by_huggingface(workspace_id: int):
    try:
        res = None
        res = await svc.get_project_by_huggingface(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

@options.post("/huggingface-token-check", summary='허깅페이스 모델 토큰 체크', tags=TAG_COMMON)
async def check_huggingface_token(huggingface_token : str = Body(...)):
    try:
        res = await svc.check_model_access(token=huggingface_token)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

@options.get("/project/training", summary='선택한 학습내에 있는 JOB, HPS 불러오기', tags=TAG_COMMON)
async def get_project_training_list(project_id : int):
    try:
        res = await svc.get_project_job_hps_list(project_id=project_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])
    
@options.get("/built-in-model/readme/download", summary='빌트인 모델 데이터 참고', tags=TAG_COMMON)
async def get_built_in_model_readme_download(project_id : int):
    try:
        res, file_name = await svc.get_built_in_model_readme_download(project_id=project_id)
        file_name = urllib.parse.quote(file_name)
        return StreamingResponse(
        content=res,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={file_name}"}
    )
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

# User list (user list만 내려줌 (llm 카드 생성))
@options.get("/users", summary='워크스페이스 유저리스트', tags=TAG_COMMON)
async def get_workspace_user_list(workspace_id : int):
    try:
        res = await svc.get_workspace_user_list(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])


@options.get("/data", summary='파일 리스트 조회', tags=TAG_COMMON)
async def get_file_and_folder_list(workspace_id : int, path : str = "",  item_type : str = None, dataset_id : int = None, project_id : int = None, search : str = None ):
    try:
        res = await svc.get_data_file_list(workspace_id=workspace_id, path=path, item_type=item_type, dataset_id=dataset_id, project_id=project_id, search=search)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

# ================================================================================
# ANALYZER
# ================================================================================
@options.get("/analyzer/dataset", summary='분석기 그래프 추가 - 데이터셋', tags=TAG_ANALYZER)
async def get_datasets_option(workspace_id: int):
    try:
        res = await svc.get_analyzer_graph_datasets_option(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])    


@options.get("/analyzer/data", summary='분석기 그래프 추가 - 데이터셋 -> 데이터', tags=TAG_ANALYZER)
async def get_dataset_data_option(dataset_id: int, search: str = None):
    try:
        res = await svc.get_analyzer_graph_data_option(dataset_id=dataset_id, search=search)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

@options.get("/analyzer/column", summary='분석기 그래프 추가 - 데이터셋 -> 데이터 -> 컬럼', tags=TAG_ANALYZER)
async def get_analyzer_graph_column_option(dataset_id: int, file_path: str):
    try:
        res = await svc.get_analyzer_graph_column_option(dataset_id=dataset_id, file_path=file_path)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

@options.get("/analyzer", summary='분석기 - 프로젝트 생성', tags=TAG_ANALYZER)
async def get_analyzer_option(workspace_id: int):
    try:
        res = await svc.get_analyzer_option(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

# ================================================================================
# PREPROCESSING
# ================================================================================
@options.get("/preprocessing/dataset", summary='데이터셋 리스트 - 데이터셋', tags=TAG_PREPROCESSING)
async def get_datasets_option(workspace_id: int):
    try:
        res = await svc.get_analyzer_graph_datasets_option(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])    

@options.get("/preprocessing/file-list", summary='학습 - 학습 파일 조회', tags=TAG_PREPROCESSING)
async def get_preprocessing_file_list(preprocessing_id: int, is_dist : bool = False, search_index : int = 0):
    try:
        return StreamingResponse(
        await svc.get_preprocessing_run_code_data_stream(preprocessing_id, is_dist, search_index),
        media_type= "text/event-stream" # "text/plain"
    )
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

@options.get("/preprocessing/data", summary='데이터셋 데이터 - 데이터셋 -> 데이터', tags=TAG_PREPROCESSING)
async def get_dataset_data_option(dataset_id: int, search: str = None):
    try:
        # cr=CustomResource()
        res = await svc.get_dataset_data_list(dataset_id=dataset_id, search=search, hierarchy=True)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

@options.get("/preprocessing/job", summary='전처리기 - JOB 생성', tags=TAG_PREPROCESSING)
async def get_preprocessing_job_option(preprocessing_id: int):
    try:
        res = await svc.preprocessing_job_option(preprocessing_id=preprocessing_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

@options.get("/preprocessing/built-in-tfs", summary='전처리기 - 빌트인 함수 생성', tags=TAG_PREPROCESSING)
async def get_preprocessing_built_in_tfs(data_type: str):
    try:
        res = svc.get_preprocessing_built_in_data_tfs(data_type=data_type)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

@options.get("/preprocessing/update", summary='전처리기 - 생성', tags=TAG_PREPROCESSING)
async def get_preprocessing_option_update(preprocessing_id: int, workspace_id : int):
    try:
        res = await svc.preprocessing_option(workspace_id=workspace_id, preprocessing_id=preprocessing_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

@options.get("/preprocessing", summary='전처리기 - 생성', tags=TAG_PREPROCESSING)
async def get_preprocessing_option(workspace_id: int):
    try:
        res = await svc.preprocessing_option(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

# ================================================================================
# FINE TUNING
# ================================================================================
@options.get("/fine-tuning/dataset/data", summary='파인튜닝 - 데이터셋 데이터 리스트', tags=TAG_FINE_TUNING)
async def get_fine_tuning_dataset_data(dataset_id : int, search : str = None):
    try:
        extension_list = TYPE.MODEL_DATA_EXTENSIONS
        res = await svc.get_dataset_data_list(dataset_id=dataset_id, extension_list=extension_list, search=search, hierarchy=True)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

# ================================================================================
# PIPELINE
# ================================================================================

@options.get("/pipeline", summary='파이프라인 - 생성', tags=TAG_PIPELINE)
async def get_pipeline_option(workspace_id: int, pipeline_id : int = None):
    try:
        res = await svc.get_pipeline_option(workspace_id=workspace_id, pipeline_id=pipeline_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

@options.get("/pipeline/built-in", summary='파이프라인 빌트인 분야- 조회', tags=TAG_PIPELINE)  
async def get_pipeline_built_in_option(built_int_type : str):
    try:
        res = await svc.get_pipeline_built_in_list(built_in_type=built_int_type)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

# ================================================================================
# PROJECT
# ================================================================================

@options.get("/project/hps", summary='학습 - HPS 생성', tags=TAG_PROJECT)
async def get_project_hps_option(project_id: int):
    try:
        res = await svc.get_project_hps_option(project_id=project_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])
    
@options.get("/project/job", summary='학습 - JOB 생성', tags=TAG_PROJECT)
async def get_project_job_option(project_id: int):
    try:
        res = await svc.get_project_job_option(project_id=project_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

@options.get("/project/tool", summary='학습 - 도구 생성', tags=TAG_PROJECT)
async def get_project_option(project_id: int, project_tool_id : int):
    try:
        res = await svc.get_tool_option(project_id=project_id, project_tool_id=project_tool_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])
    
@options.get("/project/file-list", summary='학습 - 학습 파일 조회', tags=TAG_PROJECT)
async def get_project_file_list(project_id: int, is_dist : bool = False, search_index : int = 0):
    try:
        return StreamingResponse(
        await svc.get_project_run_code_data_stream(project_id, is_dist, search_index),
        media_type= "text/event-stream" # "text/plain"
    )
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])


@options.get("/project", summary='학습 - 생성', tags=TAG_PROJECT)
async def get_project_option(workspace_id: int):
    try:
        res = await svc.get_project_option(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=[])

# ================================================================================
# DEPLOYMENT
# ================================================================================

@options.get("/deployment/list", summary="배포 리스트", tags=TAG_DEPLOYMENT)
async def get_deplyment_list_in_workspace(workspace_id : int):
    try:
        res = await svc.get_deployment_in_workspace(workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))
    
    
# @options.get("/healthz")
# async def healthz():
#     if await svc.check_healthz():
#         return JSONResponse(status_code=200, content={"status": "healthy"})
#     else:
#         return JSONResponse(status_code=500, content={"status": "not healthy"})