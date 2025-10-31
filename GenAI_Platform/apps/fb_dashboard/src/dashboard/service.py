import os
import re
import subprocess
import traceback
import time
import requests
# from flask_restplus import reqparse, Resource
from werkzeug.datastructures import FileStorage
from utils.common import byte_to_gigabyte, make_nested_dict
from datetime import datetime
# import utils.storage

from dashboard import records
import json
# from restplus import api
from utils import settings, redis_key
# # import utils.db as db
from utils import TYPE
import utils.msa_db.db_dashboard as db_dashboard
from utils.msa_db import db_workspace, db_deployment, db_project, db_user, db_dataset, db_storage
# import utils.storage as sto
from utils.redis import  get_redis_client
# from utils.resource import CustomResource #, token_checker
from utils.resource import response
from utils.exceptions import *
from utils.access_check import workspace_access_check
from utils.mongodb import get_user_dashboard_timeline, get_admin_dashboard_timeline, get_admin_dashboard_dummy_timeline
import copy
from kubernetes import config, client
config.load_kube_config(config_file=settings.KUBER_CONFIG_PATH)
coreV1Api = client.CoreV1Api()

from functools import lru_cache, cache
from utils.common import ttl_cache

from dashboard import dummy

from collections import Counter
redis_client=get_redis_client()


# redis_client = None


# def initialize_redis():
#     global redis_client
#     if redis_client is None:
#         redis_client = get_redis_client()


# ===================================================================================================
# admin dashboard
# @ttl_cache(ttl_seconds=0.5)
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

# @ttl_cache(ttl_seconds=0.5)
def get_user_dashboard_info(workspace_id, headers_user=None):
    try:
        global redis_client
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
                        reval['storage']['main_storage']['usage']=int(main_storage['used_size']/main_storage['alloc_size']*100)
                        break

                for project in project_list:
                    project_usage = int(main_storage_usage.get(project['id'], 0))
                    reval['storage']['main_storage']['project_list'].append(
                        {
                            'name': project['name'],
                            'usage': int(project_usage/reval['storage']['main_storage']['total']*100)
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
                    data_usage = int(data_storage_usage.get(dataset['dataset_name'], 0))
                    reval['storage']['data_storage']['dataset_list'].append(
                        {
                            'name': dataset['dataset_name'],
                            'usage': int(data_usage/reval['storage']['data_storage']['total']*100)
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
                        "gpu_allocate" : project.get("gpu_allocate"),
                        "cpu_allocate" : db_workspace_resource.get("tool_cpu_limit"),
                        "ram_allocate" : db_workspace_resource.get("tool_ram_limit"),
                    } for i in project_tool_active_list],
                    "job_list" : [{
                        "job_id" : i.get("id"),
                        "start_datetime" : i.get("start_datetime"),
                        "gpu_name" : project.get("resource_name"),
                        "gpu_allocate" : project.get("gpu_count"),
                        "cpu_allocate" : db_workspace_resource.get("job_cpu_limit"),
                        "ram_allocate" : db_workspace_resource.get("job_ram_limit"),
                    } for i in project_job_list],
                })

            workspace_deployment_list = db_deployment.get_deployment_list_in_workspace(workspace_id=workspace_id)
            for deployment in workspace_deployment_list:
                deployment_id = deployment.get("id")
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
                        "cpu_allocate" : db_workspace_resource.get("deployment_cpu_limit"),
                        "ram_allocate" : db_workspace_resource.get("deployment_ram_limit"),
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
            # print(workspaces_quota)
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
                        if item_info["resource"]["cpu"] is not None:
                            total_cpu += item_info["resource"]["cpu"]
                        if item_info["resource"]["ram"] is not None:
                            total_ram += item_info["resource"]["ram"]
                        if item_info["resource"]["gpu"] is not None:
                            total_gpu += item_info["resource"]["gpu"]
                        instance_id = instance_id if instance_id else item_info["instance_id"]

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
                    total_cpu += worker_info["resource"]["cpu"]
                    total_ram += worker_info["resource"]["ram"]
                    total_gpu += worker_info["resource"]["gpu"]
                    instance_id = instance_id if instance_id else worker_info["instance_id"]
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

