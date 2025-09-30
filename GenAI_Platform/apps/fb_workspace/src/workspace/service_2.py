from utils.msa_db import db_workspace, db_user, db_storage, db_project, db_deployment
from utils.resource import CustomResource, response  #, token_checker
from utils import common
from utils.redis import get_redis_client
from utils.redis_key import STORAGE_LIST_RESOURCE, GPU_INFO_RESOURCE, WORKSPACE_RESOURCE_QUOTA, WORKSPACE_PODS_STATUS, WORKSPACE_INSTANCE_QUEUE, WORKSPACE_INSTANCE_PENDING_POD, WORKSPACE_ITEM_PENDING_POD
from utils.exceptions import *
from utils import TYPE, PATH, settings
from utils import mongodb
from utils import notification_key
from utils import topic_key
from utils.log import logging_history, LogParam
from workspace.helm import create_workspace_namespace_volume, delete_workspace_namespace_volume
from workspace import model
from collections import defaultdict
from typing import List

from confluent_kafka.admin import AdminClient

import json
import os
import traceback
import requests
import random

from kubernetes import config, client
from utils.settings import KUBER_CONFIG_PATH
config.load_kube_config(config_file=KUBER_CONFIG_PATH)
coreV1Api = client.CoreV1Api()


# Consumer 설정
conf = {
    'bootstrap.servers': settings.JF_KAFKA_DNS,
}

INIT_CPU_LIMIT = 1
INIT_RAM_LIMIT = 4

redis_client = get_redis_client(role="slave")

# =================================================================================
def workspace_option(headers_user:str = None, workspace_id : int = None):
    # if headers_user != "root":
    #     return response(status=0, message="permission denied")
    # TODO
    # 추후 deployment, training user 그룹 생기면 변경
    user_list = [ { "name": user["name"] , "id" : user["id"], "type": "user"} for user in db_user.get_users() if user["name"] != settings.ADMIN_NAME]
    group_list = [ {
                    "name": user_group["name"],
                    "id" : user_group["id"],
                    "type": "group",
                    "user_id_list" : user_group["user_id_list"].split(",") if user_group["user_id_list"] is not None else [] ,
                    "user_name_list" : user_group["user_name_list"].split(",") if user_group["user_name_list"] is not None else [] }
                    for user_group in db_user.get_usergroups() ]

    # instance ===========================================================
    instance_list = []
    for item in db_workspace.get_instance_list():
        instance_id = item["id"]

        all_instance_allocate = db_workspace.get_sum_instance_allocate(instance_id=instance_id).get("all_instance_allocate")
        if all_instance_allocate is None:
            all_instance_allocate = 0

        if workspace_id is not None:
            ws_instance_allocate = db_workspace.get_workspace_allocate_instance(workspace_id=workspace_id, instance_id=instance_id)
            used = ws_instance_allocate.get("instance_allocate") if ws_instance_allocate is not None else 0
        else:
            used = 0
        free = item.get("instance_count") - all_instance_allocate

        instance_list.append({
            "name" : item["instance_name"],
            "id" : instance_id,
            "cpu" : item["cpu_allocate"],
            "gpu" : item.get("gpu_allocate") if item.get("gpu_allocate") is not None else 0,
            "ram" : item["ram_allocate"],
            "total" : item["instance_count"], # 총량
            "used" : used, # 현재 워크스페이스에 할당되어 있는 인스턴스 개수
            "free" : free, # 잔여량
            "avail" : used + free, # 할당개수 숫자 지웠을때 회색으로 표시되는 사용가능 수
            "gpu_name" : item.get("resource_name"),
        })

    # storage ===========================================================
    storage_list=[]

    storage_redis = redis_client.get(STORAGE_LIST_RESOURCE)
    print(storage_redis)
    if storage_redis:
        storage_info = json.loads(storage_redis)
        for storage_id, info in storage_info.items():
            storage_list.append(
                {
                    'id' : storage_id,
                    'name' : info['name'],
                    'type' : info['type'],
                    'total_size' : common.byte_to_gigabyte(info['total']),
                    'used_size' :  common.byte_to_gigabyte(info['total_alloc']),
                    'free_size' : common.byte_to_gigabyte(info['avail']),
                }
            )
    else:
        for storage in db_storage.get_storage():
            storage_list.append(
                {
                    "id":storage['id'],
                    "name": storage['name'],
                    "type":storage['type'], #TODO REMOVE
                    "total_size" : common.byte_to_gigabyte(storage['size']),
                    "used_size" : 0,
                    "free_size" : common.byte_to_gigabyte(storage['size'])
                }
            )
    #     "main_storage" : {}

    #     "data_storage"/

    # GPU ===========================================================
    # gpu_models = get_gpu(workspace_id=workspace_id)

    # USER ===========================================================
    for i, group in enumerate(group_list):
        user_list_temp = []
        for j in range(len(group["user_id_list"])):
            user_list_temp.append(
                {
                    "name": group["user_name_list"][j],
                    "id" : int(group["user_id_list"][j]),
                    "type" : "user"
                }
            )
        group_list[i] = {
            "name" : group_list[i]["name"],
            "id" : group_list[i]["id"],
            "user_list": user_list_temp
        }

    # result =========================================================
    result = {
        "user_list": user_list,
        "user_group_list": group_list,
        # "cpu_models" : cpu_models,
        # "gpu_models" : gpu_models,
        "instance_list" : instance_list,
        # "memory" : memory,
        "storage_list": storage_list,
    }
    if workspace_id:
        workspace_info = db_workspace.get_workspace(workspace_id=workspace_id)
        result["workspace_info"] = {
            "users" : db_workspace.get_workspace_users(workspace_id=workspace_id),
            "manager_id" : workspace_info["manager_id"],
            "manager_name" : workspace_info["manager_name"],
            "data_storage_size" : common.convert_unit_num(workspace_info["data_storage_size"], "Gi", True),
            "main_storage_size" : common.convert_unit_num(workspace_info["main_storage_size"], "Gi", True),
            "instance_list" : db_workspace.get_workspace_instance_list(workspace_id=workspace_id)
        }
    return response(status=1, result=result)

