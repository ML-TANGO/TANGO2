from fastapi import Request
from fastapi.responses import FileResponse, StreamingResponse
from utils.resource import response
from utils import (
    TYPE, PATH, common, settings
)
from utils.redis import get_redis_client_async, add_data_to_stream
# from utils.TYPE import *
from utils import (
    redis_key, topic_key, workspace_resource, TYPE_BUILT_IN
)
from utils.exception.exceptions import *
# from utils.access_check import check_training_access_level
from utils.msa_db import (
    db_prepro, db_image, db_workspace, db_user, db_dataset, db_deployment
)
if settings.LLM_USED:
    from utils.llm_db import db_model
from utils.kube import PodName
from utils.crypt import session_cipher, front_cipher
from prepro.dto import PreprocessingTool, PreprocessingJob
from utils.log import logging_history_async, LogParam

from typing import List, Dict, Tuple
from datetime import datetime
from collections import defaultdict, Counter, OrderedDict
from math import gcd
from pathlib import Path
from functools import reduce
from concurrent.futures import ThreadPoolExecutor
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
from aiokafka import AIOKafkaProducer
# from kubernetes_asyncio import config, client, stream
import kubernetes
from kubernetes import config, stream
import traceback
import os
import re
import time
import json
import subprocess
import random
import string
import asyncio
import aiofiles
import datetime
import requests
from io import StringIO
import csv

"""
vscode 오류 

- 이미지 버전이 낮을 경우 (ubuntu 18 이하)
   시스템 에러 로그 : /usr/lib/code-server/lib/node: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.28' not found (required by /usr/lib/code-server/lib/node)


이미지 자체 오류 

- 이미지에서 GPU를 요청할 경우 pod의 GPU 0개일 때 발생 POD StartError
  event message : failed to create containerd task: failed to create shim task: OCI runtime create failed: runc create failed: unable to start container process: error during container init: error running hook #0: error running hook: exit status 1, stdout: , stderr: nvidia-container-cli.real: device error: MIG-6f3175be-aa1c-54bf-8428-227b48672926: unknown device: unknown  


"""

def get_training_log_guide():
    log_guide = """
for epoch in range(EPOCHS):
    # 필수 값 : iteration (그래프의 x 축 설정 값)
    # 사라지는 필드 값 : log, timestamp
    # 반드시 json 포맷으로 작성해 주세요.
    print(f'[FLIGHTBASE] {{ "iteration_key" : "epoch"  , "epoch" : {epoch} , "loss": {loss}, "parameter1": {value1}, "parameter2": {value2} ... }}')


# 출력 예시
[FLIGHTBASE] { "iteration_key" : "epoch", "epoch" : 1 , "Loss": 0.021136578172445297 }

[FLIGHTBASE] { "iteration_key" : "epoch", "epoch" : 2 , "Loss": 0.0035603351425379515 }

[FLIGHTBASE] { "iteration_key" : "epoch", "epoch" : 3 , "Loss": 0.051356758922338486 }

...

        """
    return log_guide



async def check_healthz():
    redis_client = await get_redis_client_async()
    await redis_client.hgetall(redis_key.WORKSPACE_PODS_STATUS)
    return True
    


# KAFKA
conf = {
            'bootstrap.servers' : settings.JF_KAFKA_DNS
        }


#======================================================
# UTILS
#======================================================

def get_domain():
    if settings.EXTERNAL_HOST_REDIRECT:
        return settings.EXTERNAL_HOST
    return f"{settings.EXTERNAL_HOST}:{settings.EXTERNAL_HOST_PORT}"

# 새로운 스레드 풀 생성
custom_executor = ThreadPoolExecutor(max_workers=5)

def get_pod_event_logs_sync(pod_name : str , namespace: str = "default") -> list:
    config.load_kube_config(config_file=settings.KUBER_CONFIG_PATH)
    coreV1Api = kubernetes.client.CoreV1Api()
    field_selector = f"involvedObject.name={pod_name},involvedObject.namespace={namespace}"
    events = coreV1Api.list_namespaced_event(namespace, field_selector=field_selector)
    return events.items

async def create_preprocessing_folder(workspace_name: str, preprocessing_name: str, storage_name: str) -> bool:
    """
    비동기적으로 전처리 폴더를 생성하는 함수.

    Args:
        workspace_name (str): 작업 공간 이름.
        preprocessing_name (str): 전처리 이름.
        storage_name (str): 저장소 이름.

    Returns:
        bool: 폴더 생성 성공 여부.
    """
    preprocessing_dir_new = Path(
        PATH.JF_MAIN_PREPROCESSING_PATH.format(
            STORAGE_NAME=storage_name,
            WORKSPACE_NAME=workspace_name,
            PREPROCESSING_NAME=preprocessing_name
        )
    )

    try:
        # 디렉터리 생성
        preprocessing_dir_new.mkdir(parents=True, exist_ok=True)
    except Exception:
        # 예외 발생 시 로그 출력 및 폴더 삭제 후 재시도
        traceback.print_exc()
        try:
            await asyncio.to_thread(common.rm_rf, preprocessing_dir_new)
            preprocessing_dir_new.mkdir(parents=True, exist_ok=True)
        except Exception:
            traceback.print_exc()
            return False

    return True

async def delete_preprocessing_folder(workspace_name: str, preprocessing_name: str, storage_name: str):
    """
    비동기적으로 전처리 폴더를 삭제하는 함수. subprocess를 사용하여 rm -rf 명령 실행.

    Args:
        workspace_name (str): 작업 공간 이름.
        preprocessing_name (str): 전처리 이름.
        storage_name (str): 저장소 이름.

    Returns:
        tuple: (bool, str) 삭제 성공 여부 및 에러 메시지.
    """
    preprocessing_dir = Path(
        PATH.JF_MAIN_PREPROCESSING_PATH.format(
            STORAGE_NAME=storage_name,
            WORKSPACE_NAME=workspace_name,
            PREPROCESSING_NAME=preprocessing_name
        )
    )

    try:
        # subprocess를 사용하여 rm -rf 실행
        process = await asyncio.create_subprocess_exec(
            'rm', '-rf', str(preprocessing_dir),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise Exception(stderr.decode().strip())
    except Exception as e:
        traceback.print_exc()
        return False, str(e)

    return True, ""

async def parse_file_to_list(file_path: str, total_gpu: int) -> list:
    result = []
    try:
        async with aiofiles.open(file_path, 'r') as file:
            lines = await file.readlines()
            pod_count = len(lines)
            gpu_per_pod = int(total_gpu / pod_count) if total_gpu else 0
            for line in lines:
                parts = line.strip().split()
                ip = parts[0]
                result.append({"ip": ip, "gpu_count": gpu_per_pod, "index": parts[2]})
        return result
    except Exception as e:
        print(f"An error occurred: {e}")
        return []
    
def get_commit_image_installing_status(preprocessing_tool_id : int):
    """
    input:
        tool_id : commit한 training tool id
    output:
        True : commit 완료 O
        False : commit 완료 X
    """
    try:
        # TODO 추후 수정
        image_info = db_image.get_installing_commit_image_list(tool_id=preprocessing_tool_id)
        if image_info:
            if image_info.get("status") == TYPE.IMAGE_STATUS_PENDING or image_info.get("status") == TYPE.IMAGE_STATUS_INSTALLING:
                return True
        return False
    except Exception as e:
        traceback.print_exc()
        return None

def function_info_list(tool_type):
        type_list = TYPE.TOOL_DEFAULT_FUNCTION_LIST[tool_type]
        f_l = []
        for type_ in type_list:
            f_l.append({"type": type_})
        return f_l

def exec_pod_sync(name : str, command: list, namespace="default"):
    """
    command는 list 형태로 들어와야함
    example)
        command = ['jupyter', 'lab', 'list']
        command = exec_cmd : ['/bin/sh', '-c', 'echo "http://....." > /tmp/jupyter-url-token'
    """
    config.load_kube_config(config_file=settings.KUBER_CONFIG_PATH)
    coreV1Api = kubernetes.client.CoreV1Api()
    print(f"namespace : {namespace}, pod_name : {name}")
    res = stream.stream(coreV1Api.connect_get_namespaced_pod_exec,
                name=name, namespace=namespace, command=command,
                stdout=True, stderr=True, stdin=False, tty=False)
    return res

async def exec_pod(name: str, command: list, namespace: str = "default"):
    # Use asyncio to run the synchronous function in a thread pool
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(custom_executor, exec_pod_sync, name, command, namespace)
    return res


async def get_preprocessing_used_gpu_count(preprocessing_id : int)-> dict:
    """
    해당 project에서 실제 사용중 과 pending에 걸려있는 gpu 수
    """
    preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_id)
    used_gpus = 0
    pending_gpus = 0
    preprocessing_total_gpu = preprocessing_info["gpu_allocate"] * preprocessing_info["instance_allocate"]
    # TOOL
    tools = await db_prepro.get_preprocessing_tools(preprocessing_id=preprocessing_id)
    for tool in tools:
        if tool["request_status"] == 1:
            if tool["start_datetime"]:
                used_gpus += tool["gpu_count"]
            else:
                pending_gpus += tool["gpu_count"]
    # jobs
    jobs = await db_prepro.get_jobs_is_request(preprocessing_id=preprocessing_id)
    
    for job in jobs:
        if job["start_datetime"]:
            used_gpus += job["gpu_count"]
        else:
            pending_gpus += job["gpu_count"]
            
    return {
            "used_gpu_count": used_gpus,
            "pending_gpu_count" : pending_gpus,
            "preprocessing_total_gpu" : preprocessing_total_gpu,
            "available_gpu_count" : preprocessing_total_gpu - used_gpus - pending_gpus
        }

def extract_ip_or_dns(address):
    # 정규 표현식을 사용하여 IP 주소 또는 DNS 이름 부분만 추출
    match = re.match(r'([a-zA-Z0-9.-]+)(:\d+)?', address)
    if match:
        return match.group(1)
    return address

def check_gpu_select(gpu_select : list, pod_per_gpu: int):
    
    nodes = defaultdict(int)
    for node in gpu_select:
        nodes[node["node_name"]] += 1
        
    for gpu_select_count_by_node in nodes.values():
        if gpu_select_count_by_node < pod_per_gpu:
            raise Exception("Correct the number of gpu per pod")

async def get_gpu_cluster_info_auto(preprocessing_id : int, gpu_count : int, show_gpu_cluster_info : bool = False ):
    redis_client = await get_redis_client_async()
    preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_id)
    workspace_gpu_status = await workspace_resource.get_workspace_usage_gpu_count_by_instance(instance_id=preprocessing_info["instance_id"], workspace_id=preprocessing_info["workspace_id"])
    gpu_cluster_info = await common.get_gpu_cluster_info(instance_id=preprocessing_info["instance_id"], redis_client=redis_client)
    if TYPE.RESOURCE_TYPE_MIG in preprocessing_info["instance_name"]:
        gpu_cluster_cases = [{
                "gpu_count" : 1,
                "server" : gpu_count,
                "status" : None
            }]
    else:
        gpu_cluster_cases = await common.get_auto_gpu_cluster(redis_client=redis_client, instance_id=preprocessing_info["instance_id"], gpu_count=gpu_count, gpu_cluster_info=gpu_cluster_info)
    
    for gpu_cluster_case in gpu_cluster_cases:
        
        if gpu_cluster_case["status"] and (workspace_gpu_status["available_gpu_count"]-workspace_gpu_status["pending_gpu_count"]) < gpu_count:
            gpu_cluster_case["status"] = False 
    if show_gpu_cluster_info:
        return {
            "gpu_cluster_cases" : gpu_cluster_cases,
            "gpu_cluster_list" : gpu_cluster_info
        }
    return gpu_cluster_cases

async def delete_tool_helm(preprocessing_tool_type: str, preprocessing_tool_id: int, workspace_id : int):
    try:
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
        command = f"helm uninstall {TYPE.PREPROCESSING_HELM_CHART_NAME.format(preprocessing_tool_id, preprocessing_tool_type)} -n {namespace}"
        
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


async def set_bookmark_preprocessing(preprocessing_id : int, header_user_id : int):
    try:
        is_favorite_preprocessing = await db_prepro.get_favorite_preprocessing(preprocessing_id=preprocessing_id, user_id=header_user_id)
        if is_favorite_preprocessing:
            # 삭제
            await db_prepro.delete_favorite_preprocessing(preprocessing_id=preprocessing_id, user_id=header_user_id)
        else:
            # 추가 
            await db_prepro.create_favorite_preprocessing(preprocessing_id=preprocessing_id, user_id=header_user_id)
        return True
    except Exception as e:
        traceback.print_exc()
        return False