def get_user_resource_usage_info(workspace_id):
    try:
        res={}
        res["timeline"] = copy.deepcopy(dummy.dummy_user_resource_timeline)
        timeline_list = get_user_dashboard_timeline(now_date=datetime.now(), workspace_id=workspace_id)
        timestamp=None
        tem_dict=copy.deepcopy(dummy.resource_dummy_dict)
        count=0
        for timeline in timeline_list:
            if timestamp is None:
                timestamp = timeline['create_datetime'].strftime('%Y-%m-%d %H:%M')
            if timestamp == timeline['create_datetime'].strftime('%Y-%m-%d %H:%M'):
                count += 1
                tem_dict["gpu"]["used_gpu"] += timeline['gpu']['used']
                tem_dict["gpu"]["total_gpu"] += timeline['gpu']['hard']

                tem_dict["cpu"]["used_cpu"] += timeline['cpu']['used']
                tem_dict["cpu"]["total_cpu"] += timeline['cpu']['hard']

                tem_dict["ram"]["used_ram"] += timeline['ram']['used']
                tem_dict["ram"]["total_ram"] += timeline['ram']['hard']

                tem_dict["storage_main"]['used_storage_main'] += timeline['storage_main']['used']
                tem_dict["storage_main"]['total_storage_main'] += timeline['storage_main']['total']

                tem_dict["storage_data"]['used_storage_data'] += timeline['storage_data']['used']
                tem_dict["storage_data"]['total_storage_data'] += timeline['storage_data']['total']
            else:
                res["timeline"]["gpu"].append(
                    {
                        "used_gpu" : int(round(tem_dict["gpu"]["used_gpu"]/count)),
                        "total_gpu" : int(round(tem_dict["gpu"]["total_gpu"]/count)),
                        "usage_gpu" : int(tem_dict["gpu"]["used_gpu"]/tem_dict["gpu"]["total_gpu"]*100) if tem_dict["gpu"]["total_gpu"] > 0 else 0,
                        "date" : timestamp
                    }
                )
                res["timeline"]["cpu"].append(
                    {
                        "used_cpu" : int(round(tem_dict["cpu"]["used_cpu"]/count)),
                        "total_cpu" : int(round(tem_dict["cpu"]["total_cpu"]/count)),
                        "usage_cpu" : int(tem_dict["cpu"]["used_cpu"]/tem_dict["cpu"]["total_cpu"]*100) if tem_dict["cpu"]["total_cpu"] > 0 else 0,
                        "date" : timestamp
                    }
                )
                # 1073741824
                res["timeline"]["ram"].append(
                    {
                        "used_ram" : round(tem_dict['ram']['used_ram']/1073741824, 2),
                        "total_ram" : round(tem_dict['ram']['total_ram']/1073741824, 2),
                        "usage_ram" : int(tem_dict['ram']['used_ram']/tem_dict['ram']['total_ram']*100) if tem_dict["ram"]["total_ram"] > 0 else 0,
                        "date" : timestamp
                    }
                )
                res["timeline"]["storage_main"].append(
                    {
                        "used_storage_main" : round(tem_dict['storage_main']['used_storage_main']/1073741824, 2),
                        "total_storage_main" : round(tem_dict['storage_main']['total_storage_main']/1073741824, 2),
                        "usage_storage_main" : int(tem_dict['storage_main']['used_storage_main']/tem_dict['storage_main']['total_storage_main']*100) if tem_dict["storage_main"]["total_storage_main"] > 0 else 0,
                        "date" : timestamp
                    }
                )
                res["timeline"]["storage_data"].append(
                    {
                        "used_storage_data" : round(tem_dict['storage_data']['used_storage_data']/1073741824, 2),
                        "total_storage_data" : round(tem_dict['storage_data']['total_storage_data']/1073741824, 2),
                        "usage_storage_data" : int(tem_dict['storage_data']['used_storage_data']/tem_dict['storage_data']['total_storage_data']*100) if tem_dict["storage_data"]["total_storage_data"] > 0 else 0,
                        "date" : timestamp
                    }
                )
                count=0
                tem_dict=copy.deepcopy(dummy.resource_dummy_dict)
                timestamp = None
        # return res
        return response(status=1, result= res)
    except:
        traceback.print_exc()

