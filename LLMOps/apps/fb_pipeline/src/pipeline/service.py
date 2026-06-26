import os
import json
import asyncio
import aiofiles
import traceback
import shutil
import uuid
import math
from datetime import datetime
from fastapi import File, UploadFile, Request
from huggingface_hub import login, model_info, HfApi
from requests.exceptions import HTTPError, ConnectionError, Timeout
from typing import List, Union, Optional, Tuple
from pathlib import Path
from aiokafka import AIOKafkaProducer
from confluent_kafka.admin import AdminClient
from tensorboard.backend.event_processing import event_accumulator

from utils import redis_key, TYPE, PATH, settings, common, topic_key, kube
from utils.redis import get_redis_client_async
from utils.msa_db import db_workspace, db_pipeline, db_project, db_user, db_deployment, db_prepro
from pipeline.dto import *
from utils.crypt import session_cipher, front_cipher
# from utils.mongodb_async import urls_collection
from utils.log import logging_history_async, LogParam




"""
{
    "1" : {
        "predecessors" : [],
        "successors" : [],
    }
}


"""



async def delete_helm_pipeline(pipeline_id: int):
    try:
        namespace = settings.JF_SYSTEM_NAMESPACE
        command = f"helm uninstall {TYPE.PIPELINE_HELM_NAME.format(pipeline_id)} -n {namespace}"
        
        print(command)
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return 1, stdout
        else:
            err_msg = stderr.strip()
            if "cannot re-use a name that is still in use" in err_msg:
                return True, ""
            print(stdout)
            print(err_msg)
            print(command)
            return False, err_msg
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False, str(e)

async def check_healthz():
    redis_client = await get_redis_client_async()
    await redis_client.hgetall(redis_key.WORKSPACE_PODS_STATUS)
    return True

async def get_pipelines(workspace_id : int, header_user_id : int ) -> List[Pipelines]:
    
    pipelines = await db_pipeline.get_pipelines(workspace_id=workspace_id)
    parse = []
    for pipeline in pipelines:
        bookmark = await db_pipeline.get_favorite_pipeline(pipeline_id=pipeline["id"], user_id=header_user_id)
        private_user_list = await db_pipeline.get_pipeline_private_users(pipeline_id=pipeline["id"])
        parse.append(Pipelines(**pipeline, bookmark= 1 if bookmark else 0, private_user_list=private_user_list if private_user_list else []))
    return parse

# async def get_pipeline_info(pipeline_id : int) -> Pipeline:
#     pipeline_info = await db_pipeline.get_pipeline(pipeline_id=pipeline_id)
#     return Pipeline(**pipeline_info)

