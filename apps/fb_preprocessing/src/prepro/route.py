from fastapi import APIRouter, Depends, Body, Response, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from prepro import dto
from prepro import service as svc
from utils.resource import response, get_auth, get_user_id
from utils.exception.exceptions import *
from utils.log import logging_history_async, LogParam
from utils.msa_db import db_prepro, db_user
import traceback, time, redis
prepro = APIRouter(
    prefix = "/preprocessing"
)

TAG_TOOL = ['TOOL']
TAG_PREPROCESSING = ['PREPROCESSING']
TAG_OPTION = ['OPTION']
TAG_JOB = ['JOB']
TAG_SSE = ['SSE']


@prepro.get("/healthz")
async def healthz():
    try:
        await svc.check_healthz()
        return response(status_code=200, result={"status": "healthy"})
    except:
        return response(status_code=500, result={"status": "not healthy"})
    

@prepro.get("/job/system-log/download", tags=TAG_JOB)
async def get_job_system_log_download(job_id : int):
    try:
        res = await svc.download_job_system_log(job_id=job_id)
        return res
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))
    
@prepro.get("/job/result-log/download", tags=TAG_JOB)
async def get_job_system_log_download(job_id : int):
    try:
        res = await svc.get_built_in_result_download(job_id=job_id)
        return res
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))


@prepro.get("/option/gpu-cluster-auto", tags=TAG_OPTION)
async def get_preprocessing_gpu_cluster_auto(preprocessing_id : int, gpu_count : int):
    """training 상세 조회"""
    try:
        res = await svc.get_gpu_cluster_info_auto(preprocessing_id=preprocessing_id, gpu_count=gpu_count) 
        return response(result=res, status =1 )
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e)) 

@prepro.post("/jobs/pipeline/run", tags=TAG_JOB)
async def run_preprocessing_job(args: dto.JOBPipelinePostModel):
    """프로젝트 Training CREATE and RUN"""
    try:
        # _
        # 생성자는 추후 변경
        create_user_name = args.create_user_name 
        create_user_id = db_user.get_user(user_name=create_user_name)["id"]

        res = await svc.run_job(preprocessing_id=args.preprocessing_id, job_name=args.job_name, run_code=args.run_code, parameter=args.parameter, create_user_id=create_user_id, 
                                image_id=args.image_id, gpu_count=args.gpu_count, gpu_cluster_auto=args.gpu_cluster_auto, \
                                   gpu_auto_select=args.gpu_auto_select, gpu_select=args.gpu_select, gpu_cluster_case_old=args.gpu_cluster_case_old, \
                                       gpu_cluster_list_old=args.gpu_cluster_list_old, dataset_id=args.dataset_id, get_job_id=args.get_job_id, dataset_data_path=args.dataset_data_path, \
                                           built_in_param=args.built_in_param)
        return response(result=res, status =1 )
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))


@prepro.get("/option/job", tags=TAG_OPTION)
async def get_job_option(preprocessing_id: int):
    try:
        res = await svc.job_option(preprocessing_id=preprocessing_id)
        return response(status=1, result=res)
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))

@prepro.post("/option/gpu-cluster", tags=TAG_OPTION)
async def get_preprocessing_gpu_cluster(body : dto.GpuClusterInfoModel):
    """training 상세 조회"""
    try:
        res = await svc.get_gpu_cluster_info(preprocessing_id=body.preprocessing_id, gpu_count=body.gpu_count, gpu_select=body.gpu_select) 
        return response(result=res, status =1 )
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))   

@prepro.get("/option/tool", tags=TAG_OPTION)
async def get_prepro_tool_option(preprocessing_id : int, preprocessing_tool_id : int):
    """training 상세 조회"""
    try:
    
        res = await svc.tool_option(preprocessing_id=preprocessing_id, preprocessing_tool_id=preprocessing_tool_id) 
        return response(result=res, status =1 )
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))


@prepro.get("/sse/status", tags=TAG_SSE)
async def get_sse_status(preprocessing_id : int, request : Request): 
    """
    """
    try:
        return StreamingResponse(svc.sse_get_preprocessing_status(preprocessing_id=preprocessing_id, request=request), media_type="text/event-stream")
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))