def get_workspaces(headers_user, page, size, search_key, search_value):
    try:
        if headers_user is None:
            return response(status=0, message="Jf-user is None in headers")
        user_info = db_user.get_user(user_name=headers_user)
        if user_info is not None:
            if user_info['user_type'] == 0:
                # Admin
                list_ = get_workspace_list(page=page, size=size, search_key=search_key, search_value=search_value,
                                            user_id=None, user_name=headers_user)
                request_workspaces = db_workspace.get_workspace_requests()
                for request_workspace in request_workspaces:
                    request_workspace["user_list"] = json.loads(request_workspace["user_list"])
                    request_workspace["allocate_instance_list"] = json.loads(request_workspace["allocate_instance_list"])

                count = len(list_) + len(request_workspaces)
                list_active = [info for info in list_ if info.get("status")=="active"]
                list_expired = [info for info in list_ if info.get("status")!="active"]
                res = response(status=1, result={"list": list_active+list_expired, "total": count, "request_workspace_list" : request_workspaces})

            else:
                # User
                list_ = get_workspace_list(page=page, size=size, search_key=search_key, search_value=search_value,
                                            user_id=user_info['id'], user_name=headers_user)

                count = len(list_)
                list_active = [info for info in list_ if info.get("status")=="active"]
                list_expired = [info for info in list_ if info.get("status")!="active"]
                res = response(status=1, result={"list": list_active+list_expired, "total": count})


        else:
            res = response(status=0, message="Can not find user")

        return res
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Get workspaces Error")
        #return response(status=0, message=e)

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

def get_workspace_list(page, size, search_key, search_value, user_id, user_name):
    result = []
    try:
        workspaces = db_workspace.get_workspace_list(page=page, size=size, search_key=search_key, search_value=search_value, user_id=user_id)
        if workspaces is not None:

            # gpu_models_status = json.loads(redis_con.get("resource:gpu_info"))
            gpu_info_resource = redis_client.get(GPU_INFO_RESOURCE)
            if gpu_info_resource is None:
                gpu_status = dict()
            else:
                gpu_status = json.loads(gpu_info_resource)

            workspaces_quota = redis_client.hgetall(WORKSPACE_RESOURCE_QUOTA)

            all_workspace_users_list = db_workspace.get_workspace_users()
            all_workspace_users_dict = common.gen_dict_from_list_by_key(target_list=all_workspace_users_list, id_key="workspace_id")

            # TODO
            # 추후 각 아이템 테이블 추가시 추가
            # all_workspace_count_info_list = db.get_workspace_count_info_list()
            # all_workspace_count_info_dict = common.gen_dict_from_list_by_key(target_list=all_workspace_count_info_list, id_key="workspace_id")

            for workspace in workspaces:
                status = common.get_workspace_status(workspace)
                # 할당된 GPU 개수
                # workspace_instance_manage = db_workspace.get_workspace_instance_manage(workspace_id=workspace["id"])
                # Initial setup using defaultdict

                resource = {
                    "gpu" : {"total" : 0, "used" : 0},
                    "cpu" : {"total" : 0, "used" : 0},
                }
                workspace_quota = workspaces_quota.get(str(workspace["id"]))
                if workspace_quota is not None:
                    workspace_quota = json.loads(workspace_quota)

                    if workspace_quota.get("gpu") is not None:
                        resource["gpu"]["total"] = workspace_quota.get("gpu").get("hard")
                        resource["gpu"]["used"] = workspace_quota.get("gpu").get("used")

                    if workspace_quota.get("cpu") is not None:
                        resource["cpu"]["total"] = workspace_quota.get("cpu").get("hard")
                        resource["cpu"]["used"] = workspace_quota.get("cpu").get("used")

                project_count, deployment_count = get_workspace_used_gpu(workspace_id=workspace["id"], data=gpu_status)
                gpu = {
                       "total" :{
                           "total" : resource.get("gpu").get("total"),
                           "used" : resource.get("gpu").get("used")
                       }
                }

                workspace_data = {"id": workspace["id"],
                                  "name": workspace["name"],
                                  "create_datetime": workspace["create_datetime"],
                                  "start_datetime": workspace["start_datetime"],
                                  "end_datetime": workspace["end_datetime"],
                                  "status": status,
                                  "description": workspace["description"],
                                  "resource" : resource,
                                  "gpu": gpu, # TODO 삭제
                                  "user": {},
                                  "manager": workspace["manager_name"]
                                  }

                users = all_workspace_users_dict.get(workspace["id"])
                for u in users:
                    if u['user_name'] == user_name:
                        workspace_data['favorites'] = u['favorites']
                user_data = {"total": len(users), "list": [{"name":user['user_name'], "id":user['id']} for user in users]}
                workspace_data['user'] = user_data
                workspace_item = db_workspace.get_workspace_item_count(workspace_id=workspace["id"])
                workspace_data.update(workspace_item)
                # TODO
                # 추후 스토리지 관련 추가
                workspace_data["usage"] = {}


                result.append(workspace_data)
    except:
        traceback.print_exc()
    return result

