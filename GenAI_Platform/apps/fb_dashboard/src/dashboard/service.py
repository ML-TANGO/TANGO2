import os
import re
import subprocess
import traceback
import time
import requests
from fastapi import Request
from utils.common import byte_to_gigabyte, make_nested_dict
from datetime import datetime, timedelta
# import utils.storage

from dashboard import records
import json
# from restplus import api
from utils import settings, redis_key, TYPE, common
import utils.db as db
import utils.msa_db.db_dashboard as db_dashboard
from utils.msa_db import db_workspace, db_deployment, db_project, db_user, db_dataset, db_storage, db_prepro, db_collect, db_analyzing
if settings.LLM_USED:
    from utils.llm_db import db_model, db_playground, db_rag

# import utils.storage as sto
from utils.redis import  get_redis_client, get_redis_client_async
# from utils.resource import CustomResource #, token_checker
from utils.resource import response
from utils.exception.exceptions import *
from utils.access_check import workspace_access_check
import copy
from kubernetes import config, client
import logging
from utils.crypt import front_cipher
config.load_kube_config(config_file=settings.KUBER_CONFIG_PATH)
coreV1Api = client.CoreV1Api()


from dashboard import dummy

from collections import Counter
import functools
import time
import asyncio
import crypt

def async_timed(func):
    """
    데코레이터: 비동기 함수의 실행 시간을 측정합니다.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = await func(*args, **kwargs)
        end_time = time.perf_counter()
        run_time = end_time - start_time
        print(f"Function {func.__name__!r} executed in {run_time:.4f} seconds")
        return result
    return wrapper

async def check_healthz():
    redis_client = await get_redis_client_async()
    await redis_client.hgetall(redis_key.WORKSPACE_PODS_STATUS)
    return True

#===================================================================================================
# admin dashboard
def get_admin_dashboard_info():
    try:
        reval = {
            "history":[], # 최근실행기록
            "totalCount":[], # 최근실행기록 상단 (워크스페이스, 학습, 배포, ...)
            "resource_usage":{}, # TODO -> 사용률 - ELK 추가
        }
        reval["history"] = [] # db.get_records_for_dashboard() # TODO
        reval["totalCount"] = db_dashboard.get_admin_dashboard_total_count()
        reval["resource_usage"] = get_total_system_resource_usage() # TODO -> 사용률 - ELK 추가
        try:
            history_url = f"http://log-middleware-rest.jonathan-efk:8080/v1/dashboard/admin"
            history_response = requests.post(history_url, json={"timespan": "7d", "count": 10})
            history_raw = history_response.json()
            histories = []
            if history_raw.get("logs", None):
                for history in history_raw["logs"]:
                    current_document = history["fields"]
                    current_document["update_details"] = "-"
                    histories.append(current_document)

            reval["history"] = histories
        except:
            pass
        
        # TODO 삭제 - 없으면 터져서 남겨둠
        # reval["timeline"] = records.get_all_workspace_gpu_usage(days=31) 
        # reval["detailed_timeline"] = records.get_workspace_gpu_usage_10_mins(workspace_id='ALL', cutoff=72)
        
        
        # reval["usage"]['hdd'] = dashboard_get_total_storage_usage()
        # reval["usage"]['gpuByType'] = get_all_current_gpu_usage_by_type()
        # reval["usage"]['gpuByGuarantee'] = get_all_current_gpu_usage_by_guarantee()

    except Exception as e:
        traceback.print_exc()
        # raise GetAdminDashboardError
        # return response(status=0, message="Get admin dashboard info Error")
    return response(status=1, result=reval)

def get_total_system_resource_usage():
    # TODO -> 사용률 - ELK 추가
    # date : UTC로 보내주고 프론트에서 KST로 처리
    return dummy.dummy_admin_total_system_resource_usage

# ===================================================================================================
# user dashboard

def get_workspace_used_gpu(workspace_id : int, data : dict) -> tuple:
    project_count = 0
    deployment_count = 0
    for node in data.values():
        for gpu in node.values():
            if gpu.get("used_type", None) == "project" and gpu['used_info'].get('used_workspace') == str(workspace_id):
                project_count += 1
            if gpu.get("used_type", None) == "deployment" and gpu['used_info'].get('used_workspace') == str(workspace_id):
                deployment_count += 1
    return project_count, deployment_count
# @async_timed
async def get_storage_used(redis_client, workspace_id):
    """
    스토리지 사용 현황
    """
    try:
        tmp_storage_list_resource = await redis_client.get(redis_key.STORAGE_LIST_RESOURCE)
        storage_info = json.loads(tmp_storage_list_resource) if tmp_storage_list_resource is not None else dict()
        data_storage_usage = await redis_client.hgetall(redis_key.DATASET_STORAGE_USAGE)
        fb_main_storage_usage = await redis_client.hgetall(redis_key.PROJECT_STORAGE_USAGE)
        allm_main_storage_usage = await redis_client.hgetall(redis_key.MODEL_STORAGE_USAGE)
        allm_main_rag_storage_usage = await redis_client.hgetall(redis_key.RAG_STORAGE_USAGE)
        
        storage = copy.deepcopy(dummy.dummy_user_storage)
        if storage_info:
            ws_info = await db_workspace.get_workspace_async(workspace_id=workspace_id)
            dataset_list = await db_dataset.get_dataset_list_new(workspace_id=workspace_id)
            project_list = await db_project.get_project_list_new(workspace_id=workspace_id)
            if settings.LLM_USED:
                model_list = await db_model.get_models(workspace_id=workspace_id)
                rag_list = await db_rag.get_rag_list(workspace_id=workspace_id)
            
            main_storage_usage_list = storage_info[str(ws_info['main_storage_id'])].get('workspaces', [])
            # print(main_storage_usage_list)
            for main_storage in main_storage_usage_list['main']:
                if main_storage['workspace_name'] == ws_info['name']:
                    storage['main_storage']['total']=main_storage['alloc_size']
                    storage['main_storage']['used']=main_storage['used_size']
                    storage['main_storage']['avail']=main_storage['alloc_size']-main_storage['used_size']
                    storage['main_storage']['usage']=round(main_storage['used_size']/main_storage['alloc_size']*100) if main_storage['used_size'] else 0
                    break

            for project in project_list:
                project_usage = int(fb_main_storage_usage.get(str(project['id']), 0))
                storage['main_storage']['project_list'].append(
                    {
                        'id': project['id'],
                        'name': project['name'],
                        'usage': round(project_usage/storage['main_storage']['total']*100) if project_usage else 0
                    }
                )
                storage['main_storage']['fb_usage'] += project_usage
            if settings.LLM_USED:
                for model in model_list:
                    model_usage = int(allm_main_storage_usage.get(str(model['id']), 0))
                    storage['main_storage']['allm_list'].append(
                        {
                            'id': model['id'],
                            'name': model['name'],
                            'usage': round(model_usage/storage['main_storage']['total']*100) if model_usage else 0
                        }
                    )
                    storage['main_storage']['allm_usage'] += model_usage

                for rag in rag_list:
                    rag_usage = int(allm_main_rag_storage_usage.get(str(rag['id']), 0))
                    storage['main_storage']['allm_list'].append(
                        {
                            'id': rag['id'],
                            'name': rag['name'],
                            'usage': round(rag_usage/storage['main_storage']['total']*100) if rag_usage else 0
                        }
                    )
                    storage['main_storage']['allm_usage'] += rag_usage

                storage['main_storage']['allm_usage'] = round(storage['main_storage']['allm_usage']/storage['main_storage']['total']*100) if storage['main_storage']['allm_usage'] else 0
            storage['main_storage']['fb_usage'] = round(storage['main_storage']['fb_usage']/storage['main_storage']['total']*100) if storage['main_storage']['fb_usage'] else 0
            
            
            data_storage_usage_list = storage_info[str(ws_info['data_storage_id'])].get('workspaces', [])
            if data_storage_usage_list:
                for data_storage in data_storage_usage_list['data']:
                    if data_storage['workspace_name'] == ws_info['name']:
                        storage['data_storage']['total']=data_storage['alloc_size']
                        storage['data_storage']['used']=data_storage['used_size']
                        storage['data_storage']['avail']=data_storage['alloc_size']-data_storage['used_size']
                        storage['data_storage']['usage']=int(data_storage['used_size']/data_storage['alloc_size']*100) if data_storage['used_size'] else 0
                        break
            for dataset in dataset_list :
                data_usage = int(data_storage_usage.get(str(dataset['id']), 0))
                storage['data_storage']['dataset_list'].append(
                    {
                        'id': dataset['id'],
                        'name': dataset['dataset_name'],
                        'usage': round(data_usage/storage['data_storage']['total']*100) if data_usage else 0
                    }
                )
            return storage
    except Exception as e:
        traceback.print_exc()
        return {}
# @async_timed
async def get_workspace_resource_usage(redis_client, workspace_id):
    """
    워크스페이스 자원 사용 현황 - 워크스페이스 리소스 현황
    """
    try:
        # tmp_gpu_info = await redis_client.get(redis_key.GPU_INFO_RESOURCE)
        # gpu_status = json.loads(tmp_gpu_info) if tmp_gpu_info is not None else dict()
        workspace_quota = await redis_client.hget(redis_key.WORKSPACE_RESOURCE_QUOTA, workspace_id) 
        usage = {}
        # project_count, deployment_count = get_workspace_used_gpu(workspace_id=workspace_id, data=gpu_status)

        def safe_divide(a, b):
            try:
                return (a / b) * 100
            except ZeroDivisionError:
                return 0
            
        # start_time=datetime.now()
        # print(workspaces_quota)
        
        if not workspace_quota:
            print("!!!CHECK: workspace_quota IS NONE -> ", workspace_quota)
            workspace_quota = {"gpu" : {"hard" : 0, "used" : 0}, "cpu" : {"hard" : 0, "used" : 0},"ram" : {"hard" : 0, "used" : 0},}
        else:
            workspace_quota = json.loads(workspace_quota)
        usage['gpu'] = {
            "total" : workspace_quota.get("gpu").get("hard"),
            "used" : workspace_quota.get("gpu").get("used"),
            "usage" : safe_divide(workspace_quota.get("gpu").get("used"), workspace_quota.get("gpu").get("hard")),
            # "used_training" : project_count,
            # "used_deployment" : deployment_count,
        }
        
        usage['cpu'] = {
            "total" : workspace_quota.get("cpu").get("hard"),
            "used" : workspace_quota.get("cpu").get("used"),
            "usage" : safe_divide(workspace_quota.get("cpu").get("used"), workspace_quota.get("cpu").get("hard")),
        }
        
        usage['ram'] = {
            "total" : byte_to_gigabyte(workspace_quota.get("ram").get("hard")),
            "used" : byte_to_gigabyte(workspace_quota.get("ram").get("used")),
            "usage" : safe_divide(byte_to_gigabyte(workspace_quota.get("ram").get("used")), byte_to_gigabyte(workspace_quota.get("ram").get("hard"))),
        }
        # end_time=datetime.now()
        return usage
    except Exception as e:
        traceback.print_exc()
        return {}
    
# @async_timed
async def get_jonathan_workspace_item_count(workspace_id):
    """
    워크스페이스 자원 사용 현황 - 조나단 아이템 개수
    """
    total_count = await db_workspace.get_workspace_item_count_async(workspace_id=workspace_id)
    total_count['pricing'] = 20 # TODO 가격 정책 추가
    return total_count

# @async_timed
async def get_workspace_instance_used(redis_client, workspace_id):
    """
    인스턴스 별 사용 현황
    """
    try:
        tmp_workspace_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, workspace_id)
        redis_workspace_pod_status = json.loads(tmp_workspace_pod_status) if tmp_workspace_pod_status is not None else dict()
        projects_pod = redis_workspace_pod_status.get(TYPE.PROJECT_TYPE, {})
        preprocessing_pod = redis_workspace_pod_status.get(TYPE.PREPROCESSING_TYPE, {})
        collect_pod = redis_workspace_pod_status.get(TYPE.COLLECT_TYPE, {})
        analyzer_pod = redis_workspace_pod_status.get(TYPE.ANALYZER_TYPE, {})
        deployment_pod = redis_workspace_pod_status.get(TYPE.DEPLOYMENT_TYPE, {})
        model_pod = redis_workspace_pod_status.get(TYPE.FINE_TUNING_TYPE, {})
        
        instances = await db_dashboard.get_workspace_instance_list_new(workspace_id=workspace_id)
        instance_status = make_nested_dict() 
        platform_resource_used_total = {
            TYPE.PLATFORM_FLIGHTBASE : {
                "cpu" : 0,
                "ram" : 0,
                "gpu" : 0
                },
            TYPE.PLATFORM_A_LLM : {
                "cpu" : 0,
                "ram" : 0,
                "gpu" : 0
            }
        }      
        for project_id, project_items in projects_pod.items():
            total_cpu = 0
            total_ram = 0
            total_gpu = 0
            instance_id = None
            for item_type, items in project_items.items():
                for item_id , item_info in items.items():
                    instance_id = instance_id if instance_id else item_info["instance_id"] # TODO 확인 continue 아래에 코드가 있어서 에러인 팟은 instance_id none으로 넘어감
                    if item_info["status"] in TYPE.KUBER_NOT_RUNNING_STATUS:  # 20241217 wyatt 수정
                        continue
                    if item_info["resource"]["cpu"] is not None:
                        total_cpu += item_info["resource"]["cpu"]
                    if item_info["resource"]["ram"] is not None:
                        total_ram += item_info["resource"]["ram"]
                    if item_info["resource"]["gpu"] is not None:
                        total_gpu += item_info["resource"]["gpu"]
            instance_status[int(instance_id)][TYPE.PROJECT_TYPE][project_id] = {
                "cpu" : total_cpu,
                "ram" : total_ram,
                "gpu" : total_gpu
            } 
            platform_resource_used_total[TYPE.PLATFORM_FLIGHTBASE]["cpu"] += total_cpu
            platform_resource_used_total[TYPE.PLATFORM_FLIGHTBASE]["ram"] += total_ram
            platform_resource_used_total[TYPE.PLATFORM_FLIGHTBASE]["gpu"] += total_gpu

        for preprocessing_id, preprocessing_items in preprocessing_pod.items():
            total_cpu = 0
            total_ram = 0
            total_gpu = 0
            instance_id = None
            for item_type, items in preprocessing_items.items():
                for item_id , item_info in items.items():
                    instance_id = instance_id if instance_id else item_info["instance_id"] # TODO 확인 continue 아래에 코드가 있어서 에러인 팟은 instance_id none으로 넘어감
                    if item_info["status"] in TYPE.KUBER_NOT_RUNNING_STATUS:  # 20241217 wyatt 수정
                        continue
                    if item_info["resource"]["cpu"] is not None:
                        total_cpu += item_info["resource"]["cpu"]
                    if item_info["resource"]["ram"] is not None:
                        total_ram += item_info["resource"]["ram"]
                    if item_info["resource"]["gpu"] is not None:
                        total_gpu += item_info["resource"]["gpu"]
            instance_status[int(instance_id)][TYPE.PREPROCESSING_TYPE][preprocessing_id] = {
                "cpu" : total_cpu,
                "ram" : total_ram,
                "gpu" : total_gpu
            } 
            platform_resource_used_total[TYPE.PLATFORM_FLIGHTBASE]["cpu"] += total_cpu
            platform_resource_used_total[TYPE.PLATFORM_FLIGHTBASE]["ram"] += total_ram
            platform_resource_used_total[TYPE.PLATFORM_FLIGHTBASE]["gpu"] += total_gpu
        
        for collect_id, collect_item in collect_pod.items():
            total_cpu = 0
            total_ram = 0
            total_gpu = 0
            instance_id = None
            instance_id = collect_item["instance_id"] if collect_item.get("instance_id", None) else instance_id  # TODO 확인 continue 아래에 코드가 있어서 에러인 팟은 instance_id none으로 넘어감
            if collect_item["status"] in TYPE.KUBER_NOT_RUNNING_STATUS:  # 20241217 wyatt 수정
                continue
            if collect_item["resource"]["cpu"] is not None:
                total_cpu += collect_item["resource"]["cpu"]
            if collect_item["resource"]["ram"] is not None:
                total_ram += collect_item["resource"]["ram"]
            if collect_item["resource"]["gpu"] is not None:
                total_gpu += collect_item["resource"]["gpu"]
                    
            instance_status[int(instance_id)][TYPE.COLLECT_TYPE][collect_id] = {
                "cpu" : total_cpu,
                "ram" : total_ram,
                "gpu" : total_gpu
            } 
            platform_resource_used_total[TYPE.PLATFORM_FLIGHTBASE]["cpu"] += total_cpu
            platform_resource_used_total[TYPE.PLATFORM_FLIGHTBASE]["ram"] += total_ram
            platform_resource_used_total[TYPE.PLATFORM_FLIGHTBASE]["gpu"] += total_gpu

        # TODO 분석기 추가

        llm_deployment_list = [item.get("id") for item in db_deployment.get_deployment_llm_list(workspace_id=workspace_id)]
        for deployment_id, deployment_workers in deployment_pod.items():
            total_cpu = 0
            total_gpu = 0
            total_ram = 0
            instance_id = None

            for worker_id, worker_info in deployment_workers.items():
                instance_id = instance_id if instance_id else worker_info["instance_id"] # TODO 확인 make_nested_dict???
                if worker_info["status"] in TYPE.KUBER_NOT_RUNNING_STATUS:  # 20241217 wyatt 수정
                    continue
                total_cpu += worker_info["resource"]["cpu"]
                total_ram += worker_info["resource"]["ram"]
                total_gpu += worker_info["resource"]["gpu"] 
            instance_status[int(instance_id)][TYPE.DEPLOYMENT_TYPE][deployment_id] = {
                "cpu" : total_cpu,
                "ram" : total_ram,
                "gpu" : total_gpu
            } 

            if int(deployment_id) not in llm_deployment_list:
                platform_resource_used_total[TYPE.PLATFORM_FLIGHTBASE]["cpu"] += total_cpu
                platform_resource_used_total[TYPE.PLATFORM_FLIGHTBASE]["ram"] += total_ram
                platform_resource_used_total[TYPE.PLATFORM_FLIGHTBASE]["gpu"] += total_gpu
            else:
                platform_resource_used_total[TYPE.PLATFORM_A_LLM]["cpu"] += total_cpu
                platform_resource_used_total[TYPE.PLATFORM_A_LLM]["ram"] += total_ram
                platform_resource_used_total[TYPE.PLATFORM_A_LLM]["gpu"] += total_gpu

        for model_id, model_train in model_pod.items():
            if model_train["status"] in TYPE.KUBER_NOT_RUNNING_STATUS: # 20241217 wyatt 수정
                continue
            total_cpu = model_train["resource"]["cpu"]
            total_gpu = model_train["resource"]["gpu"] 
            total_ram = model_train["resource"]["ram"]
            instance_id = model_train["instance_id"]
            instance_status[int(instance_id)][TYPE.FINE_TUNING_TYPE][model_id] = {
                "cpu" : total_cpu,
                "ram" : total_ram,
                "gpu" : total_gpu
            }
            platform_resource_used_total[TYPE.PLATFORM_A_LLM]["cpu"] += total_cpu
            platform_resource_used_total[TYPE.PLATFORM_A_LLM]["ram"] += total_ram
            platform_resource_used_total[TYPE.PLATFORM_A_LLM]["gpu"] += total_gpu
            
        for instance in instances:
            # label_selector = "instance_id={},workspace_id={}".format(instance["id"],workspace_id)
            # pods = coreV1Api.list_pod_for_all_namespaces(label_selector=label_selector)
            instance_resource_count = 3 if instance["instance_type"] == TYPE.RESOURCE_TYPE_GPU else 2
            instance_total_gpu = instance["instance_allocate"] * instance["gpu_allocate"]
            instance_total_ram = instance["instance_allocate"] * instance["ram_allocate"]
            instance_total_cpu = instance["instance_allocate"] * instance["cpu_allocate"]
            instance_used_resource = instance_status[instance["id"]]
            instance_used_info = []
            remaining_cpu = instance_total_cpu
            remaining_ram = instance_total_ram
            remaining_gpu = instance_total_gpu
            for workspace_item_type, item_resources in  instance_used_resource.items():
                for item_id, item_resource in item_resources.items():
                    if TYPE.PROJECT_TYPE == workspace_item_type:
                        item_info = await db_project.get_project_new(project_id=item_id)
                    elif TYPE.PREPROCESSING_TYPE == workspace_item_type:
                        item_info = await db_prepro.get_preprocessing(preprocessing_id=item_id)
                        item_info["user_name"] = item_info["owner_name"]
                    elif TYPE.COLLECT_TYPE == workspace_item_type:
                        item_info = await db_collect.get_collect_info_async(collect_id=item_id)
                    elif TYPE.ANALYZER_TYPE == workspace_item_type:
                        item_info = db_analyzing.get_collect_info_async(collect_id=item_id) # 추후 async 추가 해야 함
                    elif TYPE.DEPLOYMENT_TYPE == workspace_item_type:
                        item_info = await db_dashboard.get_deployment(deployment_id=item_id)
                    elif TYPE.FINE_TUNING_TYPE == workspace_item_type:
                        item_info = await db_dashboard.get_model(model_id=item_id)
                        
                    if item_info is None: continue # 임시수정

                    used_gpu_rate = (item_resource["gpu"] / instance_total_gpu) * 100 if instance_total_gpu and instance_total_gpu != 0 else 0
                    remaining_gpu -= item_resource["gpu"] 
                    used_cpu_rate = (item_resource["cpu"] / instance_total_cpu) * 100 if instance_total_cpu and instance_total_cpu != 0 else 0
                    remaining_cpu -= item_resource["cpu"] 
                    used_ram_rate = (item_resource["ram"] / instance_total_ram) * 100 if instance_total_ram and instance_total_ram != 0 else 0
                    remaining_ram -= item_resource["ram"]
                    total_used_rate = (used_gpu_rate + used_cpu_rate + used_ram_rate) / instance_resource_count 
                    
                    
                    instance_used_info.append({
                        "item_type" : workspace_item_type,
                        "item_name" : item_info["name"],
                        "item_user" : item_info["create_user_name"] if item_info.get("create_user_name", None) else item_info["user_name"],
                        "used_resource" : item_resource,
                        "used_rate" : total_used_rate,
                    })
            remaining_gpu_rate = (remaining_gpu / instance_total_gpu) * 100 if instance_total_gpu and instance_total_gpu != 0 else 0
            remaining_cpu_rate = (remaining_cpu / instance_total_cpu) * 100 if instance_total_cpu and instance_total_cpu != 0 else 0
            remaining_ram_rate = (remaining_ram / instance_total_ram)  * 100 if instance_total_ram and instance_total_ram != 0 else 0
            total_remaining_rate = (remaining_gpu_rate + remaining_cpu_rate + remaining_ram_rate) / instance_resource_count
            # print(instance_used_info)
            
            instance["used_rate"] =  sorted(instance_used_info, key=lambda x: x['used_rate'], reverse=True)
            instance["remaining_rate"] = {
                "remaining_rate" : total_remaining_rate,
                "remaining_resource" : {
                    "cpu" : remaining_cpu,
                    "ram" : remaining_ram,
                    "gpu" : remaining_gpu
                }
            }
        return instances, platform_resource_used_total
    except Exception as e:
        traceback.print_exc()
        return [], {}

# @async_timed
async def get_jonathan_items_info(redis_client, workspace_id, platform_type):
    """
    프로젝트 별 작업 현황, 프로젝트별 인스턴스 할당 현황(flightbase만)
    """
    try:
        tmp_workspace_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, workspace_id)
        redis_workspace_pod_status = json.loads(tmp_workspace_pod_status) if tmp_workspace_pod_status is not None else dict()
        # FlightBase # TODO 추후 Flightbase 도 setting에 사용 여부 추가 
        ####################################################################
        if settings.FLIGHTBASE_USED and platform_type == TYPE.PLATFORM_FLIGHTBASE:
            projects_pod = redis_workspace_pod_status.get(TYPE.PROJECT_TYPE, {})
            preprocessing_pod = redis_workspace_pod_status.get(TYPE.PREPROCESSING_TYPE, {})

            deployment_pod = redis_workspace_pod_status.get(TYPE.DEPLOYMENT_TYPE, {})
            parse_project_list = []
            parse_prepro_list = []
            parse_deployment_list = []
            pd_project_list = []
            pd_prepro_list = []
            pd_deployment_list = []
            # TODO 수집기 , 분석기 기획 추가되면 추가하기

            project_list = await db_project.get_project_list_new(workspace_id=workspace_id)
            # for project in project_list:
            async def process_project(project):
                # print(workspace_pod_job)
                # 프로젝트 id
                project_pod_status = projects_pod.get(str(project["id"]), {})
                # workspace_pod_tool = project_pod_status.get(TYPE.TRAINING_ITEM_B, {})
                project_pod_job = project_pod_status.get(TYPE.TRAINING_ITEM_A, {})
                # project_pod_hps = redis_workspace_pod_status.get(TYPE.TRAINING_ITEM_C, {})
                project_tool_active_list = await db_dashboard.get_project_tool_active_list_new(project_id=project.get("id"))
                project_tool_kind_list = list({TYPE.TOOL_TYPE.get(item.get("tool_type")) for item in project_tool_active_list})
                project_job_list = await db_dashboard.get_project_job_list_new(project_id=project.get("id"))
                project_job_id_list = list(item.get("id") for item in project_job_list)
                # project_hps_id_list = list(item.get("id") for item in db_dashboard.get_project_hps_list(project_id=project.get("id")))
                
                job_running_count = 0
                job_pending_count = len(await db_dashboard.get_project_job_pending_list_new(project_id=project.get("id")))
                hps_running_count = 0
                hps_pending_count = 0  # len(db_dashboard.get_project_hps_pending_list(project_id=project.get("id"))) # TODO 추후 HPS 추가 되면 수정
                
                for _id in project_job_id_list:
                    id_str = str(_id)
                    if id_str in project_pod_job and project_pod_job.get(id_str).get("status") == TYPE.KUBE_POD_STATUS_RUNNING:
                        job_running_count += 1      

                # for _id in project_hps_id_list:
                #     id_str = str(_id)
                #     if id_str in project_pod_hps and project_pod_hps.get(id_str).get("status") == TYPE.KUBE_POD_STATUS_RUNNING:
                #         hps_running_count += 1        
                
                parse_project_list.append({
                    "type" : TYPE.PROJECT_TYPE,
                    "name" : project.get("name"),
                    "status_tool" : {"running" : len(project_tool_active_list), "kind" : project_tool_kind_list},
                    "status_job" : {"running" : job_running_count, "pending" : job_pending_count},
                    "status_hps" : {"running" : hps_running_count, "pending" : hps_pending_count},
                    "instance" : {
                        "gpu_name" : project.get("resource_name"),
                        "gpu_allocate" : project.get("gpu_allocate"),
                        "cpu_allocate" : project.get("cpu_allocate"),
                        "ram_allocate" : project.get("ram_allocate"),
                    },
                    "tool_list" : [{
                        "type" : TYPE.TOOL_TYPE.get(i.get("tool_type")),
                        "start_datetime" : i.get("start_datetime"),
                        "gpu_name" : project.get("resource_name"),
                        "gpu_allocate" : i.get("gpu_count"),
                        "cpu_allocate" : project.get("tool_cpu_limit"),
                        "ram_allocate" : project.get("tool_ram_limit"),
                    } for i in project_tool_active_list],
                    "job_list" : [{
                        "job_id" : i.get("id"),
                        "start_datetime" : i.get("start_datetime"),
                        "gpu_name" : project.get("resource_name"),
                        "gpu_allocate" : i.get("gpu_count"),
                        "cpu_allocate" : project.get("job_cpu_limit"),
                        "ram_allocate" : project.get("job_ram_limit"),
                    } for i in project_job_list],
                })
                pd_project_list.append({
                    "name" : project["name"],
                    "type" : "project",
                    "instance_name" : project["instance_name"],
                    "allocate" : project["instance_allocate"],
                    "instance_info" : {
                        "cpu_allocate" : project.get("cpu_allocate"),
                        "gpu_allocate" : project.get("gpu_allocate"),
                        "ram_allocate" : project.get("ram_allocate"),
                        "gpu_name" : project.get("resource_name"),
                    }
                })
            
            await asyncio.gather(*(process_project(project) for project in project_list))
            parse_project_list.sort(key=lambda x: (
                max(x['status_tool']['running'], len(x['status_tool']['kind'])),
                max(x['status_job']['running'], x['status_job']['pending']),
                max(x['status_hps']['running'], x['status_hps']['pending']),
                x['name']
            ), reverse=True)
            pd_project_list = sorted(pd_project_list, key=lambda x : x["name"])
            
            prepro_list = await db_prepro.get_preprocessing_list(workspace_id=workspace_id)
            async def process_prepro(prepro):
                # print(workspace_pod_job)
                # 프로젝트 id
                prepro_pod_status = preprocessing_pod.get(str(prepro["id"]), {})
                # workspace_pod_tool = project_pod_status.get(TYPE.TRAINING_ITEM_B, {})
                prepro_pod_job = prepro_pod_status.get(TYPE.TRAINING_ITEM_A, {})
                # project_pod_hps = redis_workspace_pod_status.get(TYPE.TRAINING_ITEM_C, {})
                prepro_tool_active_list = await db_dashboard.get_prepro_tool_active_list_new(prepro.get("id"))
                prepro_tool_kind_list = list({TYPE.TOOL_TYPE.get(item.get("tool_type")) for item in prepro_tool_active_list})
                prepro_job_list = await db_dashboard.get_prepro_job_list_new(prepro.get("id"))
                prepro_job_id_list = list(item.get("id") for item in prepro_job_list)
                
                job_running_count = 0
                job_pending_count = len(await db_dashboard.get_prepro_job_pending_list_new(prepro.get("id")))
                
                for _id in prepro_job_id_list:
                    id_str = str(_id)
                    if id_str in prepro_pod_job and prepro_pod_job.get(id_str).get("status") == TYPE.KUBE_POD_STATUS_RUNNING:
                        job_running_count += 1          
                
                parse_prepro_list.append({
                    "type" : TYPE.PREPROCESSING_TYPE,
                    "name" : prepro.get("name"),
                    "status_tool" : {"running" : len(prepro_tool_active_list), "kind" : prepro_tool_kind_list},
                    "status_job" : {"running" : job_running_count, "pending" : job_pending_count},
                    "instance" : {
                        "gpu_name" : prepro.get("resource_name"),
                        "gpu_allocate" : prepro.get("gpu_allocate"),
                        "cpu_allocate" : prepro.get("cpu_allocate"),
                        "ram_allocate" : prepro.get("ram_allocate"),
                    },
                    "tool_list" : [{
                        "type" : TYPE.TOOL_TYPE.get(i.get("tool_type")),
                        "start_datetime" : i.get("start_datetime"),
                        "gpu_name" : prepro.get("resource_name"),
                        "gpu_allocate" : i.get("gpu_count"),
                        "cpu_allocate" : prepro.get("tool_cpu_limit"),
                        "ram_allocate" : prepro.get("tool_ram_limit"),
                    } for i in prepro_tool_active_list],
                    "job_list" : [{
                        "job_id" : i.get("id"),
                        "start_datetime" : i.get("start_datetime"),
                        "gpu_name" : prepro.get("resource_name"),
                        "gpu_allocate" : i.get("gpu_count"),
                        "cpu_allocate" : prepro.get("job_cpu_limit"),
                        "ram_allocate" : prepro.get("job_ram_limit"),
                    } for i in prepro_job_list],
                })
                pd_prepro_list.append({
                    "name" : prepro["name"],
                    "type" : TYPE.PREPROCESSING_TYPE,
                    "instance_name" : prepro["instance_name"],
                    "allocate" : prepro["instance_allocate"],
                    "instance_info" : {
                        "cpu_allocate" : prepro.get("cpu_allocate"),
                        "gpu_allocate" : prepro.get("gpu_allocate"),
                        "ram_allocate" : prepro.get("ram_allocate"),
                        "gpu_name" : prepro.get("resource_name"),
                    }
                })
            
            await asyncio.gather(*(process_prepro(prepro) for prepro in prepro_list))
            parse_prepro_list.sort(key=lambda x: (
                max(x['status_tool']['running'], len(x['status_tool']['kind'])),
                max(x['status_job']['running'], x['status_job']['pending']),
                x['name']
            ), reverse=True)
            pd_prepro_list = sorted(pd_prepro_list, key=lambda x : x["name"])

            deployment_list = await db_dashboard.get_deployment_list_in_workspace(workspace_id=workspace_id)
            # for deployment in deployment_list:
            async def process_deployment(deployment):
                deployment_id = deployment.get("id")
                db_deployment_worker_list = await db_dashboard.get_deployment_worker_list_all(deployment_id=deployment_id)
                
                if deployment.get("llm"):
                    return

                worker_running_count = 0
                worker_pending_count = len(await db_dashboard.get_deployment_worker_pending_list_new(deployment_id=deployment_id))
                deployment_worker_id_list = list(item.get("id") for item in await db_dashboard.get_deployment_worker_running_list(deployment_id=deployment_id))
                workspace_pod_deployment_worker = deployment_pod.get(str(deployment_id))

                if workspace_pod_deployment_worker is not None:
                    for _id in deployment_worker_id_list:
                        id_str = str(_id)
                        if id_str in workspace_pod_deployment_worker and workspace_pod_deployment_worker.get(id_str).get("status") == "running":
                            worker_running_count += 1

                parse_deployment_list.append({
                    "type" : TYPE.DEPLOYMENT_TYPE,
                    "name" : deployment.get("name"),
                    "status_deployment" : {"running" : worker_running_count, "pending" : worker_pending_count},
                    "instance" : {
                        "gpu_name" : deployment.get("resource_name"),
                        "gpu_allocate" : deployment.get("gpu_allocate"),
                        "cpu_allocate" : deployment.get("cpu_allocate"),
                        "ram_allocate" : deployment.get("ram_allocate"),
                    },
                    "worker_list" : [{
                        "worker_id" : i.get("id"),
                        "cpu_allocate" : deployment.get("deployment_cpu_limit"),
                        "ram_allocate" : deployment.get("deployment_ram_limit"),
                        "gpu_allocate" : i.get("gpu_per_worker"),
                        "gpu_name" : i.get("gpu_name"),
                        "start_datetime" : i.get("start_datetime"),
                    } for i in db_deployment_worker_list],
                })
                pd_deployment_list.append({
                    "name" : deployment["name"],
                    "type" : "deployment",
                    "instance_name" : deployment["instance_name"],
                    "allocate" : deployment["instance_allocate"],
                    "instance_info" : {
                        "cpu_allocate" : deployment.get("cpu_allocate"),
                        "gpu_allocate" : deployment.get("gpu_allocate"),
                        "ram_allocate" : deployment.get("ram_allocate"),
                        "gpu_name" : deployment.get("resource_name"),
                    }
                })
            
            await asyncio.gather(*(process_deployment(deployment) for deployment in deployment_list))
            parse_deployment_list.sort(key=lambda x:( 
                max(x['status_deployment']['running'], x['status_deployment']['pending']),
                x['name']
            ), reverse=True)
            # parse_deployment_list = sorted(parse_deployment_list, key=lambda x : x["name"])
            pd_deployment_list = sorted(pd_deployment_list, key=lambda x : x["name"])
            return parse_project_list+parse_prepro_list+parse_deployment_list , pd_project_list + pd_deployment_list + pd_prepro_list
        ####################################################################
        
        # A-LLM
        ####################################################################
        if settings.LLM_USED and platform_type == TYPE.PLATFORM_A_LLM:
            jonathan_allm =[]
            models_pod = redis_workspace_pod_status.get(TYPE.FINE_TUNING_TYPE, {})
            model_list = await db_dashboard.get_model_list(workspace_id=workspace_id)
            model_id_info_list = {model.get("id") : model for model in model_list}

            for model in model_list:
                jonathan_allm.append({
                    "type" : TYPE.FINE_TUNING_TYPE,
                    "name" : model["name"],
                    "huggingface_model_id" : model["huggingface_model_id"],
                    "commit_model_name" : model["commit_model_name"],
                    "config_files_count" : model["config_files"],
                    "datasets_count" : model["datasets"],
                    "status" : models_pod[str(model["id"])]["status"] if models_pod.get(str(model["id"]), {}) else model["latest_fine_tuning_status"],
                    "instance" : {
                        "instance_name" : model["instance_name"],
                        "instance_count" : model["instance_count"],
                        "resource_name" : model["resource_name"],
                        "cpu_allocate" :  model["cpu_allocate"],
                        "ram_allocate" : model["ram_allocate"],
                        "gpu_allocate" : model["gpu_allocate"],
                        "used_gpu_count" : model["gpu_count"]
                    }
                })
            jonathan_allm.sort(key=lambda x: (
                (x['status'] == TYPE.KUBE_POD_STATUS_RUNNING),
                (x['status'] == TYPE.KUBE_POD_STATUS_INSTALLING),
                (x['status'] == TYPE.KUBE_POD_STATUS_PENDING),
                x['name']
            ), reverse=True)

            # Deployment: RAG, Playground  -----------------------------------------------------------------------------------
            deployment_list = db.get_deployment_list_in_workspace(workspace_id=workspace_id)
            deployment_id_info_list = {deployment.get("id") : deployment for deployment in deployment_list}
            deployment_pod = redis_workspace_pod_status.get(TYPE.DEPLOYMENT_TYPE, {})
            rag_list = await db.get_rag_list(workspace_id=workspace_id)
            rag_id_info_list = {rag.get("id") : rag for rag in rag_list}
            playground_list = await db.get_playground_list(workspace_id=workspace_id)
            # rag -----------------------------------------------------------------------------------
            rag_parse_list = []
            for rag in rag_list:
                retrieval_embedding_run = rag.get("retrieval_embedding_run")
                retrieval_reranker_run = rag.get("retrieval_reranker_run")
                test_embedding_run = rag.get("test_embedding_run")
                test_reranker_run = rag.get("test_reranker_run")

                retrieval_embedding_deployment_id = rag.get("retrieval_embedding_deployment_id")
                retrieval_reranker_deployment_id = rag.get("retrieval_reranker_deployment_id")
                test_embedding_deployment_id = rag.get("test_embedding_deployment_id")
                test_reranker_deployment_id = rag.get("test_reranker_deployment_id")

                retrieval_deployment_id = retrieval_reranker_deployment_id if retrieval_reranker_run else retrieval_embedding_deployment_id
                test_deployment_id = test_reranker_deployment_id if test_reranker_run else test_embedding_deployment_id

                # instance
                rag_deployment = {
                    "rag_embedding" : deployment_id_info_list.get(retrieval_embedding_deployment_id) if retrieval_embedding_run else None,
                    "rag_reranker" : deployment_id_info_list.get(retrieval_reranker_deployment_id) if retrieval_reranker_run else None,
                    "test_embedding" : deployment_id_info_list.get(test_embedding_deployment_id) if test_embedding_run else None,
                    "test_reranker" : deployment_id_info_list.get(test_reranker_deployment_id) if test_reranker_run else None
                }

                # status
                rag_pod = deployment_pod.get(str(retrieval_deployment_id), {})
                rag_pod_status = next(iter(rag_pod.values())).get("status") if rag_pod and len(rag_pod) > 0 else "stop"
                test_pod = deployment_pod.get(str(test_deployment_id), {})
                test_pod_status = next(iter(test_pod.values())).get("status") if test_pod and len(test_pod) > 0 else "stop"

                rag_parse_list.append({
                    "type" : "rag",
                    "name" : rag.get("name"),
                    "docs_total_count" : rag.get("docs_total_count"),
                    "chunk_len" : rag.get("chunk_len"),
                    "model" : {
                        "embedding" : rag.get("embedding_huggingface_model_id"),
                        "reranker" : rag.get("reranker_huggingface_model_id"),
                    },
                    "status" : {
                        "rag" : rag_pod_status,
                        "test" : test_pod_status
                    },
                    "instance" : {
                        key: {
                            "instance_name" : info.get("instance_name"),
                            "instance_count": info.get("instance_allocate"),
                            "resource_name": info.get("resource_name"),
                            "cpu_allocate": info.get("cpu_allocate"),
                            "ram_allocate": info.get("ram_allocate"),
                            "gpu_allocate": info.get("gpu_allocate"),
                            "used_gpu_count": info.get("gpu_per_worker"),
                        } if info else None
                        for key, info in rag_deployment.items()
                    },
                })
            rag_parse_list.sort(key=lambda x: (
                (x['status']['rag'] == TYPE.KUBE_POD_STATUS_RUNNING),
                (x['status']['rag'] == TYPE.KUBE_POD_STATUS_INSTALLING),
                (x['status']['rag'] == TYPE.KUBE_POD_STATUS_PENDING),
                (x['status']['test'] == TYPE.KUBE_POD_STATUS_RUNNING),
                (x['status']['test'] == TYPE.KUBE_POD_STATUS_INSTALLING),
                (x['status']['test'] == TYPE.KUBE_POD_STATUS_PENDING),
                x['name']
            ), reverse=True)
            jonathan_allm += rag_parse_list
            # playground -----------------------------------------------------------------------------------
            playground_parse_list = []
            for playground in playground_list:
                tmp_playground_deployment = playground.get("deployment")
                playground_deployment_info = json.loads(tmp_playground_deployment) if tmp_playground_deployment else dict()
                deployment_playground_id = playground_deployment_info.get("deployment_playground_id")
                deployment_embedding_id = playground_deployment_info.get("deployment_embedding_id")
                deployment_reranker_id = playground_deployment_info.get("deployment_reranker_id")

                # playground model - 1. model
                tmp_playground_model = playground.get("model")
                playground_model_info = json.loads(tmp_playground_model) if tmp_playground_model else dict()
                if playground_model_info.get("model_type") == "huggingface":
                    playground_model = playground_model_info.get("model_huggingface_id")
                elif playground_model_info.get("model_type") == "commit":
                    # model_commit_id = playground_model_info.get("model_allm_commit_id")
                    # playground_model = model_id_info_list.get(model_commit_id).get("commit_model_name")
                    model_allm_id = playground_model_info.get("model_allm_id")
                    if model_allm_id in model_id_info_list: # playground에서 설정한 모델이 먼저 지워질 수 있음
                        playground_model = model_id_info_list.get(model_allm_id).get("commit_model_name")
                    else:
                        playground_model = None
                else:
                    playground_model = None

                # playground model - 2. rag model
                tmp_playground_rag = playground.get("rag")
                playground_rag = json.loads(tmp_playground_rag) if tmp_playground_rag else dict()
                playground_rag_id = playground_rag.get('rag_id')
                playground_rag_info = rag_id_info_list.get(playground_rag_id) if playground_rag_id else None
                

                # playground model result - 1 + 2
                playground_model = {
                    "playground" : playground_model,
                    "embedding" : playground_rag_info.get("embedding_huggingface_model_id") if playground_rag_info else None,
                    "reranker" : playground_rag_info.get("reranker_huggingface_model_id") if playground_rag_info else None,
                }
                
                # deployment instance 정보
                playground_deployment = {
                    "playground" : deployment_id_info_list.get(deployment_playground_id) if deployment_playground_id else None,
                    "embedding" : deployment_id_info_list.get(deployment_embedding_id) if deployment_embedding_id else None,
                    "reranker" : deployment_id_info_list.get(deployment_reranker_id) if deployment_reranker_id else None,
                }

                # status
                playground_pod = deployment_pod.get(str(deployment_playground_id), {})
                playground_pod_status = next(iter(playground_pod.values())).get("status") if playground_pod and len(playground_pod) > 0 else "stop"

                # playground result
                playground_parse_list.append({
                    "type" : "playground",
                    "name" : playground.get("name"),
                    "status" : playground_pod_status,
                    "sub_status" : {
                        "model" : True if playground.get("model") else False,
                        "rag" : True if playground_rag else False,
                        "prompt" : True if playground.get("prompt") else False, 
                    },
                    "instance" : {
                        key : {
                            "model_name" : playground_model.get(key),
                            "instance_name" : info.get("instance_name"),
                            "instance_count": info.get("instance_allocate"),
                            "resource_name": info.get("resource_name"),
                            "cpu_allocate": info.get("cpu_allocate"),
                            "ram_allocate": info.get("ram_allocate"),
                            "gpu_allocate": info.get("gpu_allocate"),
                            "used_gpu_count": info.get("gpu_per_worker"),
                        } 
                        for key, info in playground_deployment.items()
                        if key and isinstance(info, dict) and playground_model.get(key)
                        # playground, embedding, reranker 다 안 보내주고 배포 선택한 것만 보내줌
                    }
                })
            playground_parse_list.sort(key=lambda x: (
                (x['status'] == TYPE.KUBE_POD_STATUS_RUNNING),
                (x['status'] == TYPE.KUBE_POD_STATUS_INSTALLING),
                (x['status'] == TYPE.KUBE_POD_STATUS_PENDING),
                x['name']
            ), reverse=True)
            jonathan_allm += playground_parse_list
            return jonathan_allm
    except Exception as e:
        traceback.print_exc()
        return [], []



def get_user_dashboard_info(workspace_id, headers_user=None):
    try:
        redis_client=get_redis_client()
        reval = {
            "info":[],                          # 기본정보
            "history":[],                       # 최근실행기록
            "total_count" : {},                 # (이미지, 데이터셋, 학습, 배포, ...) + MSA 요금 추가
            "usage" : {},                       # 워크스페이스 자원 사용 현황            
            # ===========================
            "project_items":[],                 # 프로젝트별 작업 현황
            "storage" : {},                     # 스토리지 사용 현황
            # ===========================
            "instances_used" : {},              # 전체 인스턴스 현황
            "project_instance_allocate" : {},   # 프로젝트별 인스턴스 현황
            "manager" : 0,                  # 워크스페이스 매니저
            # ===========================
            # TODO 삭제
            "timeline" : [], #  일별 워크스페이스 자원 사용 현황 # TODO ELK
            "totalCount":[], # 없으면 터져서 현재는 남겨둠 (이미지, 데이터셋, 학습, 배포, )
            "detailed_timeline" : [] # 없으면 터져서 남겨둠
            # ===========================
        }
        
        # =========================================================================================
        # user_info = db_user.get_user_id(headers_user)
        # user_id = user_info['id']

        # redis_client = get_redis_client()
        
        tmp_gpu_info = redis_client.get(redis_key.GPU_INFO_RESOURCE)
        gpu_status = json.loads(tmp_gpu_info) if tmp_gpu_info is not None else dict()
        workspaces_quota = redis_client.hgetall(redis_key.WORKSPACE_RESOURCE_QUOTA) 
        
        tmp_storage_list_resource = redis_client.get(redis_key.STORAGE_LIST_RESOURCE)
        storage_info = json.loads(tmp_storage_list_resource) if tmp_storage_list_resource is not None else dict()
        data_storage_usage = redis_client.hgetall(redis_key.DATASET_STORAGE_USAGE)
        main_storage_usage = redis_client.hgetall(redis_key.PROJECT_STORAGE_USAGE)
        
        # storage =========================================================================================
        # init storage value 
        # "main_storage": {
        #         "total": 0,
        #         "used": 0,
        #         "avail" : 0,
        #         "usage" : 0,
        #         "project_list" : []
        #         },
        #     "data_storage" : {
        #         "total": 0,
        #         "used": 0,
        #         "avail" : 0,
        #         "usage" : 0, 
        #         "dataset_list" :[]
        #         }
        # } 
        # print(redis_client.hgetall(redis_key.DATASET_STORAGE_USAGE))
        try:
            reval['storage'] = copy.deepcopy(dummy.dummy_user_storage)
            if storage_info:
                ws_info = db_workspace.get_workspace(workspace_id=workspace_id)
                dataset_list = db_dataset.get_dataset_list(workspace_id=workspace_id)
                project_list = db_project.get_project_list(workspace_id=workspace_id)
                main_storage_usage_list = storage_info[str(ws_info['main_storage_id'])].get('workspaces', [])
                # print(main_storage_usage_list)
                for main_storage in main_storage_usage_list['main']:
                    if main_storage['workspace_name'] == ws_info['name']:
                        reval['storage']['main_storage']['total']=main_storage['alloc_size']
                        reval['storage']['main_storage']['used']=main_storage['used_size']
                        reval['storage']['main_storage']['avail']=main_storage['alloc_size']-main_storage['used_size']
                        reval['storage']['main_storage']['usage']=round(main_storage['used_size']/main_storage['alloc_size']*100) if main_storage['used_size'] else 0
                        break

                for project in project_list:
                    # print(main_storage_usage)
                    # print(main_storage_usage.get(str(project['id'])))
                    project_usage = int(main_storage_usage.get(str(project['id']), 0))
                    print(project_usage)
                    reval['storage']['main_storage']['project_list'].append(
                        {
                            'name': project['name'],
                            'usage': round(project_usage/reval['storage']['main_storage']['total']*100) if project_usage else 0
                        }
                    )

                data_storage_usage_list = storage_info[str(ws_info['data_storage_id'])].get('workspaces', [])
                if data_storage_usage_list:
                    for data_storage in data_storage_usage_list['data']:
                        if data_storage['workspace_name'] == ws_info['name']:
                            reval['storage']['data_storage']['total']=data_storage['alloc_size']
                            reval['storage']['data_storage']['used']=data_storage['used_size']
                            reval['storage']['data_storage']['avail']=data_storage['alloc_size']-data_storage['used_size']
                            reval['storage']['data_storage']['usage']=int(data_storage['used_size']/data_storage['alloc_size']*100)
                            break
                for dataset in dataset_list :
                    data_usage = int(data_storage_usage.get(str(dataset['id']), 0))
                    reval['storage']['data_storage']['dataset_list'].append(
                        {
                            'name': dataset['dataset_name'],
                            'usage': round(data_usage/reval['storage']['data_storage']['total']*100) if data_usage else 0
                        }
                    )
        except:
            traceback.print_exc()
            
        # TODO training_items 최근학습현황 =========================================================================================
        try:
            tmp_workspace_pod_status = redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, workspace_id)
            redis_workspace_pod_status = json.loads(tmp_workspace_pod_status) if tmp_workspace_pod_status is not None else dict()
            projects_pod = redis_workspace_pod_status.get(TYPE.PROJECT_TYPE, {})
            deplotment_pod = redis_workspace_pod_status.get(TYPE.DEPLOYMENT_TYPE, {})
            db_workspace_resource = db_workspace.get_workspace_resource(workspace_id=workspace_id)

            test = []
            for project in db_project.get_project_list(workspace_id=workspace_id):
                # print(workspace_pod_job)
                # 프로젝트 id
                project_pod_status = projects_pod.get(str(project["id"]), {})
                # workspace_pod_tool = project_pod_status.get(TYPE.TRAINING_ITEM_B, {})
                project_pod_job = project_pod_status.get(TYPE.TRAINING_ITEM_A, {})
                project_pod_hps = redis_workspace_pod_status.get(TYPE.TRAINING_ITEM_C, {})
                project_tool_active_list = db_dashboard.get_project_tool_active_list(project_id=project.get("id"))
                project_tool_kind_list = list({TYPE.TOOL_TYPE.get(item.get("tool_type")) for item in project_tool_active_list})
                project_job_list = db_dashboard.get_project_job_list(project_id=project.get("id"))
                project_job_id_list = list(item.get("id") for item in project_job_list)
                project_hps_id_list = list(item.get("id") for item in db_dashboard.get_project_hps_list(project_id=project.get("id")))
                
                job_running_count = 0
                job_pending_count = len(db_dashboard.get_project_job_pending_list(project_id=project.get("id")))
                hps_running_count = 0
                hps_pending_count = len(db_dashboard.get_project_hps_pending_list(project_id=project.get("id")))
                
                for _id in project_job_id_list:
                    id_str = str(_id)
                    if id_str in project_pod_job and project_pod_job.get(id_str).get("status") == TYPE.KUBE_POD_STATUS_RUNNING:
                        job_running_count += 1      

                for _id in project_hps_id_list:
                    id_str = str(_id)
                    if id_str in project_pod_hps and project_pod_hps.get(id_str).get("status") == TYPE.KUBE_POD_STATUS_RUNNING:
                        hps_running_count += 1        
                
                test.append({
                    "type" : TYPE.PROJECT_TYPE,
                    "name" : project.get("name"),
                    "status_tool" : {"running" : len(project_tool_active_list), "kind" : project_tool_kind_list},
                    "status_job" : {"running" : job_running_count, "pending" : job_pending_count},
                    "status_hps" : {"running" : hps_running_count, "pending" : hps_pending_count},
                    "instance" : {
                        "gpu_name" : project.get("resource_name"),
                        "gpu_allocate" : project.get("gpu_allocate"),
                        "cpu_allocate" : project.get("cpu_allocate"),
                        "ram_allocate" : project.get("ram_allocate"),
                    },
                    "tool_list" : [{
                        "type" : TYPE.TOOL_TYPE.get(i.get("tool_type")),
                        "start_datetime" : i.get("start_datetime"),
                        "gpu_name" : project.get("resource_name"),
                        "gpu_allocate" : i.get("gpu_count"),
                        "cpu_allocate" : project.get("tool_cpu_limit"),
                        "ram_allocate" : project.get("tool_ram_limit"),
                    } for i in project_tool_active_list],
                    "job_list" : [{
                        "job_id" : i.get("id"),
                        "start_datetime" : i.get("start_datetime"),
                        "gpu_name" : project.get("resource_name"),
                        "gpu_allocate" : i.get("gpu_count"),
                        "cpu_allocate" : project.get("job_cpu_limit"),
                        "ram_allocate" : project.get("job_ram_limit"),
                    } for i in project_job_list],
                })
                
            workspace_deployment_list = db_deployment.get_deployment_list_in_workspace(workspace_id=workspace_id)
            for deployment in workspace_deployment_list:
                deployment_id = deployment.get("id")
                if deployment.get("llm"):
                    continue

                db_deployment_worker_list = db_deployment.get_deployment_worker_list(deployment_id=deployment_id)
                
                worker_running_count = 0
                worker_pending_count = len(db_dashboard.get_deployment_worker_pending_list(deployment_id=deployment_id))
                deployment_worker_id_list = list(item.get("id") for item in db_dashboard.get_deployment_worker_list(deployment_id=deployment_id))
                workspace_pod_deployment_worker = deplotment_pod.get(str(deployment_id))

                if workspace_pod_deployment_worker is not None:
                    for _id in deployment_worker_id_list:
                        id_str = str(_id)
                        if id_str in workspace_pod_deployment_worker and workspace_pod_deployment_worker.get(id_str).get("status") == "running":
                            worker_running_count += 1

                test.append({
                    "type" : TYPE.DEPLOYMENT_TYPE,
                    "name" : deployment.get("name"),
                    "status_deployment" : {"running" : worker_running_count, "pending" : worker_pending_count},
                    "instance" : {
                        "gpu_name" : deployment.get("resource_name"),
                        "gpu_allocate" : deployment.get("gpu_allocate"),
                        "cpu_allocate" : deployment.get("cpu_allocate"),
                        "ram_allocate" : deployment.get("ram_allocate"),
                    },
                    "worker_list" : [{
                        "worker_id" : i.get("id"),
                        "cpu_allocate" : deployment.get("deployment_cpu_limit"),
                        "ram_allocate" : deployment.get("deployment_ram_limit"),
                        "gpu_allocate" : i.get("gpu_per_worker"),
                        "gpu_name" : i.get("gpu_name"),
                        "start_datetime" : i.get("start_datetime"),
                    } for i in db_deployment_worker_list],
                })
            
            reval["project_items"] = test
        except:
            traceback.print_exc()

        # TODO History 최근실행현황 =========================================================================================
        # TODO EFK???
        reval["history"] = dummy.dummy_user_history

        # 워크스페이스 자원 사용 현황 ====================================================================================
        try:
            project_count, deployment_count = get_workspace_used_gpu(workspace_id=workspace_id, data=gpu_status)

            def safe_divide(a, b):
                try:
                    return (a / b) * 100
                except ZeroDivisionError:
                    return 0
                
            # start_time=datetime.now()
            workspace_quota = json.loads(workspaces_quota[str(workspace_id)])
            if not workspace_quota:
                print("!!!CHECK: workspace_quota IS NONE -> ", workspace_quota)
                workspace_quota = {"gpu" : {"hard" : 0, "used" : 0}, "cpu" : {"hard" : 0, "used" : 0},"ram" : {"hard" : 0, "used" : 0},}

            reval['usage']['gpu'] = {
                "total" : workspace_quota.get("gpu").get("hard"),
                "used" : workspace_quota.get("gpu").get("used"),
                "usage" : safe_divide(workspace_quota.get("gpu").get("used"), workspace_quota.get("gpu").get("hard")),
                "used_training" : project_count,
                "used_deployment" : deployment_count,
            }
            
            reval['usage']['cpu'] = {
                "total" : workspace_quota.get("cpu").get("hard"),
                "used" : workspace_quota.get("cpu").get("used"),
                "usage" : safe_divide(workspace_quota.get("cpu").get("used"), workspace_quota.get("cpu").get("hard")),
            }
            
            reval['usage']['ram'] = {
                "total" : byte_to_gigabyte(workspace_quota.get("ram").get("hard")),
                "used" : byte_to_gigabyte(workspace_quota.get("ram").get("used")),
                "usage" : safe_divide(byte_to_gigabyte(workspace_quota.get("ram").get("used")), byte_to_gigabyte(workspace_quota.get("ram").get("hard"))),
            }
            # end_time=datetime.now()
        except:
            traceback.print_exc()

        # print(f"time {(end_time-start_time).total_seconds()}")
        # 인스턴스 사용량 체크 =========================================================================================
        try:
            instances =  db_dashboard.get_workspace_instance_list(workspace_id=workspace_id)
            instance_status = make_nested_dict()       
            for project_id, project_items in projects_pod.items():
                total_cpu = 0
                total_ram = 0
                total_gpu = 0
                instance_id = None
                for item_type, items in project_items.items():
                    for item_id , item_info in items.items():
                        instance_id = instance_id if instance_id else item_info["instance_id"] # TODO 확인 continue 아래에 코드가 있어서 에러인 팟은 instance_id none으로 넘어감
                        if item_info["status"] == TYPE.KUBE_POD_STATUS_ERROR:
                            continue
                        if item_info["resource"]["cpu"] is not None:
                            total_cpu += item_info["resource"]["cpu"]
                        if item_info["resource"]["ram"] is not None:
                            total_ram += item_info["resource"]["ram"]
                        if item_info["resource"]["gpu"] is not None:
                            total_gpu += item_info["resource"]["gpu"]
                instance_status[int(instance_id)][TYPE.PROJECT_TYPE][project_id] = {
                    "cpu" : total_cpu,
                    "ram" : total_ram,
                    "gpu" : total_gpu
                } 
                
            for deployment_id, deployment_workers in deplotment_pod.items():
                total_cpu = 0
                total_gpu = 0
                total_ram = 0
                instance_id = None
                for worker_id, worker_info in deployment_workers.items():
                    instance_id = instance_id if instance_id else worker_info["instance_id"] # TODO 확인 make_nested_dict???
                    if worker_info["status"] == TYPE.KUBE_POD_STATUS_ERROR:
                        continue
                    total_cpu += worker_info["resource"]["cpu"]
                    total_ram += worker_info["resource"]["ram"]
                    total_gpu += worker_info["resource"]["gpu"] 
                instance_status[int(instance_id)][TYPE.DEPLOYMENT_TYPE][deployment_id] = {
                    "cpu" : total_cpu,
                    "ram" : total_ram,
                    "gpu" : total_gpu
                } 
            for instance in instances:
                # label_selector = "instance_id={},workspace_id={}".format(instance["id"],workspace_id)
                # pods = coreV1Api.list_pod_for_all_namespaces(label_selector=label_selector)
                instance_resouce_count = 3 if instance["instance_type"] == TYPE.RESOURCE_TYPE_GPU else 2
                instance_total_gpu = instance["instance_allocate"] * instance["gpu_allocate"]
                instance_total_ram = instance["instance_allocate"] * instance["ram_allocate"]
                instance_total_cpu = instance["instance_allocate"] * instance["cpu_allocate"]
                instance_used_resouce = instance_status[instance["id"]]
                instance_used_info = []
                remaining_cpu = instance_total_cpu
                remaining_ram = instance_total_ram
                reamining_gpu = instance_total_gpu
                for workspace_item_type, item_resources in  instance_used_resouce.items():
                    for item_id, item_resource in item_resources.items():
                        if TYPE.PROJECT_TYPE == workspace_item_type:
                            item_info = db_project.get_project(project_id=item_id)
                        elif TYPE.DEPLOYMENT_TYPE == workspace_item_type:
                            item_info = db_deployment.get_deployment(deployment_id=item_id)
                            
                        if item_info is None: continue # 임시수정

                        used_gpu_rate = (item_resource["gpu"] / instance_total_gpu) * 100 if instance_total_gpu and instance_total_gpu != 0 else 0
                        reamining_gpu -= item_resource["gpu"] 
                        used_cpu_rate = (item_resource["cpu"] / instance_total_cpu) * 100 if instance_total_cpu and instance_total_cpu != 0 else 0
                        remaining_cpu -= item_resource["cpu"] 
                        used_ram_rate = (item_resource["ram"] / instance_total_ram) * 100 if instance_total_ram and instance_total_ram != 0 else 0
                        remaining_ram -= item_resource["ram"]
                        total_used_rate = (used_gpu_rate + used_cpu_rate + used_ram_rate) / instance_resouce_count 
                        
                        
                        instance_used_info.append({
                            "item_type" : TYPE.PROJECT_TYPE,
                            "item_name" : item_info["name"],
                            "item_user" : item_info["create_user_name"] if TYPE.PROJECT_TYPE == workspace_item_type else item_info["user_name"],
                            "used_resource" : item_resource,
                            "used_rate" : total_used_rate,
                        })
                reamining_gpu_rate = (reamining_gpu / instance_total_gpu) * 100 if instance_total_gpu and instance_total_gpu != 0 else 0
                remaining_cpu_rate = (remaining_cpu / instance_total_cpu) * 100 if instance_total_cpu and instance_total_cpu != 0 else 0
                remaining_ram_rate = (remaining_ram / instance_total_ram)  * 100 if instance_total_ram and instance_total_ram != 0 else 0
                total_reamining_rate = (reamining_gpu_rate + remaining_cpu_rate + remaining_ram_rate) / instance_resouce_count
                # print(instance_used_info)
                
                instance["used_rate"] =  sorted(instance_used_info, key=lambda x: x['used_rate'], reverse=True)
                instance["remaining_rate"] = {
                    "remaining_rate" : total_reamining_rate,
                    "remaining_resource" : {
                        "cpu" : remaining_cpu,
                        "ram" : remaining_ram,
                        "gpu" : reamining_gpu
                    }
                }
                # pod_count = instance_usage.get(str(instance["id"]), 0)
                # instance["used"] = 100.0 if pod_count/instance["instance_allocate"] > 1 else (pod_count/instance["instance_allocate"])*100
        except:
            traceback.print_exc()
            instance["used_rate"] = []
            instance["remaining_rate"] = {
                    "remaining_rate" : 0,
                    "remaining_resource" : {
                        "cpu" : 0,
                        "ram" : 0,
                        "gpu" : 0
                    }
                }
        
        # 학습 및 배포 리스트 =========================================================================================
        pd_list = []
        try:
            project_list = db_project.get_project_list(workspace_id=workspace_id)
            deployment_list= db_deployment.get_deployment_list_in_workspace(workspace_id=workspace_id)
            
            for project in project_list:
                pd_list.append({
                    "name" : project["name"],
                    "type" : "project",
                    "instance_name" : project["instance_name"],
                    "allocate" : project["instance_allocate"],
                    "instance_info" : {
                        "cpu_allocate" : project.get("cpu_allocate"),
                        "gpu_allocate" : project.get("gpu_allocate"),
                        "ram_allocate" : project.get("ram_allocate"),
                        "gpu_name" : project.get("resource_name"),
                    }
                })
            for deployment in deployment_list:
                pd_list.append({
                    "name" : deployment["name"],
                    "type" : "deployment",
                    "instance_name" : deployment["instance_name"],
                    "allocate" : deployment["instance_allocate"],
                    "instance_info" : {
                        "cpu_allocate" : deployment.get("cpu_allocate"),
                        "gpu_allocate" : deployment.get("gpu_allocate"),
                        "ram_allocate" : deployment.get("ram_allocate"),
                        "gpu_name" : deployment.get("resource_name"),
                    }
                })
            
        except:
            traceback.print_exc()
        # =========================================================================================
        # 완료
        reval['info'] = db_dashboard.get_user_dashboard_info(workspace_id) or {}
        reval['total_count'] = db_workspace.get_workspace_item_count(workspace_id=workspace_id)
        reval['total_count']['pricing'] = 20 # TODO 가격 정책 추가
        reval["instances_used"] = instances
        reval["project_instance_allocate"] = pd_list
        reval['manager'] = db_dashboard.get_workspace(workspace_id=workspace_id)["manager_id"]

        # 로그 
        try:
            history_url = f"http://log-middleware-rest.jonathan-efk:8080/v1/dashboard/workspace/{reval['info']['name']}"
            history_response = requests.post(history_url, json={"timespan": "7d", "count": 10})
            history_raw = history_response.json()
            histories = []
            if history_raw.get("logs", None):
                for history in history_raw["logs"]:
                    current_document = history["fields"]
                    current_document["update_details"] = "-"
                    histories.append(current_document)

            reval["history"] = histories
        except:
            # traceback.print_exc()
            pass
    
    except Exception as e:
        traceback.print_exc()
        pass
        # raise GetUserDashboardError
        # return response(status=0, message="Get user dashboard info Error", result=reval)
    # print(reval)
    # redis_client.close()
    return reval # response(status=1, result=reval)

# ===================================================================================================
# resource

async def get_async_user_resource_usage_info(workspace_id):
    try:
        res={"timeline":{}}
        # record time
        #start=datetime.now()
        resource_usage_log = await common.post_request(url=f"{settings.LOG_MIDDLEWARE_DNS}/v1/resource/workspace/{workspace_id}", data={})
        res['timeline'] = resource_usage_log
        #end=datetime.now()
        #time_check=(end-start).total_seconds()
        #print(f"resource_usage_time : {time_check}")
        return response(status=1, result= res)
    except:
        traceback.print_exc()
                

def get_user_resource_usage_info(workspace_id):
    try:
        
        res={"timeline":{}}
        resource_usage_log = common.post_request_sync(url=f"{settings.LOG_MIDDLEWARE_DNS}/v1/resource/workspace/{workspace_id}", data={})

        res['timeline'] = resource_usage_log
        return response(status=1, result= res)
    except:
        traceback.print_exc()

def get_admin_resource_usage_info():
    try:
        res = {"timeline" : {"cpu" : [], "gpu" : [], "ram" : [], "storage_data" : [], "storage_main" : []}}
        rep = common.post_request_sync(url=f"{settings.LOG_MIDDLEWARE_DNS}/v1/resource/cluster", data={})
        if rep is not None:
            res["timeline"] = rep
        return response(status=1, result= res)
    except:
        traceback.print_exc()

def get_admin_resource_usage_dummy():
    try:
        print("get_admin_resource_usage_dummy")
        start=datetime.now()
        global res

        end=datetime.now()

        # time_check=(end-start).total_seconds()
        # print(f"resource_usage_time : {time_check}")
        return response(status=1, result=res)
    except:
        traceback.print_exc()


# ===================================================================================================
WORKSPACE_USER_DASHBOARD="USER:WORKSPACE:DASHBOARD"


async def set_dashboards_user():
    while True:
        try:
            redis_client= await get_redis_client_async()
            for i in db_dashboard.get_workspace_list():
                data =  await get_dashboard_user_new(i.get("id"))
                await redis_client.hset(WORKSPACE_USER_DASHBOARD, str(i.get("id")), json.dumps(data))
            await asyncio.sleep(1)
        except Exception as e:
            traceback.print_exc()
            pass

async def get_dashboard_user_project_items(workspace_id, platform_type :str = TYPE.PLATFORM_FLIGHTBASE):
    redis_client= await get_redis_client_async()
    try:
        # data = await redis_client.hget(WORKSPACE_USER_DASHBOARD, str(workspace_id))
    
        # workspace_user_info = json.loads(data)
        if platform_type == TYPE.PLATFORM_A_LLM:
            return await get_jonathan_items_info(redis_client=redis_client, workspace_id=workspace_id, platform_type=TYPE.PLATFORM_A_LLM)
        elif platform_type == TYPE.PLATFORM_FLIGHTBASE:
            fb_item_list, _ = await get_jonathan_items_info(redis_client=redis_client, workspace_id=workspace_id, platform_type=TYPE.PLATFORM_FLIGHTBASE)
            return fb_item_list
        return []
    except Exception as e:
        traceback.print_exc()
        raise

# TODO
# 추후 FB SSE 반영 시 삭제 
async def get_dashboard_user(workspace_id, user_id, platform_type):
    # global workspace_user_info
    # redis_client= await get_redis_client_async()
    try:
        # data = await redis_client.hget(WORKSPACE_USER_DASHBOARD, str(workspace_id))
        data =  await get_dashboard_user_new(workspace_id)
        
        if data is None:
            workspace_user_info = []
        else:
            workspace_user_info = data
            # workspace_user_info = json.loads(data)
            if platform_type == TYPE.PLATFORM_A_LLM:
                workspace_user_info["project_items"] = workspace_user_info.pop("allm_project_items", [])
                workspace_user_info.pop("fb_project_items", None)
                workspace_user_info.pop("project_instance_allocate", None)
            elif platform_type == TYPE.PLATFORM_FLIGHTBASE:
                workspace_user_info["project_items"] = workspace_user_info.pop("fb_project_items", [])
                workspace_user_info.pop("allm_project_items", None)
            workspace_user_info['manager'] = workspace_user_info['manager'] == user_id
        return workspace_user_info
    except Exception as e:
        traceback.print_exc()
        raise

async def sse_get_dashboard_user(workspace_id, user_id, platform_type, request : Request):
    async def fetch_dashboard_data(redis_client, workspace_id, user_id, platform_type):
        """Redis에서 대시보드 데이터를 가져오고 가공"""
        data = await redis_client.hget(WORKSPACE_USER_DASHBOARD, str(workspace_id))
        if data is None:
            return {}

        result = json.loads(data)
        result['manager'] = result.get('manager') == user_id

        return process_platform_data(result, platform_type)
    def process_platform_data(data, platform_type):
        """플랫폼별 데이터 가공"""
        if platform_type == TYPE.PLATFORM_A_LLM:
            data["project_items"] = data.pop("allm_project_items", [])
            data.pop("fb_project_items", None)
            data.pop("project_instance_allocate", None)
        elif platform_type == TYPE.PLATFORM_FLIGHTBASE:
            data["project_items"] = data.pop("fb_project_items", [])
            data.pop("allm_project_items", None)
        return data
    old_history = None
    old_datetime = datetime.now()
    try:
        while True:
            if await request.is_disconnected():
                break
            # redis_client= await get_redis_client_async()
            current_datetime = datetime.now()
            # data = await redis_client.hget(WORKSPACE_USER_DASHBOARD, str(workspace_id))
            current_data = await get_dashboard_user_new(workspace_id)
            # if data is None:
            #     data = "{{}}"
            # current_data = json.loads(data)
            if platform_type == TYPE.PLATFORM_A_LLM:
                # current_data["project_items"] = current_data.pop("allm_project_items", [])
                current_data.pop("allm_project_items", [])
                current_data.pop("fb_project_items", None)
                current_data.pop("project_instance_allocate", None)
            elif platform_type == TYPE.PLATFORM_FLIGHTBASE:
                # current_data["project_items"] = current_data.pop("fb_project_items", [])
                current_data.pop("fb_project_items", [])
                current_data.pop("allm_project_items", None)
            current_data['manager'] = current_data.get('manager') == user_id
            if current_data != old_history:
                old_history = current_data
                old_datetime = current_datetime
                for key, value in current_data.items():
                    data = json.dumps({key:value})
                    yield f"data: {data}\n\n"
            elif (current_datetime - old_datetime).total_seconds() >=30:
                old_datetime = current_datetime
                for key, value in old_history.items():
                    data = json.dumps({key:value})
                    yield f"data: {data}\n\n"
            
            await asyncio.sleep(1)
    except Exception as e:
        # 예외 처리 및 로그 남기기
        traceback.print_exc()
        print(f"Exception in SSE stream: {e}")
    finally:
        pass




# @async_timed
async def get_dashboard_user_new(workspace_id):
    pass
    try:
        redis_client = await get_redis_client_async()
        reval = {}
        usage = await get_workspace_resource_usage(redis_client=redis_client ,workspace_id = workspace_id)
        instance_usage, platform_resource_usage = await get_workspace_instance_used(redis_client=redis_client, workspace_id=workspace_id)
        usage["platform_usage"] = platform_resource_usage
        workspace_data = await db_dashboard.get_workspace_new(workspace_id=workspace_id)
        allm_item_list = await get_jonathan_items_info(redis_client=redis_client, workspace_id=workspace_id, platform_type=TYPE.PLATFORM_A_LLM)
        fb_item_list , pd_list = await get_jonathan_items_info(redis_client=redis_client, workspace_id=workspace_id, platform_type=TYPE.PLATFORM_FLIGHTBASE)
        manager = workspace_data["manager_id"]
        reval = {
                "info": await db_dashboard.get_user_dashboard_info_new(workspace_id=workspace_id),                          # 기본정보
                "history":[],                       # 최근실행기록
                "total_count" : await get_jonathan_workspace_item_count(workspace_id=workspace_id),                 # (이미지, 데이터셋, 학습, 배포, ...) + MSA 요금 추가
                "usage" : usage,                       # 워크스페이스 자원 사용 현황            
                # ===========================
                "fb_project_items":fb_item_list,                 # 프로젝트별 작업 현황
                "allm_project_items" : allm_item_list,
                "storage" : await get_storage_used(redis_client=redis_client, workspace_id=workspace_id),                     # 스토리지 사용 현황
                # ===========================
                "instances_used" : instance_usage,              # 전체 인스턴스 현황
                "project_instance_allocate" : pd_list,   # 프로젝트별 인스턴스 현황
                "manager" : manager,                  # 워크스페이스 매니저
            }
        try:
            history_url = f"http://log-middleware-rest.jonathan-efk:8080/v1/dashboard/workspace/{reval['info']['name']}"
            history_raw = await common.post_request(history_url, data={"timespan": "7d", "count": 10})
            histories = []
            if history_raw.get("logs", None):
                for history in history_raw["logs"]:
                    current_document = history["fields"]
                    current_document["update_details"] = "-"
                    histories.append(current_document)

            reval["history"] = histories
        except:
            pass
        return reval
        
    except Exception as e:
        traceback.print_exc()
        return {}
    
# 메시지를 청크 단위로 분리하는 함수
def split_message(message, chunk_size=1024):
    """
    긴 메시지를 지정된 크기(chunk_size)로 나눕니다.
    """
    for i in range(0, len(message), chunk_size):
        yield message[i:i+chunk_size]    
    
# async def sse_get_dashboard_user(workspace_id, user_id, platform_type, request : Request):
#         old_history = None
#         old_datetime = datetime.now()
#         try:
#             while True:
#                 if await request.is_disconnected():
#                     break
#                 current_datetime = datetime.now()
#                 reval = await get_dashboard_user_new(workspace_id=workspace_id, user_id=user_id, platform_type=platform_type)
#                 if reval != old_history:
#                     old_history = reval
#                     old_datetime = current_datetime
#                     for chunk in split_message(json.dumps(reval), chunk_size=1024):  # 청크 크기 설정
#                         yield f"data: {chunk}\n\n"
#                 elif (current_datetime - old_datetime).total_seconds() >=30:
#                     old_datetime = current_datetime
#                     for chunk in split_message(json.dumps(reval), chunk_size=1024):  # 청크 크기 설정
#                         yield f"data: {chunk}\n\n"
                
#                 await asyncio.sleep(1)
#         except Exception as e:
#             # 예외 처리 및 로그 남기기
#             traceback.print_exc()
#             print(f"Exception in SSE stream: {e}")
#         finally:
#             pass

# async def get_dashboard_user_new(workspace_id, user_id, platform_type):
#     """
#     각 키별로 데이터를 비교하고, 변경된 경우 JSON으로 직렬화하여 클라이언트로 전송.
#     """
#     try:
#         redis_client = await get_redis_client_async()
#         previous_data = {}  # 이전 상태를 저장할 딕셔너리
#         last_sent_time = datetime.now()  # 마지막으로 데이터를 보낸 시간

