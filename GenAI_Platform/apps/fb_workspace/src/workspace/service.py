from utils.resource import response
from utils import common
from utils.redis import get_redis_client
from utils.redis_key import (
    STORAGE_LIST_RESOURCE, 
    GPU_INFO_RESOURCE, 
    WORKSPACE_RESOURCE_QUOTA, 
    WORKSPACE_PODS_STATUS, 
    WORKSPACE_INSTANCE_QUEUE, 
    WORKSPACE_INSTANCE_PENDING_POD, 
    WORKSPACE_ITEM_PENDING_POD2, 
    DATASET_UPLOAD_LIST, 
    WORKSPACE_STORAGE_USAGE
)
from utils.exception.exceptions import *
from utils import TYPE, PATH, settings
from utils.msa_db import (
    db_workspace, db_user, db_storage, db_project, 
    db_deployment, db_dataset, db_prepro, db_collect,
    db_analyzing
)
if settings.LLM_USED:
    from utils.llm_db import db_model

from utils import mongodb
from utils import notification_key
from utils import topic_key
from utils.log import (
    logging_history, 
    logging_info_history, 
    LogParam, 
    InstanceInfo, 
    StorageInfo, 
    WorkspaceAllocationInfo
)
from workspace.helm import (
    create_workspace_namespace_volume, 
    delete_workspace_namespace_volume, 
    delete_workspace_pvc,
    create_workspace_pvc,
    delete_workspace_data_storage
)
from typing import List
from utils.kafka_producer import KafkaProducer


from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import json
import traceback
import math

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

# redis_client = get_redis_client(role="slave")

# =================================================================================
def workspace_dataset_running_check(workspace_id: int):
    try:
        try:
            redis_client = get_redis_client()
            workspace_pod_list_raw = redis_client.hget(WORKSPACE_PODS_STATUS, workspace_id)
            workspace_pod_list = json.loads(workspace_pod_list_raw) if workspace_pod_list_raw else {}
        except Exception as redis_error:
            print(f"Redis connection failed in workspace_dataset_running_check: {redis_error}, proceeding without pod status check")
            workspace_pod_list = {}
            
        if len(workspace_pod_list) > 0:
            raise Exception(f"워크스페이스에서 실행 중인 작업이 있습니다. 모든 학습 및 배포를 종료한 후 다시 시도해주세요.")
        
        # workspace에 속해있는 데이터셋에서 filebrowser 동작중인지 체크
        try:
            dataset_list_in_workspace = db_dataset.get_dataset_list(workspace_id=workspace_id)
            print(f"Dataset list for workspace {workspace_id}: {dataset_list_in_workspace}")
        except Exception as dataset_error:
            print(f"Error getting dataset list for workspace {workspace_id}: {dataset_error}")
            return False, f"데이터셋 목록을 가져오는데 실패했습니다: {str(dataset_error)}"
            
        if dataset_list_in_workspace:
            for dataset in dataset_list_in_workspace:
                try:
                    if dataset.get('filebrowser') == 1:
                        return False, f"워크스페이스에서 실행 중인 파일브라우저가 있습니다. 파일브라우저를 종료한 후 다시 시도해주세요."
                except Exception as dataset_check_error:
                    print(f"Error checking dataset filebrowser status: {dataset_check_error}, dataset: {dataset}")
                    return False, f"데이터셋 상태를 확인하는데 오류가 발생했습니다: {str(dataset_check_error)}"
                
        # workspcae에 속한 데이터셋에서 업로드중인지 체크
        try:
            upload_list = redis_client.hgetall(DATASET_UPLOAD_LIST)
            print(f"전체 업로드 목록: {upload_list}")
            if upload_list:
                for sub_key, key in upload_list.items():
                    upload_info = redis_client.hget(key, sub_key)
                    if upload_info:
                        upload_info=json.loads(upload_info)
                        print(f"업로드 정보 - key: {key}, sub_key: {sub_key}, info: {upload_info}")
                        if workspace_id == upload_info.get('workspace_id'):
                            dataset_name = upload_info.get('dataset_name', 'Unknown')
                            upload_status = upload_info.get('status', 'Unknown')
                            progress = upload_info.get('progress', 'Unknown')
                            print(f"*** workspace {workspace_id}에서 업로드 중인 데이터셋 발견 ***")
                            print(f"데이터셋명: {dataset_name}")
                            print(f"상태: {upload_status}")
                            print(f"진행률: {progress}")
                            print(f"전체 업로드 정보: {upload_info}")
                            return False, f"워크스페이스에서 데이터셋 '{dataset_name}' 업로드가 진행 중입니다. 업로드를 완료하거나 중단한 후 다시 시도해주세요."
            else:
                print("업로드 목록이 비어있습니다.")
        except Exception as redis_error:
            print(f"Redis connection failed for upload list check: {redis_error}, proceeding without upload check")
            
        return True, None
    except Exception as e:
        print(f"Exception in workspace_dataset_running_check: {e}")
        traceback.print_exc()
        return False, str(e)

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
    
    storage_redis = get_redis_client().get(STORAGE_LIST_RESOURCE)
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
            "main_storage_id" : workspace_info["main_storage_id"],
            "data_storage_id" : workspace_info["data_storage_id"],
            "manager_name" : workspace_info["manager_name"],
            "data_storage_size" : common.convert_unit_num(workspace_info["data_storage_size"], "G", True),
            "main_storage_size" : common.convert_unit_num(workspace_info["main_storage_size"], "G", True),
            "instance_list" : db_workspace.get_workspace_instance_list(workspace_id=workspace_id),
            "use_marker": workspace_info.get("use_marker", 0)  # use_marker가 없는 경우 기본값 0 사용
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
        redis_client = get_redis_client()
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
                                  "manager": workspace["manager_name"],
                                  "use_marker": workspace.get("use_marker", 0)  # use_marker가 없는 경우 기본값 0 사용
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