def job_status_parse(job_info : dict , job_status : dict):
    status = {}
    if job_info["end_datetime"]:
        status = {
            "status" : job_info["end_status"],
            "reason" : job_info["error_reason"],
            "message" : ""
        }
    elif not job_info["start_datetime"] and str(job_info["id"]) not in job_status:
        status = {
            "status" : TYPE.KUBE_POD_STATUS_PENDING,
            "reason" : "",
            "message" : ""
        }
    elif job_info["start_datetime"] and str(job_info["id"]) not in job_status: # 시작 기록은 있지만 redis에 상태 값이 업로드 되기 전
        status = {
            "status" : TYPE.KUBE_POD_STATUS_INSTALLING,
            "reason" : "",
            "message" : ""
        }
    elif str(job_info["id"]) in job_status:
        status = {
            "status" : job_status[str(job_info["id"])]["status"],
            "reason": job_status[str(job_info["id"])]["reason"],
            "message": job_status[str(job_info["id"])]["resolution"]
        }
    else:
        status = {
            "status" : TYPE.KUBE_POD_STATUS_PENDING,
            "reason" : job_info["pending_reason"],
            "message" : ""
        }
        
    return status



async def get_efk_job_logs(job_id : int, count : int = 100, is_all : bool = True):
    request_log_data = {
            "trainingTool" : TYPE.PREPROCESSING_ITEM_B,
            "trainingCategory" : TYPE.PREPROCESSING_TYPE,
            "trainingItemId" : job_id,
            "count" : count # 최근 1000개
        }
    if is_all:
        logs = await common.post_request(url=settings.LOG_MIDDLEWARE_DNS+"/v1/training/all", data=request_log_data)
    else: 
        logs = await common.post_request(url=settings.LOG_MIDDLEWARE_DNS+"/v1/training/figure", data=request_log_data)
    return logs 

async def get_file_list_from_src(file_extension: list, workspace_name: str, preprocessing_name: str, storage_name: str, ignore_folders: list = None ):
    if type(file_extension) != list:
        file_extension = [file_extension]
        
    if ignore_folders is None:
        ignore_folders = ['datasets','.ipynb_checkpoints', 'datasets_rw', 'datasets_ro']
        
    
    training_src_path_new = PATH.JF_MAIN_PREPROCESSING_PATH.format(STORAGE_NAME=storage_name, WORKSPACE_NAME=workspace_name, PREPROCESSING_NAME=preprocessing_name)
    
    return await common.get_files(base_path=training_src_path_new, file_extension=file_extension, ignore_folders=ignore_folders)

async def get_pod_event_logs(pod_name : str , namespace: str = "default"):
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(custom_executor, get_pod_event_logs_sync, pod_name, namespace)
    return res

def convert_str_to_num(s):
    try:
        # 먼저 int로 변환 시도
        if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
            return int(s)
        # float로 변환 시도
        elif '.' in s:
            return float(s)
        else:
            raise ValueError("해당 문자열은 숫자로 변환할 수 없습니다.")
    except ValueError as e:
        return None

def get_logs_metric_parser(logs: List[Dict]) -> Tuple[Dict[str, List], Dict[str, List], List[str]]:
    metrics_data = defaultdict(list)
    logs_line = []
    iteration_key = None
    iteration_value = []
    
    for log in logs:
        fields = log.get("fields", {})
        if iteration_key is None and fields.get("iteration_key", None):
            iteration_key = fields.get("iteration_key")
        for param_key, value in fields.items():
            if param_key == "log":
                logs_line.append(value)
            elif iteration_key == param_key:
                iteration_value.append(convert_str_to_num(value))
            elif param_key not in ("timestamp", "iteration_key"):
                metrics_data[param_key].append(value)
    
    metrics_info = {
        "x":  {"label": iteration_key, "value": iteration_value},
        "key_order": list(metrics_data.keys())  # dict_keys 객체를 리스트로 변환
    }
    
    return metrics_data, metrics_info, logs_line


async def get_job_system_log(job_id : int, count : int = 100):

    logs = await get_efk_job_logs(job_id=job_id, count=count)

    logs_line = [log['fields']['log'] for log in logs["logs"]] 
    return "\n".join(logs_line) 


async def download_job_system_log(job_id : int):
    job_info = await db_prepro.get_job(job_id=job_id)
    lines = await get_job_system_log(job_id=job_id, count=5000)
    return await common.text_response_generator_async(data_str=lines, filename="[Training]{}_system.log".format(job_info["name"]))

   

#=======================================================
# GET LIST
#=======================================================

async def get_preprocessing_list_user(headers_user : str, workspace_id : int, search_key=None, size=None, page=None, search_value=None,
                sort=None, preprocessing_type=None):
    redis_client = await get_redis_client_async()
    user_info = db_user.get_user(user_name=headers_user)

    if user_info is None:
        return response(status=1, message="OK", result={"list": [], "total": 0})


    user_preprocessing_bookmark_list = {tb["preprocessing_id"] for tb in await db_prepro.get_user_preprocessing_bookmark_list(user_id=user_info["id"])}


    preprocessing_list = await db_prepro.get_preprocessing_list(search_key=search_key, search_value=search_value, size=size, page=page,
                                        workspace_id=workspace_id, sort=sort, preprocessing_type=preprocessing_type)

    
    redis_workspace_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, workspace_id) 
    
    if redis_workspace_pod_status is None:
        redis_workspace_pod_status = {}
    else:
        redis_workspace_pod_status = json.loads(redis_workspace_pod_status)
    preprocessing_status = redis_workspace_pod_status.get(TYPE.PREPROCESSING_TYPE, {})
    workspace_info = await db_workspace.get_workspace_async(workspace_id=workspace_id)
    async def process_preprocessing(preprocessing):
        preprocessing_tools_db = await db_prepro.get_preprocessing_tools(preprocessing_id=preprocessing["id"])
        project_pod_status = preprocessing_status.get(str(preprocessing["id"]), {})
        project_tools_status = project_pod_status.get(TYPE.TRAINING_ITEM_B, {})
        user_list = [user["id"] for user in await db_prepro.get_preprocessing_user_list(preprocessing_id=preprocessing["id"])]
        user_list.append(workspace_info["manager_id"])
        preprocessing["instance_info"] = await db_prepro.get_instance_info_new(instance_id=preprocessing["instance_id"]) if preprocessing.get("instance_id") else {}
        if not preprocessing["instance_info"]:
            preprocessing["alert"] = "Allocate the instance"
        preprocessing["bookmark"] = 1 if preprocessing["id"] in user_preprocessing_bookmark_list else 0
        preprocessing["permission_level"] = 1 if user_info["id"] in user_list else 5
        preprocessing["status"] = {}
        preprocessing["tools"] = []

        for tool in preprocessing_tools_db:
            tool_status = project_tools_status.get(str(tool["id"]))
            if tool_status:
                preprocessing["tools"].append({
                    "tool_id": tool["id"],
                    "tool_type": tool["tool_type"],
                    "tool_status": tool_status,
                    "function_info": function_info_list(tool_type=TYPE.TOOL_BASE[tool["tool_type"]]),
                    "tool_index": tool["tool_index"]
                })
            elif tool["request_status"] == 1:
                status = TYPE.KUBE_POD_STATUS_SCHEDULING if tool["pending_reason"] else TYPE.KUBE_POD_STATUS_PENDING
                tool_status = {
                    "status": status,
                    "reason": None,
                    "resolution": None,
                    "restart_count": None,
                    "phase": None
                }
                preprocessing["tools"].append({
                    "tool_id": tool["id"],
                    "tool_type": tool["tool_type"],
                    "tool_status": tool_status,
                    "function_info": function_info_list(tool_type=TYPE.TOOL_BASE[tool["tool_type"]]),
                    "tool_index": tool["tool_index"]
                })

        preprocessing["status"]["workbench"] = TYPE.KUBE_POD_STATUS_RUNNING if preprocessing["tools"] else TYPE.KUBE_POD_STATUS_STOP
        
        jobs = await db_prepro.get_jobs_is_request(preprocessing_id=preprocessing["id"])
        preprocessing["status"]["job"] = TYPE.KUBE_POD_STATUS_RUNNING if jobs else TYPE.KUBE_POD_STATUS_STOP
        
        preprocessing["private_user_list"] = await db_prepro.get_preprocessing_private_users(preprocessing_id=preprocessing["id"])
        
        return preprocessing

    preprocessing_list = await asyncio.gather(*(process_preprocessing(preprocessing) for preprocessing in preprocessing_list))
    return {"list": preprocessing_list, "total": len(preprocessing_list)}