async def get_pipeline_setting(pipeline_id: int, is_get_tasks : bool = False)->Pipeline:
    pipeline_info = await db_pipeline.get_pipeline(pipeline_id=pipeline_id)
    pipeline_tasks = await db_pipeline.get_pipeline_tasks(pipeline_id=pipeline_id)
    # workspace_info = await db_pipeline.get_workspace(workspace_id=pipeline_info["workspace_id"])
    dataset_info = {}
    if pipeline_info.get("dataset_id", None):
        dataset_info = await db_pipeline.get_dataset(dataset_id=pipeline_info["dataset_id"])

    redis_client = await get_redis_client_async()
    workspace_pod_status_json = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, pipeline_info["workspace_id"])
    workspace_pod_status = {}
    if workspace_pod_status_json:
        workspace_pod_status = json.loads(workspace_pod_status_json)
    
    tasks = {
        TYPE.PREPROCESSING_TASK: [],
        TYPE.PROJECT_TASK: [],
        TYPE.DEPLOYMENT_TASK: [],
        TYPE.GENERATION_TASK: [],
        TYPE.FINETUNING_TASK: [],
        TYPE.QUANTIZE_TASK: [],
        TYPE.LLM_DEPLOY_TASK: [],
    }

    task_graph = pipeline_info.get("graph", "{}")
    if task_graph is None:
        task_graph = {}
    else:
        task_graph = json.loads(task_graph)
        
    increase_size = 0
    if pipeline_info["start_dataset_size"]:
        # dataset_path = PATH.JF_DATA_DATASET_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"], WORKSPACE_NAME=workspace_info["name"], \
        #     ACCESS=dataset_info["access"], DATASET_NAME=dataset_info["name"])
        current_size = await redis_client.hget(redis_key.DATASET_STORAGE_USAGE, pipeline_info["dataset_id"])


        
        increase_size = int(current_size) - int(pipeline_info["start_dataset_size"])

    async def process_pipeline_task(pipeline_task):
        # no-backing-table LLM 노드(generation/finetuning/quantize/llm_deploy):
        # backing item 테이블 없음 → get_task_item(SELECT FROM {task_type}) 우회.
        # task_name = built_in_params.manifest_name|model_name, status =
        # monitoring workspace_pods[task_type][external job_str_id] 버킷(있으면) 또는
        # pipeline_task.status fallback. ResponseTasks.{type}_task 버킷에 append.
        # (generation=WBS 1.2 / finetuning·quantize·llm_deploy=GenAI 통합 파이프라인)
        if pipeline_task["task_type"] in TYPE.NO_ITEM_TABLE_TASK_TYPES:
            try:
                gen_built_in = json.loads(pipeline_task.get("built_in_params") or "{}")
            except Exception:
                gen_built_in = {}
            if not isinstance(gen_built_in, dict):  # "null"→None 등 비-dict 방어(codex MED)
                gen_built_in = {}
            gen_name = (
                gen_built_in.get("manifest_name")
                or gen_built_in.get("model_name")
                or pipeline_task["task_type"]
            )
            gen_job_str_id = pipeline_task.get("task_item_job_str_id")
            gen_pod_status = {}
            if gen_job_str_id:
                gen_pod_status = workspace_pod_status.get(pipeline_task["task_type"], {}).get(str(gen_job_str_id), {})
            if gen_pod_status:
                gen_status = {
                    "status": gen_pod_status.get("status"),
                    "reason": gen_pod_status.get("reason", ""),
                }
            else:
                gen_status = {
                    "status": pipeline_task["status"] if pipeline_task["status"] == TYPE.KUBE_POD_STATUS_DONE else TYPE.KUBE_POD_STATUS_PENDING,
                    "reason": "",
                }
            tasks[TYPE.TASK_TYPES[pipeline_task["task_type"]]].append(ResponseTaskInfo(**{
                "id": pipeline_task["id"],
                "task_item_id": pipeline_task.get("task_item_id"),
                "task_item_type": pipeline_task["task_item_type"],
                "project_training_type": pipeline_task["project_training_type"],
                "task_type": pipeline_task["task_type"],
                "task_name": gen_name,
                "run_code": pipeline_task["run_code"],
                "gpu_count": pipeline_task["gpu_count"],
                "image_name": pipeline_task["image_name"],
                "parameter": common.parameter_dict_to_list(
                    common.parameter_str_to_dict(pipeline_task.get("parameter", "{}"))
                ),
                "built_in_params": common.parameter_dict_to_list(gen_built_in),
                "successors": task_graph.get(str(pipeline_task["id"]), {}).get("successors", []),
                "predecessors": task_graph.get(str(pipeline_task["id"]), {}).get("predecessors", []),
                "coordinate": PipelineTaskPosition(
                    x_index=pipeline_task.get("x_index", 0),
                    y_index=pipeline_task.get("y_index", 0),
                    x_position=pipeline_task.get("x_position", 0)
                ),
                "status": gen_status,
                "task_item_tool_status": 0
            }))
            return
        # TODO
        # 추후 수정
        task_pod_status = {}
        task_tool_status = {}
        task_item_tool_status = 0
        task_item_info = await db_pipeline.get_task_item(
                    task_item_id=pipeline_task["task_item_id"],
                    task_type=pipeline_task["task_type"]
                )
        if not task_item_info: # 해당 배포, 학습, 전처리기가 삭제 되었으면 task도 삭제
            await delete_pipeline_task(task_id=pipeline_task["id"])
            return
        image_name = None
        if pipeline_task["task_type"] == TYPE.PROJECT_TYPE:
            if pipeline_task["task_item_job_id"]:
                task_pod_status = workspace_pod_status.get(TYPE.PROJECT_TYPE, {}).get(str(pipeline_task["task_item_id"]), {})\
                    .get(TYPE.TRAINING_ITEM_A, {}).get(str(pipeline_task["task_item_job_id"]), {})
                task_tool_status = workspace_pod_status.get(TYPE.PROJECT_TYPE, {}).get(str(pipeline_task["task_item_id"]), {})\
                    .get(TYPE.TRAINING_ITEM_B, {}) 
                if task_tool_status:
                    task_item_tool_status = 1
        elif pipeline_task["task_type"] == TYPE.PREPROCESSING_TYPE:
            if pipeline_task["task_item_job_id"]:
                task_pod_status = workspace_pod_status.get(TYPE.PREPROCESSING_TYPE, {}).get(str(pipeline_task["task_item_id"]), {})\
                    .get(TYPE.PREPROCESSING_ITEM_B, {}).get(str(pipeline_task["task_item_job_id"]), {})
                task_tool_status = workspace_pod_status.get(TYPE.PREPROCESSING_TYPE, {}).get(str(pipeline_task["task_item_id"]), {})\
                    .get(TYPE.PREPROCESSING_ITEM_A, {}) 
                if task_tool_status:
                    task_item_tool_status = 1
        else:
            if pipeline_task["task_item_job_id"]:
                task_pod_status = workspace_pod_status.get(TYPE.DEPLOYMENT_TYPE, {}).get(str(pipeline_task["task_item_id"]), {})\
                    .get(str(pipeline_task["task_item_job_id"]), {})
            if task_item_info["image_id"]:
                image_info = db_project.get_image_info(image_id=task_item_info["image_id"])
                image_name = image_info["name"]
            else:
                # 빌트인 파이프라인일 경우
                project_info = await db_project.get_project_new(project_id=task_item_info["project_id"])
                built_in_model = await db_project.get_built_in_model(category=project_info["category"], name=project_info["built_in_model"])
                image_info = await db_project.get_built_in_model_image_info_by_real_name(built_in_model["image"])
                image_name = image_info["name"]
        
        if task_pod_status:
            status = {
                "status" : task_pod_status["status"],
                "reason" : task_pod_status["reason"],
            }
        else:
            status = {
                    "status" : pipeline_task["status"] if pipeline_task["status"] == TYPE.KUBE_POD_STATUS_DONE else TYPE.KUBE_POD_STATUS_PENDING,
                    "reason" : "",
                }
                
        
        ## TODO 
        # status 확인 
        # 전처리 및 학습의 경우 해당 task_item_id 를 통해 training 테이블에서 확인
        # deployment의 경우 deployment worker에서 확인
        
        task_info = ResponseTaskInfo(**{
            "id": pipeline_task["id"],
            "task_item_id": pipeline_task.get("task_item_id"),
            "task_item_type" : pipeline_task["task_item_type"],
            "project_training_type" : pipeline_task["project_training_type"],
            "task_type": pipeline_task["task_type"],
            "task_name": task_item_info["name"],
            "run_code": pipeline_task["run_code"],
            "gpu_count": pipeline_task["gpu_count"],
            "image_name": pipeline_task["image_name"] if image_name is None else image_name,
            "parameter": common.parameter_dict_to_list(
                common.parameter_str_to_dict(pipeline_task.get("parameter","{}"))
            ),
            "built_in_params" : common.parameter_dict_to_list(json.loads(pipeline_task.get("built_in_params", "{}"))),
            "successors": task_graph.get(str(pipeline_task["id"]), {}).get("successors", []),
            "predecessors": task_graph.get(str(pipeline_task["id"]), {}).get("predecessors", []),
            "coordinate": PipelineTaskPosition(
                x_index=pipeline_task.get("x_index", 0),  # 기본값을 제공하거나, 값이 있는지 확인
                y_index=pipeline_task.get("y_index", 0),
                x_position=pipeline_task.get("x_position", 0)
            ),
            "status": status,
            "task_item_tool_status" : task_item_tool_status
        })

        task_type_key = TYPE.TASK_TYPES.get(pipeline_task["task_type"])

        if task_type_key:
            tasks[task_type_key].append(task_info)

    await asyncio.gather(*(process_pipeline_task(task) for task in pipeline_tasks))

    if is_get_tasks:
        return ResponseTasks(**tasks)
    status = TYPE.KUBE_POD_STATUS_DONE
    if pipeline_info["start_datetime"] and pipeline_info["end_datetime"] is None:
        status = TYPE.KUBE_POD_STATUS_RUNNING

    return Pipeline(**{
        "increase_size" : increase_size,
        "tasks": ResponseTasks(**tasks),
        "pipeline_name": pipeline_info["name"],
        "create_datetime": pipeline_info["create_datetime"],
        "owner_name": pipeline_info["owner_name"],
        "create_user_name": pipeline_info["create_user_name"],
        "description": pipeline_info["description"],
        "retraining_config" : RetrainingConfig(**{
            "type" : pipeline_info["retraining_type"],
            "unit" : pipeline_info["retraining_unit"],
            "value" : pipeline_info["retraining_value"]
        }),
        "dataset_info" : dataset_info,
        "retraining_wait_start_time" : pipeline_info["retraining_wait_start_time"],
        "retraining_count" : pipeline_info["retraining_count"],
        "start_datetime" : pipeline_info["start_datetime"] or "",
        "end_datetime" : pipeline_info["end_datetime"] or "", 
        "status" : status
    })