# datetime 문자열의 시분초를 00:00:00으로 설정
def parse_datetime(dt_str):
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return dt - timedelta(hours=9)
    except ValueError:
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    
def delete_workspace_storage_volumes(workspace_id: int) -> tuple[bool, str]:
    """
    워크스페이스의 PVC와 PV를 삭제하는 함수
    
    Args:
        workspace_id (int): 워크스페이스 ID
        
    Returns:
        tuple[bool, str]: (성공 여부, 메시지)
    """
    try:
        workspace_namespace = f'{settings.JF_SYSTEM_NAMESPACE}-{workspace_id}'
        main_pvc_name = f'{workspace_namespace}-main-pvc'
        data_pvc_name = f'{workspace_namespace}-data-pvc'
        
        # PVC 정보 조회
        main_pvc = coreV1Api.read_namespaced_persistent_volume_claim(main_pvc_name, workspace_namespace)
        data_pvc = coreV1Api.read_namespaced_persistent_volume_claim(data_pvc_name, workspace_namespace)

        main_pv_name = main_pvc.spec.volume_name
        data_pv_name = data_pvc.spec.volume_name
        
        # PVC 삭제
        res, msg = delete_workspace_pvc(workspace_id=workspace_id)
        
        # PV 삭제
        try:
            coreV1Api.delete_persistent_volume(main_pv_name)
            coreV1Api.delete_persistent_volume(data_pv_name)
        except Exception as e:
            traceback.print_exc()
            # PV 삭제 실패는 무시하고 계속 진행
            
        return True, "Storage volumes deleted successfully"
        
    except Exception as e:
        traceback.print_exc()
        return False, str(e)
# =================================================================================
def create_workspace(manager_id : int, workspace_name : str,  start_datetime: str, end_datetime: str, users : List[int], 
                     description : str, main_storage_id : int, data_storage_request : str, main_storage_request : str, data_storage_id: int, \
                        allocate_instances : List[dict] =[], use_marker : int = 0):
    """
    allocate_instances = {
        "instance_id" : int,
        "instance_allocate" : int, # 할당수
    }
    """
    workspace_id = None # 없으면 Exception에서 UnboundLocalError 걸릴 수도 있음
    try:

        try:
            start_dt = parse_datetime(start_datetime)
            end_dt = parse_datetime(end_datetime)
            start_datetime = start_dt.strftime("%Y-%m-%d %H:%M:%S")
            end_datetime = end_dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            raise ValueError("날짜 형식이 올바르지 않습니다. YYYY-MM-DD HH:MM 형식이어야 합니다.")

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
        byte_data_storage_request = common.gb_to_bytes(data_storage_request)
        byte_main_storage_size = common.gb_to_bytes(main_storage_request)
        workspace_id = db_workspace.insert_workspace(manager_id=manager_id, workspace_name=workspace_name, start_datetime=start_datetime, end_datetime=end_datetime,
                                    description=description, path="", main_storage_size=byte_main_storage_size, data_storage_size=byte_data_storage_request ,data_storage_id=data_storage_id,
                                    main_storage_id=main_storage_id, use_marker=use_marker)

        if workspace_id:
            # instance ===============================================================================================
            # allocate_instances = [] 일경우
            if allocate_instances:
                db_res = db_workspace.insert_workspace_instance(workspace_id=workspace_id, allocate_instances=allocate_instances)
                if db_res == False:
                    raise Exception("workspace instance insert failed")

                #### instance_quota
                ws_instance_total_cpu, ws_instance_total_ram, ws_instance_total_gpu = get_workspace_instance_allocate(workspace_id=workspace_id)
                 ## workspace resource DB 추가
                min_instance_resource = db_workspace.get_workspace_instance_min(workspace_id=workspace_id) 
                min_cpu_allocate = min_instance_resource.get("min_cpu_allocate", 0)
                min_ram_allocate = min_instance_resource.get("min_ram_allocate", 0)

                workspace_resouce_result = db_workspace.insert_workspace_resource(workspace_id=workspace_id,
                    tool_cpu_limit=min_cpu_allocate, job_cpu_limit=min_cpu_allocate, hps_cpu_limit=min_cpu_allocate, deployment_cpu_limit=min_cpu_allocate,
                    tool_ram_limit=min_ram_allocate, job_ram_limit=min_ram_allocate, hps_ram_limit=min_ram_allocate, deployment_ram_limit=min_ram_allocate)
                if workspace_resouce_result is False:
                    raise Exception("workspace resource insert failed")
            else:
                workspace_resouce_result = db_workspace.insert_workspace_resource(workspace_id=workspace_id,
                    tool_cpu_limit=0, job_cpu_limit=0, hps_cpu_limit=0, deployment_cpu_limit=0,
                    tool_ram_limit=0, job_ram_limit=0, hps_ram_limit=0, deployment_ram_limit=0)
                ws_instance_total_cpu, ws_instance_total_ram, ws_instance_total_gpu = 0, 0, 0

           

            # storage ===============================================================================================
            data_storage_info=db_storage.get_storage(storage_id=data_storage_id)
            main_storage_info=db_storage.get_storage(storage_id=main_storage_id)
            
            # helm ==================================================================================================
            workspace_namespace_result, msg = create_workspace_namespace_volume(workspace_id=workspace_id,
                                                            workspace_name=workspace_name,
                                                            cpu_cores=ws_instance_total_cpu*1000,
                                                            memory=ws_instance_total_ram,
                                                            gpu_count=ws_instance_total_gpu,
                                                            sc_type=main_storage_info['type'], # TODO 추후 data, main 구분 필요
                                                            data_sc=data_storage_info['data_sc'],
                                                            main_sc=main_storage_info['main_sc'],
                                                            main_storage_request=byte_main_storage_size,
                                                            data_storage_request=byte_data_storage_request)
            if not workspace_namespace_result:
                raise WorkspaceNamespaceCreateError
            
            workspace_pvc_result, msg = create_workspace_pvc(workspace_id=workspace_id, workspace_name=workspace_name, main_sc=main_storage_info['main_sc'], main_storage_request=byte_main_storage_size,
                             data_sc=data_storage_info['data_sc'], data_storage_request=byte_data_storage_request)
            if not workspace_pvc_result:
                raise WorkspaceStoragePVCCreateError

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
        print(f"{workspace_name} 생성 실패 생성 데이터 삭제")
        if workspace_id:
            # TODO
            #워크스페이스 삭제
            db_workspace.delete_workspace(workspace_id=workspace_id)
            delete_workspace_pvc(workspace_id=workspace_id)
            delete_workspace_namespace_volume(workspace_id=workspace_id)
            pass 
        raise ce
    except Exception as e:
        traceback.print_exc()
        print(f"{workspace_name} 생성 실패 생성 데이터 삭제")
        if workspace_id:
            # TODO
            #워크스페이스 삭제
            db_workspace.delete_workspace(workspace_id=workspace_id)
            delete_workspace_pvc(workspace_id=workspace_id)
            delete_workspace_namespace_volume(workspace_id=workspace_id)
        raise e