# TODO
async def get_preprocessing_list_admin(search_key=None, size=None, page=None, search_value=None,
                                 sort=None, project_type=None):
    # 관리자용 프로젝트 리스트 가져오기
    
    redis_client = await get_redis_client_async()
    project_list, project_count = await asyncio.gather(
        db_prepro.get_project_list_new(search_key=search_key, size=size, page=page, search_value=search_value,
                                        user_id=None, sort=sort, project_type=project_type),
        db_prepro.get_project_list_new(search_key=search_key, size=None, page=None, search_value=search_value,
                                        user_id=None, sort=sort, project_type=project_type)
    )

    # redis_workspace_pod_status = await redis_client.hgetall(redis_key.WORKSPACE_PODS_STATUS) 

    async def process_project(project):
        project_tools_db, trainings = await asyncio.gather(
            db_prepro.get_project_tools_new(preprocessing_id=project["id"]),
            db_prepro.get_trainings_new(preprocessing_id=project["id"])
        )
        workspace_pod_status_str = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, project['workspace_id'])  # redis_workspace_pod_status.get(project['workspace_id'])
        if workspace_pod_status_str:
            workspace_pod_status = json.loads(workspace_pod_status_str)
        else:
            workspace_pod_status = {}
            
            
            
        projects_status = workspace_pod_status.get(TYPE.PROJECT_TYPE, {})
        project_pod_status = projects_status.get(str(project["id"]), {})
        project_tools_status = project_pod_status.get(TYPE.TRAINING_ITEM_B, {})
        project_training_status = project_pod_status.get(TYPE.TRAINING_ITEM_A, {})

        project["tools"] = []
        project["trainings"] = []
        project["errors"] = []
        tool_count = 0
        training_count = 0
        hps_count = 0
        time_strings  = []
        most_recent_time_str = None
        project["gpu_allocate"] = project["gpu_allocate"] if project["gpu_allocate"] else 0
        project["ram_allocate"] = project["ram_allocate"] if project["ram_allocate"] else 0
        project["cpu_allocate"] = project["cpu_allocate"] if project["cpu_allocate"] else 0
        allocate_gpu = project["instance_allocate"] * project["gpu_allocate"]
        allocate_cpu = project["instance_allocate"] * project["cpu_allocate"]
        allocate_ram = project["instance_allocate"] * project["ram_allocate"]
        instance_resouce_count = 3 if project["instance_type"] == TYPE.RESOURCE_TYPE_GPU else 2
        used_gpu = 0
        used_cpu = 0
        used_ram = 0
        
        
        
        for tool in project_tools_db:
            if tool["start_datetime"]:
                time_strings.append(tool["start_datetime"])
            if not tool["request_status"]:
                continue
            if str(tool["id"]) in project_tools_status:
                tool_status = project_tools_status[str(tool["id"])]
                if tool_status["status"] == TYPE.KUBE_POD_STATUS_ERROR:
                    project["errors"].append({
                        "type" : TYPE.TRAINING_ITEM_B,
                        "tool_type" : tool["tool_type"],
                        "tool_index": tool["tool_index"],
                        "name" : None
                    })
                else:
                    used_gpu += project_tools_status[str(tool["id"])]["resource"]["gpu"]
                    used_cpu += project_tools_status[str(tool["id"])]["resource"]["cpu"]
                    used_ram += project_tools_status[str(tool["id"])]["resource"]["ram"]
                
                tool_count += 1
                project["tools"].append({
                    "tool_id": tool["id"], "tool_type": tool["tool_type"],
                    "tool_index": tool["tool_index"],
                    "tool_commit_status": get_commit_image_installing_status(project_tool_id=tool["id"]),
                    "status": tool_status,
                    "function_info": function_info_list(tool_type=TYPE.TOOL_BASE[tool["tool_type"]]),
                    "gpu_count": tool["gpu_count"],
                    "image_name": tool["image_name"]
                })
            elif tool["request_status"] == 1 and not tool["start_datetime"]:
                tool_count += 1
                project["tools"].append({
                    "tool_id": tool["id"], "tool_type": tool["tool_type"],
                    "tool_commit_status": get_commit_image_installing_status(project_tool_id=tool["id"]),
                    "status": {
                        "status" : TYPE.KUBE_POD_STATUS_SCHEDULING,
                        "reason": None,
                        "resolution": None,
                        "restart_count": None,
                        "phase": None
                    },
                    "function_info": function_info_list(tool_type=TYPE.TOOL_BASE[tool["tool_type"]]),
                    "gpu_count": tool["gpu_count"],
                    "image_name": tool["image_name"]
                })

        for training in trainings:
            if training["start_datetime"]:
                time_strings.append(training["start_datetime"])
            if training["end_datetime"] or training["end_status"]:
                continue

            training_parse = {
                "training_name": training["name"],
                "training_id": training["id"],
                "training_type": TYPE.TRAINING_ITEM_A,
                "gpu_count": training["gpu_count"],
                "status": {
                    "status" : None,
                    "reason": None,
                    "resolution": None,
                    "restart_count": None,
                    "phase": None
                    },
                "resource_info": {
                    "resource_name": training["resource_name"],
                    "resource_type": training["resource_type"]
                },
                "image_name": training["image_name"],
                "create_datetime": training["create_datetime"]
            }
            if training["pending_reason"]:
                training_count += 1
                training_parse["status"]["status"] = TYPE.KUBE_POD_STATUS_SCHEDULING
                project["trainings"].append(training_parse)
            elif str(training["id"]) in project_training_status:
                training_count += 1
                training_parse["status"] = project_training_status[str(training["id"])]
                if project_training_status[str(training["id"])]["status"] == TYPE.KUBE_POD_STATUS_ERROR:
                    project["errors"].append({
                        "type" : TYPE.TRAINING_ITEM_A,
                        "tool_type" : None,
                        "tool_index": None,
                        "name" : training["name"]
                    })
                else:
                    used_gpu += project_training_status[str(training["id"])]["resource"]["gpu"]
                    used_cpu += project_training_status[str(training["id"])]["resource"]["cpu"]
                    used_ram += project_training_status[str(training["id"])]["resource"]["ram"]
                project["trainings"].append(training_parse)
            elif not training["start_datetime"] and not training["pending_reason"]:
                training_count += 1
                training_parse["status"]["status"] = TYPE.KUBE_POD_STATUS_PENDING
                project["trainings"].append(training_parse)
            elif training["start_datetime"] and str(training["id"]) not in project_training_status:
                training_count += 1
                training_parse["status"]["status"] = TYPE.KUBE_POD_STATUS_INSTALLING
                project["trainings"].append(training_parse)

        if time_strings:
            # 문자열을 datetime 객체로 변환
            time_objects = [datetime.strptime(time_str, TYPE.TIME_DATE_FORMAT) for time_str in time_strings]

            # 가장 최근 시간을 구함
            most_recent_time = max(time_objects)

            # 다시 문자열 형태로 변환
            most_recent_time_str = most_recent_time.strftime(TYPE.TIME_DATE_FORMAT)
        
        project["users"] = await db_prepro.get_project_users_auth_new(preprocessing_id=project["id"], include_owner=False)
        project["status"] = TYPE.KUBE_POD_STATUS_RUNNING if hps_count + tool_count + training_count else TYPE.KUBE_POD_STATUS_STOP
        project["last_start_datetime"] = most_recent_time_str
        used_gpu_rate = (used_gpu/allocate_gpu) * 100  if allocate_gpu and allocate_gpu != 0 else 0
        used_ram_rate = (used_ram/allocate_ram) * 100  if allocate_ram and allocate_ram != 0 else 0
        used_cpu_rate = (used_cpu/allocate_cpu) * 100  if allocate_cpu and allocate_cpu != 0 else 0
        
        project_resource_used_rate = (used_gpu_rate + used_cpu_rate + used_ram_rate) /  instance_resouce_count
        
        project["instance_used_info"] = {
            "used_rate" : project_resource_used_rate,
            "used_gpu" : used_gpu,
            "used_cpu" : used_cpu,
            "used_ram" : used_ram
        }
        project["instance_unused_info"] = {
            "unused_rate" : 100 - project_resource_used_rate,
            "unused_gpu" : allocate_gpu - used_gpu,
            "unused_cpu" : allocate_cpu - used_cpu,
            "unused_ram" : allocate_ram - used_ram
        }
        

        return project

    project_list = await asyncio.gather(*(process_project(project) for project in project_list))

    return {"list": project_list, "total": len(project_count)}

async def get_preprocessing_list(search_key=None, size=None, page=None, search_value=None, workspace_id=None, headers_user=None,
                sort=None, preprocessing_type=None):
    if headers_user is None:
            raise Exception("not exist header")
    if headers_user == settings.ADMIN_NAME:
        return await get_preprocessing_list_admin(search_key=search_key, size=size, page=page, search_value=search_value, sort=sort, preprocessing_type=preprocessing_type)
    else:
        return await get_preprocessing_list_user(search_key=search_key, size=size, page=page, search_value=search_value, workspace_id=workspace_id, sort=sort, preprocessing_type=preprocessing_type, headers_user=headers_user)

async def get_preprocessing_info(preprocessing_id : int):
    preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_id)
    if preprocessing_info is None:
        raise Exception("preprocessing info is None")
    user_list = await db_prepro.get_preprocessing_user_list(preprocessing_id=preprocessing_id)
    resource_limit = []
    resource_limit.append({
        "cpu_limit" : preprocessing_info["job_cpu_limit"],
        "ram_limit" : preprocessing_info["job_ram_limit"],
    })
    if preprocessing_info == TYPE.PREPROCESSING_TYPE_A:
        resource_limit.append({
            "cpu_limit" : preprocessing_info["tool_cpu_limit"],
            "ram_limit" : preprocessing_info["tool_ram_limit"],
        })
    instance_used_info = await workspace_resource.get_workspace_instance_total_info(instance_id=preprocessing_info["instance_id"], workspace_id=preprocessing_info["workspace_id"], \
        instance_allocate=preprocessing_info["instance_allocate"], resource_limit=resource_limit)
    return {
        "id" : preprocessing_info["id"],
        "type" : preprocessing_info["type"],
        "built_in_data_type" : preprocessing_info["built_in_data_type"],
        "built_in_data_tf" : preprocessing_info["built_in_data_tf"],
        "workspace_id" : preprocessing_info["workspace_id"],
        "workspace_name" : preprocessing_info["workspace_name"],
        "name" : preprocessing_info["name"],
        "description" : preprocessing_info["description"],
        "access" : preprocessing_info["access"],
        "owner_name" : preprocessing_info["owner_name"],
        "create_datetime" : preprocessing_info["create_datetime"],
        "update_datetime" : preprocessing_info["update_datetime"],
        "private_user_list" : user_list if preprocessing_info["access"] == 0 else [],
        "preprocessing_resource_limit" : {
            "job_cpu_limit" : preprocessing_info["job_cpu_limit"],
            "job_ram_limit" : preprocessing_info["job_ram_limit"],
            "tool_cpu_limit" : preprocessing_info["tool_cpu_limit"],
            "tool_ram_limit" : preprocessing_info["tool_ram_limit"],
        },
        "instance_info" : instance_used_info
    }

async def get_preprocessing_tools(preprocessing_id : int):
    redis_client = await get_redis_client_async()
    preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_id)
    workspace_info = await db_workspace.get_workspace_async(workspace_id=preprocessing_info["workspace_id"])
    tools = await db_prepro.get_preprocessing_tools(preprocessing_id=preprocessing_id)
    workspace_pods_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, preprocessing_info["workspace_id"]) 
    if workspace_pods_status is None:
        workspace_pods_status = {}
    else:
        workspace_pods_status = json.loads(workspace_pods_status)
        
    preprocessing_pod_status = workspace_pods_status.get(TYPE.PREPROCESSING_TYPE, {})
    preprocessing_pod_status = preprocessing_pod_status.get(str(preprocessing_id), {})
    project_tools_status = preprocessing_pod_status.get(TYPE.TRAINING_ITEM_B, {})
    parse_tools = []
    async def process_tools(tool):
        tool_type_name = TYPE.TOOL_TYPE[tool["tool_type"]]
        status = {
            "status" : TYPE.KUBE_POD_STATUS_PENDING,
            "reason" : "" ,# TODO error 일 때 elk에서 로그 가져오기
            "resolution" : ""
        }
        if  tool["request_status"] == 0:
            status["status"] =  TYPE.KUBE_POD_STATUS_STOP
        elif tool["pending_reason"]:
             status["reason"] = tool["pending_reason"]
             status["resolution"] = "Please wait for the resource to be returned"
        elif project_tools_status.get(str(tool["id"]), None): # helm install 후 
            status["status"] = project_tools_status[str(tool["id"])]["status"] # if project_tools_status[str(tool["id"])]["status"] else TYPE.KUBE_POD_STATUS_STOP
            status["reason"] = project_tools_status[str(tool["id"])]["reason"]
            status["resolution"] = project_tools_status[str(tool["id"])]["resolution"]
        
        # TODO 추후 수정
        commit_status = False #get_commit_image_installing_status(project_tool_id=tool["id"]) # commit 상태 값 표시
        gpu_cluster_ips = []
        _, unique_pod_name, _ = PodName(
            workspace_name=preprocessing_info["workspace_name"], start_datetime=tool["start_datetime"],
            item_name=preprocessing_info["name"], item_type=TYPE.TOOL_TYPE[tool["tool_type"]],
            sub_flag=str(tool["id"])).get_all()
        if status["status"] == TYPE.KUBE_POD_STATUS_RUNNING:
            # POD 별 ip 적어주기 
            cluster_config_file_path = PATH.JF_PREPROCESSING_TOOL_CLUSTER_HOSTFILE_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=workspace_info["name"],\
                PREPROCESSING_NAME=preprocessing_info["name"], POD_NAME=unique_pod_name)
            gpu_cluster_ips = await parse_file_to_list(cluster_config_file_path, total_gpu=tool["gpu_count"])
        elif status["status"] == TYPE.KUBE_POD_STATUS_ERROR:
            namespace = "{}-{}".format(settings.JF_SYSTEM_NAMESPACE, preprocessing_info["workspace_id"])
            events = await get_pod_event_logs(pod_name=TYPE.TOOL_URI_POD_NAME.format(unique_pod_name), namespace=namespace)
            error_event = None
            for event in events:
                if event.type == "Warning":
                    error_event = event
            status["reason"] = error_event.message if error_event else "This image is not supported"
            
        function_info = function_info_list(tool_type=TYPE.TOOL_TYPE[tool["tool_type"]])
        on_off_possible = tool["tool_type"] in TYPE.TOOL_ON_OFF_POSSIBLE_LIST
        parse_tool = {
            "id" : tool["id"],
            "tool_commit_status" : commit_status,
            "tool_index" : tool["tool_index"],
            "gpu_count" : tool["gpu_count"],
            "gpu_cluster_auto" : tool["gpu_cluster_auto"],
            "image_id" : tool["image_id"],
            "image_name" : tool["image_name"],
            "tool_type" : tool["tool_type"],
            "tool_type_name" : tool_type_name,
            "status" : status,
            "gpu_cluster_ips" : gpu_cluster_ips,
            "function_info" : function_info,
            "on_off_possible" : on_off_possible
        }
        return parse_tool
        
    parse_tools = await asyncio.gather(*(process_tools(tool) for tool in tools))    
    parse_tools = sorted(parse_tools, key=lambda x: x["id"])
    
    result = {
        "preprocessing_info" : {
            "id": preprocessing_info["id"],
            "type": preprocessing_info["type"],
            "name": preprocessing_info["name"],
            "owner_name": preprocessing_info["owner_name"],
            "resource_name": preprocessing_info["resource_name"],
            "gpu_allocate": preprocessing_info["gpu_allocate"],
            "instance_type": preprocessing_info["instance_type"],
            "instance_name": preprocessing_info["instance_name"],
            "instance_cpu": preprocessing_info["cpu_allocate"],
            "instance_ram": preprocessing_info["ram_allocate"],
            },
        "integrated_tool" : parse_tools,
        "tool_resource" : {
            "cpu" : preprocessing_info["tool_cpu_limit"],
            "ram" : preprocessing_info["tool_ram_limit"]
        }
    }
    return result