async def get_pipeline_detail(pipeline_id : int) -> PipelineInfoDetail:
    pipeline_info = await db_pipeline.get_pipeline(pipeline_id=pipeline_id)
    if pipeline_info["dataset_id"] is None:
        dataset_info = DatasetInfo()
    else:
        dataset_info =DatasetInfo( **await db_pipeline.get_dataset(dataset_id=pipeline_info["dataset_id"]))
    return PipelineInfoDetail(pipeline_info=PipelineInfo(**pipeline_info), dataset_info=dataset_info, restart_setting=RetrainingConfig(type=pipeline_info["retraining_type"], unit=pipeline_info["retraining_unit"], value=pipeline_info["retraining_value"])) 


async def get_pipeline_history(pipeline_history_id : int) :
    history_info = await db_pipeline.get_pipeline_history(pipeline_history_id=pipeline_history_id)
    
    history_tasks = json.loads(history_info["pipeline_tasks"])
    
    return {
        "tasks": history_tasks
    }


async def get_pipeline_histories(pipeline_id: int)->List[PipelineHistory]:
    pipeline_histories = await db_pipeline.get_pipeline_histories(pipeline_id=pipeline_id)
    parse = [PipelineHistory(**pipeline_history) for pipeline_history in pipeline_histories]
    return parse

async def create_pipeline(name: str, workspace_id : int, access : int,
                          owner_id : int, create_user_id : int, description : str = "", 
                          users_id : List[int] = [], type : str = TYPE.PIPELINE_TYPE_A, built_in_type : str = None, built_in_sub_type : str = None, built_in_specification : str = None, built_in_data_type : str = None, built_in_preprocessing_list : list =None):

    if common.is_good_name(name=name) == False:
        raise Exception(f"Error: invalid name")
    
    if await db_pipeline.get_pipeline_duplicate_name(workspace_id=workspace_id, pipeline_name=name):
        raise Exception(f"Error: duplicate name")
    
    if type == TYPE.PIPELINE_TYPE_A:
    
        pipeline_id = await db_pipeline.create_pipeline(name=name, workspace_id=workspace_id, description=description, access=access,\
            owner_id=owner_id, create_user_id=create_user_id)
    
    else:
        # 파이프라인 생성 
        pipeline_id = await db_pipeline.create_pipeline(name=name, workspace_id=workspace_id, description=description, access=access,\
            owner_id=owner_id, create_user_id=create_user_id, type=type, built_in_type=built_in_type, built_in_sub_type=built_in_sub_type, built_in_specification=built_in_specification, built_in_data_type=built_in_data_type, built_in_preprocessing_list= json.dumps(built_in_preprocessing_list))
        
        # 워크스페이스 인스턴스 선택 
        instance_list = db_workspace.get_workspace_instance_list(workspace_id=workspace_id)
        instance_id = None 
        instance_allocate = None
        for instance in instance_list:
            if instance["instance_type"] == TYPE.INSTANCE_TYPE_GPU:
                instance_id = instance["instance_id"]
                instance_allocate = instance["instance_allocate"]
                break
        user_info = db_user.get_user(user_name=settings.ADMIN_NAME)
        
        
        # TODO 추후 하드코딩 수정
        preprocessing_task_ids = []
        for built_in_preprocessing in built_in_preprocessing_list:
            preprocessing_name = f"pipeline_{name}_Image_Augmentation"
            preprocessing_data = {
                "owner_id": owner_id,
                "instance_id": instance_id,
                "instance_allocate": 1,
                "access": 1,
                "description": "",
                "user_list": [],
                "preprocessing_name": preprocessing_name,
                "preprocessing_type": type,
                "workspace_id": workspace_id,
                "built_in_data_tf": "이미지 증강 (Image Augmentation)", # TODO 수정 # built_in_preprocessing,
                "built_in_data_type": "Image"  #built_in_data_type
            }
            res = await common.post_request("http://jfb-app-preprocessing-svc/api/preprocessing", preprocessing_data)
            preprocessing_info = await db_prepro.get_preprocessing(workspace_id=workspace_id, preprocessing_name=preprocessing_name)
            preprocessing_task_data = {
                "pipeline_id": pipeline_id,
                "run_code": None,
                "image_id": None,
                "parameter": "",
                "task_item_id": preprocessing_info["id"],
                "task_type": TYPE.PREPROCESSING_TYPE,
                "task_item_type": TYPE.PREPROCESSING_TYPE_B,
                "dataset_data_path": "preprocessing/test_result.csv",
                "built_in_params": {
                    "image_dir": "test_image",
                    "result_file_name": f"pipeline_result_{name}_file",
                    "result_dir_name" : f"pipeline_result_{name}_dir",
                    "target_answer" : "1도"
                },
                "x_index": 0,
                "y_index": 0
            }
            preprocessing_task_id =  await create_pipeline_task(**preprocessing_task_data, is_return_id=True)
            preprocessing_task_ids.append(preprocessing_task_id)
            
        project_name = f"pipeline_{name}_burn"
        project_data = {
            "project_name": project_name,
            "project_type": type,
            "workspace_id": workspace_id,
            "owner_id": owner_id,
            "access": 1,
            "description": "",
            "category": "의료 (Healthcare/Medical AI Solutions)",
            "built_in_model": "화상 심도 탐지",
            "huggingface_model_id": "Acryl-aLLM/BurnDepthAnalysisIntelligence",
            "instance_allocate": 1,
            "instance_id": instance_id
        }
        res = await common.post_request("http://jfb-app-training-svc/api/projects", project_data)
        project_info = await db_project.get_project_new(workspace_id=workspace_id, project_name=project_name)
        
        project_task_data = {
            "pipeline_id": pipeline_id,
            "task_item_id": project_info["id"],
            "task_type": TYPE.PROJECT_TYPE,
            "task_item_type": TYPE.PROJECT_TYPE_C,
            "project_training_type": "job",
            "dataset_data_path": "training/short.csv",
            "run_code": None,
            "parameter": "",
            "image_id": None,
            "gpu_count": 1,
            "built_in_params": {
                "batch": "32",
                "num_workers": "16",
                "max_epoch": "3",
                "lr": "1e-5"
            },
            "x_index": 0,
            "y_index": 0
        }
        project_task_id = await create_pipeline_task(**project_task_data, is_return_id=True)
        
        deployment_name = f"pipeline_{name}_deployment"
        deployment_data ={
            "workspace_id": workspace_id,
            "deployment_name": deployment_name,
            "owner_id": owner_id,
            "access": 1,
            "model_type": TYPE.DEPLOYMENT_TYPE_JI,
            "is_new_model_type": False,
            "project_id": project_info["id"],
            "training_type": "pipeline",
            "instance_allocate": instance_allocate,
            "instance_id": instance_id,
        }
        
        res = await common.post_request("http://jfb-app-deployment-svc/api/deployments", deployment_data)
        deployment_info = db_deployment.get_deployment(deployment_name=deployment_name, workspace_id=workspace_id)
        deployment_task_data = {
            "pipeline_id": pipeline_id,
            "task_item_id": deployment_info["id"],
            "task_type": TYPE.DEPLOYMENT_TYPE,
            "task_item_type": TYPE.DEPLOYMENT_TYPE_JI,
            "run_code": None,
            "parameter": "",
            "image_id": None,
            "gpu_count": 1,
            "x_index": 0,
            "y_index": 0
        }
        deployment_task_id = await create_pipeline_task(**deployment_task_data, is_return_id=True)
        # graph 연결
        for preprocessing_task_id in preprocessing_task_ids:
            await update_pipeline_graph(pipeline_id=pipeline_id, predecessor_task=Task(
                id = preprocessing_task_id,
                predecessors=[],
                successors=[str(project_task_id)]
            ), successor_task=Task(
                id=project_task_id,
                predecessors=[str(task_id) for task_id in preprocessing_task_ids],
                successors=[str(deployment_task_id)]
            ))
        await update_pipeline_graph(pipeline_id=pipeline_id, predecessor_task=Task(
                id = project_task_id,
                predecessors=[str(task_id) for task_id in preprocessing_task_ids],
                successors=[str(deployment_task_id)]
            ), successor_task=Task(
                id=deployment_task_id,
                predecessors=[str(project_task_id)],
                successors=[]
            ))

    
    if pipeline_id:
        
        await db_pipeline.insert_pipeline_users(pipeline_id=pipeline_id, user_ids=users_id)
            
        # LOG
        await logging_history_async(task=LogParam.Task.PIPELINE, action=LogParam.Action.CREATE, user_id=owner_id, workspace_id=workspace_id,\
            task_name=name)
        return True
    return False