def update_workspace(workspace_id : int, workspace_name: str,  
                     start_datetime: str, end_datetime: str, users : List[int], description : str, manager_id : int,
                     main_storage_request : int = None, data_storage_request : int = None, data_storage_id : int = None, main_storage_id: int = None, allocate_instances : List[dict] = [],
                     manager_request : bool = False, use_marker : int = 0):
    
    try:
        
        redis_client = get_redis_client()
        start_dt = parse_datetime(start_datetime)
        end_dt = parse_datetime(end_datetime)
        start_datetime = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_datetime = end_dt.strftime("%Y-%m-%d %H:%M:%S")
        ## use_marker 업데이트
        try:
            db_workspace.update_workspace_use_marker(workspace_id=workspace_id, use_marker=use_marker)
        except Exception as e:
            print(f"Warning: Failed to update use_marker for workspace {workspace_id}: {e}")
            # use_marker 업데이트 실패는 전체 프로세스를 중단시키지 않음

        # 워크스페이스 기본 내용 수정 ===============================================================================# 워크스페이스 기본 내용 수정 ===============================================================================
        if not db_workspace.update_workspace(manager_id=manager_id, workspace_id=workspace_id, start_datetime=start_datetime, end_datetime=end_datetime, description=description):
            raise Exception("workspace update error")
        org_workspace = db_workspace.get_workspace(workspace_id=workspace_id)
        
        if org_workspace is None:
            raise WorkspaceNotExistError

        if org_workspace['name'] != workspace_name:
            raise WorkspaceNameChangeNotSupportedError
        
        # 워크스페이스 변경사항 체크 및 실행 중인 Pod 확인 ===============================================================================
        # 리소스 변경사항이 있는지 확인 (Pod 체크가 필요한 변경사항들)
        has_resource_changes = False
        
        # 인스턴스 변경 확인
        if allocate_instances:
            origin_instance_list = {item.get("instance_id") : {"instance_id" : item.get("instance_id"), "instance_allocate" : item.get("instance_allocate")} for item in db_workspace.get_workspace_instance_list(workspace_id=workspace_id)}
            request_instance_list = {item.get("instance_id") : item for item in allocate_instances}
            if origin_instance_list != request_instance_list:
                has_resource_changes = True
                print("인스턴스 할당 변경 감지")
        
        # 사용자 및 매니저 변경 확인 (Pod 체크 불필요)
        current_users = [user['id'] for user in db_workspace.get_workspace_users(workspace_id=workspace_id)]
        current_manager_id = org_workspace['manager_id']
        if set(current_users) != set(users):
            print("사용자 목록 변경 감지 (Pod 체크 불필요)")
        if current_manager_id != manager_id:
            print("매니저 변경 감지 (Pod 체크 불필요)")
        
        # 스토리지 변경 확인
        if main_storage_request is not None and data_storage_request is not None:
            current_main_storage_gb = math.floor(org_workspace['main_storage_size'] / (1000**3))
            current_data_storage_gb = math.floor(org_workspace['data_storage_size'] / (1000**3))
            request_main_storage_gb = int(main_storage_request)
            request_data_storage_gb = int(data_storage_request)
            
            if current_main_storage_gb != request_main_storage_gb or current_data_storage_gb != request_data_storage_gb:
                has_resource_changes = True
                print("스토리지 크기 변경 감지")
        
        # 리소스 변경사항이 있다면 실행 중인 Pod 확인
        if has_resource_changes:
            print("리소스 변경사항 감지 - 실행 중인 Pod 확인")
            res, msg = workspace_dataset_running_check(workspace_id=workspace_id)
            if not res:
                raise WorkspaceStorageError(msg)
        else:
            print("리소스 변경사항 없음 - Pod 확인 skip (사용자/매니저 변경만 있는 경우 허용)")
        
        modify_time = None
        try:
            modification_log = common.post_request_sync(url=f"{settings.LOG_MIDDLEWARE_DNS}/v1/workspace/modifyTime/{workspace_name}", data={})
            modify_time = modification_log.get("modifyTime")
            if modify_time and modify_time == "":
                modify_time = None
        except:
            pass
        # TODO 스토리지 및 자원 할당량 업데이트 정보도 추가해야 함

        previous_allocation_info = WorkspaceAllocationInfo(
            start_time=parse_datetime(org_workspace['start_datetime']).strftime("%Y-%m-%d %H:%M"), 
            end_time=parse_datetime(org_workspace['end_datetime']).strftime("%Y-%m-%d %H:%M"), 
            last_time=modify_time,
            instances=[
                InstanceInfo(
                        instance_name=item['instance_name'],
                        instance_count=item['instance_allocate']
                    ) for item in db_workspace.get_workspace_instance_list(workspace_id=workspace_id)
            ], 
            storages=[
                StorageInfo(
                        storage_name=db_storage.get_storage(storage_id=org_workspace['main_storage_id'])['name'],
                        storage_type='main',
                        storage_size=org_workspace['main_storage_size']
                    ),
                StorageInfo(
                        storage_name=org_workspace['data_storage_name'],
                        storage_type='data',
                        storage_size=org_workspace['data_storage_size']
                    )
            ])
        
        # storage check ================================================================================
        if main_storage_request is not None and data_storage_request is not None:
            try:
                print('storage check')
                # 입력값 유효성 검사
                if float(main_storage_request) <= 0 or float(data_storage_request) <= 0:
                    raise ValueError("Storage size must be greater than 0")
                
                # GB를 bytes로 변환하여 기존 storage size와 비교
                main_storage_request_bytes = common.gb_to_bytes(main_storage_request)
                data_storage_request_bytes = common.gb_to_bytes(data_storage_request)
                
                # 디버깅을 위한 로그 추가
                print(f"Original workspace storage - main: {org_workspace['main_storage_size']}, data: {org_workspace['data_storage_size']}")
                print(f"Request storage - main: {main_storage_request}GB ({main_storage_request_bytes} bytes), data: {data_storage_request}GB ({data_storage_request_bytes} bytes)")
                
                # bytes를 GB로 변환하여 비교 (프론트엔드와 동일한 방식)
                # 1000^3 기준으로 변환하고 floor() 처리 (프론트엔드와 동일)
                current_main_storage_gb = math.floor(org_workspace['main_storage_size'] / (1000**3))
                current_data_storage_gb = math.floor(org_workspace['data_storage_size'] / (1000**3))
                request_main_storage_gb = int(main_storage_request)
                request_data_storage_gb = int(data_storage_request)
                
                print(f"Current storage in GB - main: {current_main_storage_gb}GB, data: {current_data_storage_gb}GB")
                
                # GB 단위로 정확히 비교
                main_storage_changed = (current_main_storage_gb != request_main_storage_gb)
                data_storage_changed = (current_data_storage_gb != request_data_storage_gb)
                
                print(f"Storage change detection - main changed: {main_storage_changed} ({current_main_storage_gb} vs {request_main_storage_gb}), data changed: {data_storage_changed} ({current_data_storage_gb} vs {request_data_storage_gb})")
                
                if main_storage_changed or data_storage_changed:
                    print("Storage size 변경 감지 - storage 업데이트 프로세스 시작")
                    
                    try:
                        workspace_usage = redis_client.hget(WORKSPACE_STORAGE_USAGE, workspace_name)
                        if workspace_usage is None:
                            print(f"Storage usage information not found for workspace {workspace_name}, proceeding without usage check")
                            workspace_usage = None
                        else:
                            workspace_usage = json.loads(workspace_usage)
                    except Exception as redis_error:
                        print(f"Redis connection failed for storage usage check: {redis_error}, proceeding without usage check")
                        workspace_usage = None
                    
                    # Redis에서 사용량 정보를 가져올 수 있는 경우에만 사용량 체크
                    if workspace_usage:
                        current_data_usage = int(workspace_usage['data'])
                        current_main_usage = int(workspace_usage['main'])
                        
                        print(f"Current storage usage - main: {current_main_usage} bytes, data: {current_data_usage} bytes")
                        
                        if current_data_usage > data_storage_request_bytes:
                            raise WorkspaceStorageError(f"Data storage size cannot be reduced below current usage ({common.byte_to_gigabyte(current_data_usage)}GB)")
                        if current_main_usage > main_storage_request_bytes:
                            raise WorkspaceStorageError(f"Main storage size cannot be reduced below current usage ({common.byte_to_gigabyte(current_main_usage)}GB)")
                    
                    # Pod 체크는 이미 위에서 수행되었으므로 생략
                    
                    # data_storage_id와 main_storage_id 처리 - None인 경우 기존 워크스페이스에서 가져오기
                    try:
                        # None인 경우 기존 워크스페이스 정보에서 가져오기
                        if data_storage_id is None:
                            data_storage_id = org_workspace['data_storage_id']
                            print(f"Using existing data_storage_id from workspace: {data_storage_id}")
                        if main_storage_id is None:
                            main_storage_id = org_workspace['main_storage_id']
                            print(f"Using existing main_storage_id from workspace: {main_storage_id}")
                        
                        # 정수로 변환
                        data_storage_id = int(data_storage_id)
                        main_storage_id = int(main_storage_id)
                    except (ValueError, TypeError) as e:
                        raise WorkspaceStorageError(f"Invalid storage ID format: {e}")
                    except KeyError as e:
                        raise WorkspaceStorageError(f"Missing storage ID in workspace data: {e}")
                    
                    main_storage_info = db_storage.get_storage(storage_id=main_storage_id)
                    data_storage_info = db_storage.get_storage(storage_id=data_storage_id)
                    
                    if not main_storage_info:
                        raise WorkspaceStorageError(f"Main storage not found with ID: {main_storage_id}")
                    if not data_storage_info:
                        raise WorkspaceStorageError(f"Data storage not found with ID: {data_storage_id}")

                    res, msg = delete_workspace_storage_volumes(workspace_id=workspace_id)
                    if not res:
                        print(f"Storage deletion failed: {msg}")
                        raise WorkspaceStorageError(f"Failed to delete existing storage volumes: {msg}")
                    
                    # 새로운 PVC 생성 (bytes 단위로 변환된 값 사용)
                    workspace_pvc_result, msg = create_workspace_pvc(workspace_id=workspace_id, workspace_name=workspace_name, main_sc=main_storage_info['main_sc'], main_storage_request=main_storage_request_bytes,
                             data_sc=data_storage_info['data_sc'], data_storage_request=data_storage_request_bytes)
                    if not workspace_pvc_result:
                        raise WorkspaceStoragePVCCreateError(f"Failed to create new PVC: {msg}")
                    # db 업데이트 (bytes 단위로 변환된 값 사용)
                    db_workspace.update_workspace_storage_size(workspace_id=workspace_id,
                                                              data_storage_id=data_storage_id,
                                                              main_storage_id=main_storage_id,
                                                              data_storage_size=data_storage_request_bytes,
                                                              main_storage_size=main_storage_request_bytes)
                    previous_allocation_info.storages[0].storage_size = main_storage_request_bytes
                    previous_allocation_info.storages[1].storage_size = data_storage_request_bytes
                    print('storage 업데이트 완료')
                else:
                    print('storage 변경사항 없음 - skip')
            except ValueError as ve:
                traceback.print_exc()
                print(f"ValueError in storage check: {ve}")
                raise WorkspaceStorageError(str(ve))
            except json.JSONDecodeError as jde:
                print(f"JSON decode error: {jde}")
                raise WorkspaceStorageError("Invalid storage usage data format")
            except WorkspaceStorageError as wse:
                print(f"WorkspaceStorageError: {wse}")
                raise  # Re-raise WorkspaceStorageError as-is
            except Exception as e:
                traceback.print_exc()
                print(f"Unexpected error in storage check: {e}")
                raise WorkspaceStorageError(f"Storage update failed: {str(e)}")
        else:
            print('storage request 정보 없음 - storage 변경 skip')

        # instance check ===============================================================================
        if allocate_instances:

            # origin, request
            origin_instance_list = {item.get("instance_id") : {"instance_id" : item.get("instance_id"), "instance_allocate" : item.get("instance_allocate")} for item in db_workspace.get_workspace_instance_list(workspace_id=workspace_id)}
            request_instance_list = {item.get("instance_id") : item for item in allocate_instances}
            # add, update, delete
            add_instance_dict = {item : request_instance_list[item] for item in list(set(request_instance_list) - set(origin_instance_list))}
            delete_instance_dict = {item : origin_instance_list[item] for item in list(set(origin_instance_list) - set(request_instance_list))}
            tmp_update_instance_dict = {item : request_instance_list[item] for item in list(set(origin_instance_list) & set(request_instance_list))} # update는 할당량이 안바꼈을수도 있고, 바뀌었을수도 있음
            update_instance_dict = dict()
            not_update_instance_dict = dict()
            for key, value in tmp_update_instance_dict.items():
                if value not in origin_instance_list.values():
                    update_instance_dict[key] = value
                else:
                    not_update_instance_dict[key] = value

            # 인스턴스 및 리소스 수정 ==========================================================================================
            if len(add_instance_dict) > 0 or len(delete_instance_dict) > 0 or len(update_instance_dict) > 0:
                # check ==========================================================================================
                try:
                    workspace_pod_list_raw = redis_client.hget(WORKSPACE_PODS_STATUS, workspace_id)
                    workspace_pod_list = json.loads(workspace_pod_list_raw) if workspace_pod_list_raw else {}
                    workspace_pod_status = workspace_pod_list
                except Exception as redis_error:
                    print(f"Redis connection failed for pod status check: {redis_error}, proceeding without pod status check")
                    workspace_pod_list = {}
                    workspace_pod_status = {}

                # 워크스페이스에서 사용중인 인스턴스 id
                used_instance_id_list = []
                if workspace_pod_list:
                    for key, values in workspace_pod_list.items():
                        if key == "project":
                            for _, value in values.items():
                                for _, val in value.items():
                                    for _, v in val.items():
                                        if int(v["instance_id"]) not in used_instance_id_list:
                                            used_instance_id_list.append(int(v["instance_id"]))
                        elif key == "deployment":
                            for _, val in values.items():
                                for _, v in val.items():
                                    if int(v["instance_id"]) not in used_instance_id_list:
                                        used_instance_id_list.append(int(v["instance_id"]))
                
                # 삭제 or 수정하려는 인스턴스가 사용중인 인스턴스인지 확인 (추가는 used 확인 안해도 됨)
                update_delete_instance_id_list = list(delete_instance_dict.keys()) + list(update_instance_dict.keys())
                for item in update_delete_instance_id_list:
                    if item in used_instance_id_list:
                        # print("instance_id", tmp_update_instance_dict.get(item), used_instance_id_list)
                        return response(status=0, message="변경하려는 인스턴스가 사용중 입니다. 실행 중인 학습 & 배포 종료 후에 인스턴스를 변경하세요")

                # 학습, 배포 instance 초기화 ===============================================================================
                # instance_id가 할당된 학습 배포 초기화
                db_workspace.reset_workspace_project_instance(workspace_id=workspace_id, instance_id_list=update_delete_instance_id_list)
                db_workspace.reset_workspace_deployment_instance(workspace_id=workspace_id, instance_id_list=update_delete_instance_id_list)
                db_workspace.reset_workspace_collect_instance(workspace_id=workspace_id, instance_id_list=update_delete_instance_id_list)
                db_workspace.reset_workspace_preprocessing_instance(workspace_id=workspace_id, instance_id_list=update_delete_instance_id_list)
                db_workspace.reset_workspace_analyzer_instance(workspace_id=workspace_id, instance_id_list=update_delete_instance_id_list)

                # workspace instance DB 수정 ===============================================================================            
                ### workspace_instance allocate update
                db_workspace.udpate_workspace_instance(workspace_id=workspace_id, allocate_instances=list(update_instance_dict.values()) + list(not_update_instance_dict.values()))

                ### workspace_instance insert
                db_workspace.insert_workspace_instance(workspace_id=workspace_id, allocate_instances=list(add_instance_dict.values()))

                ### workspace_instance delete
                db_workspace.delete_workspace_instance(workspace_id=workspace_id, instance_id_list= list(delete_instance_dict.keys()))
                
                ### workspace resource DB 수정 ===============================================================================
                # workspace_resource = db_workspace.get_workspace_resource(workspace_id=workspace_id)

                min_instance_resource = db_workspace.get_workspace_instance_min(workspace_id=workspace_id) 
                min_cpu_allocate = min_instance_resource.get("min_cpu_allocate", 0)
                min_ram_allocate = min_instance_resource.get("min_ram_allocate", 0)
                workspace_resource = db_workspace.get_workspace_resource(workspace_id=workspace_id)
                if workspace_resource is None:
                    db_workspace.insert_workspace_resource(workspace_id=workspace_id, 
                        tool_cpu_limit=min_cpu_allocate, tool_ram_limit=min_ram_allocate, 
                        job_cpu_limit=min_cpu_allocate, job_ram_limit=min_ram_allocate,
                        hps_cpu_limit=min_cpu_allocate, hps_ram_limit=min_ram_allocate,
                        deployment_cpu_limit=min_cpu_allocate, deployment_ram_limit=min_ram_allocate)
                else:
                    db_workspace.update_workspace_resource(workspace_id=workspace_id, 
                            tool_cpu_limit=min_cpu_allocate, tool_ram_limit=min_ram_allocate, 
                            job_cpu_limit=min_cpu_allocate, job_ram_limit=min_ram_allocate,
                            hps_cpu_limit=min_cpu_allocate, hps_ram_limit=min_ram_allocate,
                            deployment_cpu_limit=min_cpu_allocate, deployment_ram_limit=min_ram_allocate)
                db_workspace.update_workspace_project_deployment_resource_limit(workspace_id=workspace_id, cpu_limit=min_cpu_allocate, ram_limit=min_ram_allocate)
            # resource 수정 (instance quota 수정) ===============================================================================
            ws_instance_total_cpu, ws_instance_total_ram, ws_instance_total_gpu = get_workspace_instance_allocate(workspace_id=workspace_id)
        else:
            # 기존 workspace 인스턴스 삭제
            # 모든 pod의 인스턴스 할당 삭제 
            db_workspace.reset_workspace_project_instance(workspace_id=workspace_id)
            db_workspace.reset_workspace_deployment_instance(workspace_id=workspace_id)
            db_workspace.reset_workspace_collect_instance(workspace_id=workspace_id)
            db_workspace.reset_workspace_preprocessing_instance(workspace_id=workspace_id)
            db_workspace.reset_workspace_analyzer_instance(workspace_id=workspace_id)

            # workspace instance DB 수정 ===============================================================================            
            ### workspace_instance allocate update
            db_workspace.delete_workspace_instance(workspace_id=workspace_id, instance_id="all")

            ws_instance_total_cpu, ws_instance_total_ram, ws_instance_total_gpu = 0, 0, 0

            pass

        namespace = f'{settings.JF_SYSTEM_NAMESPACE}-{workspace_id}'
        resource_quota_name = f'{namespace}-quota'
        
        quota = coreV1Api.read_namespaced_resource_quota(resource_quota_name, namespace)
        quota.spec.hard.update({
            'limits.cpu': str(ws_instance_total_cpu),
            'limits.memory': str(ws_instance_total_ram) + 'G',
            'requests.nvidia.com/gpu' : str(ws_instance_total_gpu)
        })
        coreV1Api.replace_namespaced_resource_quota(resource_quota_name, namespace, quota)
        # 사용자 수정 ===============================================================================
        get_org_user_list = db_workspace.get_workspace_users(workspace_id=workspace_id)
        org_user_id_list = []
        for user_info in get_org_user_list:
            org_user_id_list.append(user_info['id'])
        users.append(int(manager_id))
        add_user, del_user = common.get_add_del_item_list(users, org_user_id_list)     
        
        db_workspace.insert_user_workspace_s(workspaces_id=[[workspace_id]]*len(add_user), users_id=add_user)
        db_workspace.delete_user_workspace_s(workspaces_id=[[workspace_id]]*len(del_user), users_id=del_user)

        logging_info_history(task=LogParam.Task.WORKSPACE, action=LogParam.Action.UPDATE, workspace_name=workspace_name, info=previous_allocation_info.to_dict())
        #logging_history(task=LogParam.Task.WORKSPACE, action=LogParam.Action.UPDATE, workspace_name=workspace_name)

        return response(status=1, message="success")
    except WorkspaceStorageError as wse:
        traceback.print_exc()
        print(f"WorkspaceStorageError in update_workspace: {wse.message}")
        return response(status=0, message=str(wse.message))
    except Exception as e:
        traceback.print_exc()
        print(f"Exception in update_workspace: {e}")
        return response(status=0, message=str(e))