@prepro.post("/jobs/stop", tags=TAG_JOB)
async def get_stop_job(job_id : int = Body(...)): 
    """
    """
    try:
        res = await svc.stop_job(job_id=job_id)
        return response(result=res, status =1 )
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))


@prepro.get("/job/system-log", tags=TAG_JOB)
async def get_job_system_log(job_id : int):
    try:
        res = await svc.get_job_system_log(job_id=job_id)
        return response(result=res, status =1 )
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))

@prepro.delete("/jobs/all", tags=TAG_JOB)
async def run_preprocessing_job(body : dto.PreprocessingJobModelAllDelete):
    """프로젝트 Training CREATE and RUN"""
    try:
        # _
        # 생성자는 추후 변경
        res = await svc.delete_job_all(preprocessing_id=body.preprocessing_id)
        return response(result=res, status =1 )
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))

@prepro.post("/jobs/run", tags=TAG_JOB)
async def run_preprocessing_job(args: dto.JOBPostModel):
    """프로젝트 Training CREATE and RUN"""
    try:
        # _
        # 생성자는 추후 변경
        user_id = get_user_id()
        res = await svc.run_job(preprocessing_id=args.preprocessing_id, job_name=args.job_name, run_code=args.run_code, parameter=args.parameter, create_user_id=user_id, 
                                image_id=args.image_id, gpu_count=args.gpu_count, gpu_cluster_auto=args.gpu_cluster_auto, \
                                   gpu_auto_select=args.gpu_auto_select, gpu_select=args.gpu_select, gpu_cluster_case_old=args.gpu_cluster_case_old, \
                                       gpu_cluster_list_old=args.gpu_cluster_list_old, dataset_id=args.dataset_id, get_job_id=args.get_job_id, dataset_data_path=args.dataset_data_path, \
                                           built_in_param=args.built_in_param)
        return response(result=res, status =1 )
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))

@prepro.post("/format-convert/ensure", tags=TAG_PREPROCESSING)
async def post_format_convert_ensure(args: dto.FormatConvertEnsureModel):
    """데이터셋 상세 '포맷 변환' 전용 built-in 프로젝트 find-or-create (멱등).

    FE 가 전처리 프로젝트를 고르지 않고 버튼 한 번으로 변환하도록, 워크스페이스당
    FORMAT_CONVERT 프로젝트 하나를 보장하고 preprocessing_id 를 돌려준다.
    """
    try:
        user_id = get_user_id()
        preprocessing_id = await svc.ensure_format_convert_project(workspace_id=args.workspace_id,
                                                                   owner_id=user_id, header_user_id=user_id)
        return response(status=1, result={"preprocessing_id": preprocessing_id})
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        # CustomError 는 CustomErrorList 에서 제외돼 여기로 떨어진다 — message 속성을 그대로 노출.
        error_msg = getattr(e, 'message', str(e))
        return response(status=0, message="Format convert project ensure error : {}".format(error_msg))

@prepro.post("/sds-convert/ensure", tags=TAG_PREPROCESSING)
async def post_sds_convert_ensure(args: dto.FormatConvertEnsureModel):
    """데이터셋 상세 'SDS 변환' 전용 built-in 프로젝트 find-or-create (멱등).

    포맷 변환과 같은 흐름 — FE 가 전처리 프로젝트를 따로 만들지 않고 데이터셋에서
    바로 실행하도록 워크스페이스당 SDS_LLAVA_CONVERT 프로젝트 하나를 보장한다.
    (요청 본문이 workspace_id 하나뿐이라 FormatConvertEnsureModel 을 그대로 재사용.)
    """
    try:
        user_id = get_user_id()
        preprocessing_id = await svc.ensure_sds_convert_project(workspace_id=args.workspace_id,
                                                                owner_id=user_id, header_user_id=user_id)
        return response(status=1, result={"preprocessing_id": preprocessing_id})
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        error_msg = getattr(e, 'message', str(e))
        return response(status=0, message="SDS convert project ensure error : {}".format(error_msg))