async def create_pipeline_task(pipeline_id : int, task_item_id : int, task_type : str, task_item_type : str, project_training_type : str = None, run_code : str = None, parameter : str = None, dataset_data_path : str = None, built_in_params : dict ={}, image_id : int = None, gpu_count : int = 0, x_index : int = 0, y_index : int = 0, is_return_id : bool = False):
    

    # generation 노드(생성형 데이터 파이프라인)는 backing item 테이블이 없다 —
    # 외부 컨테이너 manifest 참조가 built_in_params 에 들어간다. get_task_item
    # (SELECT FROM {task_type}) 은 generation 테이블이 없어 SQL 에러나므로 건너뜀.
    if task_type in TYPE.NO_ITEM_TABLE_TASK_TYPES:
        task_item_info = None
    else:
        task_item_info = await db_pipeline.get_task_item(task_item_id=task_item_id, task_type=task_type)
    pipeline_info = await db_pipeline.get_pipeline(pipeline_id=pipeline_id)
    if task_type not in TYPE.NO_ITEM_TABLE_TASK_TYPES and not task_item_info:
        raise Exception(f"Error: Not exist {task_type} item")
    if not pipeline_info:
        raise Exception(f"Error: Not exist pipeline")
    # LLM-model-backed 노드(finetuning/quantize/llm_deploy)는 task_item_id=LLM model_id.
    # get_task_item 스킵으로 존재/소유 검증이 사라지므로, 모델 존재 + 파이프라인 워크스페이스
    # 일치를 명시 검증한다(codex HIGH: 타 워크스페이스 model 참조/실행 차단).
    if task_type in TYPE.LLM_MODEL_BACKED_TASK_TYPES:
        from utils.llm_db import db_model as llm_db_model
        model_row = await llm_db_model.get_model(model_id=task_item_id)
        if not model_row:
            raise Exception(f"Error: Not exist LLM model {task_item_id}")
        if int(model_row.get("workspace_id") or 0) != int(pipeline_info.get("workspace_id") or -1):
            raise Exception("Error: LLM model workspace mismatch")
    graph = json.loads( pipeline_info.get("graph") if pipeline_info.get("graph") else "{}")
    if task_item_type != TYPE.PROJECT_TYPE_A:
        # TODO 추후 수정
        if task_type == TYPE.PROJECT_TYPE:
            if task_item_type == TYPE.PROJECT_TYPE_C:
                built_in_model = await db_project.get_built_in_model(category=task_item_info["category"], name=task_item_info["built_in_model"])
                image_info = await db_project.get_built_in_model_image_info_by_real_name(built_in_model["image"])
                image_id = image_info["id"]
            elif task_item_type == TYPE.PROJECT_TYPE_B:
                built_in_model = await db_project.get_built_in_model(category="의료 (Healthcare/Medical AI Solutions)", name="화상 심도 탐지")
                image_info = await db_project.get_built_in_model_image_info_by_real_name(built_in_model["image"])
                image_id = image_info["id"]
        elif task_type == TYPE.PREPROCESSING_TYPE:
            image_info = await db_project.get_built_in_model_image_info_by_real_name(settings.JF_DEFAULT_UBUNTU_22_IMAGE)
            image_id = image_info["id"]
        elif task_type == TYPE.DEPLOYMENT_TYPE:
            image_id = None
    
    task_id = await db_pipeline.create_pipeline_task(pipeline_id=pipeline_id, task_item_id=task_item_id, image_id=image_id, gpu_count=gpu_count, \
        task_item_type=task_item_type, dataset_data_path=dataset_data_path, built_in_params=json.dumps(built_in_params), run_code=run_code, \
            parameter=parameter, task_type=task_type, x_index=x_index, y_index=y_index, project_training_type=project_training_type)
    if task_id:
        graph[str(task_id)] = {
            "task_type" : task_type,
            "predecessors" : [],
            "successors" : []
        }
        res = await db_pipeline.update_pipeline_graph(pipeline_id=pipeline_id, graph=json.dumps(graph))
        if is_return_id:
            return task_id
        
        return res
    return False