def delete_workspaces(workspace_list : List[int], headers_user_id : int, headers_user_type : int):
    try:
        print(headers_user_id, headers_user_type)
        redis_client = get_redis_client()
        for workspace_id in workspace_list:
            
            workspace = db_workspace.get_workspace(workspace_id=workspace_id)
            print(workspace["manager_id"], headers_user_id, int(headers_user_type), int(settings.ADMIN_TYPE))
            print(workspace["manager_id"] != headers_user_id, int(headers_user_type) != int(settings.ADMIN_TYPE))
            if workspace["manager_id"] == headers_user_id or int(headers_user_type) == int(settings.ADMIN_TYPE):

                # workspace에서 동작중인 pod 확인
                # dataset
                res, msg = workspace_dataset_running_check(workspace_id=workspace_id)
                if not res:
                    raise Exception(msg)
                
                # project, deployment, preprocessing, analyzer, collect pod 확인 
                workspace_pod_status = redis_client.hget(WORKSPACE_PODS_STATUS, workspace_id)
                workspace_pod_status = json.loads(workspace_pod_status) if workspace_pod_status is not None else {}

                if workspace_pod_status:
                    raise Exception("실행 중인 학습, 전처리기, 배포, 수집기, 분석기를 종료 후에 워크스페이스를 삭제하세요")
                            
                workspace_insttance_list = db_workspace.get_workspace_instance_list(workspace_id=workspace_id)
                
                # TODO: data / main storage 삭제
                res, msg = delete_workspace_data_storage(workspace_id=workspace_id, workspace_name=workspace["name"],
                                                          main_sc=workspace["main_storage_name"], data_sc=workspace["data_storage_name"])
                if not res:
                    raise Exception(msg)
                # pv 삭제
                res, msg = delete_workspace_storage_volumes(workspace_id=workspace_id)
                if not res:
                    raise Exception(msg)

                result, message =delete_workspace_namespace_volume(workspace_id=workspace_id)
                try:
                    coreV1Api.delete_namespace(name="{}-{}".format(settings.JF_SYSTEM_NAMESPACE, workspace_id))
                except:
                    pass

                # workspace image list 확인
                # image_list = db_workspace.get_workspace_image_list(workspace_id=workspace_id)
                # TODO: registry에서 이미지 삭제
                image_list = db_workspace.get_workspace_image_list(workspace_id=workspace_id)
                
                instance_ids = [instance["instance_id"] for instance in workspace_insttance_list]
                # workspace db 삭제
                db_workspace.delete_workspace(workspace_id=workspace_id)
                # redis key 삭제
                # pod 상태 및 pending 상태 삭제 
                redis_client.hdel(WORKSPACE_PODS_STATUS, workspace_id)
                redis_client.hdel(WORKSPACE_ITEM_PENDING_POD2, workspace_id)
            
                # instance queue 삭제
                for instance_id in instance_ids:
                    try:
                        redis_client.delete(WORKSPACE_INSTANCE_QUEUE.format(workspace_id, instance_id))
                    except:
                        continue
                
                
                

                notification = mongodb.NotificationInfo(
                    user_id=workspace["manager_id"],
                    noti_type=notification_key.NOTIFICATION_TYPE_WORKSPACE,
                    user_type=notification_key.NOTIFICATION_USER_TYPE_WORKSPACE_MANAGER,
                    message=notification_key.WORKSPACE_DELETE_MESSAGE.format(workspace_name=workspace["name"])
                )
                KafkaProducer(conf).produce(topic=topic_key.ALERT_SYSTEM_TOPIC, value=notification.model_dump_json())
                logging_history(task=LogParam.Task.WORKSPACE, action=LogParam.Action.DELETE, workspace_name=workspace.get("name"))
                return True
            else:
                raise Exception("워크스페이스 삭제 권한이 없습니다. 관리자이거나 해당 워크스페이스의 매니저인 경우에만 삭제가 가능합니다.")
    except Exception as e:
        traceback.print_exc()
        raise Exception(str(e))