async def get_tool_url(preprocessing_tool_id : int):
    # global redis_client
    redis_client = await get_redis_client_async()
    preprocessing_tool_info = await db_prepro.get_preprocessing_tool(preprocessing_tool_id=preprocessing_tool_id)
    if preprocessing_tool_info is None:
        # TODO TEST (2022-09-29)
        raise ItemNotExistError
    redis_workspace_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, preprocessing_tool_info["workspace_id"] )
    if redis_workspace_pod_status:
        
        redis_workspace_pod_status = json.loads(redis_workspace_pod_status)
    else:
        redis_workspace_pod_status={}

    preprocessings_pod_status = redis_workspace_pod_status.get(TYPE.PREPROCESSING_TYPE, {})
    preprocessing_pod_status = preprocessings_pod_status.get(str(preprocessing_tool_info["preprocessing_id"]), {})
    preprocessing_tools_status = preprocessing_pod_status.get(TYPE.PREPROCESSING_ITEM_A, {})
    
    if str(preprocessing_tool_id) in preprocessing_tools_status and preprocessing_tools_status[str(preprocessing_tool_id)]["status"] == "running":
        if preprocessing_tool_info["tool_type"] == TYPE.TOOL_JUPYTER_ID:
            return await get_jupyter_url(preprocessing_tool_info=preprocessing_tool_info)
        elif preprocessing_tool_info["tool_type"] == TYPE.TOOL_VSCODE_ID:
            return get_vscode_url(preprocessing_tool_info=preprocessing_tool_info)
        elif preprocessing_tool_info["tool_type"] == TYPE.TOOL_SHELL_ID:
            return get_shell_url(preprocessing_tool_info=preprocessing_tool_info)
        else:
            raise Exception("Unexpected Tool Type.")
    raise Exception("tool is not running.")

def get_jupyter_lab_url_cmd(n):
    # get_jupyter_lab_run_cmd 에 따라서 url 가져오는 방식이 달라 질 수 있음
    # user_base_cmd = get_user_base_cmd(auth=auth)
    # jupyter_lab_url_cmd = """{user_base_cmd} "jupyter lab list | grep http" """.format(user_base_cmd=user_base_cmd)
    
    # CMD          D N
    # jupyter list X X
    # jupyter notebook list X O
    # jupyter-notebook list X O
    # jupyter lab list O X
    cmd_list = [
        "jupyter lab list",
        "jupyter notebook list",
        "jupyter-notebook list",
        "jupyter list"
    ]

    jupyter_lab_url_cmd = """{cmd} | grep http """.format(cmd=cmd_list[n % len(cmd_list)])
    return jupyter_lab_url_cmd

async def get_jupyter_url(preprocessing_tool_info: dict):
    _, unique_pod_name, _ = PodName(
        workspace_name=preprocessing_tool_info["workspace_name"], 
        start_datetime=preprocessing_tool_info["start_datetime"],
        item_name=preprocessing_tool_info["preprocessing_name"], 
        item_type=TYPE.TOOL_TYPE[preprocessing_tool_info["tool_type"]], sub_flag=str(preprocessing_tool_info["id"])).get_all()
    
    # Debug: Print expected vs actual pod name
    expected_pod_name = TYPE.TOOL_URI_POD_NAME.format(unique_pod_name)
    namespace = "{}-{}".format(settings.JF_SYSTEM_NAMESPACE, preprocessing_tool_info["workspace_id"])
    print(f"[DEBUG] Expected pod name: {expected_pod_name}")
    print(f"[DEBUG] Namespace: {namespace}")
    print(f"[DEBUG] Unique pod name: {unique_pod_name}")
    print(f"[DEBUG] Tool info: preprocessing_tool_id={preprocessing_tool_info.get('id')}")
    
    cmd_res = ""  # Initialize cmd_res to prevent UnboundLocalError
    for i in range(10):
        try:
            pod_cmd = get_jupyter_lab_url_cmd(n=i)
            
            pod_cmd = pod_cmd.split(" ")
            cmd_res = await exec_pod(name=TYPE.TOOL_URI_POD_NAME.format(unique_pod_name), command=pod_cmd, namespace="{}-{}".format(settings.JF_SYSTEM_NAMESPACE, preprocessing_tool_info["workspace_id"]))
            print(cmd_res)
            if "?token=" in cmd_res:
                break
        except :
            traceback.print_exc()
            print("URL GET Retry")
        time.sleep(0.1)
    
    # Check if cmd_res is empty (all attempts failed)
    if not cmd_res:
        raise Exception(f"Failed to get Jupyter URL from pod {unique_pod_name} after 10 attempts")
    for cmd in cmd_res.split("\n"):
        if "http://" in cmd:
            cmd_res = cmd 
            break
    #EX1) cmd_res = http://0.0.0.0:8888/jupyter/7a971ecb54579ff453383a853ac2d4d9/?token=7a9abd0d44d1655bd825ef7539ac6a6267342a617951b837 :: /home/robert \n
    #EX2) cmd_res = http://h3783d0a5c26a5ed60bfb6611f5d9f21c:8888/jupyter/h3783d0a5c26a5ed60bfb6611f5d9f21c/?token=1532405c0631be6ca6cf98796d102fda5742a077566bec65 :: /home/robert
    last_line = cmd_res.split('\n')[0]
    url = last_line.split(' :: ')[0]
    url = re.sub(r'http://.*:88*', "", url)
    url = url.replace("\n","")
    return {"url":url}

def get_vscode_url(preprocessing_tool_info : dict) -> str:
    
    VSCODE_URL = TYPE.TRAINING_TOOL_VSCODE_URL # code-server에서 자체적으로 리다이렉트를 해주기 때문에 파라미터까지 붙여야함
    _, unique_pod_name, _ = PodName(workspace_name=preprocessing_tool_info["workspace_name"], start_datetime=preprocessing_tool_info["start_datetime"], item_name=preprocessing_tool_info["preprocessing_name"], item_type=TYPE.TOOL_TYPE[preprocessing_tool_info["tool_type"]], sub_flag=str(preprocessing_tool_info["id"])).get_all()
    url = VSCODE_URL.format(TYPE.TOOL_URI_POD_NAME.format(unique_pod_name) , PATH.JF_PREPROCESSING_BASE_HOME_POD_PATH)
    return {"url":url}

def get_shell_url(preprocessing_tool_info : dict) -> str:
    
    SHELL_URL = TYPE.TRAINING_TOOL_SSH_URL
    _, unique_pod_name, _ = PodName(workspace_name=preprocessing_tool_info["workspace_name"], start_datetime=preprocessing_tool_info["start_datetime"], item_name=preprocessing_tool_info["preprocessing_name"], item_type=TYPE.TOOL_TYPE[preprocessing_tool_info["tool_type"]], sub_flag=str(preprocessing_tool_info["id"])).get_all()

    url = SHELL_URL.format(TYPE.TOOL_BASE_SHELL, TYPE.TOOL_URI_POD_NAME.format(unique_pod_name))
    return {"url":url}

async def get_tool_ssh_jump_url(preprocessing_tool_id : int, header_user : str):
    preprocessing_tool_info = await db_prepro.get_preprocessing_tool(preprocessing_tool_id=preprocessing_tool_id)
    preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_tool_info["preprocessing_id"])
    workspace_info = await db_workspace.get_workspace_async(workspace_id=preprocessing_info["workspace_id"])
    _, unique_pod_name, _ = PodName(workspace_name=preprocessing_tool_info["workspace_name"], start_datetime=preprocessing_tool_info["start_datetime"], item_name=preprocessing_tool_info["preprocessing_name"], item_type=TYPE.TOOL_TYPE[preprocessing_tool_info["tool_type"]], sub_flag=str(preprocessing_tool_info["id"])).get_all()
    namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=preprocessing_info["workspace_id"])
    # ingress_ip = await tool_loadbalancer_ingress(pod_name=unique_pod_name, tool_type=TYPE.TOOL_TYPE[project_tool_info["tool_type"]], namespace=namespace)
    # if ingress_ip is None:
        
    #     ingress_ip = settings.EXTERNAL_HOST
    ingress_ip = settings.EXTERNAL_HOST
    ssh_port = settings.JF_SSH_PORT
    cluster_config_file_path = PATH.JF_PREPROCESSING_TOOL_CLUSTER_HOSTFILE_PATH.format(STORAGE_NAME=workspace_info["main_storage_name"], WORKSPACE_NAME=preprocessing_info["workspace_name"], \
        PREPROCESSING_NAME=preprocessing_info["name"], POD_NAME=unique_pod_name)
    container_ips = await parse_file_to_list(cluster_config_file_path, preprocessing_tool_info["gpu_count"])
    print(container_ips)
    master_tool_ip = container_ips[0]["ip"]
    # TODO kubeapi 연결이 느려 변경
    # master_tool_ip = get_tool_ip(pod_name=TYPE.TOOL_URI_POD_NAME.format(unique_pod_name), namespace="{}-{}".format(settings.JF_SYSTEM_NAMESPACE, project_tool_info["workspace_id"]))
    return {
        "user" : header_user,
        "ingress_ip" : extract_ip_or_dns(ingress_ip),
        "tool_ip" : master_tool_ip,
        "ssh_url" : settings.BASE_SSH_JUMP_FORMAT.format(ssh_port=ssh_port, header_user=header_user, ingress_ip=ingress_ip, tool_pod_ip=master_tool_ip),
        "tool_password" : front_cipher.encrypt(preprocessing_tool_info["tool_password"])
    }

async def get_jobs(preprocessing_id : int, search_key=None, size=None, page=None, search_value=None, sort=None, order_by="DESC"):
    # global redis_client
    redis_client = await get_redis_client_async()
    preprocessing_info = await get_preprocessing_info(preprocessing_id=preprocessing_id)
    jobs  = await db_prepro.get_jobs(preprocessing_id = preprocessing_id, search_key=search_key, size=size, page=page, search_value=search_value, sort=sort, order_by=order_by)
    jobs_total = await db_prepro.get_jobs_simple(preprocessing_id =preprocessing_id)
    # workspace_resources = db_workspace.get_workspace_resource(workspace_id=preprocessing_info["workspace_id"])
    redis_workspace_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, preprocessing_info["workspace_id"]) 
    if redis_workspace_pod_status is None:
        redis_workspace_pod_status = {}
    else:
        redis_workspace_pod_status = json.loads(redis_workspace_pod_status)
    
    projects_pod_status = redis_workspace_pod_status.get(TYPE.PREPROCESSING_TYPE, {})
    project_pod_status = projects_pod_status.get(str(preprocessing_id), {})
    
    job_status = project_pod_status.get(TYPE.PREPROCESSING_ITEM_B, {})
    
    async def process_job(job):
        parameter = common.parameter_str_to_dict(job["parameter"])
        preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=job["preprocessing_id"])
        if preprocessing_info["type"] == TYPE.PREPROCESSING_TYPE_A:
            # logs = await get_efk_job_logs(job_id=job["id"], count=1, is_all=False)
            # job["log_file"] = True if logs else False
            job.pop("dataset_data_path")
        else:
            workspace_info = await db_workspace.get_workspace_async(workspace_id=preprocessing_info["workspace_id"])
            dataset_info = db_dataset.get_dataset(dataset_id=job["dataset_id"])
            # TODO 
            # 추후 수정
            if preprocessing_info["built_in_data_tf"] in (
                TYPE_BUILT_IN.MARKER_ANALYSIS, TYPE_BUILT_IN.IMAGE_AUGMENT,
                TYPE_BUILT_IN.FORMAT_CONVERT, TYPE_BUILT_IN.SDS_LLAVA_CONVERT):
                dataset_data_path = PATH.JF_DATA_DATASET_DATA_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"], WORKSPACE_NAME=workspace_info["name"], \
                    ACCESS=dataset_info["access"], DATASET_NAME=dataset_info["name"], DATA_PATH=job["dataset_data_path"])
                dataset_data_path = os.path.dirname(dataset_data_path)
            try:
                if preprocessing_info["built_in_data_tf"] == TYPE_BUILT_IN.SDS_LLAVA_CONVERT:
                    # SDS 출력 = 입력 디렉토리 안 {result_file_name}_{variant}.json (variant별 최대 3개).
                    base = os.path.basename(parameter.get("result_file_name") or "sds_train")
                    variant = parameter.get("sds_variant", "all")
                    variants = ["en", "ko", "ko_compact"] if variant == "all" else [variant]
                    job["log_file"] = any(
                        os.path.exists(f"{dataset_data_path}/{base}_{v}.json") for v in variants
                    )
                else:
                    # result_file_name 미저장 시 스크립트 기본값("converted")과 맞추고 basename 으로 경로조작 차단.
                    file_name = os.path.basename(parameter.get("result_file_name") or "converted")
                    # marker/augment 출력은 .csv, 포맷변환은 사용자 선택 output_format(json/jsonl).
                    ext = (parameter.get("output_format", "jsonl")
                           if preprocessing_info["built_in_data_tf"] == TYPE_BUILT_IN.FORMAT_CONVERT
                           else "csv")
                    result_file_path = f"{dataset_data_path}/{file_name}.{ext}"
                    job["log_file"] = os.path.exists(result_file_path)
            except Exception as e:
                traceback.print_exc()
                job["log_file"] = False
        job["parameter"] = common.parameter_dict_to_list(parameter)

        job["status"] = job_status_parse(job_status=job_status, job_info=job)
        return job
    
    jobs = await asyncio.gather(*(process_job(job) for job in jobs))

    return {
        "list" : jobs,
        "total" : len(jobs_total),
        "preprocessing_info" : preprocessing_info,
        # "job_resource" : {
        #     "cpu" : preprocessing_info["job_cpu_limit"],
        #     "ram" : preprocessing_info["job_ram_limit"]
        # }
    }