# =================================================================================
def create_workspace(manager_id : int, workspace_name : str, allocate_instances : List[dict], start_datetime: str, end_datetime: str, users : List[int],
                     description : str, main_storage_id : int, data_storage_request : str, main_storage_request : str, data_storage_id: int):
    """
    allocate_instances = {
        "instance_id" : int,
        "instance_allocate" : int, # 할당수
    }
    """
    workspace_id = None # 없으면 Exception에서 UnboundLocalError 걸릴 수도 있음
    try:
        # TODO
        # 저장되는 시점에 입력받은 GPU 자원 값이 할당 가능한지 check

        # workspace name check
        is_good = common.is_good_name(name=workspace_name)
        if is_good == False:
            raise WorkspaceNameInvalidError

        # GPU 개수 일정한지 check
        # if allocate_gpus:
        #     check_model_allocation(allocate_models=allocate_gpus)
        # CPU 개수 일정한지 check
        # if allocate_cpus:
        #     check_model_allocation(allocate_models=allocate_cpus)
        # TODO instance 개수 check

        # duplicate check
        if db_workspace.get_workspace(workspace_name=workspace_name):
            raise WorkspaceNameDuplicatedError

        # create pvc, namespace
        # TODO
        # 추후 스토리지 타입에따라 Path를 추가할건지 아닌지를 정해야함
        # 현재는 nfs 고정
        # monitoring_app_url="http://"+os.getenv('JF_MONITORING_APP_URL')+"/api/monitoring/get_workspace_path"
        # TODO
        # 추후 cpu, memory 개수는 변경될 수 있음

        # ceph 일 경우만 필요
        # get volume path
        # path = requests.get(monitoring_app_url, params={'workspace_name': workspace_name}).json()
        byte_data_storage_request = common.gib_to_bytes(data_storage_request)
        byte_main_storage_size = common.gib_to_bytes(main_storage_request)
        workspace_id = db_workspace.insert_workspace(manager_id=manager_id, workspace_name=workspace_name, start_datetime=start_datetime, end_datetime=end_datetime,
                                    description=description, path="", main_storage_size=byte_main_storage_size, data_storage_size=byte_data_storage_request ,data_storage_id=data_storage_id,
                                    main_storage_id=main_storage_id)

        if workspace_id:
            # instance ===============================================================================================
            db_res = db_workspace.insert_workspace_instance(workspace_id=workspace_id, allocate_instances=allocate_instances)
            if db_res == False:
                raise

            ### TODO 임의로 project, deployment instance 할당 -> db_workspace.insert_workspace_instance_manage 함수에 설정해둠
            # db_res = db_workspace.insert_workspace_instance_manage(workspace_id=workspace_id, allocate_instances=allocate_instances)
            # if db_res == False:
            #    raise

            # db_workspace.insert_workspace_resources(workspace_id=workspace_id, allocate_gpus=allocate_gpus)
            # for resource in allocate_gpus:
            #     db_workspace.insert_workspace_resource_manage(workspace_id=workspace_id, resource_group_id=RESOURCE_GROUP_KEY.get(resource["resource_name"]), allocate=resource["allocate"],
            #                                                   type=random.choices(["project", "deployment"], [0.8, 0.2], k=1)[0])

            #### instance_quota
            ws_instance_total_cpu, ws_instance_total_ram, ws_instance_total_gpu = get_workspace_instance_allocate(workspace_id=workspace_id)

            ## workspace resource DB 추가 # 초기값 cpu 1, ram 4 or 2
            INIT_RAM_LIMIT = 4
            if 4 > ws_instance_total_ram:
                INIT_RAM_LIMIT = 2
            elif 2 > ws_instance_total_ram:
                INIT_RAM_LIMIT = 1

            db_workspace.insert_workspace_resource(workspace_id=workspace_id,
                tool_cpu_limit=INIT_CPU_LIMIT, job_cpu_limit=INIT_CPU_LIMIT, hps_cpu_limit=INIT_CPU_LIMIT, deployment_cpu_limit=INIT_CPU_LIMIT,
                tool_ram_limit=INIT_RAM_LIMIT, job_ram_limit=INIT_RAM_LIMIT, hps_ram_limit=INIT_RAM_LIMIT, deployment_ram_limit=INIT_RAM_LIMIT)

            # storage ===============================================================================================
            data_storage_info=db_storage.get_storage(storage_id=data_storage_id)
            ws_storage_info=db_storage.get_storage(storage_id=main_storage_id)

            # helm ==================================================================================================
            res, message = create_workspace_namespace_volume(workspace_id=workspace_id,
                                                             workspace_name=workspace_name,
                                                             cpu_cores=ws_instance_total_cpu*1000,
                                                             memory=ws_instance_total_ram,
                                                             gpu_count=ws_instance_total_gpu,
                                                            #  memory=50, cpu_cores=4*1000,
                                                            #  gpu_count=sum([gpu["allocate"] for gpu in allocate_gpus]),
                                                             data_sc=data_storage_info['data_sc'],
                                                             main_sc=ws_storage_info['main_sc'],
                                                             main_storage_request=byte_main_storage_size,
                                                             data_storage_request=byte_data_storage_request)

                                                            # 2024/6/13 klod [0] 을 사용하니까 에러나서 일단 없는 것으로 변경하였음
                                                            #  data_sc=data_storage_info[0]['data_sc'],
                                                            #  main_sc=ws_storage_info[0]['main_sc'],

            if not res:
                raise Exception(message)

            # user ==================================================================================================
            users.append(manager_id)
            for user in users:
                db_workspace.insert_user_workspace(workspace_id=workspace_id, user_id=user)
            # log
            logging_history(task=LogParam.Task.WORKSPACE, action=LogParam.Action.CREATE, workspace_name=workspace_name)
            return True
        else:
            return False

    except CustomErrorList as ce:
        traceback.print_exc()
        if workspace_id:
            # TODO
            #워크스페이스 삭제
            db_workspace.delete_workspace(workspace_id=workspace_id)
            delete_workspace_namespace_volume(workspace_id=workspace_id)
            pass
        raise ce
    except Exception as e:
        traceback.print_exc()
        if workspace_id:
            # TODO
            #워크스페이스 삭제
            db_workspace.delete_workspace(workspace_id=workspace_id)
            delete_workspace_namespace_volume(workspace_id=workspace_id)
        raise e