# =================================================================================
# request

def request_workspace(headers_user: str, manager_id : int, workspace_name : str, allocate_instances : List[dict], start_datetime: str, end_datetime: str, users : List[int], 
                     description : str, main_storage_id : int, data_storage_request : str, main_storage_request : str, data_storage_id: int, request_type: str = None, 
                     workspace_id: int = None, use_marker : int = 0):
    try:
        print("request_workspace")
        redis_client = get_redis_client()
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
                try:
                    workspace_pod_list_raw = redis_client.hget(WORKSPACE_PODS_STATUS, workspace_id)
                    workspace_pod_list = json.loads(workspace_pod_list_raw) if workspace_pod_list_raw else {}
                    if len(workspace_pod_list) > 0:
                        raise Exception("실행 중인 학습 & 배포 종료 후에 인스턴스를 변경하세요")
                except Exception as redis_error:
                    print(f"Redis connection failed for pod status check in request_workspace: {redis_error}, proceeding without pod status check")
                    # Redis 연결 실패 시에도 인스턴스 변경 요청을 허용
            # storage =============================================================================
            # bytes를 GB로 변환하여 비교 (프론트엔드와 동일한 방식)
            # 1000^3 기준으로 변환하고 floor() 처리 (프론트엔드와 동일)
            current_main_storage_gb = math.floor(ws_info["main_storage_size"] / (1000**3))
            current_data_storage_gb = math.floor(ws_info["data_storage_size"] / (1000**3))
            request_main_storage_gb = int(main_storage_request)
            request_data_storage_gb = int(data_storage_request)
            
            print(f"Request workspace storage check - current: main {current_main_storage_gb}GB, data {current_data_storage_gb}GB")
            print(f"Request workspace storage check - request: main {request_main_storage_gb}GB, data {request_data_storage_gb}GB")
            
            # GB 단위로 정확히 비교
            main_storage_changed = (current_main_storage_gb != request_main_storage_gb)
            data_storage_changed = (current_data_storage_gb != request_data_storage_gb)
            
            if main_storage_changed or data_storage_changed:
                flag = False
                print("Storage 변경 감지됨 - 관리자 승인 필요")

            # ===============================================================================
            # date, instance, storage 변경이 안되었을 경우 종료 (사용자/매니저 변경만 있는 경우)
            if flag == True:
                print("사용자/매니저 정보만 변경됨 - 즉시 적용")
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
                                    main_storage_id=main_storage_id, user_list=user_list_json, allocate_instance_list=instance_allocate_list_json, type=request_type, 
                                    workspace_id=workspace_id, use_marker=use_marker)
        if workspace_request_id:
            KafkaProducer(conf).produce(topic=topic_key.ALERT_ADMIN_TOPIC, value=notification.model_dump_json())

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
        
        KafkaProducer(conf).produce(topic=topic_key.ALERT_SYSTEM_TOPIC, value=notification.model_dump_json())
        return response(status=1, result=True)
    return response(status=0, result=False)