@prepro.post("/data-pipeline/ensure", tags=TAG_PREPROCESSING)
async def post_data_pipeline_ensure(args: dto.DataPipelineEnsureModel):
    """데이터 파이프라인 전용 built-in 프로젝트 find-or-create (멱등).

    파이프라인당 프로젝트 하나를 보장하고 preprocessing_id 를 돌려준다. 노드 실행은
    이 프로젝트의 잡으로 돌며 어느 노드인지는 잡의 run_code 가 구분한다.
    """
    try:
        user_id = get_user_id()
        preprocessing_id = await svc.ensure_data_pipeline_project(
            workspace_id=args.workspace_id, dp_dataset_id=args.dp_dataset_id,
            owner_id=user_id, header_user_id=user_id)
        return response(status=1, result={"preprocessing_id": preprocessing_id})
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        error_msg = getattr(e, 'message', str(e))
        return response(status=0, message="Data pipeline project ensure error : {}".format(error_msg))


@prepro.put("/tool/run", tags=TAG_TOOL)
async def run_preprocessing_tool(args: dto.ToolControlModel):
    try:
        preprocessing_tool_id = args.preprocessing_tool_id
        action = args.action
        gpu_count = args.gpu_count
        gpu_cluster_auto = args.gpu_cluster_auto
        gpu_select = args.gpu_select
        docker_image_id = args.docker_image_id
        gpu_auto_select = args.gpu_auto_select
        gpu_cluster_case_old = args.gpu_cluster_case_old
        gpu_cluster_list_old= args.gpu_cluster_list_old
        pod_per_gpu = args.pod_per_gpu
        res = await svc.control_tool(preprocessing_tool_id=preprocessing_tool_id, action=action, gpu_count=gpu_count, gpu_cluster_auto=gpu_cluster_auto, gpu_select=gpu_select, docker_image_id=docker_image_id, gpu_auto_select=gpu_auto_select, gpu_cluster_case_old=gpu_cluster_case_old, gpu_cluster_list_old=gpu_cluster_list_old, pod_per_gpu=pod_per_gpu, dataset_id=args.dataset_id)
        return response(status=1, result=res)
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))

@prepro.post("/tool/add", tags=TAG_TOOL)
async def get_preprocessing_tool_add(preprocessing_id : int = Body(...), preprocessing_tool_type : int = Body(...)):
    """training 상세 조회"""
    try:
        res = await svc.tool_add(preprocessing_id=preprocessing_id, preprocessing_tool_type=preprocessing_tool_type) 
        return response(result=res, status=1 )
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))

@prepro.get("/tool/url", tags=TAG_TOOL)
async def get_tool_url(preprocessing_tool_id : int):
    """Gets Tool URL including token for browser access."""
    try:
        res = await svc.get_tool_url(preprocessing_tool_id=preprocessing_tool_id)

        return response(result=res, status =1 )
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))

    
@prepro.get("/tool/ssh", tags=TAG_TOOL)
async def get_prepro_tool_ssh_url(preprocessing_tool_id : int):
    """training 상세 조회"""
    try:
        user_name, _ = get_auth()
        res = await svc.get_tool_ssh_jump_url(preprocessing_tool_id=preprocessing_tool_id, header_user=user_name)
        return response(result=res, status =1 )
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))   

@prepro.get("/tool", tags=TAG_TOOL)
async def get_preprocessing_tools(preprocessing_id : int):
    """
    Training Tool 목록 조회
    """
    try:    
        res = await svc.get_preprocessing_tools(preprocessing_id=preprocessing_id)

        return response(status=1, result=res)
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))

@prepro.delete("/tool", tags=TAG_TOOL)
async def get_prepro_tool_add(body : dto.PreprocessingToolModelDelete):
    """training 상세 조회"""
    try:
        res = await svc.delete_tool(preprocessing_tool_id=body.preprocessing_tool_id) 
        return response(result=res, status =1 )
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))

@prepro.delete("/jobs", tags=TAG_JOB)
async def get_jobs(body : dto.PreprocessingJobModelDelete):
    """Job 삭제"""
    try:
        res = await svc.delete_job(job_id=body.preprocessing_job_id)
        return response(result=res, status =1 )
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))


@prepro.get("/jobs", tags=TAG_JOB)
async def get_jobs(args: dto.JOBCRUDModel = Depends()):
    """Job Key - Value Page 조회"""
    try:
        page = args.page
        size = args.size
        search_key = args.search_key
        search_value = args.search_value
        sort = args.sort
        preprocessing_id = args.preprocessing_id
        res = await svc.get_jobs(search_key=search_key, size=size, page=page, search_value=search_value,
                                preprocessing_id=preprocessing_id, sort=sort)

        return response(result=res, status =1 )
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))