def update_workspace(workspace_id : int, workspace_name: str, allocate_instances : List[dict],
                     start_datetime: str, end_datetime: str, users : List[int], description : str, manager_id : int):

    try:
        org_workspace = db_workspace.get_workspace(workspace_id=workspace_id)

        if org_workspace is None:
            raise WorkspaceNotExistError

        if org_workspace['name'] != workspace_name:
            raise WorkspaceNameChangeNotSupportedError

        # instance check ===============================================================================
        # check1
        for instance in allocate_instances:
            if instance.get("instance_allocate") == 0:
                # instance 할당량이 0 인 경우
                return response(status=0, message="instance는 최소 1개 이상 할당되어야 합니다.")

        # check2
        org_instances = [{"instance_id" : item.get("instance_id"), "instance_allocate" : item.get("instance_allocate")}
                              for item in db_workspace.get_workspace_instance_list(workspace_id=workspace_id)]

        print("origin instance: ", org_instances)
        print("new    instance: ", allocate_instances)
        diff_instance = [x for x in org_instances + allocate_instances if x not in org_instances or x not in allocate_instances]
        print("diff-", diff_instance)

        # 인스턴스 및 리소스 수정 ==========================================================================================
        if len(diff_instance) > 0:
            # 인스턴스 변경
            workspace_pod_list = json.loads(redis_client.hget(WORKSPACE_PODS_STATUS, workspace_id))
            if len(workspace_pod_list) > 0:
                return response(status=0, message="실행 중인 학습 & 배포 종료 후에 인스턴스를 변경하세요")

            # instance 초기화
            db_workspace.reset_workspace_project_instance(workspace_id=workspace_id)
            db_workspace.reset_workspace_deployment_instance(workspace_id=workspace_id)

            # resource 수정 (instance 수정) ===============================================================================
            # workspace update가 동시에 여러곳에서 일어나지 않는다는 가정
            existed_instance_list = db_workspace.get_workspace_instance_list(workspace_id=workspace_id)
            existed_instance_dict, existed_instance_id_list = dict(), list()
            for item in existed_instance_list:
                existed_instance_dict[item["instance_id"]] = item
                existed_instance_id_list.append(item["instance_id"])

            create_list, update_list = [], []
            for item in allocate_instances:
                if item["instance_id"] in existed_instance_id_list:
                    update_list.append(item)
                else:
                    create_list.append(item)
                if item["instance_id"] in existed_instance_dict:
                    del existed_instance_dict[item["instance_id"]]
            delete_instance_id_list = list(existed_instance_dict)

            ### workspace_instance allocate update -> workspace_instance allocate 개수 수정 or 그대로일 수 있음
            db_workspace.udpate_workspace_instance(workspace_id=workspace_id, allocate_instances=update_list)

            ### workspace_instance insert
            db_workspace.insert_workspace_instance(workspace_id=workspace_id, allocate_instances=create_list)

            ### workspace_instance delete
            db_workspace.delete_workspace_instance(workspace_id=workspace_id, instance_id_list=delete_instance_id_list)

            # resource 수정 (instance quota 수정) ===============================================================================
            ws_instance_total_cpu, ws_instance_total_ram, ws_instance_total_gpu = get_workspace_instance_allocate(workspace_id=workspace_id)

            namespace = f'{settings.JF_SYSTEM_NAMESPACE}-{workspace_id}'
            resource_quota_name = f'{namespace}-quota'

            quota = coreV1Api.read_namespaced_resource_quota(resource_quota_name, namespace)
            quota.spec.hard.update({
                'limits.cpu': str(ws_instance_total_cpu),
                'limits.memory': str(ws_instance_total_ram) + 'Gi',
                'requests.nvidia.com/gpu' : str(ws_instance_total_gpu)
            })
            coreV1Api.replace_namespaced_resource_quota(resource_quota_name, namespace, quota)

            ### workspace resource DB 수정
            # 현재 설정되어 있는 제한 값이 수정된 워크스페이스 자원을 초과할 경우, 초기값으로 워크스페이스 자원 제한값을 수정함
            workspace_resource = db_workspace.get_workspace_resource(workspace_id=workspace_id)

            update_workspace_limit = dict()
            for key, val in workspace_resource.items():
                if key in ["tool_cpu_limit", "job_cpu_limit", "hps_cpu_limit", "deployment_cpu_limit"]:
                    update_workspace_limit[key] = val if ws_instance_total_cpu >= val else INIT_CPU_LIMIT
                else:
                    update_workspace_limit[key] = val if ws_instance_total_ram >= val else INIT_RAM_LIMIT

            db_workspace.update_workspace_resource(workspace_id=workspace_id,
                    tool_cpu_limit=update_workspace_limit.get("tool_cpu_limit"), tool_ram_limit=update_workspace_limit.get("tool_ram_limit"),
                    job_cpu_limit=update_workspace_limit.get("job_cpu_limit"), job_ram_limit=update_workspace_limit.get("job_ram_limit"),
                    hps_cpu_limit=update_workspace_limit.get("hps_cpu_limit"),   hps_ram_limit=update_workspace_limit.get("hps_ram_limit"),
                    deployment_cpu_limit=update_workspace_limit.get("deployment_cpu_limit"), deployment_ram_limit=update_workspace_limit.get("deployment_ram_limit"))


        # 사용자 수정 ===============================================================================
        get_org_user_list = db_workspace.get_workspace_users(workspace_id=workspace_id)
        org_user_id_list = []
        for user_info in get_org_user_list:
            org_user_id_list.append(user_info['id'])
        users.append(int(manager_id))
        add_user, del_user = common.get_add_del_item_list(users, org_user_id_list)

        # 워크스페이스 기본 내용 수정 ===============================================================================
        if not db_workspace.update_workspace(manager_id=manager_id, workspace_id=workspace_id, start_datetime=start_datetime, end_datetime=end_datetime, description=description):
            raise Exception("workspace update error")

        db_workspace.insert_user_workspace_s(workspaces_id=[[workspace_id]]*len(add_user), users_id=add_user)
        db_workspace.delete_user_workspace_s(workspaces_id=[[workspace_id]]*len(del_user), users_id=del_user)

        # TODO storage 수정 추가   ===============================================================================

        logging_history(task=LogParam.Task.WORKSPACE, action=LogParam.Action.UPDATE, workspace_name=workspace_name)

        return response(status=1, message="success")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=None)