def request_workspace_accept(request_workspace_id: int):
    workspace_id = None # 없으면 Exception에서 UnboundLocalError 걸릴 수도 있음
    try:
        info = db_workspace.get_workspace_request(request_workspace_id=request_workspace_id)
        request_type = info.get("type")
        workspace_name=info.get("name")
        manager_id=info.get("manager_id")
        MESSAGE = None
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
                            data_storage_request=info.get("data_storage_size"),
                            use_marker=info.get("use_marker")
                            )
            MESSAGE = notification_key.WORKSPACE_CREATE_ACCEP_MESSAGE.format(workspace_name=workspace_name)
        elif request_type == "update":
            res = update_workspace(
                workspace_id=info.get("workspace_id"),
                workspace_name=info.get("name"),
                allocate_instances=json.loads(info.get("allocate_instance_list")),
                start_datetime=info.get("start_datetime"),
                end_datetime=info.get("end_datetime"),
                users=json.loads(info.get("user_list")),
                description=info.get("description"),
                manager_id=info.get("manager_id"),
                main_storage_request=info.get("main_storage_size"),
                data_storage_request=info.get("data_storage_size"),
                data_storage_id=info.get("data_storage_id"),
                main_storage_id=info.get("main_storage_id"),
                use_marker=info.get("use_marker")
            )
            MESSAGE = notification_key.WORKSPACE_UPDATE_ACCEP_MESSAGE.format(workspace_name=workspace_name)
        

        if db_workspace.delete_workspace_request(request_workspace_id=request_workspace_id):
            notification = mongodb.NotificationInfo(
                user_id=manager_id,
                noti_type=notification_key.NOTIFICATION_TYPE_WORKSPACE,
                user_type=notification_key.NOTIFICATION_USER_TYPE_USER,
                message=MESSAGE.format(workspace_name=workspace_name)
            )
            KafkaProducer(conf).produce(topic=topic_key.ALERT_SYSTEM_TOPIC, value=notification.model_dump_json())
        
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
    
    request_workspace_info = db_workspace.get_workspace_request(request_workspace_id=request_workspace_id)
    request_workspace_info["user_list"] = json.loads(request_workspace_info["user_list"]) if request_workspace_info.get("user_list", None) else []
    request_workspace_info["allocate_instance_list"] = json.loads(request_workspace_info["allocate_instance_list"]) if request_workspace_info.get("allocate_instance_list", None) else []
    allocate_inatance_dict = { instance["instance_id"] : instance["instance_allocate"]  for instance in request_workspace_info["allocate_instance_list"]}
    # instance ===========================================================
    instance_list = []
    for item in db_workspace.get_instance_list():
        used = allocate_inatance_dict.get(item["id"], 0) #item["instance_allocate"]
        if request_workspace_info.get("workspace_id",None):
            old_workspace_instance_allocate = db_workspace.get_workspace_allocate_instance(workspace_id=request_workspace_info["workspace_id"], instance_id=item["id"])
            old_workspace_instance_allocate = old_workspace_instance_allocate["instance_allocate"] if old_workspace_instance_allocate is not None else 0
            if old_workspace_instance_allocate - used > 0:
                item["instance_allocate"] -= old_workspace_instance_allocate - used
            else:
                item["instance_allocate"] += used - old_workspace_instance_allocate
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
    
    storage_info = json.loads(get_redis_client().get(STORAGE_LIST_RESOURCE))
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
        workspace_quota = json.loads(get_redis_client().hgetall(WORKSPACE_RESOURCE_QUOTA).get(str(workspace_id)))
        res = db_workspace.get_workspace_resource(workspace_id=workspace_id)
        workspace_instances = db_workspace.get_workspace_instance_list(workspace_id=workspace_id)
        min_cpu = min(instance["cpu_allocate"] for instance in workspace_instances)
        min_ram = min(instance["ram_allocate"] for instance in workspace_instances)
       
        res["cpu_max_limit"] = min_cpu
        res["ram_max_limit"] = min_ram
        return res
    except Exception as e:
        traceback.print_exc()
        return None
     