def get_admin_resource_usage_info():
    try:
        res={}
        res["timeline"] = copy.deepcopy(dummy.dummy_user_resource_timeline)
        timeline_list = get_admin_dashboard_timeline(now_date=datetime.now())
        # global timeline_list
        # print(len(timeline_list))
        timestamp=None
        tem_dict=copy.deepcopy(dummy.resource_dummy_dict)
        count=0
        for timeline in timeline_list:
            if timestamp is None:
                timestamp = timeline['create_datetime'].strftime('%Y-%m-%d %H:%M')
            if timestamp == timeline['create_datetime'].strftime('%Y-%m-%d %H:%M'):
                count += 1
                tem_dict["gpu"]["used_gpu"] += timeline['gpu']['used_gpu']
                tem_dict["gpu"]["total_gpu"] += timeline['gpu']['total_gpu']

                tem_dict["cpu"]["used_cpu"] += timeline['cpu']['used_cpu']
                tem_dict["cpu"]["total_cpu"] += timeline['cpu']['total_cpu']

                tem_dict["ram"]["used_ram"] += timeline['ram']['used_ram']
                tem_dict["ram"]["total_ram"] += timeline['ram']['total_ram']

                tem_dict["storage_main"]['used_storage_main'] += timeline['storage_main']['used_storage_main']
                tem_dict["storage_main"]['total_storage_main'] += timeline['storage_main']['total_storage_main']

                tem_dict["storage_data"]['used_storage_data'] += timeline['storage_data']['used_storage_data']
                tem_dict["storage_data"]['total_storage_data'] += timeline['storage_data']['total_storage_data']
            else:
                res["timeline"]["gpu"].append(
                    {
                        "used_gpu" : int(round(tem_dict["gpu"]["used_gpu"]/count)),
                        "total_gpu" : int(round(tem_dict["gpu"]["total_gpu"]/count)),
                        "usage_gpu" : int(tem_dict["gpu"]["used_gpu"]/tem_dict["gpu"]["total_gpu"]*100) if tem_dict["gpu"]["total_gpu"] > 0 else 0,
                        "date" : timestamp
                    }
                )
                res["timeline"]["cpu"].append(
                    {
                        "used_cpu" : int(round(tem_dict["cpu"]["used_cpu"]/count)),
                        "total_cpu" : int(round(tem_dict["cpu"]["total_cpu"]/count)),
                        "usage_cpu" : int(tem_dict["cpu"]["used_cpu"]/tem_dict["cpu"]["total_cpu"]*100) if tem_dict["cpu"]["total_cpu"] > 0 else 0,
                        "date" : timestamp
                    }
                )
                # 1073741824
                res["timeline"]["ram"].append(
                    {
                        "used_ram" : round(tem_dict['ram']['used_ram']/1073741824, 2),
                        "total_ram" : round(tem_dict['ram']['total_ram']/1073741824, 2),
                        "usage_ram" : int(tem_dict['ram']['used_ram']/tem_dict['ram']['total_ram']*100) if tem_dict["ram"]["total_ram"] > 0 else 0,
                        "date" : timestamp
                    }
                )
                res["timeline"]["storage_main"].append(
                    {
                        "used_storage_main" : round(tem_dict['storage_main']['used_storage_main']/1073741824, 2),
                        "total_storage_main" : round(tem_dict['storage_main']['total_storage_main']/1073741824, 2),
                        "usage_storage_main" : int(tem_dict['storage_main']['used_storage_main']/tem_dict['storage_main']['total_storage_main']*100) if tem_dict["storage_main"]["total_storage_main"] > 0 else 0,
                        "date" : timestamp
                    }
                )
                res["timeline"]["storage_data"].append(
                    {
                        "used_storage_data" : round(tem_dict['storage_data']['used_storage_data']/1073741824, 2),
                        "total_storage_data" : round(tem_dict['storage_data']['total_storage_data']/1073741824, 2),
                        "usage_storage_data" : int(tem_dict['storage_data']['used_storage_data']/tem_dict['storage_data']['total_storage_data']*100) if tem_dict["storage_data"]["total_storage_data"] > 0 else 0,
                        "date" : timestamp
                    }
                )
                count=0
                tem_dict=copy.deepcopy(dummy.resource_dummy_dict)
                timestamp = None
        # return res
        return response(status=1, result= res)
    except:
        traceback.print_exc()