async def update_pipeline_task_position(task_id : int, x_position : int, x_index : int, y_index : int):
    
    res = await db_pipeline.update_pipeline_task_position(task_id=task_id, x_position=x_position, x_index=x_index, y_index=y_index)
    
    return res

async def update_pipeline_dataset(pipeline_id : int, dataset_id : int):
    res = await db_pipeline.update_pipeline_dataset(pipeline_id=pipeline_id, dataset_id=dataset_id)
    return res

async def update_pipeline_graph(pipeline_id : int, successor_task : Task, predecessor_task : Task):
    
    pipeline_info = await db_pipeline.get_pipeline(pipeline_id=pipeline_id)
    graph = json.loads(pipeline_info.get("graph", "{}"))
    
    # successor
    if graph.get(str(successor_task.id), None):
        graph[str(successor_task.id)]["successors"] = successor_task.successors
        graph[str(successor_task.id)]["predecessors"] = successor_task.predecessors
    
    # predecessors
    if graph.get(str(predecessor_task.id), None):
        graph[str(predecessor_task.id)]["successors"] = predecessor_task.successors
        graph[str(predecessor_task.id)]["predecessors"] = predecessor_task.predecessors
    print(graph)
    
    res = await db_pipeline.update_pipeline_graph(pipeline_id=pipeline_id, graph=json.dumps(graph))
    
    return res 

async def delete_pipeline(pipeline_id : int):
    # TODO
    # 해당 pipeline이 실행 중인지 확인 
    # start datetime은 있고 end datetime 이없을 경우
    
    pipeline_info = await db_pipeline.get_pipeline(pipeline_id=pipeline_id)
    
    if pipeline_info["start_datetime"] and pipeline_info["end_datetime"] is None:
        raise Exception(f"Error:Pipeline is running")
    
    res = await db_pipeline.delete_pipeline(pipeline_id=pipeline_id)
    
    return res

async def delete_pipeline_task(task_id : int):
    # TODO
    # 동작 중인지 확인 
    try:
        pipeline_task_info = await db_pipeline.get_pipeline_task(task_id=task_id)
        pipeline_info = await db_pipeline.get_pipeline(pipeline_id=pipeline_task_info["pipeline_id"])
        
        if await db_pipeline.delete_pipeline_task(task_id=task_id):
            graph = json.loads(pipeline_info.get("graph", "{}"))
            if str(task_id) in graph:
                del graph[str(task_id)]
            for key, val in graph.items():
                if str(task_id) in val["successors"]:
                    val["successors"].remove(str(task_id))
                if str(task_id) in val["predecessors"]:
                    val["predecessors"].remove(str(task_id))
                    
            res = await db_pipeline.update_pipeline_graph(pipeline_id=pipeline_task_info["pipeline_id"], graph=json.dumps(graph))
            return res
        return False
    except Exception as e:
        traceback.print_exc()
        return False

async def update_retraining_setting(pipeline_id : int, retraining_type : str, retraining_unit : str, retraining_value : int):
    # TODO 
    # 동작 중인지 확인
    res = await db_pipeline.update_pipeline_retraining(pipeline_id=pipeline_id, retraining_type=retraining_type, retraining_unit=retraining_unit, retraining_value=retraining_value)
    return res