def delete_workspaces(workspace_list : List[int]):
    try:
       for workspace_id in workspace_list:

            # TODO
            # - 학습 또는 배포가 돌아가고 있는지 확인하는 로직 필요
            # - 자원 스케줄링 수정

            # workspace instance 삭제
            db_workspace.delete_workspace_instance(workspace_id=workspace_id, instance_id="all")

            workspace = db_workspace.get_workspace(workspace_id=workspace_id)
            result, message =delete_workspace_namespace_volume(workspace_id=workspace_id)
            try:
                coreV1Api.delete_namespace(name="{}-{}".format(settings.JF_SYSTEM_NAMESPACE, workspace_id))
            except:
                pass

            workspace_insttance_list = db_workspace.get_workspace_instance_list(workspace_id=workspace_id)
            project_list = db_project.get_project_list(workspace_id=workspace_id)
            deployment_list = db_deployment.get_deployment_list_in_workspace(workspace_id=workspace_id)

            instance_ids = [instance["instance_id"] for instance in workspace_insttance_list]
            project_ids = [project["id"] for project in project_list]
            deployment_ids = [deployment["id"] for deployment in deployment_list]

            db_workspace.delete_workspace(workspace_id=workspace_id)
            # redis key 삭제
            # pod 상태 및 pending 상태 삭제
            redis_client.hdel(WORKSPACE_PODS_STATUS, workspace_id)
            redis_client.hdel(WORKSPACE_INSTANCE_PENDING_POD, workspace_id)
            redis_client.hdel(WORKSPACE_ITEM_PENDING_POD, workspace_id)

            # instance queue 삭제
            for instance_id in instance_ids:
                try:
                    redis_client.delete(WORKSPACE_INSTANCE_QUEUE.format(workspace_id, instance_id, "CPU"))
                    redis_client.delete(WORKSPACE_INSTANCE_QUEUE.format(workspace_id, instance_id, "GPU"))
                except:
                    continue
            # TOPIC 삭제
            try:
                # resource_types = ["CPU", "GPU"]
                delete_topics = []
                delete_topics += [topic_key.PROJECT_TOPIC.format(project_id) for project_id in project_ids ]
                delete_topics += [topic_key.DEPLOYMENT_TOPIC.format(deployment_id) for deployment_id in deployment_ids]
                admin_client = AdminClient(conf)
                admin_client.delete_topics(delete_topics, operation_timeout=10)
            except:
                pass
            notification = mongodb.NotificationInfo(
                user_id=workspace["manager_id"],
                noti_type=notification_key.NOTIFICATION_TYPE_WORKSPACE,
                user_type=notification_key.NOTIFICATION_USER_TYPE_WORKSPACE_MANAGER,
                message=notification_key.WORKSPACE_DELETE_MESSAGE.format(workspace_name=workspace["name"])
            )
            res, message = mongodb.insert_notification_history(notification)
            logging_history(task=LogParam.Task.WORKSPACE, action=LogParam.Action.DELETE, workspace_name=workspace.get("name"))

    except Exception as e:
        traceback.print_exc()
        raise Exception(str(e))
    return True