# TODO 추후 기획이 바뀌면 수정해야 함 IPO 용
async def get_built_in_result_download(job_id : int):
    preprocessing_job_info = db_prepro.get_job_simple(job_id)
    preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_job_info["preprocessing_id"])
    workspace_info = await db_workspace.get_workspace_async(workspace_id=preprocessing_info["workspace_id"])
    dataset_info = db_dataset.get_dataset(dataset_id=preprocessing_job_info["dataset_id"])
    parameter = common.parameter_str_to_dict(preprocessing_job_info["parameter"])
    # print(parameter)
    if preprocessing_info["built_in_data_tf"] == TYPE_BUILT_IN.MARKER_ANALYSIS:
        dataset_data_path = PATH.JF_DATA_DATASET_DATA_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"], WORKSPACE_NAME=workspace_info["name"], \
            ACCESS=dataset_info["access"], DATASET_NAME=dataset_info["name"], DATA_PATH=preprocessing_job_info["dataset_data_path"])
        file_name = parameter["result_file_name"]
        directory = os.path.dirname(dataset_data_path)
        download_file_path = os.path.join(directory, f"{file_name}.csv")
        return FileResponse(
        path=download_file_path,
        media_type="text/csv",
        filename=f"{file_name}.csv"
        )
    elif preprocessing_info["built_in_data_tf"] == TYPE_BUILT_IN.IMAGE_AUGMENT:
        dataset_data_path = PATH.JF_DATA_DATASET_DATA_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"], WORKSPACE_NAME=workspace_info["name"], \
            ACCESS=dataset_info["access"], DATASET_NAME=dataset_info["name"], DATA_PATH=preprocessing_job_info["dataset_data_path"])
        file_name = parameter["result_file_name"]
        directory = os.path.dirname(dataset_data_path)
        download_file_path = os.path.join(directory, f"{file_name}.csv")
        return FileResponse(
        path=download_file_path,
        media_type="text/csv",
        filename=f"{file_name}.csv"
        )
    elif preprocessing_info["built_in_data_tf"] == TYPE_BUILT_IN.FORMAT_CONVERT:
        # 포맷 변환 결과 = 원본 옆 {result_file_name}.{output_format}(json/jsonl).
        dataset_data_path = PATH.JF_DATA_DATASET_DATA_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"], WORKSPACE_NAME=workspace_info["name"], \
            ACCESS=dataset_info["access"], DATASET_NAME=dataset_info["name"], DATA_PATH=preprocessing_job_info["dataset_data_path"])
        # result_file_name 미저장 시 스크립트 기본값과 일치 + basename 경로조작 차단.
        file_name = os.path.basename(parameter.get("result_file_name", "converted"))
        out_fmt = parameter.get("output_format", "jsonl")
        directory = os.path.dirname(dataset_data_path)
        download_file_path = os.path.join(directory, f"{file_name}.{out_fmt}")
        media_type = "application/json" if out_fmt == "json" else "application/x-ndjson"
        return FileResponse(
        path=download_file_path,
        media_type=media_type,
        filename=f"{file_name}.{out_fmt}"
        )
    elif preprocessing_info["built_in_data_tf"] == TYPE_BUILT_IN.SDS_LLAVA_CONVERT:
        # SDS 출력 = 입력 디렉토리 안 {result_file_name}_{variant}.json (variant별 최대 3개).
        # 다운로드는 존재하는 variant 중 하나(ko>en>ko_compact 우선) 반환.
        dataset_data_path = PATH.JF_DATA_DATASET_DATA_PATH.format(STORAGE_NAME=workspace_info["data_storage_name"], WORKSPACE_NAME=workspace_info["name"], \
            ACCESS=dataset_info["access"], DATASET_NAME=dataset_info["name"], DATA_PATH=preprocessing_job_info["dataset_data_path"])
        directory = os.path.dirname(dataset_data_path)
        base = os.path.basename(parameter.get("result_file_name") or "sds_train")
        variant = parameter.get("sds_variant", "all")
        order = ["ko", "en", "ko_compact"] if variant == "all" else [variant]
        for v in order:
            p = os.path.join(directory, f"{base}_{v}.json")
            if os.path.exists(p):
                return FileResponse(path=p, media_type="application/json", filename=f"{base}_{v}.json")

    pass

#=======================================================
# DELETE
#=======================================================
async def delete_preprocessing(header_user_id : int, id_list : List[int]):
    try:
        admin_info = db_user.get_user(user_name=settings.ADMIN_NAME)
        for preprocessing_id in id_list:
            preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_id)
            if preprocessing_info is None:
                raise Exception("preprocessing info is None")
            workspace_info = await db_workspace.get_workspace_async(workspace_id=preprocessing_info["workspace_id"])
            preprocessing_private_users = await db_prepro.get_preprocessing_private_users(preprocessing_id=preprocessing_id)
            prepro_private_user_ids = [user["id"] for user in preprocessing_private_users]
            prepro_user_ids = prepro_private_user_ids + [workspace_info["manager_id"], admin_info["id"], preprocessing_info["owner_id"]]
            if preprocessing_info["access"] == 0 and header_user_id not in prepro_user_ids :
                raise Exception("preprocessing is not owner or manager or admin")
            
            redis_client = await get_redis_client_async()
            workspaces_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, preprocessing_info["workspace_id"])
            if workspaces_pod_status:
                workspaces_pod_status = json.loads(workspaces_pod_status)
            else:
                workspaces_pod_status = {}
            preprocessing_status = workspaces_pod_status.get(TYPE.PREPROCESSING_TYPE, {})
            prepro_pod_status = preprocessing_status.get(str(preprocessing_id), {})
            if prepro_pod_status or prepro_pod_status != {}:
                raise Exception("실행중인 개발도구가 있습니다. 종료 후 진행해주세요.")
            
            await db_prepro.delete_preprocessing(preprocessing_id=preprocessing_id)
            await delete_preprocessing_folder(workspace_name=preprocessing_info["workspace_name"], preprocessing_name=preprocessing_info["name"], storage_name=workspace_info["main_storage_name"])
            await logging_history_async(task=LogParam.Task.PREPROCESSING, action=LogParam.Action.DELETE, user_id=header_user_id, workspace_id=preprocessing_info["workspace_id"], task_name=preprocessing_info["name"])
        return True
    except Exception as e:
        traceback.print_exc()
        raise e

async def delete_tool(preprocessing_tool_id: int):
    # global redis_client
    redis_client = await get_redis_client_async()
    preprocessing_tool_info = await db_prepro.get_preprocessing_tool(preprocessing_tool_id=preprocessing_tool_id)
    redis_workspace_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, preprocessing_tool_info["workspace_id"])
    if redis_workspace_pod_status:
        
        redis_workspace_pod_status = json.loads(redis_workspace_pod_status)
        preprocessings_pod_status = redis_workspace_pod_status.get(TYPE.PREPROCESSING_TYPE, {})
        preprocessing_pod_status = preprocessings_pod_status.get(str(preprocessing_tool_info["preprocessing_id"]),{})
        preprocessing_tools_status = preprocessing_pod_status.get(TYPE.PREPROCESSING_ITEM_A, {})
    else:
        preprocessing_tools_status={}
        
    if str(preprocessing_tool_id) in preprocessing_tools_status and preprocessing_tools_status[str(preprocessing_tool_id)]["status"]:
        raise Exception("Tool is Running")
    
    return await db_prepro.delete_tool(preprocessing_tool_id=preprocessing_tool_id)

async def delete_job_all(preprocessing_id):
    jobs = await db_prepro.get_jobs_simple(preprocessing_id=preprocessing_id)
    for job in jobs:
        await delete_job(job_id=job["id"])
    return True

async def delete_job(job_id: int):
    job_info = await db_prepro.get_job(job_id=job_id)
    redis_client = await get_redis_client_async()
    redis_workspace_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, job_info["workspace_id"])
    if redis_workspace_pod_status:
        redis_workspace_pod_status = json.loads(redis_workspace_pod_status)
    else:
        redis_workspace_pod_status = {}
    
    preprocessings_pod_status = redis_workspace_pod_status.get(TYPE.PREPROCESSING_TYPE, {})
    preprocessing_pod_status = preprocessings_pod_status.get(str(job_info["preprocessing_id"]), {})
    
    if str(job_id) in preprocessing_pod_status.get(TYPE.PREPROCESSING_ITEM_B, {}):
        await delete_tool_helm(preprocessing_tool_id=job_id, preprocessing_tool_type=TYPE.PREPROCESSING_ITEM_B, workspace_id=job_info["workspace_id"])
    
    return db_prepro.delete_job(job_id=job_id)

#=======================================================
# OPTION
#=======================================================


async def get_gpu_cluster_info(preprocessing_id : int, gpu_count : int, gpu_select : List[dict] = []):
    redis_client= await get_redis_client_async()
    preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_id)
    divisors = []
    if TYPE.RESOURCE_TYPE_MIG in  preprocessing_info["instance_name"]:
        if gpu_select:
            divisors.append({
                "gpu_count" : 1,
                "server" : gpu_count,
                "status" : None
            })
    else:
        # node_name별 gpu_uuid 개수 세기
        node_counts = Counter(item['node_name'] for item in gpu_select)
        
        # node_name별 개수 추출
        counts = list(node_counts.values())
        
        # 최대 공약수 계산
        if len(counts) < 2:
            gcd_result = counts[0] if counts else 0
        else:
            gcd_result = reduce(gcd, counts)
        for i in range(1, gcd_result + 1):
            if gcd_result % i == 0:
                divisors.append({
                    "gpu_count" : i,
                    "server" : int(gpu_count/i),
                    "status" : None
                })
    
    return {
        "gpu_cluster_cases" : divisors,
        "gpu_cluster_list" : await common.get_gpu_cluster_info(instance_id=preprocessing_info["instance_id"], redis_client=redis_client )
    }


async def preprocessing_option(workspace_id : int = None, preprocessing_id : int = None):
    if workspace_id == None:
        # workspace_list
        result = {
            "workspace_list" : await db_prepro.get_workspace_name_and_id_list()
        }
        return response(status=1, result=result)

    workspace_allocate_instance = await db_prepro.get_workspace_instances(workspace_id=workspace_id)
    result = {
        "user_list": db_user.get_user_list_in_workspace(workspace_id=workspace_id),
        "instances": workspace_allocate_instance,
        # "docker_image_list": await db_prepro.get_workspace_image_list(workspace_id),
        "built_in_data_types": TYPE_BUILT_IN.PREPROCESSING_BUILT_IN_DATA_TYPES,
        # DOMAIN 상수는 공유lib(fb_utils) 업데이트가 pod 에 반영돼야 존재. 미반영(baked utils)
        # 이미지에서도 크래시 안 나도록 getattr 폴백(빈 리스트) — 공유lib 마운트 배선 정합 후 실제 값 노출.
        "domain_data_types": getattr(TYPE_BUILT_IN, "PREPROCESSING_DOMAIN_DATA_TYPES", [])
    }
    if preprocessing_id: # 수정용
        preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_id)
        if preprocessing_info["access"] == 0:
            result["secreted_user"] = await db_prepro.get_preprocessing_private_users(preprocessing_id=preprocessing_id)
        result["preprocessing_info"] = preprocessing_info
    return result