def get_admin_resource_usage_dummy():
    try:
        print("get_admin_resource_usage_dummy")
        start=datetime.now()
        global res
        # res={}
        # res["timeline"] = copy.deepcopy(dummy.dummy_user_resource_timeline)
        # timeline_list = get_admin_dashboard_dummy_timeline(now_date=datetime.now())
        # # print(type(timeline_list))
        # timestamp=None
        # # global timeline_list
        # # print(len(timeline_list))
        # tem_dict=copy.deepcopy(dummy.resource_dummy_dict)
        # count=0
        # for timeline in timeline_list:
        #     if timestamp is None:
        #         timestamp = timeline['create_datetime'].strftime('%Y-%m-%d %H:%M')
        #     if timestamp == timeline['create_datetime'].strftime('%Y-%m-%d %H:%M'):
        #         count += 1
        #         tem_dict["gpu"]["used_gpu"] += timeline['gpu']['used_gpu']
        #         tem_dict["gpu"]["total_gpu"] += timeline['gpu']['total_gpu']

        #         tem_dict["cpu"]["used_cpu"] += timeline['cpu']['used_cpu']
        #         tem_dict["cpu"]["total_cpu"] += timeline['cpu']['total_cpu']

        #         tem_dict["ram"]["used_ram"] += timeline['ram']['used_ram']
        #         tem_dict["ram"]["total_ram"] += timeline['ram']['total_ram']

        #         tem_dict["storage_main"]['used_storage_main'] += timeline['storage_main']['used_storage_main']
        #         tem_dict["storage_main"]['total_storage_main'] += timeline['storage_main']['total_storage_main']

        #         tem_dict["storage_data"]['used_storage_data'] += timeline['storage_data']['used_storage_data']
        #         tem_dict["storage_data"]['total_storage_data'] += timeline['storage_data']['total_storage_data']
        #     else:
        #         res["timeline"]["gpu"].append(
        #             {
        #                 "used_gpu" : int(round(tem_dict["gpu"]["used_gpu"]/count)),
        #                 "total_gpu" : int(round(tem_dict["gpu"]["total_gpu"]/count)),
        #                 "usage_gpu" : int(tem_dict["gpu"]["used_gpu"]/tem_dict["gpu"]["total_gpu"]*100) if tem_dict["gpu"]["total_gpu"] > 0 else 0,
        #                 "date" : timestamp
        #             }
        #         )
        #         res["timeline"]["cpu"].append(
        #             {
        #                 "used_cpu" : int(round(tem_dict["cpu"]["used_cpu"]/count)),
        #                 "total_cpu" : int(round(tem_dict["cpu"]["total_cpu"]/count)),
        #                 "usage_cpu" : int(tem_dict["cpu"]["used_cpu"]/tem_dict["cpu"]["total_cpu"]*100) if tem_dict["cpu"]["total_cpu"] > 0 else 0,
        #                 "date" : timestamp
        #             }
        #         )
        #         # 1073741824
        #         res["timeline"]["ram"].append(
        #             {
        #                 "used_ram" : round(tem_dict['ram']['used_ram']/1073741824, 2),
        #                 "total_ram" : round(tem_dict['ram']['total_ram']/1073741824, 2),
        #                 "usage_ram" : int(tem_dict['ram']['used_ram']/tem_dict['ram']['total_ram']*100) if tem_dict["ram"]["total_ram"] > 0 else 0,
        #                 "date" : timestamp
        #             }
        #         )
        #         res["timeline"]["storage_main"].append(
        #             {
        #                 "used_storage_main" : round(tem_dict['storage_main']['used_storage_main']/1073741824, 2),
        #                 "total_storage_main" : round(tem_dict['storage_main']['total_storage_main']/1073741824, 2),
        #                 "usage_storage_main" : int(tem_dict['storage_main']['used_storage_main']/tem_dict['storage_main']['total_storage_main']*100) if tem_dict["storage_main"]["total_storage_main"] > 0 else 0,
        #                 "date" : timestamp
        #             }
        #         )
        #         res["timeline"]["storage_data"].append(
        #             {
        #                 "used_storage_data" : round(tem_dict['storage_data']['used_storage_data']/1073741824, 2),
        #                 "total_storage_data" : round(tem_dict['storage_data']['total_storage_data']/1073741824, 2),
        #                 "usage_storage_data" : int(tem_dict['storage_data']['used_storage_data']/tem_dict['storage_data']['total_storage_data']*100) if tem_dict["storage_data"]["total_storage_data"] > 0 else 0,
        #                 "date" : timestamp
        #             }
        #         )
        #         count=0
        #         tem_dict=copy.deepcopy(dummy.resource_dummy_dict)
        #         timestamp = None
        end=datetime.now()

        # time_check=(end-start).total_seconds()
        # print(f"resource_usage_time : {time_check}")
        return response(status=1, result=res)
    except:
        traceback.print_exc()