#         while True:
#             current_time = datetime.now()

#             # 기본 정보
#             info = await db_dashboard.get_user_dashboard_info_new(workspace_id=workspace_id)
#             if "info" not in previous_data or previous_data["info"] != info:
#                 yield json.dumps({"key": "info", "value": info})
#                 previous_data["info"] = info

#             # 최근 실행 기록
#             history = await get_recent_history(workspace_id=workspace_id)
#             if "history" not in previous_data or previous_data["history"] != history:
#                 yield json.dumps({"key": "history", "value": history})
#                 previous_data["history"] = history

#             # 총 개수
#             total_count = await get_jonathan_workspace_item_count(workspace_id=workspace_id)
#             if "total_count" not in previous_data or previous_data["total_count"] != total_count:
#                 yield json.dumps({"key": "total_count", "value": total_count})
#                 previous_data["total_count"] = total_count

#             # 자원 사용 현황
#             usage = await get_workspace_resource_usage(redis_client=redis_client, workspace_id=workspace_id)
#             instance_usage, platform_resource_usage = await get_workspace_instance_used(redis_client=redis_client, workspace_id=workspace_id)
#             usage["platform_usage"] = platform_resource_usage
#             if "usage" not in previous_data or previous_data["usage"] != usage:
#                 yield json.dumps({"key": "usage", "value": usage})
#                 previous_data["usage"] = usage