async def tool_option(preprocessing_id : int, preprocessing_tool_id: int) :
    
    preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_id)
    if not preprocessing_info:
        raise Exception("not exist project")
    preprocessing_tool_info = await db_prepro.get_preprocessing_tool(preprocessing_tool_id=preprocessing_tool_id)
    preprocessing_gpu_total = 0
    result = {
        "preprocessing_gpu_total" : preprocessing_gpu_total,
        "dataset_list" : await db_prepro.get_workspace_dataset_list(workspace_id=preprocessing_info["workspace_id"]),
        "image_list": await db_prepro.get_workspace_image_list(preprocessing_info["workspace_id"]),
        "instance_type" : preprocessing_info["instance_type"],
        "tool_gpu_count" :preprocessing_tool_info["gpu_count"]
        }
    if preprocessing_info["gpu_allocate"]:
        # GPU
        project_gpu_used_info = await get_preprocessing_used_gpu_count(preprocessing_id=preprocessing_id)
        result["distributed_frameworks"] = TYPE.DISTRIBUTED_FRAMEWORKS
        total_gpu = preprocessing_info["gpu_allocate"] * preprocessing_info["instance_allocate"]
        result["preprocessing_gpu_total"] = total_gpu
        # result["gpu_cluster_list"] = common.get_gpu_cluster_info(instance_id=preprocessing_info["instance_id"])
        result["instance_info"] = {
            "resource_name" : preprocessing_info["resource_name"],
            "total" : total_gpu,
            "used"  : project_gpu_used_info["used_gpu_count"], # TODO 해당 값이 필요한지 의문
            "instance_type" : preprocessing_info["instance_type"]
        } 
        # result["workspace_gpu_status"] = await get_workspace_usde_gpu_count_by_instance(instance_id=preprocessing_info["instance_id"], workspace_id=preprocessing_info["workspace_id"])
        # result["project_gpu_status"] = get_project_used_gpu_count(preprocessing_id=preprocessing_id)
    else:
        # CPU
        result["instance_info"] = {
            "resource_name" : None,
            "total" : None,
            "used"  : None, # TODO 해당 값이 필요한지 의문
            "instance_type" : preprocessing_info["instance_type"]
        } 
    
    return result

# TODO
# built in 로직 추가
async def job_option(preprocessing_id : int):
    preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_id)
    if not preprocessing_info["instance_id"]:
        raise Exception("Allocate the instance")
    workspace_info = await db_workspace.get_workspace_async(workspace_id=preprocessing_info["workspace_id"])
    docker_images = await db_prepro.get_workspace_image_list(workspace_id=preprocessing_info["workspace_id"])
    gpu_allocate = preprocessing_info["gpu_allocate"] if preprocessing_info["gpu_allocate"] else 0
    total_gpu = gpu_allocate * preprocessing_info["instance_allocate"]
    # is_distributed = total_gpu >= 2 
    run_code_list, _ = await get_file_list_from_src(workspace_name=preprocessing_info["workspace_name"], preprocessing_name=preprocessing_info["name"], \
        storage_name=workspace_info["main_storage_name"], file_extension=["py", "sh"])
    
    
    result = {
        "image_list": docker_images, 
        "run_code_list": run_code_list,
        "dataset_list" : await db_prepro.get_workspace_dataset_list(workspace_id=preprocessing_info["workspace_id"]),
        "preprocessing_type":  preprocessing_info["type"], 
        "instance_info" : {},
        # "gpu_cluster_list" : {},
        "workspace_gpu_status" : {},
        }
    
    if preprocessing_info["gpu_allocate"]:
        # GPU
        preprocessing_gpu_used_info = await get_preprocessing_used_gpu_count(preprocessing_id=preprocessing_id)
        # result["gpu_cluster_list"] = common.get_gpu_cluster_info(instance_id=preprocessing_info["instance_id"])
        result["instance_info"] = {
            "resource_name" : preprocessing_info["resource_name"],
            "total" : total_gpu,
            "used"  : preprocessing_gpu_used_info["used_gpu_count"], # TODO 해당 값이 필요한지 의문
            "instance_type" : preprocessing_info["instance_type"]
        } 
        result["workspace_gpu_status"] = await workspace_resource.get_workspace_usage_gpu_count_by_instance(instance_id=preprocessing_info["instance_id"], workspace_id=preprocessing_info["workspace_id"])
        # result["project_gpu_status"] = get_project_used_gpu_count(preprocessing_id=preprocessing_id)
    else:
        # CPU
        result["instance_info"] = {
            "resource_name" : None,
            "total" : None,
            "used"  : None, # TODO 해당 값이 필요한지 의문
            "instance_type" : preprocessing_info["instance_type"]
        } 

    return result

#=======================================================
# CREATE
#=======================================================

async def tool_add(preprocessing_id : int, preprocessing_tool_type : int):
    
    if not await db_prepro.get_preprocessing_simple(preprocessing_id=preprocessing_id):
        raise Exception("preprocessing not exist")
    
    if preprocessing_tool_type not in TYPE.TOOL_BASE_LIST:
        raise Exception("Tool is not supported")
    tool_index = 0
    project_tool_last = await db_prepro.get_preprocessing_tool_by_type(tool_type=preprocessing_tool_type, preprocessing_id=preprocessing_id)
    if project_tool_last:
        tool_index = project_tool_last["tool_index"] + 1
    return await db_prepro.create_preprocessing_tool(preprocessing_id=preprocessing_id, tool_type=preprocessing_tool_type, tool_index=tool_index)

def is_preprocessing_good_name(preprocessing_name):
    is_good = common.is_good_name(name=preprocessing_name)
    if is_good == False:
        raise CustomError("Invalid preprocessing name")
    return True

async def create_preprocessing(preprocessing_name: str, preprocessing_type: str, workspace_id: int, owner_id: int,
                 access: int, description: str, instance_id : int, instance_allocate : int, user_list : List[int] = [],
                  built_in_data_type: str = None, built_in_data_tf: str = None):
    
    preprocessing_id = None  # 초기화 추가
    workspace_info = None    # 초기화 추가
    try:
        is_preprocessing_good_name(preprocessing_name=preprocessing_name)
        
        if await db_prepro.get_preprocessing(preprocessing_name=preprocessing_name, workspace_id=workspace_id):
            raise DuplicateKeyError
        
        # workspace 정보 가져오기
        workspace_info = await db_prepro.get_workspace_new(workspace_id=workspace_id)
        # 워크스페이스 기본 자원 관리
        workspace_resource = await db_workspace.get_workspace_resource_new(workspace_id=workspace_id)
        
        # DB 추가
        preprocessing_id = None
        preprocessing_id = await db_prepro.create_preprocessing(workspace_id=workspace_id, type=preprocessing_type, name=preprocessing_name, access=access, description=description,
                                               owner_id=owner_id, instance_id=instance_id, instance_allocate=instance_allocate, job_ram_limit=workspace_resource["job_ram_limit"],
                                               job_cpu_limit=workspace_resource["job_cpu_limit"], tool_cpu_limit=workspace_resource["tool_cpu_limit"], tool_ram_limit=workspace_resource["tool_ram_limit"],
                                                built_in_data_type=built_in_data_type, built_in_data_tf=built_in_data_tf)
        
        if preprocessing_id:
            # 폴더 생성
            await create_preprocessing_folder(workspace_name=workspace_info["name"], preprocessing_name=preprocessing_name, storage_name=workspace_info["main_storage_name"])
            # user 추가
            user_list.append(owner_id)
            await db_prepro.insert_preprocessing_users(preprocessing_id=preprocessing_id, user_ids=user_list)
            
            # ACL 설정을 위한 webhook 호출
            try:
                user_names = []
                for user_id in user_list:
                    user_info = await db_user.get_user_async(user_id=user_id)
                    if user_info:
                        user_names.append(user_info["name"])
                
                webhook_data = {
                    "project_id": str(preprocessing_id),
                    "project_type": "preprocessing",
                    "workspace_id": str(workspace_id),
                    "is_public": access == 1,
                    "user_list": user_names
                }
                
                ingress_mgmt_url = f"http://{settings.JF_INGRESS_MANAGEMENT_DNS}/api/ingress/webhook/project-created"
                webhook_response = requests.post(ingress_mgmt_url, json=webhook_data, timeout=5)
                if webhook_response.status_code == 201:
                    print(f"ACL webhook called successfully for preprocessing {preprocessing_id}")
                else:
                    print(f"ACL webhook failed for preprocessing {preprocessing_id}: {webhook_response.text}")
            except Exception as e:
                print(f"Error in ACL webhook call for preprocessing {preprocessing_id}: {e}")
                
            # LOG
            await logging_history_async(task=LogParam.Task.PREPROCESSING, action=LogParam.Action.CREATE, user_id=owner_id, workspace_id=workspace_id,\
                task_name=preprocessing_name)
            return True
        else:
            raise PreprocessingCreateError
        
    except CustomErrorList as e:
        if preprocessing_id and workspace_info:
            await db_prepro.delete_preprocessing(preprocessing_id=preprocessing_id)
            await delete_preprocessing_folder(workspace_name=workspace_info["name"], preprocessing_name=preprocessing_name, storage_name=workspace_info["main_storage_name"])
        traceback.print_exc()
        raise e
    except Exception as e:
        if preprocessing_id and workspace_info:
            await db_prepro.delete_preprocessing(preprocessing_id=preprocessing_id)
            await delete_preprocessing_folder(workspace_name=workspace_info["name"], preprocessing_name=preprocessing_name, storage_name=workspace_info["main_storage_name"])
        traceback.print_exc()
        raise e


# 데이터셋 상세 '포맷 변환' 버튼이 자동 생성/재사용하는 예약 프로젝트 이름.
# is_good_name(소문자·숫자·단일 '-') 규칙 준수. preprocessing UNIQUE KEY(workspace_id, name)
# 가 이 이름의 멱등성(동시 호출 중복 생성 방지)을 DB 차원에서 보장한다.
FORMAT_CONVERT_PROJECT_NAME = "dataset-format-convert"


def pick_min_cpu_instance(instances : List[dict]) -> dict:
    """포맷 변환용 최소 인스턴스 선택.

    포맷 변환은 순수 데이터 변환이라 GPU 가 필요 없다(잡은 gpu_count=0 으로 실행).
    실증 중 학습과 쿼터가 충돌하지 않도록 gpu_allocate=0(=CPU 인스턴스)을 우선하고,
    그 다음 cpu/ram 이 작은 순으로 고른다. instance_id 로 tie-break 해 결정적으로 만든다.
    워크스페이스에 할당량(instance_allocate)이 없는 인스턴스는 후보에서 제외.
    """
    candidates = [i for i in (instances or []) if (i.get("instance_allocate") or 0) >= 1]
    if not candidates:
        raise CustomError("No instance is allocated to this workspace. Ask an administrator to allocate one.")
    return sorted(candidates, key=lambda i: (
        i.get("gpu_allocate") or 0,
        i.get("cpu_allocate") or 0,
        i.get("ram_allocate") or 0,
        i.get("instance_id") or 0,
    ))[0]


async def ensure_format_convert_project(workspace_id : int, owner_id : int, header_user_id : int) -> int:
    """데이터셋 상세 '포맷 변환' 전용 built-in 프로젝트 find-or-create (멱등).

    FE 가 프로젝트를 고르지 않도록 워크스페이스당 하나의 FORMAT_CONVERT 프로젝트를
    보장한다. run_job 은 프로젝트에 instance 할당을 요구하므로(Allocate the instance)
    instance_id 가 있는 프로젝트만 재사용 가능으로 본다.

    Return: preprocessing_id
    """
    projects = await db_prepro.get_preprocessing_list(workspace_id=workspace_id,
                                                      preprocessing_type=TYPE.PREPROCESSING_TYPE_B)
    matched = sorted(
        [p for p in (projects or []) if p.get("built_in_data_tf") == TYPE_BUILT_IN.FORMAT_CONVERT],
        key=lambda p: p["id"]
    )

    # 1) 바로 쓸 수 있는(인스턴스 할당된) 기존 프로젝트 재사용 — 가장 낮은 id(결정적).
    for project in matched:
        if project.get("instance_id"):
            return project["id"]

    instance = pick_min_cpu_instance(await db_prepro.get_workspace_instances(workspace_id=workspace_id))

    # 2) 예약 프로젝트가 인스턴스 없이 남아있는 경우(예: instance 삭제 → ON DELETE SET NULL)
    #    만 자동 재할당. 사용자가 직접 만든 프로젝트는 건드리지 않는다.
    reserved = next((p for p in matched if p.get("name") == FORMAT_CONVERT_PROJECT_NAME), None)
    if reserved:
        users = await db_prepro.get_preprocessing_user_list(preprocessing_id=reserved["id"])
        await update_preprocessing(
            preprocessing_id=reserved["id"],
            user_list=[u["id"] for u in (users or [])],
            access=reserved["access"],
            description=reserved.get("description") or "",
            instance_id=instance["instance_id"],
            instance_allocate=1,
            owner_id=reserved["owner_id"],
            header_user_id=header_user_id,
        )
        return reserved["id"]

    # 3) 없으면 생성. 동시 호출은 UNIQUE KEY(workspace_id, name) 위반으로 한쪽만 성공하고
    #    패자는 아래 재조회에서 승자의 id 를 그대로 돌려받는다(멱등).
    try:
        await create_preprocessing(
            preprocessing_name=FORMAT_CONVERT_PROJECT_NAME,
            preprocessing_type=TYPE.PREPROCESSING_TYPE_B,
            workspace_id=workspace_id,
            owner_id=owner_id,
            access=1,  # public — 워크스페이스 공용 유틸리티 프로젝트
            description="Auto-created for dataset format conversion (CSV/TXT/Parquet to JSON/JSONL).",
            instance_id=instance["instance_id"],
            instance_allocate=1,
            user_list=[],
            built_in_data_type=TYPE_BUILT_IN.PREPROCESSING_BUILT_IN_TABULAR_TYPE,
            built_in_data_tf=TYPE_BUILT_IN.FORMAT_CONVERT,
        )
    except Exception:
        # 중복 생성(동시 호출 패자)일 수 있으므로 삼키고 재조회로 판정.
        traceback.print_exc()

    created = await db_prepro.get_preprocessing(workspace_id=workspace_id,
                                                preprocessing_name=FORMAT_CONVERT_PROJECT_NAME)
    if not created or not created.get("instance_id"):
        raise CustomError("Failed to prepare the format conversion project.")
    return created["id"]