# res={}
# def test():
#     global res
#     res["timeline"] = copy.deepcopy(dummy.dummy_user_resource_timeline)
#     tem_dict=copy.deepcopy(dummy.resource_dummy_dict)
#     while(1):
#         # timeline_list= get_admin_dashboard_dummy_timeline(now_date=datetime.now())
#         # res={}
#         timeline_list = get_admin_dashboard_dummy_timeline(now_date=datetime.now())
#         # print(type(timeline_list))
#         timestamp=None
#         # global timeline_list
#         # print(len(timeline_list))

#         count=0
#         for timeline in timeline_list:
#             if timestamp is None:
#                 timestamp = timeline['create_datetime'].strftime('%Y-%m-%d %H:%M')
#             if timestamp == timeline['create_datetime'].strftime('%Y-%m-%d %H:%M'):
#                 count += 1
#                 tem_dict["gpu"]["used_gpu"] += timeline['gpu']['used_gpu']
#                 tem_dict["gpu"]["total_gpu"] += timeline['gpu']['total_gpu']

#                 tem_dict["cpu"]["used_cpu"] += timeline['cpu']['used_cpu']
#                 tem_dict["cpu"]["total_cpu"] += timeline['cpu']['total_cpu']

#                 tem_dict["ram"]["used_ram"] += timeline['ram']['used_ram']
#                 tem_dict["ram"]["total_ram"] += timeline['ram']['total_ram']

#                 tem_dict["storage_main"]['used_storage_main'] += timeline['storage_main']['used_storage_main']
#                 tem_dict["storage_main"]['total_storage_main'] += timeline['storage_main']['total_storage_main']