def get_project_list(workspace_id : int): # 인스턴스가 할당된 
    project_list = db_project.get_project_list_by_instance_not_null(workspace_id=workspace_id)
    res = [{"item_type" : TYPE.PROJECT_TYPE, "item_id" : p["id"], "name" : p["name"], "job_cpu_limit" : p["job_cpu_limit"], \
        "job_ram_limit" : p["job_ram_limit"], "tool_cpu_limit" : p["tool_cpu_limit"], "tool_ram_limit" : p["tool_ram_limit"], \
            "hps_cpu_limit" : p["hps_cpu_limit"], "hps_ram_limit" : p["hps_ram_limit"], \
            "max_cpu" : p["cpu_allocate"], "max_ram" : p["ram_allocate"]} for p in project_list]
    return res

def get_deployment_list(workspace_id : int): # 인스턴스가 할당된
    deployment_list = db_deployment.get_deployment_list_by_instance_not_null(workspace_id=workspace_id)
    res = [{"item_type" : TYPE.DEPLOYMENT_TYPE, "item_id" : d["id"], "name" : d["name"], "deployment_cpu_limit" : d["deployment_cpu_limit"], \
        "deployment_ram_limit" : d["deployment_ram_limit"], "max_cpu" : d["cpu_allocate"], "max_ram" : d["ram_allocate"]} for d in deployment_list]
    return res