# =================================================================================
# request

def request_workspace(headers_user: str, manager_id : int, workspace_name : str, allocate_instances : List[dict], start_datetime: str, end_datetime: str, users : List[int],
                     description : str, main_storage_id : int, data_storage_request : str, main_storage_request : str, data_storage_id: int, request_type: str = None, workspace_id: int = None):
    try:
        print("request_workspace")
        if request_type == "create":
            # name check
            is_good = common.is_good_name(name=workspace_name)
            if is_good == False:
                raise WorkspaceNameInvalidError

            # duplicate check
            if db_workspace.get_workspace(workspace_name=workspace_name):
                raise WorkspaceNameDuplicatedError

            # notification message
            noti_message = notification_key.WORKSPACE_CREATE_REQUEST.format(user_name=headers_user)

        elif request_type == "update":

            if db_workspace.get_workspace_request(request_workspace_name=workspace_name) is not None:
                raise Exception("이미 요청이 있습니다.")

            ws_info = db_workspace.get_workspace(workspace_id=workspace_id)
            workspace_name = ws_info.get("name")
            origin_ws_start_datetime = ws_info.get("start_datetime")
            origin_ws_end_datetime = ws_info.get("end_datetime")


            # (스토리지는 수정X)
            # 즉시 변경 ===============================================================================
            db_workspace.update_workspace(workspace_id=workspace_id, manager_id=manager_id, description=description,
                                          start_datetime=origin_ws_start_datetime, end_datetime=origin_ws_end_datetime)

            #### 사용자 수정 ===============================================================================
            get_org_user_list = db_workspace.get_workspace_users(workspace_id=workspace_id)
            org_user_id_list = []
            for user_info in get_org_user_list:
                org_user_id_list.append(user_info['id'])
            users.append(int(manager_id))
            add_user, del_user = common.get_add_del_item_list(users, org_user_id_list)

            db_workspace.insert_user_workspace_s(workspaces_id=[[workspace_id]]*len(add_user), users_id=add_user)
            db_workspace.delete_user_workspace_s(workspaces_id=[[workspace_id]]*len(del_user), users_id=del_user)


            # 요청 후 어드민이 변경 ==================================================================
            ### Date ===============================================================================
            flag = True
            if origin_ws_start_datetime != start_datetime or origin_ws_end_datetime != end_datetime:
                flag = False

            # instance ==============================================================================
            instance_list = dict()
            for item in db_workspace.get_workspace_instance_list(workspace_id=workspace_id):
                     instance_list.update({
                        item.get("instance_id") : item.get("instance_allocate")
                     })
            update_instance_list = dict()
            for item in allocate_instances:
                     update_instance_list.update({
                        item.get("instance_id") : item.get("instance_allocate")
                     })
            if instance_list != update_instance_list:
                flag = False

                # 인스턴스 사용 체크
                workspace_pod_list = json.loads(redis_client.hget(WORKSPACE_PODS_STATUS, workspace_id))
                if len(workspace_pod_list) > 0:
                    raise Exception("실행 중인 학습 & 배포 종료 후에 인스턴스를 변경하세요")

            # ===============================================================================
            # date or instance 변경이 안되었을 경우 종료
            if flag == True:
                return True, "update"

            # notification message
            noti_message = notification_key.WORKSPACE_UPDATE_REQUEST.format(user_name=headers_user, workspace_name=workspace_name)

        # Data Input Format
        notification = mongodb.NotificationInfo(
            user_id=db_user.get_user(user_name="admin")["id"],
            noti_type=notification_key.NOTIFICATION_TYPE_WORKSPACE,
            message=noti_message,
        )

        user_list_json = json.dumps(users)
        instance_allocate_list_json = json.dumps(allocate_instances)
        print("instance_allocate_list_json", instance_allocate_list_json)
        workspace_request_id = db_workspace.insert_workspace_request(manager_id=manager_id, workspace_name=workspace_name, start_datetime=start_datetime, end_datetime=end_datetime,
                                    description=description, path="", main_storage_size=main_storage_request, data_storage_size=data_storage_request ,data_storage_id=data_storage_id,
                                    main_storage_id=main_storage_id, user_list=user_list_json, allocate_instance_list=instance_allocate_list_json, type=request_type, workspace_id=workspace_id)
        if workspace_request_id:
            res, message = mongodb.insert_notification_history(notification)

            # notification.request_info = workspace_request_info

            # mongodb insert
            if not res:
                raise Exception(message)
            # res, message = mongodb.insert_request(request)
            if not res:
                raise Exception(message)

            return True, "request"
        else:
            raise Exception("server error")
    except Exception as e:
        raise Exception(str(e))

def refuse_workspace_request(request_workspace_id : int):
    request_workspace = db_workspace.get_workspace_request(request_workspace_id=request_workspace_id)
    request_type = request_workspace.get("type")

    if db_workspace.delete_workspace_request(request_workspace_id=request_workspace_id):

        if request_type == "create":
            message = notification_key.WORKSPACE_CREATE_REFUSE_MESSAGE.format(workspace_name=request_workspace["name"])
        elif request_type == "update":
            message = notification_key.WORKSPACE_UPDATE_REFUSE_MESSAGE.format(workspace_name=request_workspace["name"])

        notification = mongodb.NotificationInfo(
            user_id=request_workspace["manager_id"],
            noti_type=notification_key.NOTIFICATION_TYPE_WORKSPACE,
            user_type=notification_key.NOTIFICATION_USER_TYPE_USER,
            message=message)

        res, message = mongodb.insert_notification_history(notification)
        return response(status=1, result=True)
    return response(status=0, result=False)