#                 tem_dict["storage_data"]['used_storage_data'] += timeline['storage_data']['used_storage_data']
#                 tem_dict["storage_data"]['total_storage_data'] += timeline['storage_data']['total_storage_data']
#             else:
#                 res["timeline"]["gpu"].append(
#                     {
#                         "used_gpu" : int(round(tem_dict["gpu"]["used_gpu"]/count)),
#                         "total_gpu" : int(round(tem_dict["gpu"]["total_gpu"]/count)),
#                         "usage_gpu" : int(tem_dict["gpu"]["used_gpu"]/tem_dict["gpu"]["total_gpu"]*100) if tem_dict["gpu"]["total_gpu"] > 0 else 0,
#                         "date" : timestamp
#                     }
#                 )
#                 res["timeline"]["cpu"].append(
#                     {
#                         "used_cpu" : int(round(tem_dict["cpu"]["used_cpu"]/count)),
#                         "total_cpu" : int(round(tem_dict["cpu"]["total_cpu"]/count)),
#                         "usage_cpu" : int(tem_dict["cpu"]["used_cpu"]/tem_dict["cpu"]["total_cpu"]*100) if tem_dict["cpu"]["total_cpu"] > 0 else 0,
#                         "date" : timestamp
#                     }
#                 )
#                 # 1073741824
#                 res["timeline"]["ram"].append(
#                     {
#                         "used_ram" : round(tem_dict['ram']['used_ram']/1073741824, 2),
#                         "total_ram" : round(tem_dict['ram']['total_ram']/1073741824, 2),
#                         "usage_ram" : int(tem_dict['ram']['used_ram']/tem_dict['ram']['total_ram']*100) if tem_dict["ram"]["total_ram"] > 0 else 0,
#                         "date" : timestamp
#                     }
#                 )
#                 res["timeline"]["storage_main"].append(
#                     {
#                         "used_storage_main" : round(tem_dict['storage_main']['used_storage_main']/1073741824, 2),
#                         "total_storage_main" : round(tem_dict['storage_main']['total_storage_main']/1073741824, 2),
#                         "usage_storage_main" : int(tem_dict['storage_main']['used_storage_main']/tem_dict['storage_main']['total_storage_main']*100) if tem_dict["storage_main"]["total_storage_main"] > 0 else 0,
#                         "date" : timestamp
#                     }
#                 )
#                 res["timeline"]["storage_data"].append(
#                     {
#                         "used_storage_data" : round(tem_dict['storage_data']['used_storage_data']/1073741824, 2),
#                         "total_storage_data" : round(tem_dict['storage_data']['total_storage_data']/1073741824, 2),
#                         "usage_storage_data" : int(tem_dict['storage_data']['used_storage_data']/tem_dict['storage_data']['total_storage_data']*100) if tem_dict["storage_data"]["total_storage_data"] > 0 else 0,
#                         "date" : timestamp
#                     }
#                 )
#                 count=0
#                 tem_dict=copy.deepcopy(dummy.resource_dummy_dict)
#                 timestamp = None


# ===================================================================================================
WORKSPACE_USER_DASHBOARD="USER:WORKSPACE:DASHBOARD"
def set_dashboard_user():
    try:
        global redis_client
        # global workspace_user_info
        # redis=get_redis_client()
        while True:
            workspace_user_info = dict()
            for i in db_dashboard.get_workspace_list():
                workspace_user_info[i.get("id")] =  get_user_dashboard_info(i.get("id"))
            redis_client.set(WORKSPACE_USER_DASHBOARD, json.dumps(workspace_user_info))
            time.sleep(1)
    except:
        pass

def get_dashboard_user(workspace_id, user_id):
    # global workspace_user_info
    global redis_client
    try:
        data = redis_client.get(WORKSPACE_USER_DASHBOARD)

        if data is None:
            res = None
        else:
            workspace_user_info = json.loads(data)
            res = workspace_user_info.get(str(workspace_id))
            res['manager'] = res['manager'] == user_id
        return res
    except Exception as e:
        traceback.print_exc()
        raise