async def add_pipeline_history(pipeline_id : int, start_datetime : str, start_user_id : int, is_retraining_setting : int):
    pipeline_info = await db_pipeline.get_pipeline(pipeline_id=pipeline_id)
    pipeline_graph = pipeline_info.get("graph", "{}")
    graph = json.loads(pipeline_graph)
    pipeline_tasks = await db_pipeline.get_pipeline_tasks(pipeline_id=pipeline_id)
    tasks = {
        TYPE.PREPROCESSING_TASK : [],
        TYPE.PROJECT_TASK : [],
        TYPE.DEPLOYMENT_TASK : [],
        TYPE.GENERATION_TASK : [],
        TYPE.FINETUNING_TASK : [],
        TYPE.QUANTIZE_TASK : [],
        TYPE.LLM_DEPLOY_TASK : [],
    }

    for task in pipeline_tasks:
        # no-backing-table LLM 노드(generation/finetuning/quantize/llm_deploy):
        # backing item 테이블 없음 → get_task_item 우회. task_name =
        # built_in_params.manifest_name|model_name. {type}_task 버킷에 기록.
        if task["task_type"] in TYPE.NO_ITEM_TABLE_TASK_TYPES:
            try:
                gen_built_in = json.loads(task.get("built_in_params") or "{}")
            except Exception:
                gen_built_in = {}
            if not isinstance(gen_built_in, dict):  # "null"→None 등 비-dict 방어(codex MED)
                gen_built_in = {}
            tasks[TYPE.TASK_TYPES[task["task_type"]]].append({
                "id": task["id"],
                "task_item_id": task.get("task_item_id"),
                "task_type": task["task_type"],
                "end_status": task["status"],
                "task_name": gen_built_in.get("manifest_name") or gen_built_in.get("model_name") or task["task_type"],
                "built_in_params": common.parameter_dict_to_list(gen_built_in),
                "task_item_type": task["task_item_type"],
                "run_code": task["run_code"],
                "gpu_count": task["gpu_count"],
                "image_name": task["image_name"],
                "successors": graph.get(str(task["id"]), {}).get("successors", []),
                "predecessors": graph.get(str(task["id"]), {}).get("predecessors", []),
                "coordinate": {
                    "x_index": task.get("x_index", 0),
                    "y_index": task.get("y_index", 0),
                    "x_position": task.get("x_position", 0)
                },
                "parameter": task["parameter"],
            })
            continue

        task_item_info = await db_pipeline.get_task_item(
                task_item_id=task["task_item_id"],
                task_type=task["task_type"]
            )
        if task_item_info:
            # tasks[task["id"]] = task_item_info["name"]
            tasks[f"{task['task_type']}_task"].append({
                "id": task["id"],
                "task_item_id": task.get("task_item_id"),
                "task_type": task["task_type"],
                "end_status" : task["status"],
                "task_name": task_item_info["name"],
                "built_in_params" : common.parameter_dict_to_list(json.loads(task["built_in_params"])),
                "task_item_type" : task["task_item_type"],
                "run_code": task["run_code"],
                "gpu_count": task["gpu_count"],
                "image_name": task["image_name"],
                "successors": graph.get(str(task["id"]), {}).get("successors", []),
                "predecessors": graph.get(str(task["id"]), {}).get("predecessors", []),
                "coordinate": {
                    "x_index" : task.get("x_index", 0),
                    "y_index" : task.get("y_index", 0),
                    "x_position" : task.get("x_position", 0)
                },
                "parameter": task["parameter"],
            })
    tasks = json.dumps(tasks)
    
    res = await db_pipeline.create_pipeline_history(pipeline_id=pipeline_id, start_datetime=start_datetime, start_user_id=start_user_id, pipeline_graph=pipeline_graph, pipeline_tasks=tasks, is_retraining_setting=is_retraining_setting)
    return res