def get_prepro_list(workspace_id : int):
    prepro_list = db_prepro.get_preprocessing_list_by_instance_not_null(workspace_id=workspace_id)
    res = [{"item_type" : TYPE.PREPROCESSING_TYPE, "item_id" : p["id"], "name" : p["name"], "job_cpu_limit" : p["job_cpu_limit"], \
        "job_ram_limit" : p["job_ram_limit"], "tool_cpu_limit" : p["tool_cpu_limit"], "tool_ram_limit" : p["tool_ram_limit"], \
            "max_cpu" : p["cpu_allocate"], "max_ram" : p["ram_allocate"]} for p in prepro_list]
    return res


def get_workspace_item_list(workspace_id : int):
    project_list = get_project_list(workspace_id=workspace_id)
    deployment_list = get_deployment_list(workspace_id=workspace_id)
    preprocessing_list = get_prepro_list(workspace_id=workspace_id)
    item_list = project_list + preprocessing_list + deployment_list
    return item_list

def update_workspace_item_resource(workspace_id : int, item_type : str, item_id : int, job_cpu_limit : float = None, job_ram_limit : float = None, 
                                   tool_cpu_limit : float = None, tool_ram_limit : float = None, deployment_cpu_limit : float = None,
                                   deployment_ram_limit : float = None, hps_cpu_limit : float = None, hps_ram_limit : float = None):
    workspace_info = db_workspace.get_workspace(workspace_id=workspace_id)
    if workspace_info is None:
        return Exception("not exist workspace")
    workspace_pods = json.loads(get_redis_client().hget(WORKSPACE_PODS_STATUS, workspace_id))
    
    
    if item_type == TYPE.PROJECT_TYPE:
        if workspace_pods.get(TYPE.PROJECT_TYPE, None) and workspace_pods[TYPE.PROJECT_TYPE].get(str(item_id), None):
            raise Exception("실행 중인 학습 & 배포 종료 후에 변경하세요")
            
        db_project.update_project_resource(project_id=item_id, job_cpu_limit=job_cpu_limit, job_ram_limit=job_ram_limit, tool_cpu_limit=tool_cpu_limit, tool_ram_limit=tool_ram_limit,
                                           hps_cpu_limit=hps_cpu_limit, hps_ram_limit=hps_ram_limit)
    elif item_type == TYPE.DEPLOYMENT_TYPE:
        if workspace_pods.get(TYPE.DEPLOYMENT_TYPE, None) and workspace_pods[TYPE.TYPE.DEPLOYMENT_TYPE].get(str(item_id), None):
            raise Exception("실행 중인 학습 & 배포 종료 후에 변경하세요")
        db_deployment.update_deployment(deployment_id=item_id, deployment_cpu_limit=deployment_cpu_limit, deployment_ram_limit=deployment_ram_limit)
    
    return True

def update_workspace_resource_reset(workspace_id : int):
    min_instance_resource = db_workspace.get_workspace_instance_min(workspace_id=workspace_id) 
    min_cpu_allocate = min_instance_resource.get("min_cpu_allocate", 0)
    min_ram_allocate = min_instance_resource.get("min_ram_allocate", 0)
    db_project.update_all_project_resource(workspace_id=workspace_id, job_cpu_limit=min_cpu_allocate, job_ram_limit=min_ram_allocate, tool_cpu_limit=min_cpu_allocate, tool_ram_limit=min_ram_allocate,
                                           hps_cpu_limit=min_cpu_allocate, hps_ram_limit=min_ram_allocate)
    db_deployment.update_all_deployment_resource(workspace_id=workspace_id, deployment_cpu_limit=min_cpu_allocate, deployment_ram_limit=min_ram_allocate)
    return True


def update_workspace_resource(workspace_id, tool_cpu_limit, tool_ram_limit, job_cpu_limit, job_ram_limit,
            hps_cpu_limit, hps_ram_limit, deployment_cpu_limit, deployment_ram_limit):
    try:
        workspace_pod_list = json.loads(get_redis_client().hget(WORKSPACE_PODS_STATUS, workspace_id))
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