#             # 워크스페이스 매니저 정보
#             workspace_data = await db_dashboard.get_workspace_new(workspace_id=workspace_id)
#             manager = workspace_data["manager_id"]
#             is_manager = manager == user_id
#             if "manager" not in previous_data or previous_data["manager"] != is_manager:
#                 yield json.dumps({"key": "manager", "value": is_manager})
#                 previous_data["manager"] = is_manager

#             # 플랫폼 타입에 따른 추가 정보
#             if platform_type == TYPE.PLATFORM_A_LLM:
#                 item_list = await get_jonathan_items_info(redis_client=redis_client, workspace_id=workspace_id, platform_type=platform_type)
#                 if "project_items" not in previous_data or previous_data["project_items"] != item_list:
#                     yield json.dumps({"key": "project_items", "value": item_list})
#                     previous_data["project_items"] = item_list
#             elif platform_type == TYPE.PLATFORM_FLIGHTBASE:
#                 item_list, pd_list = await get_jonathan_items_info(redis_client=redis_client, workspace_id=workspace_id, platform_type=platform_type)
#                 if "project_items" not in previous_data or previous_data["project_items"] != item_list:
#                     yield json.dumps({"key": "project_items", "value": item_list})
#                     previous_data["project_items"] = item_list
#                 if "project_instance_allocate" not in previous_data or previous_data["project_instance_allocate"] != pd_list:
#                     yield json.dumps({"key": "project_instance_allocate", "value": pd_list})
#                     previous_data["project_instance_allocate"] = pd_list