def request_workspace_accept(request_workspace_id: int):
    workspace_id = None # 없으면 Exception에서 UnboundLocalError 걸릴 수도 있음
    try:
        info = db_workspace.get_workspace_request(request_workspace_id=request_workspace_id)
        request_type = info.get("type")
        workspace_name=info.get("name")
        manager_id=info.get("manager_id")

        if request_type == "create":
            create_workspace(manager_id=info.get("manager_id"),
                            workspace_name=info.get("name"),
                            allocate_instances=json.loads(info.get("allocate_instance_list")),
                            start_datetime=info.get("start_datetime"),
                            end_datetime=info.get("end_datetime"),
                            users=json.loads(info.get("user_list")),
                            description=info.get("description"),
                            main_storage_id=info.get("main_storage_id"),
                            main_storage_request=info.get("main_storage_size"),
                            data_storage_id=info.get("data_storage_id"),
                            data_storage_request=info.get("data_storage_size"))

        elif request_type == "update":
            update_workspace(
                workspace_id=info.get("workspace_id"),
                workspace_name=info.get("name"),
                allocate_instances=json.loads(info.get("allocate_instance_list")),
                start_datetime=info.get("start_datetime"),
                end_datetime=info.get("end_datetime"),
                users=json.loads(info.get("user_list")),
                description=info.get("description"),
                manager_id=info.get("manager_id"),
            )

        if db_workspace.delete_workspace_request(request_workspace_id=request_workspace_id):
            notification = mongodb.NotificationInfo(
                user_id=manager_id,
                noti_type=notification_key.NOTIFICATION_TYPE_WORKSPACE,
                user_type=notification_key.NOTIFICATION_USER_TYPE_USER,
                message=notification_key.WORKSPACE_CREATE_MESSAGE.format(workspace_name=workspace_name)
            )
            res, message = mongodb.insert_notification_history(notification)

        return True
    except CustomErrorList as ce:
        if workspace_id:
            # TODO
            #워크스페이스 삭제
            db_workspace.delete_workspace(workspace_id=workspace_id)
            delete_workspace_namespace_volume(workspace_id=workspace_id)
            pass
        raise ce
    except Exception as e:
        if workspace_id:
            # TODO
            #워크스페이스 삭제
            db_workspace.delete_workspace(workspace_id=workspace_id)
            delete_workspace_namespace_volume(workspace_id=workspace_id)
        raise e

# def request_workspace_accept(manager_id : int, workspace_name : str, allocate_instances : List[dict], start_datetime: str, end_datetime: str, users : List[int],
#                      description : str, main_storage_id : int, data_storage_request : str, main_storage_request : str, data_storage_id: int, request_workspace_id: int):

def request_workspace_option(request_workspace_id : int):
    user_list = [ { "name": user["name"] , "id" : user["id"], "type": "user"} for user in db_user.get_users() if user["name"] != settings.ADMIN_NAME]
    group_list = [ {
                    "name": user_group["name"],
                    "id" : user_group["id"],
                    "type": "group",
                    "user_id_list" : user_group["user_id_list"].split(",") if user_group["user_id_list"] is not None else [] ,
                    "user_name_list" : user_group["user_name_list"].split(",") if user_group["user_name_list"] is not None else [] }
                    for user_group in db_user.get_usergroups() ]

    # instance ===========================================================
    instance_list = []
    for item in db_workspace.get_instance_list():
        used = item["instance_allocate"]
        free = item["instance_count"] - item["instance_allocate"] if item["instance_count"] - item["instance_allocate"] > 0 else 0
        instance_list.append({
            "name" : item["instance_name"],
            "id" : item["id"],
            "cpu" : item["cpu_allocate"],
            "gpu" : item.get("gpu_allocate") if item.get("gpu_allocate") is not None else 0,
            "ram" : item["ram_allocate"],
            "total" : item["instance_count"],
            "used" : used,
            "free" : free,
            "avail" : used + free, # 할당량 칸 지웠을때 회색으로 나오는 사용가능 숫자
        })

    # storage ===========================================================
    storage_list=[]

    storage_info = json.loads(redis_client.get(STORAGE_LIST_RESOURCE))
    for storage_id, info in storage_info.items():
        storage_list.append(
            {
                'id' : storage_id,
                'name' : info['name'],
                'type' : info['type'],
                'total_size' : common.byte_to_gigabyte(info['total']),
                'used_size' :  common.byte_to_gigabyte(info['total_alloc']),
                'free_size' : common.byte_to_gigabyte(info['avail']),
            }
        )
    #     "main_storage" : {}

    #     "data_storage"/

    # GPU ===========================================================
    # gpu_models = get_gpu(workspace_id=workspace_id)

    # USER ===========================================================
    for i, group in enumerate(group_list):
        user_list_temp = []
        for j in range(len(group["user_id_list"])):
            user_list_temp.append(
                {
                    "name": group["user_name_list"][j],
                    "id" : int(group["user_id_list"][j]),
                    "type" : "user"
                }
            )
        group_list[i] = {
            "name" : group_list[i]["name"],
            "id" : group_list[i]["id"],
            "user_list": user_list_temp
        }

    # result =========================================================
    request_workspace_info = db_workspace.get_workspace_request(request_workspace_id=request_workspace_id)
    request_workspace_info["user_list"] = json.loads(request_workspace_info["user_list"]) if request_workspace_info.get("user_list", None) else []
    request_workspace_info["allocate_instance_list"] = json.loads(request_workspace_info["allocate_instance_list"]) if request_workspace_info.get("allocate_instance_list", None) else []
    result = {
        "user_list": user_list,
        "user_group_list": group_list,
        # "cpu_models" : cpu_models,
        # "gpu_models" : gpu_models,
        "instance_list" : instance_list,
        # "memory" : memory,
        "storage_list": storage_list,
        "request_workspace_info" : request_workspace_info
    }
    return response(status=1, result=result)