@prepro.get("/option", tags=TAG_OPTION)
async def get_preprocessing_create_option(workspace_id: int = None, preprocessing_id : int = None):
    try:
        
        res = await svc.preprocessing_option(workspace_id=workspace_id, preprocessing_id=preprocessing_id)
        return response(status=1, result=res)
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))

@prepro.post("/bookmark", tags=TAG_PREPROCESSING) 
async def post_preprocessing_bookmark(preprocessing_id : int = Body(...)):
    """Training Bookmark 추가"""
    try:

        user_id = get_user_id()
        res = await svc.set_bookmark_preprocessing(preprocessing_id=preprocessing_id, header_user_id=user_id)

        return response(status=1, result=res)
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))

@prepro.get("/{preprocessing_id}", tags=TAG_PREPROCESSING)
async def get_preprocessing_detail(preprocessing_id: int):
    try:
        res = await svc.get_preprocessing_info(preprocessing_id=preprocessing_id)
        return response(status=1, result=res)
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))
  
@prepro.get("", tags=TAG_PREPROCESSING)
async def get_preprocessing_list(args: dto.PreprocessingModelGET = Depends()):
    try:
        page = args.page
        size = args.size
        search_key = args.search_key
        search_value = args.search_value
        workspace_id = args.workspace_id
        sort = args.sort
        preprocessing_type = args.preprocessing_type

        user_name, _ = get_auth()
        res = await svc.get_preprocessing_list(search_key=search_key, size=size, page=page, search_value=search_value, workspace_id=workspace_id, headers_user=user_name, sort=sort, preprocessing_type=preprocessing_type)
        
        return response(status=1, result=res)
    except CustomErrorList as ce:
        return ce.response()
    except redis.exceptions.ConnectionError as e:
        return response(status=1) # TODO 임시
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown Error : {}".format(e))
    
@prepro.delete("", tags=TAG_PREPROCESSING)
async def delete_preprocessing(body : dto.PreprocessingModelDelete):
    try:
        user_id = get_user_id()
        id_list = body.id_list
        res = await svc.delete_preprocessing(user_id ,id_list)
        return response(status=1, result=res)
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Unknown error : {}".format(e))

@prepro.post("", tags=TAG_PREPROCESSING)
async def post_preprocessing(args: dto.PreprocessingModelPOST):
    try:
        preprocessing_name = args.preprocessing_name
        preprocessing_type = args.preprocessing_type
        workspace_id = args.workspace_id
        owner_id = args.owner_id
        instance_id = args.instance_id
        instance_allocate = args.instance_allocate
        access = args.access
        description = args.description
        built_in_data_type = args.built_in_data_type
        built_in_data_tf = args.built_in_data_tf
        user_list = args.user_list
        res = await svc.create_preprocessing(preprocessing_name=preprocessing_name, preprocessing_type=preprocessing_type, workspace_id=workspace_id,
                                 owner_id=owner_id, access=access, instance_id=instance_id, instance_allocate=instance_allocate, built_in_data_type=built_in_data_type,
                                 built_in_data_tf=built_in_data_tf, description=description, user_list=user_list)


        return response(status=1, result = res, message = "Created training [{}]".format(preprocessing_name))
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Create Training Error {}".format(e))

@prepro.put("", tags=TAG_PREPROCESSING)
async def put_preprocessing(args: dto.PreprocessingModelPUT):

    try:    
        preprocessing_id = args.preprocessing_id    
        user_list = args.user_list
        instance_id = args.instance_id
        instance_allocate = args.instance_allocate
        access = args.access
        description = args.description
        owner_id = args.owner_id

        user_id = get_user_id()
        res = await svc.update_preprocessing(preprocessing_id=preprocessing_id, access=access, description=description, owner_id=owner_id, instance_allocate=instance_allocate, instance_id=instance_id, user_list=user_list, header_user_id=user_id )
        return response(status=1, result=res)
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        error_msg = getattr(e, 'message', str(e))  # CustomError의 message 속성이 있으면 사용, 없으면 str(e) 사용
        return response(status=0, message="Training Update Error : {}".format(error_msg))


    



    






 