async def start_pipeline(pipeline_id : int, start_user_id : int):
    import sys
    try:
        redis_client = await get_redis_client_async()
        #  TODO
        # retraining_wait_start_time, retraining_count 및 start_datetime 초기화
        pipeline_info = await db_pipeline.get_pipeline(pipeline_id=pipeline_id)
        if not pipeline_info:
            return False, "Error: not exist pipeline"
        # await delete_helm_pipeline(pipeline_id=pipeline_id)
        if pipeline_info["start_datetime"] and pipeline_info["end_datetime"] is None:
            return False, "Error:pipeline is running"
        start_datetime = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
        await delete_helm_pipeline(pipeline_id=pipeline_id)
        
        workspace_id = pipeline_info["workspace_id"]
        workspace_name = pipeline_info["workspace_name"]
        owner_name = pipeline_info["owner_name"]
        workspace_info = await db_pipeline.get_workspace(workspace_id=workspace_id)
        dataset_info = await db_pipeline.get_dataset(dataset_id=pipeline_info["dataset_id"])
        if not dataset_info:
            raise Exception(f"Error:not exist dataset")
        dataset_access = dataset_info["access"]
        dataset_name = dataset_info["name"]
        volume_name = workspace_info["data_storage_name"]
        # dataset_path = PATH.JF_DATA_DATASET_PATH.format(STORAGE_NAME=volume_name, WORKSPACE_NAME=workspace_name, ACCESS=dataset_access, DATASET_NAME=dataset_name)
        start_dataset_size = await redis_client.hget(redis_key.DATASET_STORAGE_USAGE, pipeline_info["dataset_id"])
        # print(dataset_path)
        if not await db_pipeline.update_pipeline_reset(pipeline_id=pipeline_id, start_datetime=start_datetime, dataset_size=start_dataset_size):
            return False, "dataset 경로가 올바르지 않음"
        await db_pipeline.update_pipeline_task_reset(pipeline_id=pipeline_id)
        
        
        pod_name = kube.PodName(workspace_name=pipeline_info["workspace_name"], item_name=pipeline_info["name"], item_type=TYPE.PIPELINE_TYPE).unique_pod_name
        image_name =settings.SYSTEM_DOCKER_REGISTRY_URL + "jfb-system/pipeline_app:dev"
        # helm 실행
        os.chdir("/app/helm")
        helm_command = f"""
            helm install {TYPE.PIPELINE_HELM_NAME.format(pipeline_id)} pipe/ \
            -n  {settings.JF_SYSTEM_NAMESPACE} \
            --set namespace={settings.JF_SYSTEM_NAMESPACE} \
            --set pod_name={pod_name} \
            --set labels.pipeline_id={pipeline_id} \
            --set labels.pod_type={TYPE.PIPELINE_TYPE} \
            --set labels.workspace_id={workspace_id} \
            --set labels.helm_name={TYPE.PIPELINE_HELM_NAME.format(pipeline_id)} \
            --set labels.owner_name={owner_name} \
            --set dataset.workspace_name={workspace_name} \
            --set dataset.access={dataset_access} \
            --set dataset.dataset_name={dataset_name} \
            --set dataset.volume_name={volume_name} \
            --set image={image_name}
        """
        process = await asyncio.create_subprocess_shell(
                helm_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            is_retraining_setting = 1 if pipeline_info["retraining_type"] else 0
            pipeline_history_id = await add_pipeline_history(pipeline_id=pipeline_id, start_datetime=start_datetime, start_user_id=start_user_id, is_retraining_setting=is_retraining_setting)
            await db_pipeline.update_pipeline_history_id(pipeline_id=pipeline_id, history_id=pipeline_history_id)
            return True, stdout
        else:
            err_msg = stderr.strip()
            print(err_msg)
            print(stdout)
            print(err_msg)
            if "cannot re-use a name that is still in use" in err_msg:
                return True, ""
            raise Exception(err_msg)
    except Exception as e:
        traceback.print_exc()
        await db_pipeline.update_pipeline_reset(pipeline_id=pipeline_id, start_datetime=None)
        await delete_helm_pipeline(pipeline_id=pipeline_id)
        print(f"An unexpected error occurred: {e}")
        return False, str(e)

async def stop_pipeline(pipeline_id : int):
    
    # TODO
    # 동작중 확인 
    redis_client = await get_redis_client_async()
    pipeline_info = await db_pipeline.get_pipeline(pipeline_id=pipeline_id)
    dataset_info = await db_pipeline.get_dataset(dataset_id=pipeline_info["dataset_id"])
    workspace_info = await db_pipeline.get_workspace(workspace_id=pipeline_info["workspace_id"])
    # dataset_path = PATH.JF_DATA_DATASET_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"], WORKSPACE_NAME=workspace_info["name"], ACCESS=dataset_info["access"], DATASET_NAME=dataset_info["name"])
    current_size = await redis_client.hget(redis_key.DATASET_STORAGE_USAGE, pipeline_info["dataset_id"])
    if pipeline_info["start_datetime"] and not pipeline_info["end_datetime"]:
        await delete_helm_pipeline(pipeline_id=pipeline_id)
        await db_pipeline.update_pipeline_stop(pipeline_id=pipeline_id, end_datetime=datetime.today().strftime("%Y-%m-%d %H:%M:%S"))
        tasks = await get_pipeline_setting(pipeline_id=pipeline_id, is_get_tasks=True)
        tasks_str = tasks.model_dump_json()
        await db_pipeline.update_pipeline_history_stop(pipeline_history_id=pipeline_info["latest_history_id"], end_datetime=datetime.today().strftime("%Y-%m-%d %H:%M:%S"), \
            increase_dataset_size= 0 if (int(current_size) - pipeline_info["start_dataset_size"]) < 0 else int(current_size) - pipeline_info["start_dataset_size"], end_status=TYPE.KUBE_POD_STATUS_STOP, \
                retraining_count=pipeline_info["retraining_count"], tasks=tasks_str)
        return True
    return False


async def add_pipeline_task_serial(pipeline_id : int, task_type : str, y_index_base : int):
    
    res = await db_pipeline.update_pipeline_task_y_index(pipeline_id=pipeline_id, task_type=task_type, y_index_base=y_index_base)
    return res

async def delete_pipeline_task_serial(pipeline_id : int, task_type : str, y_index_base : int):
    res = await db_pipeline.update_pipeline_task_y_index(pipeline_id=pipeline_id, task_type=task_type, y_index_base=y_index_base, add=False)
    return res


async def get_efk_training_logs(task_item_id : int, task_type : str, task_tool_type : str,  count : int = 100, is_all : bool = True):
    # request_log_data = {
    #         "trainingTool" : TYPE.TRAINING_ITEM_A,
    #         "trainingItemId" : training_id,
    #         "count" : count # 최근 1000개
    #     }
    request_log_data = {
            "trainingTool" : task_tool_type,  #TYPE.PREPROCESSING_ITEM_B,
            "trainingCategory" : task_type, # TYPE.PREPROCESSING_TYPE,
            "trainingItemId" : task_item_id,
            "count" : count # 최근 1000개
        }
    if is_all:
        logs = await common.post_request(url=settings.LOG_MIDDLEWARE_DNS+"/v1/training/all", data=request_log_data)
    else: 
        logs = await common.post_request(url=settings.LOG_MIDDLEWARE_DNS+"/v1/training/figure", data=request_log_data)
    return logs 

async def get_efk_worker_logs(deployment_worker_id : int, count : int = 100):
    data = {
            "count" : count,
            "deploymentWorkerId" : deployment_worker_id
        }
    logs = []
    logs = await common.post_request(url=settings.LOG_MIDDLEWARE_DNS+"/v1/deployment/all", data=data)

    return logs

# generate job 은 외부 컨테이너 — stdout(JSONL 이벤트)을 pod 에서 tail. 결과는 NFS.
GENERATION_EXTERNAL_CONTAINER_SVC = "http://jfb-app-external-container-svc/api/v1"

async def _get_generation_pod_log(job_str_id : str, count : int = 300) -> str:
    import aiohttp
    url = f"{GENERATION_EXTERNAL_CONTAINER_SVC}/jobs/{job_str_id}"
    ext = None
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status < 400:
                    ext = await r.json()
    except Exception:
        ext = None
    if not ext:
        return ""
    pod_name = ext.get("pod_name")
    namespace = ext.get("namespace")
    log = kube.get_pod_log(namespace, pod_name, tail_lines=count) if (pod_name and namespace) else None
    if log is None:
        status = (ext.get("result") or {}).get("status")
        return f"[platform] 실시간 로그 없음 (status={status or 'pending'}). 완료된 결과는 결과 데이터에서 확인하세요."
    return log

async def get_pipeline_task_system_log(task_id : int, count: int=100, is_download : bool = False):
    task_info = await db_pipeline.get_pipeline_task(task_id=task_id)
    if task_info["task_type"] == TYPE.PROJECT_TYPE:
        # job 로그 
        logs = await get_efk_training_logs(task_item_id=task_info["task_item_job_id"], count=count, task_type=task_info["task_type"], task_tool_type=TYPE.TRAINING_ITEM_A)

        logs_line = [log['fields']['log'] for log in logs["logs"]] 
        if is_download:
            task_item_info = await db_pipeline.get_task_item(task_item_id=task_info["task_item_id"], task_type=task_info["task_type"])
            return await common.text_response_generator_async(data_str="\n".join(logs_line) , filename="[PIPELINE]{}_system.log".format(task_item_info["name"]))
        return "\n".join(logs_line) 
    elif task_info["task_type"] == TYPE.PREPROCESSING_TYPE:
        logs = await get_efk_training_logs(task_item_id=task_info["task_item_job_id"], count=count, task_type=task_info["task_type"], task_tool_type=TYPE.PREPROCESSING_ITEM_B)
        logs_line = [log['fields']['log'] for log in logs["logs"]] 
        if is_download:
            task_item_info = await db_pipeline.get_task_item(task_item_id=task_info["task_item_id"], task_type=task_info["task_type"])
            return await common.text_response_generator_async(data_str="\n".join(logs_line) , filename="[PIPELINE]{}_system.log".format(task_item_info["name"]))
        return "\n".join(logs_line)
    elif task_info["task_type"] == TYPE.DEPLOYMENT_TYPE:
        logs = await get_efk_worker_logs(deployment_worker_id=task_info["task_item_job_id"], count=count)
        logs_line = [log['fields']['log'] for log in logs["logs"]]
        if is_download:
            task_item_info = await db_pipeline.get_task_item(task_item_id=task_info["task_item_id"], task_type=TYPE.DEPLOYMENT_TYPE)
            return await common.text_response_generator_async(data_str="\n".join(logs_line) , filename="[PIPELINE]{}_system.log".format(task_item_info["name"]))
        return "\n".join(logs_line)
    elif task_info["task_type"] in (TYPE.GENERATION_TYPE, TYPE.FINETUNING_TYPE, TYPE.QUANTIZE_TYPE):
        # 외부 컨테이너 job(generate/train/convert) — pod stdout tail
        # (task_item 테이블 없음, str job id 사용). llm_deploy 는 외부 str job 이 아니라 제외.
        log_text = await _get_generation_pod_log(task_info.get("task_item_job_str_id"), count=count)
        if is_download:
            return await common.text_response_generator_async(data_str=log_text, filename="[PIPELINE]{}_{}_system.log".format(task_info["task_type"], task_id))
        return log_text


async def update_pipeline(pipeline_id : int, description : str, access : int, owner_id : int, users_id : List[int] = []):
    try:
        res = await db_pipeline.update_pipeline(pipeline_id=pipeline_id, description=description, access=access, owner_id=owner_id)
        if res:
            if not access:
                private_users = await db_pipeline.get_pipeline_private_users(pipeline_id=pipeline_id)
                old_user_list = [i["user_id"] for i in private_users]
                insert_user_list = list(set(users_id) - set(old_user_list))
                delete_user_list = list(set(old_user_list) - set(users_id))
                
                for id in delete_user_list:
                    await db_pipeline.delete_pipeline_user_list(pipeline_id=pipeline_id, user_id=id)
                await db_pipeline.insert_pipeline_users(pipeline_id=pipeline_id, user_ids=insert_user_list)
            return True
        return False
    except Exception as e:
        traceback.print_exc()
        return False

async def set_bookmark_pipeline(pipeline_id : int, header_user_id : int):
    try:
        is_favorite_pipeline = await db_pipeline.get_favorite_pipeline(pipeline_id=pipeline_id, user_id=header_user_id)
        if is_favorite_pipeline:
            # 삭제
            await db_pipeline.delete_favorite_pipeline(pipeline_id=pipeline_id, user_id=header_user_id)
        else:
            # 추가 
            await db_pipeline.create_favorite_pipeline(pipeline_id=pipeline_id, user_id=header_user_id)
        return True
    except Exception as e:
        traceback.print_exc()
        return False

#################
# OPTION
#################


async def get_users(workspace_id : int):
    users = await db_pipeline.get_users(workspace_id=workspace_id)
    return users
    
async def get_datasets(workspace_id : int):
    datasets = await db_pipeline.get_datasets(workspace_id=workspace_id)
    return datasets

async def get_images(workspace_id : int):
    images = await db_pipeline.get_images(workspace_id=workspace_id)
    return images

async def get_task_items(workspace_id : int, task_type : str):
    
    if task_type == TYPE.DEPLOYMENT_TYPE:
        task_items = await db_pipeline.get_task_deployment_items(workspace_id=workspace_id)
    else:
        task_items = await db_pipeline.get_task_items(workspace_id=workspace_id, task_type=task_type)

    return task_items

async def get_generation_manifests():
    # 생성형 파이프라인 노드용 외부 컨테이너 manifest 목록 (job_type=generate). WBS 1.2
    return await db_pipeline.get_generation_manifests()

async def get_llm_models(workspace_id : int):
    # GenAI 통합 파이프라인 finetuning/quantize 노드용 워크스페이스 LLM 모델 목록.
    # llm db(jonathan_llm) 직접 조회(utils.llm_db). FE 가 노드 성격(external/internal,
    # domain)별로 필터/바인딩. external 모델은 external_manifest_name/version 으로 학습 launch.
    from utils.llm_db import db_model as llm_db_model
    rows = await llm_db_model.get_models_option(workspace_id=workspace_id)
    return [{
        "id": r.get("id"),
        "name": r.get("name"),
        "training_type": r.get("training_type"),
        "domain": r.get("domain"),
        "external_manifest_name": r.get("external_manifest_name"),
        "external_manifest_version": r.get("external_manifest_version"),
    } for r in (rows or [])]

async def get_run_code(task_item_id : int, task_type : str) -> List[str]:
    # TODO
    # 전처리기 생기면 수정
    if task_type in [TYPE.PROJECT_TYPE, TYPE.PREPROCESSING_TYPE]:
        task_info = await db_pipeline.get_task_item(task_item_id=task_item_id, task_type=task_type)
    else:
        deployment_info = await db_pipeline.get_task_item(task_item_id=task_item_id, task_type=TYPE.DEPLOYMENT_TYPE)
        if not deployment_info["project_id"]:
            return []
        task_info = await db_pipeline.get_task_item(task_item_id=deployment_info["project_id"], task_type=TYPE.PROJECT_TYPE)
    
    if task_type in [TYPE.PROJECT_TYPE, TYPE.DEPLOYMENT_TYPE]:
        code_path = PATH.JF_MAIN_PROJECT_SRC_PATH.format(STORAGE_NAME=task_info["main_storage_name"], WORKSPACE_NAME=task_info["workspace_name"], PROJECT_NAME=task_info["name"])
        run_codes , _ = await common.get_files(base_path=code_path, file_extension=["py", "sh"], ignore_folders=['datasets','.ipynb_checkpoints', 'datasets_rw', 'datasets_ro'], is_full_path=True, replace_file_path=TYPE.PROJECT_TYPE)
    else:
        code_path = PATH.JF_MAIN_PREPROCESSING_PATH.format(STORAGE_NAME=task_info["main_storage_name"], WORKSPACE_NAME=task_info["workspace_name"], PREPROCESSING_NAME=task_info["name"])
        run_codes , _ = await common.get_files(base_path=code_path, file_extension=["py", "sh"], ignore_folders=['datasets','.ipynb_checkpoints', 'datasets_rw', 'datasets_ro'], is_full_path=True, replace_file_path=TYPE.PREPROCESSING_TYPE)
    
    
    return run_codes


async def get_prepro_built_in_model_params(preprocessing_id : int):
    
    
    pass


async def get_training_built_in_model_params(project_id : int):
    pass