# =================================================================================

# def group_by_gpu_model(data):
#     grouped_data = {}
#     for item in data:
#         model_name = item["gpu_model_name"]
#         grouped_data.setdefault(model_name, []).append(item)
#     return [{"gpu_model_name": model_name, "records": records, "total": len(records)} for model_name, records in grouped_data.items()]

# def check_model_allocation(workspace_id : int = None , allocate_models : List[dict] = []):
#     """Check if the total GPU allocation exceeds the available GPUs."""
#     allocate_models = {model["resource_name"]: model["allocate"] for model in allocate_models}
#     # Get the currently allocated GPUs
#     allocated_models = get_gpu(workspace_id=workspace_id)
#     # if resource_type == ResourceType.GPU.value:
#     #     allocated_models = get_gpu(workspace_id=workspace_id)
#     # else:
#     #     allocated_models = get_cpu(workspace_id=workspace_id)
#     # Create a dictionary of available GPUs
#     available_gpus = {model["resource_name"]: model["free"] for model in allocated_models}

#     # Check if any model exceeds its allocated GPU resources
#     for resource_name, allocate in allocate_models.items():
#         if resource_name in available_gpus and available_gpus[resource_name] < allocate:
#             raise Exception(f"GPU over allocation for model: {resource_name}")

def get_workspace_instance_allocate(workspace_id):
    cpu, ram, gpu = 0, 0, 0
    try:
        info_list = db_workspace.get_workspace_instance_list(workspace_id=workspace_id)
        for item in info_list:
            cpu += item["instance_allocate"] * item["cpu_allocate"]
            ram += item["instance_allocate"] * item["ram_allocate"]
            gpu += item.get("instance_allocate") * (item.get("gpu_allocate") if item.get("gpu_allocate") is not None else 0)
    except Exception as e:
        traceback.print_exc()
    return cpu, ram, gpu

def update_favorites(workspace_id, action, headers_user):
    try:
        if headers_user is None:
            return response(status=0, message="Jf-user is None in headers")
        user_id = db_user.get_user_id(headers_user)
        if user_id is not None:
            user_id = user_id['id']
            result = db_workspace.update_favorites(user_id, workspace_id, action)
            if result :
                return response(status=1, message="OK")
            else:
                return response(status=0, message="Can not update db")
        else:
            return response(status=0, message="Can not find user")

    except Exception as e:
        print(e)
        return response(status=0, message="Update favorites Error")


def get_workspace_resource(workspace_id):
    try:
        workspace_quota = json.loads(redis_client.hgetall(WORKSPACE_RESOURCE_QUOTA).get(str(workspace_id)))
        res = db_workspace.get_workspace_resource(workspace_id=workspace_id)
        res["cpu_max_limit"] = workspace_quota["cpu"]["hard"]
        res["ram_max_limit"] = workspace_quota["ram"]["hard"]
        return res
    except Exception as e:
        traceback.print_exc()
        return None

def update_workspace_resource(workspace_id, tool_cpu_limit, tool_ram_limit, job_cpu_limit, job_ram_limit,
            hps_cpu_limit, hps_ram_limit, deployment_cpu_limit, deployment_ram_limit):
    try:
        workspace_pod_list = json.loads(redis_client.hget(WORKSPACE_PODS_STATUS, workspace_id))
        if len(workspace_pod_list) > 0:
            raise Exception("실행 중인 학습 & 배포 종료 후에 변경하세요")

        res = db_workspace.update_workspace_resource(workspace_id=workspace_id,
            tool_cpu_limit=tool_cpu_limit, tool_ram_limit=tool_ram_limit, job_cpu_limit=job_cpu_limit, job_ram_limit=job_ram_limit,
            hps_cpu_limit=hps_cpu_limit, hps_ram_limit=hps_ram_limit, deployment_cpu_limit=deployment_cpu_limit, deployment_ram_limit=deployment_ram_limit)
        return res
    except Exception as e:
        traceback.print_exc()
        raise Exception(str(e))

def check_workspace_name(workspace_name):
    try:
        if db_workspace.get_workspace(workspace_name=workspace_name) is not None:
            return 0, "이미 사용중인 workspace 이름입니다."

        if db_workspace.get_workspace_request(request_workspace_name=workspace_name) is not None:
            return 0, "요청 대기중인 workspace 이름입니다."

        return 1, "OK"
    except:
        traceback.print_exc()
        return 0, "Check workspace name Error"