#             # 스토리지 사용 현황
#             storage = await get_storage_used(redis_client=redis_client, workspace_id=workspace_id)
#             if "storage" not in previous_data or previous_data["storage"] != storage:
#                 yield json.dumps({"key": "storage", "value": storage})
#                 previous_data["storage"] = storage

#             # 30초마다 마지막 상태 전체 전송
#             if (current_time - last_sent_time) >= timedelta(seconds=30):
#                 for key, value in previous_data.items():
#                     yield json.dumps({"key": key, "value": value})
#                 last_sent_time = current_time

#             await asyncio.sleep(1)  # 1초 대기
#     except Exception as e:
#         traceback.print_exc()
#         yield json.dumps({"key": "error", "value": str(e)})


async def get_recent_history(workspace_id):
    """
    최근 실행 기록 생성
    """
    try:
        history_url = f"http://log-middleware-rest.jonathan-efk:8080/v1/dashboard/workspace/{workspace_id}"
        history_raw = await common.post_request(history_url, data={"timespan": "7d", "count": 10})
        histories = []
        if history_raw.get("logs", None):
            for history in history_raw["logs"]:
                current_document = history["fields"]
                current_document["update_details"] = "-"
                histories.append(current_document)
        return histories
    except Exception as e:
        traceback.print_exc()
        return []









def create_user_new(new_user_name : str, workspace_id : int, password : str, user_type : int, headers_user : str,
                    email: str = None, job: str = None, nickname: str = None, team: str = None): 
    if headers_user is None:
        return response(status=0, message="Jf-user is None in headers")
    if db_user.get_user(user_name=new_user_name):
        return response(status=0, message="Already Exist User")
    try:
        password = front_cipher.decrypt(password)
    except Exception as e:
        print(e)
        password = password
    enc_pw = crypt.crypt(password, settings.PASSWORD_KEY)
    uid = 1000 # TODO 임시 
    user_id = db_user.insert_user(user_name=new_user_name, password=enc_pw, uid=uid, user_type=user_type, email=email, job=job, nickname=nickname, team=team)
    if user_id:
        try:
            db_workspace.insert_user_workspace(workspace_id=workspace_id, user_id=user_id)
            return True
        except:
            return response(status=0, message="Create Error")

        return response(status=1, message=f"create user : {new_user_name}")
    else:
        return response(status=0, message="Create Error")