#=======================================================
# UPDATE
#=======================================================

async def update_preprocessing(preprocessing_id : int, user_list: List[int],
                     access: int, description: str, instance_id : int, instance_allocate : int, owner_id : int, header_user_id : int):
    # global redis_client
    
    try:
        old_preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_id)
        if not old_preprocessing_info:
            raise ItemNotExistError
        
        workspace_resource = await db_workspace.get_workspace_resource_new(workspace_id=old_preprocessing_info["workspace_id"])
        
        # 기존 preprocessing 사용자 목록 가져오기  
        old_users = await db_prepro.get_preprocessing_user_list(preprocessing_id=preprocessing_id)
        old_user_ids = {user["id"] for user in old_users}
        
        # 현재 요청된 사용자 목록과 비교
        if owner_id not in user_list:
            user_list.append(owner_id)
        new_user_ids = set(user_list)
        
        # 다른 속성들이 변경되었는지 확인
        basic_info_changed = (
            old_preprocessing_info["description"] != description or
            old_preprocessing_info["access"] != access or
            old_preprocessing_info["instance_id"] != instance_id or
            old_preprocessing_info["instance_allocate"] != instance_allocate or
            old_preprocessing_info["owner_id"] != owner_id
        )
        
        # 사용자 목록만 변경되고 다른 중요한 속성은 변경되지 않은 경우
        users_only_changed = (old_user_ids != new_user_ids) and not basic_info_changed
        
        # Tool이 실행 중인지 확인 (사용자 목록만 변경된 경우는 제외)
        if not users_only_changed:
            preprocessing_tool_list = await db_prepro.get_preprocessing_tools(preprocessing_id=preprocessing_id)
            for preprocessing_tool in preprocessing_tool_list:
                if preprocessing_tool["request_status"] == 1:  # 1 = Running status
                    raise CustomError("실행중인 개발도구가 있습니다. 종료 후 진행해주세요.")
        
        # instance 사용개수 체크
        # TODO: Implement instance allocation validation if needed
        # if instance_id != old_preprocessing_info["instance_id"] or instance_allocate != old_preprocessing_info["instance_allocate"]:
        #     await check_instance_allocate_total(workspace_id = old_preprocessing_info["workspace_id"], instance_id = instance_id, instance_allocate=instance_allocate, preprocessing_id=old_preprocessing_info["id"])
        
        # DB 업데이트
        import datetime
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db_prepro.update_preprocessing(preprocessing_id=preprocessing_id, description=description, instance_id=instance_id, instance_allocate=instance_allocate, owner_id=owner_id, access=access,
                                       job_ram_limit=workspace_resource["job_ram_limit"], job_cpu_limit=workspace_resource["job_cpu_limit"], tool_cpu_limit=workspace_resource["tool_cpu_limit"], tool_ram_limit=workspace_resource["tool_ram_limit"], update_datetime=current_time)
        
        # 사용자 목록 업데이트
        if user_list and user_list != []:
            await db_prepro.delete_preprocessing_users(preprocessing_id=preprocessing_id, user_ids=[])
            if owner_id not in user_list:
                user_list.append(owner_id)
            await db_prepro.insert_preprocessing_users(preprocessing_id=preprocessing_id, user_ids=user_list)
        else:
            user_list = [owner_id]
            await db_prepro.delete_preprocessing_users(preprocessing_id=preprocessing_id, user_ids=[])
            await db_prepro.insert_preprocessing_users(preprocessing_id=preprocessing_id, user_ids=[owner_id])
        
        # ACL 설정을 위한 webhook 호출
        try:
            user_names = []
            for user_id in user_list:
                user_info = await db_user.get_user_async(user_id=user_id)
                if user_info:
                    user_names.append(user_info["name"])
            
            webhook_data = {
                "project_id": str(preprocessing_id),
                "project_type": "preprocessing",
                "workspace_id": str(old_preprocessing_info["workspace_id"]),
                "is_public": access == 1,
                "user_list": user_names
            }
            
            ingress_mgmt_url = f"http://{settings.JF_INGRESS_MANAGEMENT_DNS}/api/ingress/webhook/project-updated"
            webhook_response = requests.post(ingress_mgmt_url, json=webhook_data, timeout=5)
            if webhook_response.status_code == 200:
                print(f"ACL webhook called successfully for preprocessing {preprocessing_id}")
            else:
                print(f"ACL webhook failed for preprocessing {preprocessing_id}: {webhook_response.text}")
        except Exception as e:
            print(f"Error in ACL webhook call for preprocessing {preprocessing_id}: {e}")
        
        # LOG
        await logging_history_async(task=LogParam.Task.PREPROCESSING, action=LogParam.Action.UPDATE, user_id=header_user_id, workspace_id=old_preprocessing_info["workspace_id"],\
            task_name=old_preprocessing_info["name"])
        
        return True
    except CustomErrorList as e:
        traceback.print_exc()
        raise e
    except Exception as e:
        traceback.print_exc()
        raise e

#=======================================================
# POD RUNNING
#=======================================================

async def control_tool(preprocessing_tool_id : int, action : str, gpu_cluster_auto : bool = False, gpu_count : int = 0, docker_image_id : int = None, gpu_select : List[dict] = [], \
    gpu_auto_select: dict = {}, gpu_cluster_case_old : List[dict] = [], gpu_cluster_list_old : List[dict] = [], pod_per_gpu : int = 0, dataset_id : int = None):
    # global redis_client
    
    try:
        preprocessing_tool_info = await db_prepro.get_preprocessing_tool(preprocessing_tool_id=preprocessing_tool_id)
        if preprocessing_tool_info is None:
            raise ItemNotExistError
        
        if action == "start" or action == "on":
            await run_preprocessing_tool(preprocessing_tool_id=preprocessing_tool_id , docker_image_id=docker_image_id, gpu_cluster_auto=gpu_cluster_auto, gpu_count=gpu_count, gpu_select=gpu_select, \
                gpu_auto_select=gpu_auto_select, gpu_cluster_case_old=gpu_cluster_case_old, gpu_cluster_list_old=gpu_cluster_list_old, pod_per_gpu=pod_per_gpu, dataset_id=dataset_id)
            
            # ACL 설정을 위한 webhook 호출 (tool 시작 시)
            try:
                preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_tool_info["preprocessing_id"])
                if preprocessing_info:
                    webhook_data = {
                        "tool_id": str(preprocessing_tool_id),
                        "project_id": str(preprocessing_info["id"]),
                        "project_type": "preprocessing",
                        "workspace_id": str(preprocessing_info["workspace_id"])
                    }
                    
                    ingress_mgmt_url = f"http://{settings.JF_INGRESS_MANAGEMENT_DNS}/api/ingress/webhook/tool-created"
                    webhook_response = requests.post(ingress_mgmt_url, params=webhook_data, timeout=5)
                    if webhook_response.status_code == 201:
                        print(f"ACL webhook called successfully for tool {preprocessing_tool_id}")
                    else:
                        print(f"ACL webhook failed for tool {preprocessing_tool_id}: {webhook_response.text}")
            except Exception as e:
                print(f"Error in ACL webhook call for tool {preprocessing_tool_id}: {e}")
            
        elif action == "stop" or action == "off":
            await stop_preprocessing_tool(preprocessing_tool_id=preprocessing_tool_id)
        else:
            raise CustomError("Not supports action")
        
        return True
            
    except Exception as e:
        traceback.print_exc()
        raise e

async def stop_preprocessing_tool(preprocessing_tool_id : int):
    preprocessing_tool_info = await db_prepro.get_preprocessing_tool(preprocessing_tool_id=preprocessing_tool_id)
    
    tool_commit_status = get_commit_image_installing_status(preprocessing_tool_id=preprocessing_tool_id)
    if tool_commit_status:
        raise Exception("Saving tool images.")
    
    res ,message = await delete_tool_helm(preprocessing_tool_type=TYPE.TOOL_TYPE[preprocessing_tool_info["tool_type"]], preprocessing_tool_id=preprocessing_tool_id, workspace_id=preprocessing_tool_info["workspace_id"])
    res = db_prepro.update_preprocessing_tool_datetime(preprocessing_tool_id=preprocessing_tool_id, end_datetime=datetime.datetime.now().strftime(TYPE.TIME_DATE_FORMAT))
        
    return res

async def run_preprocessing_tool(preprocessing_tool_id : int , docker_image_id : int , gpu_cluster_auto : bool = False, gpu_count : int = 0, gpu_select : List[dict] = [], \
    gpu_auto_select: dict = {}, gpu_cluster_case_old : List[dict] = [], gpu_cluster_list_old : List[dict] = [], pod_per_gpu : int = 0, dataset_id : int = None):
    try:
        redis_client = await get_redis_client_async()
        preprocessing_tool_info = await db_prepro.get_preprocessing_tool(preprocessing_tool_id=preprocessing_tool_id)
        if not preprocessing_tool_info:
            raise Exception("tool not exist")
        
        if preprocessing_tool_info["request_status"] == 1:
            raise Exception("Already running request")
        

        if gpu_count > 1 and gpu_cluster_auto: # 자동 설정 
            if not gpu_auto_select:
                raise Exception("Please select a cluster type")
            
            new_gpu_cluster_case = await get_gpu_cluster_info_auto(preprocessing_id=preprocessing_tool_info["preprocessing_id"], gpu_count=gpu_count)
            if new_gpu_cluster_case != gpu_cluster_case_old:
                return False
        elif gpu_count > 1 and not gpu_cluster_auto: # 수동 설정
            if not gpu_select:
                raise Exception("Please select gpus")
            gpu_cluster_list_new = await common.get_gpu_cluster_info(instance_id=preprocessing_tool_info["instance_id"], redis_client=redis_client)
            if gpu_cluster_list_new != gpu_cluster_list_old:
                return False
            check_gpu_select(gpu_select=gpu_select, pod_per_gpu=pod_per_gpu)
            
        
        # redis_workspace_pod_status =await redis_hget(main_key=redis_key.WORKSPACE_PODS_STATUS, sub_key=project_tool_info["workspace_id"])
        # if redis_workspace_pod_status is None:
        #     redis_workspace_pod_status = dict()
        # else:
        #     redis_workspace_pod_status = json.loads(redis_workspace_pod_status)
        # project_tools_status = redis_workspace_pod_status.get("tool", {})
        # if str(project_tool_id) in project_tools_status and project_tools_status[str(project_tool_id)]["status"] == "running":
        #     raise Exception("Already running")
        
        if gpu_select and len(gpu_select) != gpu_count:
            raise Exception("The number of GPUs requested and GPU selection do not match.")
        
        preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_tool_info["preprocessing_id"])
        if not preprocessing_info["instance_id"]:
            raise Exception("Allocate the instance")
        preprocessing_gpu_total = 0
        if preprocessing_info["gpu_allocate"]:
            preprocessing_gpu_total = preprocessing_info["gpu_allocate"] * preprocessing_info["instance_allocate"]
            
        if gpu_count > preprocessing_gpu_total:
            raise Exception("Please correct the number of gpu")
        preprocessing_tool_info["gpu_count"] = gpu_count
        preprocessing_tool_info["pod_type"] = TYPE.PREPROCESSING_TYPE
        preprocessing_tool_info["work_func_type"] = TYPE.PREPROCESSING_ITEM_A
        image_info = db_image.get_image(image_id=docker_image_id)
        if image_info == None:
            
            raise Exception("not exist image")
        preprocessing_tool_info["image_name"] = image_info["real_name"]
        preprocessing_tool_info["image_id"] = docker_image_id
        dataset_info = await db_dataset.get_dataset_async(dataset_id=dataset_id)
        if not dataset_info:
            raise Exception("not exist dataset")
        preprocessing_tool_info["dataset_id"] = dataset_id
        # tool password 지정
        characters = string.ascii_letters + string.digits + "-_./:@#+%=^~"
        tool_password = ''.join(random.choice(characters) for _ in range(12))
        if not await db_prepro.update_preprocessing_tool_request(preprocessing_tool_id=preprocessing_tool_id, request_status=1, gpu_cluster_auto=gpu_cluster_auto, \
            gpu_count=gpu_count, image_id=docker_image_id, gpu_select=json.dumps(gpu_select), tool_password=tool_password, dataset_id=dataset_id):
            raise Exception("update failed project tool")
        
        # 기존 실행중이던 tool 삭제 
        tool_type = preprocessing_tool_info["tool_type"]
        await delete_tool_helm(preprocessing_tool_type=TYPE.TOOL_TYPE[tool_type], preprocessing_tool_id=preprocessing_tool_id, workspace_id=preprocessing_info["workspace_id"])
        
        preprocessing_tool_info["gpu_cluster_auto"] = gpu_cluster_auto
        preprocessing_tool_info["gpu_select"] = gpu_select
        preprocessing_tool_info["gpu_auto_cluster_case"] = gpu_auto_select
        preprocessing_tool_info["tool_password"] = tool_password
        preprocessing_tool_info["pod_per_gpu"] = pod_per_gpu
        preprocessing_tool_info["preprocessing_type"] = preprocessing_info["type"]
        
        # 데이터 체크 
        preprocessing_tool_info = PreprocessingTool(**preprocessing_tool_info)
        topic = topic_key.SCHEDULER_TOPIC
        
        producer = AIOKafkaProducer(
        bootstrap_servers=settings.JF_KAFKA_DNS,
        value_serializer=lambda v: str(v).encode('utf-8'),  # 모든 값을 문자열로 변환 후 바이트로 직렬화
        # key_serializer=lambda v: v.encode('utf-8')    # 문자열 키를 바이트로 직렬화
        )
        # 프로듀서 시작
        await producer.start()
        try:
            # 메시지 보내기
            message = preprocessing_tool_info.model_dump_json()
            await producer.send_and_wait(topic, value=message)
        except Exception as e:
            traceback.print_exc()
            raise e
        finally:
            # 프로듀서 종료
            await producer.stop()
        return True
    
    except Exception as e:
        await db_prepro.update_preprocessing_tool_request_status(preprocessing_tool_id=preprocessing_tool_id, request_status=0)
        raise False

async def run_job(preprocessing_id : int, parameter: str, create_user_id : int, \
    job_name : str, run_code: str = None, image_id : int = None,  gpu_count: int = 0, gpu_cluster_auto : bool = False, gpu_select : List[dict] = [], gpu_auto_select: dict = {}, \
         gpu_cluster_case_old : List[dict] = [], gpu_cluster_list_old : dict = {}, pod_per_gpu : int = 0, \
            dataset_id : int = None, get_job_id : int = 0, dataset_data_path : str = None, built_in_param : dict = None):
    try:
        preprocessing_info = await db_prepro.get_preprocessing(preprocessing_id=preprocessing_id)
        redis_client = await get_redis_client_async()
        if not preprocessing_info["instance_id"]:
            raise Exception("Allocate the instance")
        if gpu_count > 1 and gpu_cluster_auto: # 자동 설정 
            if not gpu_auto_select:
                raise Exception("Please select a cluster type")
            
            new_gpu_cluster_case = await get_gpu_cluster_info_auto(preprocessing_id=preprocessing_id, gpu_count=gpu_count)
            if new_gpu_cluster_case != gpu_cluster_case_old:
                return False
        elif gpu_count > 1 and not gpu_cluster_auto: # 수동 설정
            if not gpu_select:
                raise Exception("Please select gpus")
            gpu_cluster_list_new = await common.get_gpu_cluster_info(instance_id=preprocessing_info["instance_id"], redis_client=redis_client)
            if gpu_cluster_list_new != gpu_cluster_list_old:
                return False
            check_gpu_select(gpu_select=gpu_select, pod_per_gpu=pod_per_gpu)
        
        if gpu_select and gpu_count != len(gpu_select):
            raise Exception("The number of GPUs requested and GPU selection do not match.")
        
        if image_id is None:
            image_id = db_image.get_image_id_by_name(name=settings.JF_DEFAULT_UBUNTU_22)["id"]
        
        image_info = db_prepro.get_image_info(image_id=image_id)
        
        dataset_info = await db_dataset.get_dataset_async(dataset_id=dataset_id)
        if not dataset_info:
            raise Exception("not exist dataset")
        
        # TODO
        # built in 일 경우 param 확인 
        if preprocessing_info["type"] == TYPE.PREPROCESSING_TYPE_B:
            # param check
            
            parameter = common.parameter_dict_to_str(built_in_param)
            # built-in 잡은 FE 가 run_code 를 안 보냄 → TFS 스크립트명으로 파생(스케줄러가
            # /built_in/<script> 로 재계산·실행). preprocessing_job.run_code NOT NULL 대응
            # (SDS 뿐 아니라 모든 built-in 공통 — null insert IntegrityError fix).
            if run_code is None:
                run_code = TYPE_BUILT_IN.PREPROCESSING_TFS_SCRIPT.get(
                    preprocessing_info["built_in_data_tf"], ""
                )

        
        job_info = {
            "create_user_id" : create_user_id,
            "preprocessing_type" : preprocessing_info["type"],
            "dataset_id" : dataset_id,
            "workspace_id" : preprocessing_info["workspace_id"],
            "preprocessing_id" : preprocessing_id,
            "preprocessing_name" : preprocessing_info["name"],
            "owner_id" : preprocessing_info["owner_id"],
            "owner_name" : preprocessing_info["owner_name"],
            "job_name" : job_name,
            "image_name" : image_info["real_name"],
            "image_id" : image_id, 
            "workspace_name" : preprocessing_info["workspace_name"],
            "run_code" : run_code,
            "parameter" : parameter,
            "gpu_count" : gpu_count,
            "gpu_cluster_auto" : gpu_cluster_auto,
            "dataset_data_path" : dataset_data_path,
            "resource_type" : preprocessing_info["instance_type"],
            "instance_id" : preprocessing_info["instance_id"],
            "work_func_type" : TYPE.PREPROCESSING_ITEM_B,
            "gpu_select" : gpu_select,
            "gpu_auto_cluster_case" : gpu_auto_select,
            "pod_per_gpu" : pod_per_gpu,
            "built_in_data_type" : preprocessing_info["built_in_data_type"],
            "built_in_data_tf" : preprocessing_info["built_in_data_tf"]
        }
        
        job_id = None
        job_id = await db_prepro.create_preprocessing_job(preprocessing_id=preprocessing_id, create_user_id=create_user_id, image_id=image_id, resource_type=preprocessing_info["instance_type"],
                                        name=job_name, gpu_count=gpu_count, resource_group_id=preprocessing_info["gpu_resource_group_id"], dataset_data_path=dataset_data_path,
                                        parameter=parameter, run_code=run_code, gpu_cluster_auto=gpu_cluster_auto, dataset_id=dataset_id)
        
        if job_id:
            job_info["id"] = job_id
            
            # 데이터 체크
            
            job_info = PreprocessingJob(**job_info)
            topic = topic_key.SCHEDULER_TOPIC
                
            
            producer = AIOKafkaProducer(
            bootstrap_servers=settings.JF_KAFKA_DNS,
            value_serializer=lambda v: v.encode('utf-8'),  # 문자열 값을 바이트로 직렬화
            # key_serializer=lambda v: v.encode('utf-8')    # 문자열 키를 바이트로 직렬화
            )
            # 프로듀서 시작
            await producer.start()
            try:
                # 메시지 보내기
                await producer.send_and_wait(topic ,value=job_info.model_dump_json())
            finally:
                # 프로듀서 종료
                await producer.stop()
            if get_job_id:
                return job_id
            return True
        else:
            raise Exception("job create error")
    except Exception as e:
        traceback.print_exc()
        if job_id:
            db_prepro.delete_job(job_id=job_id)
        raise e

async def stop_job(job_id : int):
    
    # global redis_client
    redis_client = await get_redis_client_async()
    job_info = await db_prepro.get_job(job_id=job_id)
    if not job_info:
        raise Exception("not exist training")
    if job_info["end_datetime"]:
        raise Exception("already done")
    redis_workspace_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, job_info["workspace_id"])
    if redis_workspace_pod_status:
        redis_workspace_pod_status = json.loads(redis_workspace_pod_status)
    else:
        redis_workspace_pod_status = {}
    
    preprocessings_pod_status = redis_workspace_pod_status.get(TYPE.PREPROCESSING_TYPE, {})
    preprocessing_pod_status = preprocessings_pod_status.get(str(job_info["preprocessing_id"]), {})
    
    
    job_status = preprocessing_pod_status.get(TYPE.PREPROCESSING_ITEM_B, {})
    await delete_tool_helm(preprocessing_tool_type=TYPE.PREPROCESSING_ITEM_B, preprocessing_tool_id=job_id, workspace_id=job_info["workspace_id"])
    if str(job_id) in job_status:
        db_prepro.update_preprocessing_job_datetime(preprocessing_job_id=job_id, end_datetime=time.strftime('%Y-%m-%d %H:%M:%S'), end_status="stop")
    elif not job_info["start_datetime"] and str(job_id) not in job_status: # pending
        db_prepro.delete_job(job_id=job_id)
    return True


#========================================================
# SSE
#========================================================

async def sse_get_preprocessing_status(preprocessing_id : int, request : Request):
    old_history = None
    old_datetime = datetime.datetime.now()
    try:
        while True:
            if await request.is_disconnected():
                break
            current_datetime = datetime.datetime.now()
            tools = await db_prepro.get_preprocessing_tool_by_request(preprocessing_id=preprocessing_id)
            jobs = await db_prepro.get_jobs_is_request(preprocessing_id=preprocessing_id)
            status = {
                "status" : TYPE.KUBE_POD_STATUS_RUNNING if tools or jobs else TYPE.KUBE_POD_STATUS_DONE,
                }
            if status != old_history:
                print(status)
                old_history = status
                old_datetime = current_datetime
                yield f"data: {json.dumps(status)}\n\n"
            elif (current_datetime - old_datetime).total_seconds() >=30:
                old_datetime = current_datetime
                yield f"data: {json.dumps(old_history)}\n\n"
            await asyncio.sleep(1)
    except Exception as e:
        # 예외 처리 및 로그 남기기
        traceback.print_exc()
        print(f"Exception in SSE stream: {e}")
    finally:
        # 연결이 끊어졌을 때의 후속 처리
        pass



#========================================================
# START CHECK
#=======================================================

async def check_preprocessing_pods():
    all_preprocessing = await db_prepro.get_preprocessing_all()
    redis_client = await get_redis_client_async()
    
    for preprocessing in all_preprocessing:
        workspace_pods_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, preprocessing["workspace_id"])
        if workspace_pods_status:
            workspace_pods_status = json.loads(workspace_pods_status)
        else:
            workspace_pods_status = {}
        preprocessing_pod_status = workspace_pods_status.get(TYPE.PREPROCESSING_TYPE, {})
        preprocessing_pod_status = preprocessing_pod_status.get(str(preprocessing["id"]), {})
        tools = await db_prepro.get_preprocessing_tool_by_request(preprocessing_id=preprocessing["id"])
        jobs = await db_prepro.get_jobs_is_running(preprocessing_id=preprocessing["id"])
        
        for tool in tools:
            if str(tool["id"]) not in preprocessing_pod_status.get(TYPE.PREPROCESSING_ITEM_A, {}):
                db_prepro.update_preprocessing_tool_datetime(preprocessing_tool_id=tool["id"], end_datetime=datetime.datetime.today().strftime(TYPE.TIME_DATE_FORMAT), error_reason="Pod is not running")
        for job in jobs:
            if str(job["id"]) not in preprocessing_pod_status.get(TYPE.PREPROCESSING_ITEM_B, {}):
                db_prepro.update_preprocessing_job_datetime(preprocessing_job_id=job["id"], end_datetime=datetime.datetime.today().strftime(TYPE.TIME_DATE_FORMAT), end_status=TYPE.KUBE_POD_STATUS_ERROR, error_reason="Pod is not running")


