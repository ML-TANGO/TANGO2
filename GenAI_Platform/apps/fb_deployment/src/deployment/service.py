# from typing_extensions import runtime
import traceback, string, os, random, json, subprocess, time, asyncio, logging
from requests.exceptions import HTTPError, ConnectionError, Timeout
from huggingface_hub import login, model_info, HfApi

from utils.resource import response
from utils.kube import  PodName
from utils.TYPE import *
from utils.settings import *
from utils.PATH import *
from utils import TYPE, TYPE_BUILT_IN
import utils.common as common
from datetime import datetime #, date, timedelta
from utils.exception.exceptions import *
from utils.exception.exceptions_deployment import *
from utils.access_check import check_deployment_access_level
from utils.log import logging_history, LogParam
from deployment import service_monitoring_new as svc_mon

from fastapi.responses import StreamingResponse

from utils.common import byte_to_gigabyte

from utils.redis import get_redis_client
from utils.redis_key import WORKSPACE_PODS_STATUS, DEPLOYMENT_WORKER_RESOURCE
from utils.msa_db import db_user, db_deployment, db_workspace, db_instance, db_project, db_built_in_model


from deployment import dto
from utils import topic_key

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

from utils.kube import PodName
from utils.crypt import front_cipher
from utils.connection_manager import connection_manager

# Redis client를 함수로 변경하여 연결 실패 시 안전하게 처리
def get_safe_redis_client():
    try:
        return connection_manager.get_redis_client_sync()
    except Exception as e:
        logger.warning(f"Redis 연결 실패: {e}")
        return None

redis_client = get_safe_redis_client()

class KubeNamespace:
    def __init__(self, workspace_name=None, workspace_id=None):
        self.workspace_name = workspace_name
        self.workspace_id = workspace_id

        if workspace_name is not None:
            self.namespace = str(JF_SYSTEM_NAMESPACE) + "-" + str(self.workspace_name)
        else:
            workspace_name = db_workspace.get_workspace(workspace_id=workspace_id)["name"]
            self.namespace = str(JF_SYSTEM_NAMESPACE) + "-" + str(workspace_name)

class DeploymentKafka:
    def __init__(self):
        self.conf = {
            'bootstrap.servers' : f"{JF_KAFKA_DNS}"
        }
    
    def acked(self, err, msg):
        if err is not None:
            print("Failed to deliver message: %s: %s" % (str(msg), str(err)))
        else:
            print("Message produced: %s" % (str(msg)))


# call_count_chart  ====================================================================================
"""
call_count_chart 앱 내부 메모리에 저장
배포 목록 리스트에서 불러오는게 너무 느려 따로 메모리 사용
"""
import threading
DEPLOYMENT_CALL_CHART = dict() 
def call_count_chart_thread():
    global DEPLOYMENT_CALL_CHART
    while True:
        try:
            time.sleep(1)
            deployment_info = db_deployment.get_deployment_list()
            for item in deployment_info:
                if item.get("llm"):
                    continue
                deployment_id = item.get("id")
                call_count_chart = svc_mon.get_deployment_call_count_per_hour_chart(deployment_id=item.get('id'))
                # print("***********call_count_chart******", item["id"])
                # print(call_count_chart)
                DEPLOYMENT_CALL_CHART[deployment_id] = call_count_chart
        except:
            pass
thread = threading.Thread(target=call_count_chart_thread, args=())
thread.start()


# 배포 ====================================================================================
async def get_deployment_list(workspace_id, headers_user):
    global DEPLOYMENT_CALL_CHART
    """배포 첫화면 - 배포 전체 리스트"""
    try:
        # user
        user_info = db_user.get_user_id(user_name=headers_user)
        deployment_list = db_deployment.get_deployment_list_in_workspace(workspace_id=workspace_id)

        # workspace
        workspace_users = db_deployment.get_workspace_users(workspace_id=workspace_id)
        workspace_users_id = list(map(lambda x: x['id'], workspace_users))

        # bookmark
        user_deployment_bookmark_list = [deployment_bookmark["deployment_id"]
            for deployment_bookmark in db_deployment.get_user_deployment_bookmark_list(user_id=user_info["id"])]
        
        # redis deployment
        redis_pod_list = dict()
        try:
            redis_client = get_safe_redis_client()
            if redis_client:
                tmp_workspace_pod_status = redis_client.hget(WORKSPACE_PODS_STATUS, workspace_id)
                if tmp_workspace_pod_status is not None:
                    redis_pod_list = json.loads(tmp_workspace_pod_status)
        except Exception as e:
            logger.warning(f"Redis 연결 실패, 기본 상태로 진행: {e}")
            redis_pod_list = dict()
        
        deployment_redis_list = redis_pod_list.get('deployment', dict())
        
        # db workspace deployment list
        db_ws_dp_worker_list = db_deployment.get_deployment_worker_list(workspace_id=workspace_id, running=True) 
        db_workers_grouped_deployment_id = {
            deployment_id: [d for d in db_ws_dp_worker_list if d['deployment_id'] == deployment_id] 
                    for deployment_id in set(d['deployment_id'] for d in db_ws_dp_worker_list)
        }

        res = []
        for item in deployment_list: # DB
            # ======================================
            # LLM 제거: LLM은 deployment로 배포를 생성하여 작업함. 배포 화면에서 LLM이 안보이도록 넘김
            if item.get("llm") and item.get("llm") > 0: continue
            if item.get("id") is None: continue
            
            # users ==========================================================================================
            # user list (access == 0 private, 1 public)
            users = db_deployment.get_user_list_deployment(deployment_id=item["id"]) if item["access"]==0 else []
            permission_level = check_deployment_access_level(user_id=user_info["id"], deployment_id=item["id"], owner_id=item["user_id"],
                                          access=item["access"], workspace_users=workspace_users_id)

            # status ==========================================================================================
            deployment_worker_redis_list = deployment_redis_list.get(str(item["id"]))
            deployment_worker_db_list = db_workers_grouped_deployment_id.get(item["id"])

            status = {"status" : "stop", "worker" : {"count" : 0}}
            # worker count: 마커에서 사용, 없으면 front 에러
            status_status = "stop"
            if deployment_worker_redis_list:
                for _, val in deployment_worker_redis_list.items():
                    tmp_status=val.get("status")
                    if tmp_status == KUBE_POD_STATUS_RUNNING:
                        status_status = KUBE_POD_STATUS_RUNNING
                    elif status_status != KUBE_POD_STATUS_RUNNING and tmp_status == KUBE_POD_STATUS_ERROR:
                        status_status = KUBE_POD_STATUS_ERROR
                    elif status_status not in [KUBE_POD_STATUS_RUNNING, KUBE_POD_STATUS_ERROR] and tmp_status == KUBE_POD_STATUS_INSTALLING:
                        status_status = KUBE_POD_STATUS_INSTALLING
                    else:
                        status_status = KUBE_POD_STATUS_PENDING
                status["status"] = status_status
                status["worker"]["count"] = len(deployment_worker_redis_list)
            elif deployment_worker_db_list:
                status["status"] = KUBE_POD_STATUS_INSTALLING

            # model==========================================================================================
            model_type = item.get("model_type")
            project_id = item.get('project_id')
            training_type = item.get("training_type")
            training_id = item.get('training_id')
            huggingface_model_id = item.get("huggingface_model_id")

            # result ==========================================================================================
            data = {
                "access" : item["access"], # 0 private, 1 public
                "id" : item["id"],
                "deployment_name" : item["name"],
                "description" : item["description"],
                "user_name" : item["user_name"],
                "bookmark" : 1 if item["id"] in user_deployment_bookmark_list else 0,
                "users": users, # public은 x, private
                "permission_level": permission_level, # front에서 활성화, 비활성화
                "deployment_status": status,
                "instance" : {
                    "type" : item.get("instance_type"),
                    "name" : item.get("instance_name"),
                    "allocate" : item.get("instance_allocate"),
                    "gpu" : {
                        "name" : item.get("resource_name") if item.get("instance_type") == TYPE.INSTANCE_TYPE_GPU else None,
                        "count" : item.get("gpu_allocate"),
                    },
                    "cpu" : item.get("cpu_allocate"),
                    "ram" : item.get("ram_allocate"),
                    "npu" : {
                        "name" : item.get("resource_name") if item.get("instance_type") == TYPE.INSTANCE_TYPE_NPU else None,
                        "count" : item.get("npu_allocate", 0)
                    }
                },
                "model_type" : model_type,
                "built_in_model_name" : huggingface_model_id, # marker에서 사용 : TODO 마커에서 어떤 모델 사용했는지 보여주려고 쓰는데, 어떤 값을 보여줄지는 추후 논의해서 결정
                "create_datetime" : item.get("create_datetime"),
                # Running 일때만 보여줌 ============================
                "api_address" : None,
                "call_count_chart" : [],
            }
            
            # running일때만 보여주는 값
            if status["status"] in KUBER_RUNNING_STATUS:
                # data["call_count_chart"] = svc_mon.get_deployment_call_count_per_hour_chart(deployment_id=item["id"])
                data["call_count_chart"] = DEPLOYMENT_CALL_CHART.get(item.get("id"), [])
                data["api_address"] = get_deployment_full_api_address(base_api=item.get("api_path")) # marker
            res.append(data)
        return res
    except Exception as e:
        traceback.print_exc()
        raise Exception(str(e))

def get_deployment(deployment_id, headers_user):
    """
    배포 첫 화면 아이템 수정시 Get 정보
    """
    try:
        user_info = db_user.get_user_id(user_name=headers_user)
        deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
        print(deployment_info)

        # workspace
        workspace_users = db_deployment.get_workspace_users(workspace_id=deployment_info["workspace_id"])
        workspace_users_id = list(map(lambda x: x['id'], workspace_users))
        
        if deployment_info["access"]==1:
            users=[]
        else:
            users = db_deployment.get_user_list_deployment(deployment_id=deployment_id)

        permission_level = check_deployment_access_level(user_id=user_info["id"], deployment_id=deployment_info["id"], owner_id=deployment_info["user_id"],
                                          access=deployment_info["access"], workspace_users=workspace_users_id)

        result = {
            "workspace_id": deployment_info["workspace_id"],
            "workspace_name": deployment_info["workspace_name"],
            "deployment_name": deployment_info["name"],
            "description": deployment_info["description"],

            # 자원요청
            "instance_type": deployment_info["instance_type"],
            "instance" : {
                "id" : deployment_info["instance_id"],
                "name" : deployment_info["instance_name"],
                "total" : deployment_info["instance_total"],
                "instance_allocate" :  deployment_info["instance_allocate"],
                "cpu_allocate" :  deployment_info["instance_allocate"],
                "ram_allocate" :  deployment_info["instance_allocate"],
                "gpu_allocate" :  deployment_info["instance_allocate"],
            },

            # 접근권한, 소유자
            "access": deployment_info["access"],
            "user_id": deployment_info["user_id"],
            "users":  users ,
            "permission_level": permission_level, # 접근권한 설정 활성화, 비활성화
            
            # "options" : get_deployment_options(workspace_id=deployment_info["workspace_id"], deployment_id=deployment_id)s

            # 모델타입
            "model_type": deployment_info.get("model_type"),
            "project_name" : deployment_info.get('project_name'),
            "project_id" : deployment_info.get('project_id'),
            "training_name" : deployment_info.get('training_name'),
            "training_id" : deployment_info.get('training_id'),
            "training_type" : deployment_info.get('training_type'),

            # 배포 수정시 필요한 값 - 새모델 불러오기
            "model_category" : deployment_info.get("model_category"),
            "model_name" : deployment_info.get("built_in_model_name"),
            "is_new_model" : bool(deployment_info.get("is_new_model")),
        }
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="deployment get error")
    return response(status=1, result=result)

def get_deployment_admin_list():
    try:
        deployment_list = db_deployment.get_deployment_list()
        deployment_user_list = db_deployment.get_user_list_deployment()
        deployment_user_list_dict = {
            deployment_id: [d for d in deployment_user_list if d['deployment_id'] == deployment_id]
            for deployment_id in set(d['deployment_id'] for d in deployment_user_list)
        }
        
        # db workspace deployment list
        db_dp_worker_list = db_deployment.get_deployment_worker_list(running=True)
        db_workers_grouped_deployment_id = {
                deployment_id: [d for d in db_dp_worker_list if d['deployment_id'] == deployment_id] 
                        for deployment_id in set(d['deployment_id'] for d in db_dp_worker_list)
        }
        
        result = []
        for deployment_info in deployment_list:
            # LLM 제거
            if deployment_info.get("llm") and deployment_info.get("llm") > 0: continue

            # redis deployment
            redis_pod_list = dict()
            deployment_redis_list = dict()
            try:
                redis_client = get_safe_redis_client()
                if redis_client:
                    redis_pod_list_raw = redis_client.hget(WORKSPACE_PODS_STATUS, deployment_info.get("workspace_id"))
                    if redis_pod_list_raw:
                        redis_pod_list = json.loads(redis_pod_list_raw)
                        deployment_redis_list = redis_pod_list.get('deployment', dict())
            except Exception as e:
                logger.warning(f"Redis 연결 실패, 기본 상태로 진행: {e}")
                redis_pod_list = dict()
                deployment_redis_list = dict()
            
            deployment_worker_redis_list = deployment_redis_list.get(str(deployment_info["id"]))
            deployment_worker_db_list = db_workers_grouped_deployment_id.get(deployment_info["id"])
            # =================================================================================================================
            # worker, instance
            # default format
            running_worker_list = []
            deployment_status = {
                "status": "stop",
                "worker": {
                    "count": 0,
                    "status": {"running": 0,"installing": 0,"error": 0,"pending": 0},
                    "resource_usage": {"gpu": 0, "cpu": 0}, "configurations": []}
            }
            deployment_instance =  {
                "instance_info" : {
                        "allocated" : True if deployment_info.get("instance_type") is not None else False,
                        "name" : deployment_info.get("instance_name"),
                        "type" : deployment_info.get("instance_type"),
                        "instance_allocate" : deployment_info.get("instance_allocate"),
                        "cpu_allocate" : deployment_info.get("cpu_allocate"), 
                        "ram_allocate" : deployment_info.get("ram_allocate"),
                        "gpu_allocate" : deployment_info.get("gpu_allocate"),
                        "gpu_name" : deployment_info.get("gpu_name"),
                    },
                "used_info" :   {"rate" : 0, "cpu" : 0, "ram" : 0, "gpu" : 0,},
                "unused_info" : {"rate" : 100, "cpu" : 0, "ram" : 0, "gpu" : 0,}
            }
            # ------------------------------------------------------------------------------------------------------------
            try:
                deployment_worker_redis_list = deployment_redis_list.get(str(deployment_info["id"]))
                deployment_worker_db_list = db_workers_grouped_deployment_id.get(deployment_info["id"])
                if deployment_worker_db_list and deployment_worker_redis_list:
                # if deployment_worker_db_list: -> if deployment_worker_db_list and deployment_worker_redis_list:
                    for db_worker_info in deployment_worker_db_list:
                        # running_worker_list
                        worker_id = db_worker_info.get("id")
                        status = deployment_worker_redis_list[str(worker_id)]["status"] if str(worker_id) in deployment_worker_redis_list else "stop"
                        running_worker_list.append({
                            # 기본정보
                            "id": db_worker_info.get("id"),
                            "description": db_worker_info.get("description"),
                            "create_datetime": db_worker_info.get("start_datetime"),
                            # 상태
                            "status" : status,
                            "status_reason" : None,
                            # 구성
                            "configurations" : [], # TODO 삭제
                            "configurations_resource" : {
                                "cpu" : db_worker_info["deployment_cpu_limit"],
                                "ram" : db_worker_info["deployment_ram_limit"],                         
                                "gpu" : db_worker_info["gpu_per_worker"],
                            }
                        })
                        # worker insatnce used -----------------------------------------------------------------------------------------------
                        deployment_instance["used_info"]["cpu"] += db_worker_info.get("deployment_cpu_limit", 0)
                        deployment_instance["used_info"]["ram"] += db_worker_info.get("deployment_ram_limit", 0)
                        deployment_instance["used_info"]["gpu"] += db_worker_info.get("gpu_per_worekr", 0)
                        # status.worker.status -----------------------------------------------------------------------------------------------
                        if deployment_worker_redis_list and str(db_worker_info.get("id")) in deployment_worker_redis_list:
                            deployment_status["worker"]["status"][deployment_worker_redis_list.get(str(db_worker_info.get("id"))).get("status")] += 1
                        else:
                            deployment_status["worker"]["status"][KUBE_POD_STATUS_PENDING] += 1 # pending
                        # status.worker.resource_usage -----------------------------------------------------------------------------------------------
                        if db_worker_info.get("instance_type") == INSTANCE_TYPE_GPU:
                            deployment_status["worker"]["resource_usage"]["gpu"] += 1
                        else:
                            deployment_status["worker"]["resource_usage"]["cpu"] += 1

                    # deployment_status -----------------------------------------------------------------------------------------------
                    deployment_status["worker"]["count"] = len(deployment_worker_db_list)
                    deployment_status["status"] = max(deployment_status["worker"]["status"], key=deployment_status["worker"]["status"].get)
                    # deployment instance rate --------------------------------------------------------------------------------------------
                    used_cpu_rate = (deployment_instance["used_info"]["cpu"] / deployment_instance["instance_info"]["cpu_allocate"]) * 100 \
                        if deployment_instance["instance_info"]["cpu_allocate"] and deployment_instance["instance_info"]["cpu_allocate"] != 0 else 0
                    used_ram_rate = (deployment_instance["used_info"]["ram"] / deployment_instance["instance_info"]["ram_allocate"]) * 100 \
                        if deployment_instance["instance_info"]["ram_allocate"] and deployment_instance["instance_info"]["ram_allocate"] != 0 else 0
                    used_gpu_rate = (deployment_instance["used_info"]["gpu"] / deployment_instance["instance_info"]["gpu_allocate"]) * 100 \
                        if deployment_instance["instance_info"]["gpu_allocate"] and deployment_instance["instance_info"]["gpu_allocate"] != 0 else 0

                    instance_resouce_count = 3 if deployment_instance["instance_info"]["type"] == TYPE.RESOURCE_TYPE_GPU else 2
                    deployment_resource_used_rate = (used_cpu_rate + used_ram_rate + used_gpu_rate) / instance_resouce_count
                    deployment_instance['used_info']['rate'] = format(float(deployment_resource_used_rate), ".3f")
                    deployment_instance['unused_info']['rate'] = format(100 - deployment_resource_used_rate, ".3f")
                    deployment_instance["unused_info"]["cpu"] = deployment_instance["instance_info"]["cpu_allocate"] - deployment_instance["used_info"]["cpu"]
                    deployment_instance["unused_info"]["ram"] = deployment_instance["instance_info"]["ram_allocate"] - deployment_instance["used_info"]["ram"]
                    deployment_instance["unused_info"]["gpu"] = deployment_instance["instance_info"]["gpu_allocate"] - deployment_instance["used_info"]["gpu"]
            except:
                traceback.print_exc()
                pass
            # =================================================================================================================
            try:
                # operation_time = svc_mon.get_deployment_total_running_time_and_worker_start_time(deployment_id=deployment_info["id"]).get("total_running_time")
                api_address = get_deployment_full_api_address(base_api=deployment_info["api_path"])
            except:
                # operation_time = 0
                api_address = None
            # =================================================================================================================
            result.append({
                # 기본정보
                "id": deployment_info["id"],
                "workspace_name": deployment_info["workspace_name"], # admin 쪽에서 쓰임
                "deployment_name":deployment_info["name"], #deployment_name,
                "user_name": deployment_info["user_name"], #user_name,
                # 상태
                "deployment_status": deployment_status, # 없으면 터짐, 큰틀의 상태, 워커, 자원 쪽 정보로 사용
                "create_datetime": deployment_info["create_datetime"],
                "operation_time" : 0,
                "log_size": 0, # get_log_size(workspace_name=deployment_info["workspace_name"], deployment_name=deployment_info["name"], deployment_worker_id_list=[i.get("id") for i in running_worker_list]),                     
                # row 열었을때
                "description": deployment_info["description"],
                "users": deployment_user_list_dict.get(deployment_info["id"]), # admin 쪽에서 쓰임
                "access": deployment_info["access"],
                "api_address": api_address,
                # 인스턴스
                "instance" : deployment_instance,
                # 워커리스트
                "deployment_worker_list": running_worker_list, #deployment_status.get_running_worker_list(),
                # TODO 삭제
            })
        return response(status=1, result=result)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, result=[], message="Deployment List get Error : {}".format(e))

def create_deployment(workspace_id, deployment_name, description,  instance_id, instance_allocate, access, owner_id, users_id,
                    model_type, is_new_model_type, project_id, training_id, training_type,
                    model_category, huggingface_model_id, huggingface_model_token): # instance_type,
    """
    model_type: str = Field(default="custom", description="custom or huggingface or built-in")
    training_type: Optional[str] = Field(default=None, description="학습에서 불러오기 - job or hps")

    TODO!!!
    huggingface_model_info - 현재 허깅페이스 모델은 빌트인 모델에 있는 모델만 사용 가능한 범위에서 기획됨, 추후 모든 모델에 대응 해야한다면 워커세팅, 데이터폼부분 수정필요
    -> set_deployment_worker_and_data_form_by_built_in_and_hf
    """
    deployment_id = None
    try:
        deployment_name_and_user_info_validation_check(
            deployment_name=deployment_name, workspace_id=workspace_id, owner_id=owner_id, users_id=users_id)

        workspace_name = db_workspace.get_workspace(workspace_id=workspace_id)["name"]

        # API PATH 생성
        default_api_path = PodName(workspace_name=workspace_name, item_name=deployment_name, item_type=DEPLOYMENT_TYPE).get_base_pod_name()
        
        # resource TODO resource update 
        resources_info = db_workspace.get_workspace_resource(workspace_id=workspace_id)
        deployment_cpu_limit = resources_info.get('deployment_cpu_limit', 0)
        deployment_ram_limit = resources_info.get('deployment_ram_limit', 0)

        instance_info = db_instance.get_instance(instance_id=instance_id)
        instance_type = instance_info.get("instance_type")

        # 새모델 + 빌트인
        model_info = None
        built_in_model_id = None

        if is_new_model_type:
            if model_type == TYPE.DEPLOYMENT_TYPE_JI:
                model_info = db_built_in_model.get_built_in_model_by_huggingface_model_id_sync(huggingface_model_id=huggingface_model_id)
                built_in_model_id = model_info.get("id")
                huggingface_model_token = model_info.get("token")
            elif model_type == TYPE.DEPLOYMENT_TYPE_HUGGINGFACE:
                # TODO 현재 무조건 화상 모델이 들어가게 되어있음 !!! 추후 수정해야됨!!!
                model_info = db_built_in_model.get_built_in_model_sync(category="의료 (Healthcare/Medical AI Solutions)", name="화상 심도 탐지")
                built_in_model_id = model_info.get("id")
                huggingface_model_token = model_info.get("token")
                huggingface_model_id = model_info.get("huggingface_model_id") # 무조건 화상모델만 되도록 현재 하드코딩

        # Insert DB - deployment
        insert_deployment_result = db_deployment.insert_deployment(
            workspace_id=workspace_id, user_id=owner_id,
            name=deployment_name, description=description, access=access,
            instance_type=instance_type, instance_id=instance_id, instance_allocate=instance_allocate, api_path=default_api_path,
            deployment_cpu_limit=deployment_cpu_limit, deployment_ram_limit=deployment_ram_limit, 
            model_type=model_type, project_id=project_id, training_id=training_id, training_type=training_type,
            huggingface_model_id=huggingface_model_id, huggingface_model_token=huggingface_model_token, 
            built_in_model_id=built_in_model_id, model_category=model_category, is_new_model=int(is_new_model_type),
        )

        # 배포 ID 받기
        if not insert_deployment_result["result"]:
            print("Create Deployment DB Insert Error: {}".format(insert_deployment_result["message"]))
            raise CreateDeploymentDBInsertError
        deployment_id = insert_deployment_result["id"]

        # Insert DB - user_deployment
        users_id.append(owner_id)
        deployments_id = [deployment_id]*len(users_id)
        insert_user_deployment_result, message = db_deployment.insert_user_deployment_list(
            deployments_id=deployments_id, users_id=users_id)
        if not insert_user_deployment_result:
            raise DeploymentUserDBInsertError
        
        # built-in, huggingface & 학습에서 불러오기
        if model_type in [TYPE.DEPLOYMENT_TYPE_JI, TYPE.DEPLOYMENT_TYPE_HUGGINGFACE]:
            gpu_count = 1  if instance_type == TYPE.INSTANCE_TYPE_GPU else 0
            set_deployment_worker_and_data_form_by_built_in_and_hf(
                deployment_id=deployment_id, gpu_count=gpu_count, is_new_model_type=is_new_model_type,
                project_id=project_id, training_id=training_id, training_type=training_type, model_info=model_info,
            )

        # log
        logging_history(task=LogParam.Task.DEPLOYMENT, action=LogParam.Action.CREATE,
                        user_id=owner_id, workspace_name=workspace_name, task_name=deployment_name)

        return response(status=1, message="Created Deployment")
    except CustomErrorList as ce:
        traceback.print_exc()
        raise ce
    except Exception as e:
        traceback.print_exc()
        if deployment_id is not None:
            db_deployment.delete_deployments(deployment_ids=[deployment_id])
        raise e

# builtin, huggingface =====================================================================================================

def set_deployment_worker_and_data_form_by_built_in_and_hf(deployment_id, gpu_count, is_new_model_type,
                                                          project_id=None, training_id=None, training_type=None, model_info=None):
    try:
        if is_new_model_type:
            # 새모델
            image_real_name = model_info.get("image")
            image_info = db_built_in_model.get_built_in_model_image_info_by_real_name_sync(real_name=image_real_name)
            docker_image_id = image_info.get("id")
            built_in_model_id = model_info.get("id")
            arguments=f" --checkpoint=/model/swin_4_256.pth "
        else:
            # 학습에서 불러오기
            if training_type == "hps":
                training_info = db_project.get_hps(hps_id=training_id)
                docker_image_id = training_info.get("image_id")
                built_in_model_id = training_info.get("built_in_model_id")
            elif training_type == "job":
                training_info = db_project.get_training(training_id=training_id)
                docker_image_id = training_info.get("image_id")
                built_in_model_id = training_info.get("built_in_model_id")
            elif training_type == "pipeline": # pipeline은 training_id를 안받음, job이 생성 안된 상태에서 파이프라인 세팅하고 실행
                # job, hps 빌트인 사용시 job, hps도 이미지 선택을 안한다면 이 로직을 사용해도 될듯, huggingface는 job, hps에서 이미지 선택하면 사용 못함
                training_info = db_project.get_project(project_id=project_id)
                docker_image_id = training_info.get("built_in_model_image_id")
                built_in_model_id = training_info.get("built_in_model_id")
            # --------------------------------------------------------------
            arguments=f" --checkpoint=/built_in_checkpoint/checkpoint.pth "
        
        command = {"binary" : "python3", "script" : "/model/deploy.py", "arguments" : arguments}

        # 1. worker
        update_deployment_worker_setting(deployment_id, gpu_count=gpu_count, docker_image_id=docker_image_id, command=command, environments=[], project_id=project_id) # command=None, environments=None,

        # 2. dataform 
        result = db_deployment.copy_built_in_data_form(deployment_id, built_in_model_id)
        if not result:
            raise Exception("copy data form error")

    except Exception as e:
        traceback.print_exc()
        raise e

# =====================================================================================================

def update_deployment(deployment_id, description, access, owner_id, users_id, instance_id, instance_allocate=None):
    try:
        # Update Deployment
        origin_deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
        instance_info = db_instance.get_instance(instance_id=instance_id)
        instance_type = instance_info.get("instance_type")
        
        # TODO KLOD (2024-09-30: resource update)
        origin_instance_id = origin_deployment_info.get("instance_id")
        deployment_cpu_limit = origin_deployment_info.get("deployment_cpu_limit")
        deployment_ram_limit = origin_deployment_info.get("deployment_ram_limit")
        if origin_instance_id != instance_id:
            resources_info = db_workspace.get_workspace_resource(workspace_id=origin_deployment_info.get("workspace_id"))
            deployment_cpu_limit = resources_info.get('deployment_cpu_limit', 0)
            deployment_ram_limit = resources_info.get('deployment_ram_limit', 0)
        # + db update도 추가하기

        # builtin, huggingface --------------------------------------------------------------------------------------------------------
        model_info = origin_deployment_info.get("model")
        gpu_count = 0
        if model_info:
            model_info = json.loads(model_info)
            model_type = model_info.get("model_type")
            if model_type in [TYPE.DEPLOYMENT_TYPE_JI, TYPE.DEPLOYMENT_TYPE_HUGGINGFACE] and instance_type == TYPE.INSTANCE_TYPE_GPU:
                gpu_count = 1
        # --------------------------------------------------------------------------------------------------------
        
        update_deployment_result, message = db_deployment.update_deployment(
            deployment_id=deployment_id, description=description,
            instance_type=instance_type, instance_id=instance_id, instance_allocate=instance_allocate, access=access, user_id=owner_id,
            gpu_per_worker=gpu_count, deployment_cpu_limit=deployment_cpu_limit, deployment_ram_limit=deployment_ram_limit) # instance 수정시 gpu per worker 초기화
        
        if not update_deployment_result:
            print("Update Deployment Error : {}".format(message))
            raise UpdateDeploymentDBInsertError
        
        # user_deployment update --------------------------------------------------------------------------------------------------------
        org_users_id = [user['user_id'] for user in db_deployment.get_user_list_deployment(deployment_id)]
        users_id.append(owner_id)
        del_user = list(set(org_users_id) - set(users_id))
        add_user = list(set(users_id) - set(org_users_id))

        ### Insert User deployment
        insert_result, message = db_deployment.insert_user_deployment_list(deployments_id=[deployment_id]*len(add_user), users_id=add_user)
        if not insert_result:
            print("insert user deployment error : {}".format(str(message)))
            raise DeploymentUserDBInsertError
        
        ### Delete User deployment
        delete_result, message = db_deployment.delete_user_deployment(deployments_id=[deployment_id]*len(del_user), users_id=del_user)
        if not delete_result:
            print("delete user deployment error : {}".format(str(message)))
            raise DeploymentDBDeleteUserError

        # log --------------------------------------------------------------------------------------------------------
        deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
        logging_history(task=LogParam.Task.DEPLOYMENT, action=LogParam.Action.UPDATE,
                        user_id=owner_id, workspace_name=deployment_info.get("workspace_name"), task_name=deployment_info.get("name"))

        return response(status=1, message="Updated Deployment")
    except CustomErrorList as ce:
        traceback.print_exc()
        raise ce
    except Exception as e:
        raise e

def delete_deployment(deployment_ids, headers_user):
    """
    Description:
        서빙 첫 페이지에서 삭제하는 경우
        사용자 - 단일 삭제, 어드민 - 복수 삭제
    MSA 변경:
        lock 제거, 배포 pod 상태확인후 삭제 -> helm 삭제
        템플릿 제거, 로깅 제거
    """
    try:
        deployment_list = db_deployment.get_deployment_list(deployment_id_list=deployment_ids)
        delete_deployment_list = []
        
        for deployment in deployment_list:
            workspace_name = deployment["workspace_name"]
            workspace_id = deployment["workspace_id"]
            deployment_id = deployment["id"]
            owner_name = deployment["user_name"]
            delete_deployment_list.append(deployment.get("name"))
            
            # 소유자 or admin 확인
            # if owner_name != headers_user and "admin" != headers_user:
            #     raise Exception("Not Deployment owner")
            #     continue
            
            # 배포 pod 삭제: status 확인 안하고 바로 helm uninstall 하는 방식으로 변경 
            try:
                uninstall_all_deployment(workspace_id=workspace_id, deployment_id=deployment_id)
            except Exception as e:
                traceback.print_exc()
                pass
            
            # 내부 메모리 call_count_chart 삭제
            try:
                del DEPLOYMENT_CALL_CHART[deployment_id]
            except:
                pass
            
            # admin_client = AdminClient({
            # 'bootstrap.servers' : JF_KAFKA_DNS
            # })
            # admin_client.delete_topics([topic_key.DEPLOYMENT_TOPIC.format(deployment_id)], operation_timeout=1)
            # # TODO 배포 폴더 삭제
            # delete_folder_result, for_message = delete_deployment_folder(workspace_name=workspace_name, deployment_name=deployment["name"])
            # if delete_folder_result ==False:
            #     print("Delete deployment folder fail: {}".format(for_message)) 
            #     raise DeleteDeploymentFolderError
            
        # 배포 DB 삭제
        delete_result = db_deployment.delete_deployments(deployment_ids=deployment_ids)

        if not delete_result: 
            raise DeleteDeploymentDBError
        
        
        logging_history(task=LogParam.Task.DEPLOYMENT, action=LogParam.Action.DELETE, 
                        user_name=owner_name, workspace_id=workspace_id, task_name=','.join(delete_deployment_list))
        print("배포삭제")
        return None
    except Exception as e:
        traceback.print_exc()
        raise Exception(str(e))

# 워커 ====================================================================================
def get_deployment_worker_setting(deployment_id):
    try:
        #TODO checkpoint 설명을 위한 정보 추가 필요.
        #TODO 버그
        # From Job + (예정)  Hps, checkpoint 
        # running_info = get_deployment_running_info(id=deployment_id)
        
        deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
        
        command = deployment_info.get("command")
        if command is not None:
            json_command = json.loads(command)
            command_binary = json_command.get("binary")
            command_run_code = json_command.get("script")
            command_arguments = json_command.get("arguments")
        else:
            command_binary = None
            command_run_code = None
            command_arguments = None
            
        environments = deployment_info.get("environments")
        environments = json.loads(environments) if environments is not None else []

        result = {
            "deployment_name" : deployment_info['name'], # /deployments/deployment_names 대체
            "deployment_description" : deployment_info['description'], 
            "instance_type": deployment_info["instance_type"],

            "gpu_count": deployment_info["gpu_per_worker"], # gpu 사용량
            "gpu_model": deployment_info["gpu_name"], # gpu 모델
            "resource_name": deployment_info["resource_name"], # gpu 모델
            "resource_count": deployment_info["gpu_per_worker"], # gpu 사용량

            "docker_image": deployment_info['image_name'], # 도커이미지
            "command_binary" : command_binary,
            "command_run_code" : command_run_code,
            "command_arguments" : command_arguments,
            "environments" : [str(i.get("name")) + "=" + str(i.get("value")) for i in environments],

            # model type, 학습에서 가져오기만 있음

            # ipo기획 변경 전부터 사용중이었음 / custom
            "model_type": deployment_info.get("model_type"), # custom, built-in, huggingface
            "deployment_type" : deployment_info.get("model_type"),
            "project_id" :  deployment_info.get("project_id"),
            "project_name" : deployment_info.get("project_name"),
            "training_id" : deployment_info.get("training_id"),
            "training_name" : deployment_info.get("training_name"),

            # 새모델 가져오기
            "is_new_model" : bool(deployment_info.get("is_new_model", False)),
            "model_category" : deployment_info.get("model_category"),
            # 새모델 + 빌트인
            "model_name" : deployment_info.get("built_in_model_name"),
            # 새모델 + hf
            "huggingface_model_id" : deployment_info.get("huggingface_model_id")

        }
        return response(status=1, result=result)
    except Exception as e:
        traceback.print_exc()
        return response(status=0)

def update_deployment_worker_setting(deployment_id, command, environments, gpu_count, docker_image_id, project_id=None):
    # gpu_cluster_auto, gpu_auto_cluster_case,
    # access, owner_id, users_id, deployment_type, training_type
    """
    deployment_type : built_in / custom
    training_type : job / hps
    dataform 관련 세팅: 기존 모놀리식 -> create deployment 할때 실행했는데 MSA는 워커에서 세팅하므로 이 함수에서 dataform 세팅함
    """
    try:
        # =========================================================================================================================
        # 배포 data form 작업 먼저함 (여기서 실패하면 deployment, deployment_worker db 다시 수정해야하므로 먼저 설정)
        # update - data form setting (배포 시뮬레이션 data form 설정) -> add_deployment_worker_new 에서 워커 추가할때마다 체크
        ### 현재는 custom 기준 코드만 작성 -> TODO 추후 built_in, job, hps 대응
        ### 빌트인/커스텀 모델의 deployment form list 정보 받기
        
        deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
        # workspace_name = deployment_info.get("workspace_name")
        # project_info = db_deployment.get_project(project_id=project_id)
        # project_name = project_info.get("name")
        # main_storage_name = project_info.get("main_storage_name")
        # run_code = command["script"] if command and command["script"] is not None else None

        # update - deployment worker setting : 여기서 update는 워커 업데이트이므로 gpu 모델이 바뀔수는 없음
        # if gpu_count == 0 or gpu_count == None:
        #     instance_type = INSTANCE_TYPE_CPU
        # else:
        #     instance_type = INSTANCE_TYPE_GPU
            
        # multiple gpu
        gpu_auto_cluster_case = None
        if gpu_count > 1:
            gpu_allocate = deployment_info.get("gpu_allocate")
            a, b = divmod(gpu_allocate, gpu_count)
            if a >= 1 and b != 0:
                raise Exception(f"gpu {gpu_allocate} 배수 입력")
            else:
                gpu_auto_cluster_case = {"gpu_count": gpu_count, "server": 1}

        update_result, message = db_deployment.update_deployment_worker_setting(
            deployment_id=deployment_id, project_id=project_id, command=command, environments=environments,
            gpu_cluster_auto=True, gpu_auto_cluster_case=json.dumps(gpu_auto_cluster_case),
            gpu_per_worker=gpu_count, docker_image_id=docker_image_id)
        if not update_result:
            print("update deployment setting error : {}".format(str(message)))
            raise

        return response(status=1)
    except CustomErrorList as ce:
        traceback.print_exc()
        return response(status=0, message=str(ce))
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))

def get_deployment_form_list_and_input_type_new(run_code=None, workspace_name=None, project_name=None, storage_name=None):
    def load_custom_api_system_info_to_json_new(run_code=None, workspace_name=None, project_name=None, storage_name=None):
        """
        Description : loads custom API system info into json
        Args :
            deployment_id (int) : deployment id 로 정보 추가
            -------------------
            run_code_path (str) : JF_TRAINING_POD_PATH 기준으로 작성되어 있음 - 실제 HOST 경로는 다름 변환 필요
            workspace_name (str) : HOST 경로 재작성용
            training_name (str) : HOST 경로 재작성용
        """
        try:
            # TODO BUILTIN, JOB, HPS
            if run_code is None:
                raise Exception("command를 입력하세요")
            
            # run_code_path = get_project_src_path(storage_name=storage_name, workspace_name=workspace_name, project_name=project_name, run_code=run_code)
            if run_code:
                run_code_src = run_code.replace("/root/project/", "")
                run_code_path = f"/jf-data/{storage_name}/main/{workspace_name}/projects/{project_name}/src/{run_code_src}"
            else:
                run_code_path = f"/jf-data/{storage_name}/main/{workspace_name}/projects/{project_name}/src"
                # TODO 앞에서 막긴함

            print(run_code_path)
            """
            시스템 정보
            아래 스크립트 삭제시 JF deploy 실행이 안됩니다.
            #JF_DEPLOYMENT_INPUT_DATA_INFO_START
            {
                "deployment_input_data_form_list": [
                    {
                        "method": "POST",
                        "location": "file",
                        "api_key": "num_image",
                        "value_type": "image",
                        "category": "image",
                        "category_description": "numberic"
                    }
                ]
            }
            #JF_DEPLOYMENT_INPUT_DATA_INFO_END
            """
            with open(run_code_path, mode="r", encoding="utf8") as f:
                api_txt = f.read()
                if '#JF_DEPLOYMENT_INPUT_DATA_INFO_START' in api_txt:
                    api_str_list = api_txt.split("#JF_DEPLOYMENT_INPUT_DATA_INFO_START")
                    # print("=========\n1: "+str(api_str_list))
                    # print("=========\n1-2: "+str(len(api_str_list)))
                    # print("=========\n1-3: "+str(api_str_list[0]))
                    # print("=========\n2: "+str(api_str_list[1]))
                    # print("=========\n3: "+str(api_str_list[1].split('\n"""')))
                    api_str = api_str_list[1].split("#JF_DEPLOYMENT_INPUT_DATA_INFO_END")[0]
                    try:
                        system_info_json = json.loads(api_str)
                        return system_info_json
                    except:
                        pass
            return None
        except Exception as e:
            traceback.print_exc()
            return None

    try:
        deployment_form_list = []
        
        # deployment_type 제거, built-in, job, hps는 따로 처리(모놀리식)
        deployment_form_list = load_custom_api_system_info_to_json_new(run_code=run_code,
                                                                           workspace_name=workspace_name,
                                                                           project_name=project_name,
                                                                           storage_name=storage_name)
        if deployment_form_list:
            deployment_form_list = deployment_form_list.get("deployment_input_data_form_list")
        
        if deployment_form_list and len(deployment_form_list) > 0:
            input_type = ",".join([ deployement_form["category"] for deployement_form in deployment_form_list])
        else:
            input_type = None
            
        return {
            "deployment_form_list":deployment_form_list,
            "input_type": input_type
        }
    except CustomErrorList as ce:
        traceback.print_exc()
        return None
    except Exception:
        traceback.print_exc()
        return None

def get_deployment_detail_info(deployment_id, headers_user):
    try:
        deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
        deployment_worker_id_list = [ data["id"] for data in db_deployment.get_deployment_worker_list(deployment_id=deployment_id) ]

        tmp_workspace_pod_status = redis_client.hget(WORKSPACE_PODS_STATUS, deployment_info.get("workspace_id"))
        if tmp_workspace_pod_status is None:
            redis_pod_list = dict()
        else:
            redis_pod_list = json.loads(tmp_workspace_pod_status)
        deployment_redis_list = redis_pod_list.get('deployment', dict())
        deployment_worker_redis_list = deployment_redis_list.get(str(deployment_info["id"]))

        result = {
            "basic_info": {
                "name": deployment_info.get("name"),
                "description": deployment_info.get("description"),
                "create_datetime": deployment_info.get("create_datetime"),
                # 모델타입
                "model_info" : {
                    "model_type" : deployment_info.get("model_type"), # custom, built-in, huggingface
                    # 학습에서 선택하기만 있음
                    "project_name" : deployment_info.get("project_name"),
                    "training_name" : deployment_info.get("training_name"), 
                    # 새모델 가져오기
                    "is_new_model" : bool(deployment_info.get("is_new_model", False)),
                    "model_category" : deployment_info.get("model_category"),
                    # 새모델 + 빌트인
                    "model_name" : deployment_info.get("built_in_model_name"),
                    # 새모델 + hf
                    "huggingface_model_id" : deployment_info.get("huggingface_model_id")
                }
                # "model_type": deployment_info.get("model_type"),
                # "model_name" : deployment_info.get("huggingface_model_id") if deployment_info.get("huggingface_type") == "new" else None
            },
            "instance_info" : {
              "instance_name" : deployment_info.get("instance_name"),
              "instance_allocate" : deployment_info.get("instance_allocate"),
              "config_gpu_name" : deployment_info.get("gpu_name"),
              "config_gpu_allocate" : deployment_info.get("gpu_allocate"),
              "config_vcpu" : deployment_info.get("cpu_allocate"),
              "config_ram" : deployment_info.get("ram_allocate"),
            },
            "access_info": {
                "access": deployment_info.get("access"),
                "owner": deployment_info.get("user_name"),
                "user_list": db_deployment.get_user_list_deployment(deployment_id=deployment_id),
                # "permission_level": None
            },
            "usage_status_info":{
                "api_address": get_deployment_full_api_address(base_api=deployment_info.get("api_path")), # From Node
                'worker_count' : len(deployment_worker_redis_list) if deployment_worker_redis_list is not None else 0,
                "total_log_size": get_log_size(workspace_id=deployment_info.get("workspace_id"), workspace_name=deployment_info.get("workspace_name"),
                                               deployment_name=deployment_info.get("name"), deployment_worker_id_list=deployment_worker_id_list)
            }
        }
        return response(status=1, result=result)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Get Deployment detail info error : {}".format(e))

def update_deployment_worker_description(deployment_worker_id, description):
    """배포 -> 워커 -> 미리보기 -> 메모"""
    try:
        update_result, message = db_deployment.update_deployment_worker_description(deployment_worker_id=deployment_worker_id, description=description)
        if update_result:
            return response(status=1, message="Updated")
        else:
            print("Deployment Worker description update error : {}".format(message))
            raise DeploymentWorkerDescriptionDBUpdateError
            # return response(status=0, message="Deployment Worker description update error : {}".format(message))
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Deployment Worker description update error : {}".format(e))

# 워커 실행 ===============================================================================
def add_deployment_worker_new(deployment_id, headers_user):
    deployment_worker_id = None # excetp
    try:
        deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
        deployment_name = deployment_info["name"]
        workspace_id = deployment_info["workspace_id"]
        workspace_name = deployment_info["workspace_name"]
        owner_name = deployment_info["user_name"]
        docker_image_real_name = deployment_info["image_real_name"]
        # --------------------------------------------------------------        
        instance_type = deployment_info["instance_type"]
        instance_id = deployment_info["instance_id"]
        resource_group_id = deployment_info.get("resource_group_id", None)
        resource_name = deployment_info.get("resource_name", None)
        gpu_per_worker = deployment_info.get("gpu_per_worker", 0)
        gpu_cluster_auto = deployment_info.get("gpu_cluster_auto")
        gpu_auto_cluster_case = deployment_info.get("gpu_auto_cluster_case") if gpu_cluster_auto == True else None
        # --------------------------------------------------------------        
        command = deployment_info["command"]
        # --------------------------------------------------------------        
        model_info = deployment_info.get("model")
        model_type = deployment_info.get("model_type")
        project_id = deployment_info.get("project_id")
        project_name = deployment_info.get("project_name")
        training_id = deployment_info.get("training_id")
        training_type = deployment_info.get("training_type")
        huggingface_model_id = deployment_info.get("deployment_huggingface_model_id", None) # TYPE이 huggingface 일때 사용
        huggingface_model_token = deployment_info.get("deployment_huggingface_model_token", None) # TYPE이 huggingface 일때 사용
        is_new_model = bool(deployment_info.get("is_new_model", False))


        # if model_info:
        #     model_info = json.loads(model_info)
        # else:
        #     model_info = {"model_type" : "custom", "project_id" : None, "training_id" : None, "training_type" : None}
        # model_type = model_info.get("model_type")
        # =====================================================================================
        # 파이프라인 동작시 사용, 워커 추가시 가장 최신의 training_id로 업데이트 (job or hps 중에 가장 최신 id로 업데이트한다)
        if training_type == "pipeline":
            training_id = db_deployment.update_deployment_training_id(deployment_id=deployment_id, project_id=project_id)

        # =====================================================================================
        # Setting - worker
        if instance_type is None or instance_id is None:
            raise Exception("워커 설정이 필요합니다.")

        if not is_new_model and project_name is None:
            raise Exception("학습 설정이 필요합니다.")

        if docker_image_real_name is None:
            raise Exception("도커 이미지 설정이 필요합니다.")
        # =====================================================================================
        # DB: deployment Worker Insert
        insert_worker_result = db_deployment.insert_deployment_worker_item(
            deployment_id=deployment_id, project_id=deployment_info["project_id"], image_id=deployment_info["image_id"],
            instance_type=deployment_info["instance_type"], instance_id=deployment_info["instance_id"], gpu_per_worker=deployment_info["gpu_per_worker"],
            command=deployment_info["command"], environments=deployment_info["environments"])
        if not insert_worker_result["result"]:
            print("Create Deployment DB Insert Error: {}".format(insert_worker_result["message"]))
            raise "Deployment worker insert error"
        deployment_worker_id = insert_worker_result["id"]

        # =====================================================================================
        # DB: deployment data form Insert - builtin, huggingface는 배포 카드 생성시 만듬
        if model_type == TYPE.DEPLOYMENT_TYPE_CUSTOM:
            project_info = db_deployment.get_project(project_id=project_id)
            main_storage_name = project_info.get("main_storage_name")
            run_code = json.loads(command).get("script")

            deployment_form_list_json = get_deployment_form_list_and_input_type_new(
                run_code=run_code, workspace_name=workspace_name, project_name=project_name, storage_name=main_storage_name)
            deployment_form_list = deployment_form_list_json["deployment_form_list"]

            db_deployment.delete_deployment_data_form(deployment_id=deployment_id)
            ## custom deployment 에서 api 만 사용하는 경우 deployment form list 가 None 일 수 있다.
            if deployment_form_list: 
                for deployment_form in deployment_form_list:
                    insert_deployment_input_form_result, message = db_deployment.insert_deployment_data_form(
                        deployment_id=deployment_id, location=deployment_form["location"], method=deployment_form["method"], api_key=deployment_form["api_key"], 
                        value_type=deployment_form["value_type"], category=deployment_form["category"], category_description=deployment_form["category_description"])
                    if insert_deployment_input_form_result == False:
                        message = "Insert deployment input form error : {}".format(message)
                        raise Exception(message)
            else:
                # TODO deployment input이 없어서 넘어간 경우가 있을 수 있는데 아예API 코드가 잘못된 경우라면???
                # raise Exception("실행 코드의 API 입력 부분을 확인해보세요")
                pass

        # =====================================================================================
        # Helm 실행 데이터
        # pod_name: pod_base_name은 svc, ingress 이름에 사용 (워커아이디 제외)
        pod_base_name, unique_pod_name, container_name \
            = PodName(workspace_name=workspace_name, item_name=deployment_name, item_type="deployment", sub_flag=deployment_worker_id).get_all()

        # run_code, # TODO builtin, job, hps
        run_code = None
        if command is not None:
            command = json.loads(command)
            run_code = command['binary'] + " " + command['script'] + " " + command['arguments']
        
        # resources
        deployment_cpu_limit = deployment_info.get('deployment_cpu_limit', 0)
        deployment_ram_limit = deployment_info.get('deployment_ram_limit', 0)
        resources = dto.DeploymentResources(limits=dto.DeploymentResourcesDetail(cpu=deployment_cpu_limit, memory=deployment_ram_limit))
        if gpu_auto_cluster_case is not None:
            gpu_auto_cluster_case = json.loads(gpu_auto_cluster_case)
        print("gpu_auto_cluster_case", gpu_auto_cluster_case) # gpu_auto_cluster_case TODO
        resource_type = RESOURCE_TYPE_CPU if gpu_per_worker == 0 else RESOURCE_TYPE_GPU
        helm_parameter = dto.DeploymentInfo(
            workspace_id=workspace_id, workspace_name=workspace_name, user=str(owner_name),
            deployment_id=deployment_id, deployment_worker_id=deployment_worker_id, deployment_name=deployment_name, project_name=project_name,
            pod_name=unique_pod_name, pod_base_name=pod_base_name, pod_image=docker_image_real_name, run_code=run_code,
            instance_id=instance_id, resource_group_id=resource_group_id, 
            resource_type=resource_type, resource_name=resource_name, 
            gpu_count=gpu_per_worker, gpu_cluster_auto=gpu_cluster_auto,
            gpu_auto_cluster_case=gpu_auto_cluster_case, resources=resources,
            model_type=model_type, huggingface_model_id=huggingface_model_id, huggingface_token=huggingface_model_token, training_id=training_id,
        )
        print(helm_parameter)
        
        # =====================================================================================
        # kafka 요청
        
        # print(topic_key.DEPLOYMENT_TOPIC.format(deployment_id, resource_type))
        kafka = DeploymentKafka()
        conf = kafka.conf
        producer = Producer(conf)
        producer.produce(topic=topic_key.SCHEDULER_TOPIC,
                         key="create_pod", value=json.dumps(helm_parameter.dict()), callback=kafka.acked)
        producer.poll(1)
        producer.flush()
        return response(status=1, message="Deployment Run", result={"worker_id" : deployment_worker_id})
    except CustomErrorList as ce:
        if deployment_worker_id is not None:
            # delete_deployment_worker(deployment_worker_id=deployment_worker_id)
            stop_deployment_worker(deployment_worker_id=deployment_worker_id)
        traceback.print_exc()
        raise ce
    except Exception as e:
        if deployment_worker_id is not None:
            # delete_deployment_worker(deployment_worker_id=deployment_worker_id)
            stop_deployment_worker(deployment_worker_id=deployment_worker_id)
        traceback.print_exc()
        # return response(status=0, message="Add Deployment Worker error")
        return response(status=0, message="Deployment Cannot Run : [{}]".format(e))

# 워커 중지 ===============================================================================
# def delete_deployment_worker(deployment_worker_id):
#     """단일 중지, stop_deployment_worker 함수 통합, 추후 삭제"""
#     try:
#         res, message = stop_deployment_worker(deployment_worker_id=deployment_worker_id)

#         if res:
#             return response(status=1, message="OK")
#         else:
#             print("Delete Deployment Worker Error: {}".format(message))
#             raise DeleteDeploymentWorkerDBError
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         return ce.response()
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Delete Deployment worker error : {}".format(e))

def delete_deployment_workers(deployment_worker_id_list=None, deployment_worker=None):
    """워커 페이지 -> 상단 중지된 워커 -> 리스트 삭제, 여기서는 DB도 지움"""
    try:
        if deployment_worker is not None and deployment_worker_id_list is None:
            deployment_worker_id_list=[deployment_worker_id]
        else:
            deployment_worker_id_list=[i.strip() for i in deployment_worker_id_list.split(",")]

        for deployment_worker_id in deployment_worker_id_list:
            res, message = stop_deployment_worker(deployment_worker_id=deployment_worker_id)

        db_deployment.delete_deployment_worker_list(deployment_worker_id_list)
        return response(status=1, message="OK")
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Delete Deployment worker error : {}".format(e))

def stop_deployment_worker(deployment_worker_id):
    try:
        """단일 중지, delete_deployment_worker 함수 통합"""
        """
        실제로 helm uninstall 하는 함수
        모놀리식에서는 parent worker, child worker 관련 로직이 있었으나
        msa에서는 helm으로 pod, svc/ing를 분리하였으므로
        pod count 가 1 일때 -> helm - pod, svc/ing 삭제
        pod count > 1 일때 ->  helm pod 만 삭제
        """
        deployment_worker_info = db_deployment.get_deployment_worker(deployment_worker_id=deployment_worker_id)
        workspace_id = deployment_worker_info["workspace_id"]
        deployment_id = deployment_worker_info["deployment_id"]
        workspace_name = deployment_worker_info.get('workspace_name')
        deployment_name = deployment_worker_info.get('deployment_name')
        start_datetime = deployment_worker_info.get('start_datetime')
        end_datetime = deployment_worker_info.get('end_datetime')



        print(f"----helm 삭제 : {deployment_worker_id} ----")
        # ==========HELM 삭제===========================
        pod_count = len(db_deployment.get_deployment_worker_list(deployment_id=deployment_id, running=True))

        if pod_count == 1:
            res, message = uninstall_all_deployment(workspace_id=workspace_id, deployment_id=deployment_id)
        elif pod_count > 1:
            res, message = uninstall_pod_deployment(workspace_id=workspace_id, deployment_id=deployment_id, deployment_worker_id=deployment_worker_id)
        else:
            res, message = uninstall_pod_deployment(workspace_id=workspace_id, deployment_id=deployment_id, deployment_worker_id=deployment_worker_id)
            pass

        # ==========DB 업데이트===========================
        # worker 중지 - DB 삭제 하면 안됨 -> 기록 남겨야됨 - end_datetime 만 추가
        res, message = db_deployment.update_end_datetime_deployment_worker(deployment_worker_id=deployment_worker_id)

        # ==========TODO 폴더 삭제===========================
        # ==========TODO 로그: 추후 변경(min님)===========================
        # [JFB/USAGE] {"log_type": "allocation", "allocation_info": { "workspace_name": "AAAI",  "start_datetime": "YYYY-MM-DD hh:mm:ss", "end_datetime": "시작시간과동일", "period": 초, "type": "editor/job/hyperparamsearch/deployment", "type_detail": "editor이름 or 학습이름 / job이름 or 학습이름 / hps이름 / 배포이름"}}
        # type detail에 배포 이름? 워커아이디?
        try:
            if start_datetime:
                deployment_worker_info = db_deployment.get_deployment_worker(deployment_worker_id=deployment_worker_id)
                instance_info = db_instance.get_instance(instance_id=deployment_worker_info["instance_id"])
                elapsed_time = common.calculate_elapsed_time(start_time=start_datetime, end_time=deployment_worker_info["end_datetime"])
                allocation_info = {
                        "workspace_name": deployment_worker_info["workspace_name"],
                        "start_datetime": deployment_worker_info["start_datetime"],
                        "item_name": "worker",
                        "deployment_name": deployment_worker_info["deployment_name"],
                        "end_datetime": deployment_worker_info["end_datetime"],
                        "period": elapsed_time,
                        "type": "deployment",
                        "type_detail": deployment_worker_info["deployment_name"],
                        "total_gpu_count": deployment_worker_info["gpu_per_worker"],
                        "instance_info": {
                            "instance_name": instance_info["instance_name"],
                            "gpu_name": instance_info.get("gpu_name", None),
                            "instance_type": "GPU" if instance_info.get("gpu_name", None) else "CPU",
                            "gpu_allocate": instance_info.get("gpu_allocate", 0),
                            "cpu_allocate": instance_info.get("cpu_allocate", 0),
                            "ram_allocate": instance_info.get("ram_allocate", 0)
                        }
                    }
                log = {
                    "log_type": "allocation",
                    "allocation_info": json.dumps(allocation_info, separators=(',', ':'))
                }
                print("[JFB/USAGE]", json.dumps(log, separators=(',', ':')))
        except:
            # 빠른 적용 위해 try except 처리
            pass
        return True, ""

    except Exception as e:
        traceback.print_exc()
        return False, str(e)

def stop_deployment(deployment_id):
    """
    Description: admin - 배포 에서 deployment 중지 버튼 (개별 worker 중지 말고, 배포 중지 버튼)
    """
    try:
        deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
        if deployment_info is None:
            return response(status=0, message="Not Found Deployment")
        deployment_name = deployment_info.get("deployment_name")
        workspace_name = deployment_info.get("workspace_name")

        # Helm 삭제 삭제 전송 ======================================
        try:
            res, message = uninstall_all_deployment(workspace_id=deployment_info["workspace_id"], deployment_id=deployment_id)
        except:
            print(message)

        for item in db_deployment.get_deployment_worker_list(deployment_id=deployment_id, running=True):
            # ==========DB 업데이트===========================
            # worker 중지 - DB 삭제 하면 안됨 -> 기록 남겨야됨 - end_datetime 만 추가
            res, message = db_deployment.update_end_datetime_deployment_worker(deployment_worker_id=item.get("id"))
            # ==========TODO 로그: 추후 변경(min님)===========================
            # [JFB/USAGE] {"log_type": "allocation", "allocation_info": { "workspace_name": "AAAI",  "start_datetime": "YYYY-MM-DD hh:mm:ss", "end_datetime": "시작시간과동일", "period": 초, "type": "editor/job/hyperparamsearch/deployment", "type_detail": "editor이름 or 학습이름 / job이름 or 학습이름 / hps이름 / 배포이름"}}
            # type detail에 배포 이름? 워커아이디?
            try:
                deployment_worker_info = db_deployment.get_deployment_worker(deployment_worker_id=item.get("id"))
                
                if deployment_worker_info["start_datetime"]:
                    instance_info = db_instance.get_instance(instance_id=deployment_worker_info["instance_id"])
                    elapsed_time = common.calculate_elapsed_time(start_time=deployment_worker_info["start_datetime"], end_time=deployment_worker_info["end_datetime"])
                    allocation_info = {
                            "workspace_name": deployment_worker_info["workspace_name"],
                            "start_datetime": deployment_worker_info["start_datetime"],
                            "item_name": "worker",
                            "deployment_name": deployment_worker_info["deployment_name"],
                            "end_datetime": deployment_worker_info["end_datetime"],
                            "period": elapsed_time,
                            "type": "deployment",
                            "type_detail": deployment_worker_info["deployment_name"],
                            "total_gpu_count": deployment_worker_info["gpu_per_worker"],
                            "instance_info": {
                                "instance_name": instance_info["instance_name"],
                                "gpu_name": instance_info.get("gpu_name", "-"),
                                "instance_type": "GPU" if instance_info.get("gpu_name", "-") else "CPU",
                                "gpu_allocate": instance_info.get("gpu_allocate", 0),
                                "cpu_allocate": instance_info.get("cpu_allocate", 0),
                                "ram_allocate": instance_info.get("ram_allocate", 0)
                            }
                    }
                    log = {
                        "log_type": "allocation",
                        "allocation_info": json.dumps(allocation_info, separators=(',', ':'))
                    }
                    print("[JFB/USAGE]", json.dumps(log, separators=(',', ':')))
                # start_datetime = item.get("start_datetime")
                # end_datetime = item.get("end_datetime")

                # allocation_info = {"workspace_name" : workspace_name, "start_datetime" : start_datetime, "end_datetime" : end_datetime, "period" : None, "type" : "deployment", "type_detail" : deployment_name}
                # print(f'[JFB/USAGE] {{"log_type": "allocation", "allocation_info": "{allocation_info}"}}')
            except:
                # 빠른 적용 위해 try except 처리
                pass
        # res = 1 if res == True else 0
        return response(status=1, message=message)

    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Deployment Cannot Stop")

# 워커 조회 ====================================================================
def get_deployment_worker_list(deployment_id, user_id, deployment_worker_running_status=1):
    """
    기능
        deployment worker list 조회용
    Input
        deployment_worker_running_status : db 조회시 중지된 목록까지 보여줄 것인지, end_datetime이 None(동작중) 인것만 보여줄것인지 - DB속도 매우달라짐
    없으면 터지는 데이터
        restart_count: 미리보기 터짐
        run_version, running_info: status running일때 없으면 터짐
        running_info history : 미리보기 터짐
    조회
        1. db에서 워커 목록 불러옴
        2. redis에서 deployment_id, worker_id로 조회
    """
    try:        
        def get_run_version(deployment_info, deployment_worker_info):
            """
            chaged_items = { "item": "aaa", "latest_version": "bbb", "current_version": "ccc"}
            """
            # 추후 프론트랑 맞춰서 바꾸기?? [{}] -> {}
            res = [{"changed": False, "changed_items": []}]
            try:
                # "resource_group_id",
                key_list = [ "gpu_per_worker", "instance_type", "project_id", "image_id", "command", "environments",  ]

                for key in key_list:
                    if deployment_info[f"{key}"] != deployment_worker_info[f"{key}"]:
                        res[0]["changed"] = True
                        res[0]["changed_items"].append({"item" : f"{key}", "latest_version" : deployment_info[f"{key}"], "current_version" : deployment_worker_info[f"{key}"]})                
            except:
                traceback.print_exc()
            return res

        # 탭: 작동중인 워커 
        def get_running_worker_info(deployment_worker_info):
            deployment_worker_id=deployment_worker_info["id"]
            workspace_name=deployment_worker_info["workspace_name"]
            deployment_name=deployment_worker_info["deployment_name"]
            
            # TODO EFK nginx_access_per_hour
            log_per_hour_info_list = svc_mon.get_deployment_worker_nginx_access_log_per_hour_info_list(deployment_worker_id=deployment_worker_id, workspace_name=workspace_name, deployment_name=deployment_name)
            time_table = svc_mon.get_nginx_per_hour_time_table_dict(log_per_hour_info_list=log_per_hour_info_list)
            call_count_chart = svc_mon.get_call_count_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list)
            median_chart = svc_mon.get_median_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list)
            nginx_abnormal_count_chart = svc_mon.get_nginx_abnormal_call_count_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list)
            api_monitor_abnormal_count_chart= svc_mon.get_api_monitor_abnormal_call_count_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list)
            chart_data = {
                "call_count_chart": call_count_chart,
                "median_chart": median_chart,
                "nginx_abnormal_count_chart": nginx_abnormal_count_chart,
                "api_monitor_abnormal_count_chart": api_monitor_abnormal_count_chart
            }

            # resource
            tmp_redis_worker_resource = redis_client.hget(DEPLOYMENT_WORKER_RESOURCE, str(deployment_worker_info['id']))
            if tmp_redis_worker_resource is not None:
                redis_worker_resource = json.loads(tmp_redis_worker_resource)
            else:
                redis_worker_resource = {'cpu_cores' :  {'total' : 0, 'usage' : 0, 'percentage' : 0}, 'ram' : {'total' : 0, 'usage' : 0, 'percentage' : 0}, 'gpus' : 0}

            return {
                    "deployment_worker_id" : deployment_worker_id,
                    "description" : deployment_worker_info["description"],
                    "instance" : { # 기획은 인스턴스가 아니라 워커자원 리소스 할당량임 # 백엔드만 수정하기위해 인스턴스에 담아서 내려줌
                        "cpu_allocate" :  workspace_resource_deployment_cpu,
                        "ram_allocate" :  workspace_resource_deployment_ram,
                        "gpu_allocate" :  deployment_worker_info["gpu_per_worker"],
                        "gpu_name" :  deployment_worker_info["gpu_name"],
                    },
                    "worker_status" : deployment_worker_redis_list[str(deployment_worker_id)],
                    # "worker_status" : {"status" : , "reason" : , "resolution" : , "restart_count" : , "phase" : ,}
                    # run_env 필요한건지?? "run_env" : [{"docker_image": "[jf]cpu"}, {"gpu_model": None}, {"gpu_count": 0}, {"run_code": None}],
                    "start_datetime" : deployment_worker_info["start_datetime"],
                    "run_version" : get_run_version(deployment_info=deployment_info, deployment_worker_info=deployment_worker_info),
                    "running_info": [ # 리스트라서 순서 바뀌면 프론트 터짐
                        # cpu, ram 그래프
                        {"configurations" : deployment_worker_info["gpu_name"]}, 
                        {"cpu_cores" :  "{} | {}%".format(redis_worker_resource["cpu_cores"]["total"], redis_worker_resource["cpu_cores"]["percentage"])},
                        {"ram" : "{} | {}%".format(byte_to_gigabyte(int(redis_worker_resource["ram"]["total"])), redis_worker_resource["ram"]["percentage"])},
                        {"gpus" : redis_worker_resource["gpus"]}, # TODO??
                        {"network" : None}, # TODO 삭제
                        # chart_data
                        {"call_count_chart" : chart_data["call_count_chart"]}, # 콜 수 - 초록색 그래프
                        {"median_chart" : chart_data["median_chart"]}, # 콜 수 - 보라색?선
                        {"nginx_abnormal_count_chart" : chart_data["nginx_abnormal_count_chart"]}, # 비정상처리 - nginx
                        {"api_monitor_abnormal_count_chart" : chart_data["api_monitor_abnormal_count_chart"]}, # 비정상 처리 - api
                        # resource_usage_graph - 미리보기
                        # { "mem_history" : resource_usage_graph.get("mem_history") if resource_usage_graph is not None else None},
                        # { "cpu_history" : resource_usage_graph.get("cpu_history") if resource_usage_graph is not None else None},
                        # { "gpu_history" : resource_usage_graph.get("gpu_history") if resource_usage_graph is not None else None},
                        { "mem_history" : redis_worker_resource.get("mem_history") if redis_worker_resource is not None else None},
                        { "cpu_history" : redis_worker_resource.get("cpu_history") if redis_worker_resource is not None else None},
                        { "gpu_history" : redis_worker_resource.get("gpu_history") if redis_worker_resource is not None else None},
                    ],
                }
        
        # 탭: 중지된 워커 
        def get_stop_worker_info(deployment_worker_info):
            start_datetime = deployment_worker_info["start_datetime"] if deployment_worker_info["start_datetime"] else deployment_worker_info["create_datetime"]
            end_datetime = deployment_worker_info["end_datetime"]

            return {
            "deployment_worker_id": deployment_worker_info["id"],
            "description": deployment_worker_info["description"],
            "instance" : {
                "cpu_allocate" :  deployment_worker_info["cpu_allocate"],
                "ram_allocate" :  deployment_worker_info["ram_allocate"],
                "gpu_allocate" :  deployment_worker_info["gpu_allocate"],
                "gpu_name" :  deployment_worker_info["gpu_name"],
            },
            "operation_time" : common.date_str_to_timestamp(end_datetime) - common.date_str_to_timestamp(start_datetime),
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "log_size": get_deployment_worker_log_size(workspace_name=deployment_worker_info["workspace_name"],
                                                       deployment_name=deployment_worker_info["deployment_name"],
                                                       deployment_worker_id=deployment_worker_info["id"]),
            "call_count": svc_mon.get_deployment_worker_nginx_call_count(deployment_worker_id=deployment_worker_info["id"])["total_count"],
            # "call_count": get_deployment_worker_nginx_call_count(deployment_worker_id=deployment_worker_info["id"], workspace_name=deployment_worker_info["workspace_name"], deployment_name=deployment_worker_info["deployment_name"])["total_count"],
            # "permission_level": permission_level
        }
        
        deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
        deployment_worker_db_list = db_deployment.get_deployment_worker_list(deployment_id=deployment_id, running=bool(deployment_worker_running_status))
        # workspace_resource = db_workspace.get_workspace_resource(workspace_id=deployment_info.get("workspace_id"))
        workspace_resource_deployment_cpu = deployment_info.get("deployment_cpu_limit")
        workspace_resource_deployment_ram = deployment_info.get("deployment_ram_limit")

        tmp_workspace_pod_status = redis_client.hget(WORKSPACE_PODS_STATUS, deployment_info["workspace_id"])        
        redis_pod_list = json.loads(tmp_workspace_pod_status) if tmp_workspace_pod_status is not None else dict()
        deployment_redis_list = redis_pod_list.get('deployment', dict())
        deployment_worker_redis_list = deployment_redis_list.get(str(deployment_id), dict())

        worker_list = []
        for deployment_worker_info in deployment_worker_db_list:
            deployment_worker_id = deployment_worker_info["id"]
            
            if deployment_worker_running_status==1 and deployment_worker_info.get("end_datetime") is not None:
                continue
            
            # 탭: 중지된 워커
            if deployment_worker_running_status == 0:
                worker_list.append(get_stop_worker_info(deployment_worker_info=deployment_worker_info))

            # 탭: 작동 중인 워커
            elif deployment_worker_info["end_datetime"] is None:
                if deployment_worker_redis_list is not None and \
                    (len(deployment_worker_redis_list) == 0 or str(deployment_worker_id) not in deployment_worker_redis_list.keys()):
                    # 바로 안뜨는 경우 / Redis에 바로 추가되지 않는 경우 or worker DB end_time이 null 인 경우(실제로 pod은 없는데)
                    # TODO -> 현재 installing으로 처리하게 함
                    deployment_worker_redis_list.update ({
                        str(deployment_worker_id) : {
                            "status" : "pending",
                            "reason" : None,
                            "resolution" : None,
                        }})
                worker_list.append(get_running_worker_info(deployment_worker_info=deployment_worker_info))
        return response(status=1, result=worker_list)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Get deployment worker list error {}".format(e))

# 워커 시스템로그 ==========================================================================
def get_worker_system_log(deployment_worker_id):
    """
    Description :
        kubectl logs {} 출력 전달

    Args :
        deployment_worker_id (int)

    """
    try:
        # workspace_id = db_deployment.get_deployment_worker(deployment_worker_id=deployment_worker_id)["workspace_id"]
        # deployment_worker_namespace = JF_SYSTEM_NAMESPACE + "-" + str(workspace_id)
        # pod_logs = get_deployment_worker_pod_log(namespace=deployment_worker_namespace,
        #                                                   deployment_worker_id=deployment_worker_id)
        
        data = {
            "count" : 100,
            "deploymentWorkerId" : deployment_worker_id
        }
        
        rquest_logs = common.post_request_sync(url=LOG_MIDDLEWARE_DNS+"/v1/deployment/all", data=data)
        res = []
        if rquest_logs is not None:
            logs = rquest_logs.get("logs")
            for i in logs:
                try:
                    res.append(i.get("fields").get('log'))
                except:
                    pass
            result = '\n'.join(res)
        return result
    except Exception as e:
        traceback.print_exc()
        raise Exception(e)

def get_worker_system_log_download(deployment_worker_id):
    try:
        # workspace_id = db_deployment.get_deployment_worker(deployment_worker_id=deployment_worker_id)["workspace_id"]
        # deployment_worker_namespace = JF_SYSTEM_NAMESPACE + "-" + str(workspace_id)
        # pod_logs = get_deployment_worker_pod_log(namespace=deployment_worker_namespace,
        #                                                   deployment_worker_id=deployment_worker_id)
        
        data = {
            "count" : 100,
            "deploymentWorkerId" : deployment_worker_id
        }
        
        rquest_logs = common.post_request_sync(url=LOG_MIDDLEWARE_DNS+"/v1/deployment/all", data=data)
        res = []
        if rquest_logs is not None:
            logs = rquest_logs.get("logs")
            for i in logs:
                try:
                    res.append(i.get("fields").get('log'))
                except:
                    pass
        data = '\n'.join(res)
        return common.text_response_generator(data_str=data)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Deployment worker system log download error")

# 기타 ==========================================================================
def add_deployment_bookmark(deployment_id, user_id):
    try:
        result, message = db_deployment.insert_deployment_bookmark(deployment_id=deployment_id, user_id=user_id)
        if result == True:
            return response(status=1)
        else :
            print("Add deployment bookmark error : {}".format(message))
            # return response(status=0, message="Add deployment bookmark error : {}".format(message))
            raise DeploymentBookmarkDBInsertError
    except CustomErrorList as ce:
        traceback.print_exc()
        return response(status=0, message=ce.message)

def delete_deployment_bookmark(deployment_id, user_id):
    result, message = db_deployment.delete_deployment_bookmark(deployment_id=deployment_id, user_id=user_id)
    if result == True:
        return response(status=1)
    else :
        print("Delete deployment bookmark error : {}".format(message))
        # return response(status=0, message="Delete deployment bookmark error : {}".format(message))
        raise DeploymentBookmarkDBDeleteError

def get_deployment_name(deployment_id):
    # 배포 > 대시보드 페이지에서 사용 남겨둠
    try:
        info = db_deployment.get_deployment(deployment_id=deployment_id)
        deployment_name = info["name"]
        return response(status=1, result=deployment_name, message="OK")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="fail")     

def deployment_name_and_user_info_validation_check(deployment_name, workspace_id, owner_id, users_id):
    """
    Description: 배포 사용자, 배포 Owner 있는지 체크, 배포 이름 중복 체크

    Args:
        workspace_id (int): workspace id
        deployment_name (str): 배포 이름
        owner_id (int): 배포 owner id
        users_id (list):    public 배포 => 워크스페이스 사용자들
                            private 배포 => 허용된 사용자

    Raises:
        DeploymentNameExistError: 이름 중복 에러
        DeploymentOwnerIDNotExistError: owner 아이디 없음 에러
        DeploymentUserIDNotExistError: 사용자 아이디 없음 에러
        DeploymentNoOwnerInWorkspaceError: 워크스페이스에 해당 메니저 없음 에러
        DeploymentNoUserInWorkspaceError: 워크스페이스에 해당 사용자 없음 에러
    """    
    try:
        def is_deployment_good_name(deployment_name):
            is_good = common.is_good_name(name=deployment_name)
            if is_good == False:
                raise DeploymentNameInvalidError
            return True
        
        def user_in_workspace_check(workspace_id, user_id):
            user_workspaces = db_deployment.check_user_in_workspace(user_id=user_id, workspace_id=workspace_id)
            if user_workspaces is not None:
                return True
            else:
                return False
        
        # deployment name check
        is_deployment_good_name(deployment_name=deployment_name)
            
        ## Info Unique Check
        # Deployment Name exist Check
        deployment_info = db_deployment.get_deployment(deployment_name=deployment_name, workspace_id=workspace_id)
        if deployment_info is not None:
            if workspace_id == deployment_info["workspace_id"]:
                raise DeploymentNameExistError
            
        # Check Owner or Users Exist Check
        owner_info = db_user.get_user(user_id=owner_id)
        if owner_info is None:
            raise DeploymentOwnerIDNotExistError
        for user_id in users_id:
            user_info = db_user.get_user(user_id=user_id)
            if user_info is None:
                raise DeploymentUserIDNotExistError

        # Check Owner or Users belong to workspace
        flag = user_in_workspace_check(workspace_id=workspace_id, user_id=owner_id)
        if flag == False:
            raise DeploymentNoOwnerInWorkspaceError
        for user_id in users_id:
            flag = user_in_workspace_check(workspace_id=workspace_id, user_id=user_id)
            if flag == False:
                raise DeploymentNoUserInWorkspaceError

    except CustomErrorList as ce:
        traceback.print_exc()
        raise ce
    except Exception:
        traceback.print_exc()
        return False

def get_deployment_full_api_address(deployment_id=None, base_api=None):
    try:
        if deployment_id is None and base_api is None:
            return None
        
        protocol = INGRESS_PROTOCOL
        if EXTERNAL_HOST_REDIRECT :
            api_address = EXTERNAL_HOST
        else:
            api_address = f"{EXTERNAL_HOST}:{EXTERNAL_HOST_PORT}"
        
        if base_api:
            path = base_api
        else:
            path = db_deployment.get_deployment(deployment_id=deployment_id)["api_path"]
        # return f"{protocol}://{api_address}/deployment/{path}/"
        return f"/deployment/{path}/"
    except Exception as e:
        traceback.print_exc()
        return None

# 옵션 ====================================================================================
"""
공통 : docker_image_list, user_list
배포모달 -> instance_list
"""
async def get_deployment_options(workspace_id, deployment_id=None):
    try:
        # 공통 option
        res = {
            "docker_image_list" : db_deployment.get_image_list(workspace_id=workspace_id), # 0.002
            "user_list" : db_deployment.get_user_list_workspace(workspace_id=workspace_id)
        }
        if deployment_id is not None:
            deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
            
            # false일 경우는 워커설정모달에서 "인스턴스설정이 필요합니다" 메시지
            res["instance_type"] = None if deployment_info.get("instance_id") is None else deployment_info["instance_type"]
            
            # 워커별 gpu 할당 # 이전에 설정하여, 세팅되어 있는 값을 보여줌
            res["gpu_list"] = {
                "gpu_name" : deployment_info.get("gpu_name"),
                "gpu_total" : deployment_info.get("instance_allocate", 0) * deployment_info.get("gpu_allocate", 0) \
                if deployment_info.get("instance_id") and (deployment_info["instance_type"] == INSTANCE_TYPE_GPU) else 0, # 최대 할당 가능 개수
                "gpu_allocate" : deployment_info.get("gpu_per_worker", None), # 현재 할당되어 있는 개수
                "gpu_multiple" : None, # 몇개씩 증가 가능한지
            }
            
            
            # # gpu cluster # 이전에 설정하여, 세팅되어 있는 값을 보여줌
            # gpu_auto_cluster_case = deployment_info.get("gpu_auto_cluster_case")
            # if gpu_auto_cluster_case is not None:
            #     gpu_auto_cluster_case = json.loads(gpu_auto_cluster_case)
            # res["gpu_cluster"] = {
            #     "auto" : bool(deployment_info.get("gpu_cluster_auto", True)),
            #     "auto_select" : gpu_auto_cluster_case,
            # }
        else:
            # deployment option
            res["instance_list"] = db_deployment.get_workspace_instance(workspace_id=workspace_id)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        raise ce
    except Exception as e:
        traceback.print_exc()
        raise Exception(str(e))

# 학습 리스트
def get_option_usertrained_list(workspace_id, headers_user):
    try:
        result = []
        user_id = db_user.get_user(user_name=headers_user)["id"]
        workspace_custom_list = db_deployment.get_workspace_custom_training_list(workspace_id=workspace_id, user_id=user_id)

        # training --> project
        for training in workspace_custom_list:
            # private이고 접근권한 없으면 통과
            if training.get("access") == 0:
                if user_id not in [int(i) for i in training.get("user_ids").split(',')]:
                    continue
            
            result.append({
                "is_thumbnail" : 0, # TODO
                "training_type" : "custom", # TODO 삭제
                "training_name" : training["name"],
                "training_id" : training["id"],
                "training_description" : training["description"],
                "training_bookmark" : training["bookmark"],
                "training_user_id" : training["create_user_id"],
                "training_user_name" : training["user_name"],
                # "built_in_model_id" : training.get("built_in_model_id"),
                # "built_in_model_kind" : training.get("built_in_model_kind"),
                # "built_in_model_name" : training.get("built_in_model_name"),
                # "built_in_model_thumbnail_image_info" : get_built_in_model_thumnail_image_info(
                #     built_in_model_id=training.get("id"), path=training.get("path"),
                #     thumbnail_path=training.get("thumbnail_path")
                # ) if training.get("thumbnail_path") != None else None,
                # "deployment_type" : None,
                # "enable_to_deploy_with_gpu" : None,
                # "enable_to_deploy_with_cpu" : None,
                # "deployment_multi_gpu_mode" : None,
                # "header_user_tool_start_datetime" : None,
            })
        return response(status=1, result=result)
    except CustomErrorList as ce:
        traceback.print_exc()
        raise ce
    except Exception as e:
        traceback.print_exc()
        return response(status=0, result=None)

# 학습 코드 리스트 & 분산 설정파일
async def get_option_usertrained_training_list(training_id):
    try:
        result = dict()
        info = db_deployment.get_project(project_id=training_id)

        file_extension = ["py", "sh"]
        ignore_folders = ['datasets', 'training_logs', '.ipynb_checkpoints']
        base_path = "/jf-data/{storage_name}/main/{workspace_name}/projects/{project_name}/src".format(storage_name=info["main_storage_name"], workspace_name=info["workspace_name"], project_name=info["name"])

        run_code_list, config_file_list = await common.get_files(base_path=base_path, file_extension=file_extension, ignore_folders=ignore_folders, is_full_path=False)
        result = {
            "run_code_list" : run_code_list,
            "config_file_list" : config_file_list,
        }
        return response(status=1, result=result)
    except CustomErrorList as ce:
        traceback.print_exc()
        raise ce
    except Exception as e:
        traceback.print_exc()
        return response(status=0, result=None)


# TODO JOB, HPS option example
"""
result = {
    "job_list" : [
        {
            'job_name': 'robert-job',
            'job_create_datetime': '2022-11-18 04:04:23',
            'job_runner_name': 'lyla',
            'job_group_list': [
                {
                    'job_id': 55,
                    'job_group_name': 0,
                    'run_parameter':{
                        'data':'/user_dataset/',
                        'batch_size': '32'
                    },
                    'checkpoint_list':[
                        '00-0.61.json',
                        '00-0.61.json'
                    ]
                },
                {
                    'job_id': 54,
                    'job_group_name': 1,
                    'run_parameter':{
                        'data':'/user_dataset/',
                        'batch_size': '64'
                    },
                    'checkpoint_list':[
                        '00-0.61.json',
                        '00-0.61.json'
                    ]
                }
            ]
        }
    ],
    "hps_list" : [
        {
            'hps_name': 'robert-hps',
            'hps_create_datetime': '2022-11-18 04:04:23',
            'hps_runner_name': 'lyla',
            'hps_group_list': [
                {
                    'hps_id': 55,
                    'hps_group_name': 0,
                    'best_score':92,
                    'best_hps_number':45,
                    'run_parameter':{
                        'data':'/user_dataset/',
                        'batch_size': '32'
                    }, 
                    'search_parameter': {
                        'dropout_rate': '(0.1,0.6)',
                    'learning_rate': '(0.0005,0.003)'
                    },
                    'hps_number_info': {
                        'log_table': [
                            {
                                'target': 66.56,
                                'params': {
                                    'dropout_rate': 0.30851100235128703,
                                    'learning_rate': 0.0023008112336053953
                                },
                                'datetime': {
                                    'datetime': '2022-04-12 09:03:28',
                                    'elapsed': 0.0,
                                    'delta': 0.0
                                },
                                'hps_id': 40,
                                'id': 1,
                                'checkpoint_list': [
                                    '01-0.67.json',
                                    '01-0.67.json',
                                    '00-0.66.json',
                                    '00-0.66.json'
                                ]
                            },
                        ],
                    'parameter_settings': {},
                    'status': {},
                    'max_index': 47,
                    'max_item': {
                        'target': 68.5,
                        'params': {
                            'dropout_rate': 0.30786751396801826,
                            'learning_rate': 0.0028685824670648266
                        },
                        'datetime': {
                            'datetime': '2022-11-15 02:15:18',
                            'elapsed': 2167.977708,
                            'delta': 50.848016
                        },
                        'hps_id': 45,
                        'id': 48,
                        'checkpoint_list': [
                            '00-0.68.json',
                            '00-0.68.json'
                        ]
                        }
                    }
                },
            ]
        },
    ]
}
"""    

# log =======================================================================================================
# log size
def get_dir_size(file_path):
    if os.path.exists(file_path):
        cmd = "du -b {}".format(file_path)
        try:
            out = subprocess.check_output(cmd, shell=True).strip().decode()
            out = out.split("\t")[0]
            return int(out)
        except:
            traceback.print_exc()
            return None
    else:
        return 0

def get_log_size(workspace_id, workspace_name, deployment_name, deployment_worker_id_list=None):
    if deployment_worker_id_list is None or len(deployment_worker_id_list) == 0:
        deployment_worker_id_list = check_deployment_worker_log_dir(workspace_id=workspace_id, workspace_name=workspace_name, deployment_name=deployment_name)["log_dir"]
    else :
        pass
    total_log_size_list=[]
    for deployment_worker_id in deployment_worker_id_list:
        main_storage_name = db_deployment.get_workspace_info_storage(workspace_name=workspace_name)["main_storage_name"]
        deployment_worker_log_dir = JF_DEPLOYMENT_WORKER_LOG_DIR_PATH.format(main_storage_name=main_storage_name,
                                                                             workspace_name=workspace_name, 
                                                                            deployment_name=deployment_name, 
                                                                            deployment_worker_id=int(deployment_worker_id))
        log_size = get_dir_size(deployment_worker_log_dir)
        if log_size !=None:
            total_log_size_list.append(log_size)
        # for file_name in [POD_NGINX_ACCESS_LOG_FILE_NAME, POD_API_LOG_FILE_NAME]:
        #     if os.path.exists("{}/{}".format(deployment_worker_log_dir, file_name)):
        #         log_size = get_dir_size("{}/{}".format(deployment_worker_log_dir, file_name))
        #     else:
        #         log_size = 0
        #     if log_size !=None:
        #         total_log_size_list.append(log_size)
    return sum(total_log_size_list)

def get_deployment_worker_log_size(workspace_name, deployment_name, deployment_worker_id):
    # NGINX_ACCESS_LOG + API_MONITOR_LOG FILE
    main_storage_name = db_deployment.get_workspace_info_storage(workspace_name=workspace_name)["main_storage_name"]
    deployment_worker_log_dir = JF_DEPLOYMENT_WORKER_LOG_DIR_PATH.format(main_storage_name=main_storage_name,
                                                                        workspace_name=workspace_name, 
                                                                        deployment_name=deployment_name, 
                                                                        deployment_worker_id=int(deployment_worker_id))
    total_log_size = 0
    for file_name in [POD_NGINX_ACCESS_LOG_FILE_NAME, POD_API_LOG_FILE_NAME]:
        if os.path.exists("{}/{}".format(deployment_worker_log_dir, file_name)):
            log_size = get_dir_size("{}/{}".format(deployment_worker_log_dir, file_name))
        else:
            log_size = 0
        if log_size is not None:
            total_log_size += log_size
        
    return total_log_size

def get_worker_info_dic(start_time, end_time, worker_list, deployment_path, deployment_id=None, workspace_id=None):
    # time to time object
    if start_time!=None and end_time!=None:
        start_time_obj=datetime.strptime(start_time, POD_RUN_TIME_DATE_FORMAT)
        end_time_obj=datetime.strptime(end_time, POD_RUN_TIME_DATE_FORMAT)
        start_timestamp=common.date_str_to_timestamp(start_time, POD_RUN_TIME_DATE_FORMAT)
        end_timestamp=common.date_str_to_timestamp(end_time, POD_RUN_TIME_DATE_FORMAT)
    # get worker list if pod run time in time range
    running_worker_list = get_running_worker_dir(workspace_id=workspace_id, deployment_id=deployment_id)
    running_worker_list=running_worker_list["running_worker_list"]
    worker_info_dic={}
    now_time_obj = datetime.now()
    # now_timestamp = common.date_str_to_timestamp()
    for i in range(len(worker_list)):
        try:
            pod_run_time_path = "{}/log/{}/{}".format(deployment_path, worker_list[i], POD_RUN_TIME_FILE_NAME)
            with open(pod_run_time_path, "r") as f:
                run_time=json.load(f)
        except FileNotFoundError:
            continue
        # print("pod run time",run_time)
        worker_start_time_obj=datetime.strptime(run_time["start_time"], POD_RUN_TIME_DATE_FORMAT)
        worker_end_time_obj=datetime.strptime(run_time["end_time"], POD_RUN_TIME_DATE_FORMAT)
        worker_start_timestamp=common.date_str_to_timestamp(run_time["start_time"], POD_RUN_TIME_DATE_FORMAT)
        worker_end_timestamp=common.date_str_to_timestamp(run_time["end_time"], POD_RUN_TIME_DATE_FORMAT)
        check_range=True
        if start_time!=None and end_time!=None:
            
            # TODO 변경 체크 2024-11-12 klod            
            # def check_worker_time_range(start_time, end_time, worker_start_time, worker_end_time):
            #     # print("start_time", start_time)
            #     # print("end_time", end_time)
            #     # print("worker_start_time", worker_start_time)
            #     # print("worker_end_time", worker_end_time)
            #     result=False
            #     if worker_start_time<start_time:
            #         if worker_end_time>=start_time:
            #             result=True
            #     elif worker_start_time<end_time:
            #         result=True
            #     return result
            # check_range = check_worker_time_range(start_time_obj, end_time_obj, worker_start_time_obj, worker_end_time_obj)
            check_range = True if (worker_start_time_obj<start_time_obj and worker_end_time_obj>=start_time_obj) or worker_start_time_obj<end_time_obj else False
            
        if check_range:
            worker_dic={
                "start_time":run_time["start_time"],
                "end_time":datetime.strftime(now_time_obj, POD_RUN_TIME_DATE_FORMAT) if worker_list[i] in running_worker_list else run_time["end_time"],
                "start_time_obj":worker_start_time_obj,
                "end_time_obj": now_time_obj if worker_list[i] in running_worker_list else worker_end_time_obj
            }
            worker_info_dic[worker_list[i]]=worker_dic
    return worker_info_dic

def get_graph_log(end_time, start_time=None, deployment_id=None, deployment_worker_id=None, worker_list=None, nginx_log=True, api_log=True):
    from ast import literal_eval
    import time
    result={
        "error": 0,
        "message": "",
        "monitor_log": [],
        "nginx_access_log": [],
        "deployment_worker_id":None
    }
    if deployment_id!=None:
        info = db_deployment.get_deployment(deployment_id=deployment_id)
    elif deployment_worker_id!=None:
        info = db_deployment.get_deployment_worker(deployment_worker_id=deployment_worker_id)
    else:
        return None
    workspace_name = info.get("workspace_name")
    deployment_name = info.get("name")
    workspace_id = info.get("workspace_id")
    
    result_list = []
    if worker_list==None:
        log_dir_result = check_deployment_worker_log_dir(start_time=start_time, end_time=end_time,
                                                        workspace_id=workspace_id, workspace_name=workspace_name, deployment_name=deployment_name,
                                                        deployment_worker_id=deployment_worker_id)
        if log_dir_result["error"]==1:
            result["error"]=1
            result["message"]=log_dir_result["message"]
            result_list=[result]
            return result_list
        else:
            worker_list = log_dir_result["log_dir"]
    # else:
    # load_file_time=time.time()
    for log_dir in worker_list:
        result = check_deployment_worker_log_file(workspace_name, deployment_name, log_dir, nginx_log, api_log)
        result["deployment_worker_id"]=int(log_dir)
        result_list.append(result)
    # str 을 dic 형태로 변경
    # dic_log_time=time.time()
    if nginx_log:
        for result in result_list:
            result["nginx_access_log"] = [json.loads(dic) for dic in result["nginx_access_log"]]
    if api_log:
        for result in result_list:
            try:
                result["monitor_log"] = [json.loads(dic.replace("\'", "\"")) for dic in result["monitor_log"]]
            except:
                try:
                    result["monitor_log"] = [literal_eval(dic) for dic in result["monitor_log"]]
                except:
                    pass
    return result_list

def check_deployment_worker_log_file(workspace_name, deployment_name, deployment_worker_id, nginx_log=True, api_log=True):
    result = {
        "error": 0,
        "message": "",
        "monitor_log": [],
        "nginx_access_log": []
    }
    main_storage_name = db_deployment.get_workspace_info_storage(workspace_name=workspace_name)["main_storage_name"]
    deployment_worker_log_dir = JF_DEPLOYMENT_WORKER_LOG_DIR_PATH.format(main_storage_name=main_storage_name, workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
    try :
        worker_log_dir_file_list = os.listdir(deployment_worker_log_dir)

    except OSError as ose:
        # No log
        result["error"] = 1
        result["message"] = "No Log"
        return result
    except Exception as e:
        traceback.print_exc()
        # Unknown error
        result["error"] = 1
        result["message"] = "Unknown error {}".format(e)
        return result

    if check_deployment_api_monitor_import(worker_log_dir_file_list) == False:
        # api monitor not imported
        result["message"] = "API Monitor Not Imported"
    
    monitor_file_path = "{}/{}".format(deployment_worker_log_dir, POD_API_LOG_FILE_NAME)
    nginx_access_file_path = "{}/{}".format(deployment_worker_log_dir, POD_NGINX_ACCESS_LOG_FILE_NAME)

    # monitor.txt 의 time, response_time 추출해 list 에 담기
    if api_log:
        try:
            with open(monitor_file_path, "r") as f:
                monitor_log = f.read().splitlines()
        except:
            monitor_log = []
            result["message"] = "No Monitor Log"
        result["monitor_log"] = monitor_log
        
    if nginx_log:
        try:
            with open(nginx_access_file_path, "r") as f:
                nginx_access_log = f.read().splitlines()
        except:
            print("NGINX ACCESS LOG ERROR ")
            traceback.print_exc()
            nginx_access_log = []
            result["message"] = "No Nginx Log"
        result["nginx_access_log"] = nginx_access_log
    return result

def check_deployment_api_monitor_import(file_list):
    if POD_API_LOG_IMPORT_CHECK_FILE_NAME in file_list:
        # API MONITOR IMPORTED
        return True
    else:
        return False

def download_logfile(result_list, worker_info, deployment_path, start_time, end_time, nginx_log, api_log, deployment_name, background_tasks):
    from datetime import datetime
    try:
        def time_file_name(time_str):
            return time_str[2:].replace("-", "").replace(":", "").replace(" ", "-")

        mode_log_dic = {"nginx": "nginx_access_log", "api": "monitor_log"}
        mode_time_dic = {"nginx": "time_local", "api": "time"}

        mode_dic = {"nginx": nginx_log, "api": api_log}
        mode_list = [key for key in mode_dic.keys() if mode_dic[key]]
        # filter log by time
        if start_time!=None and end_time!=None:
            if start_time==end_time:
                end_time=end_time+" 23:59:59"
                end_time=end_time+" 00:00:00"
            for mode in mode_list:
                for idx in range(len(result_list)):
                    log_list = result_list[idx][mode_log_dic[mode]]
                    time_key = mode_time_dic[mode]
                    start_idx=0
                    end_idx=len(log_list)-1
                    for log_dic in log_list:
                        if common.date_str_to_timestamp(log_dic[time_key])>=common.date_str_to_timestamp(start_time):

                            start_idx = log_list.index(log_dic)
                            break
                    for log_dic in list(reversed(log_list)):
                        if common.date_str_to_timestamp(log_dic[time_key])<=common.date_str_to_timestamp(end_time):
                            end_idx = log_list.index(log_dic)
                            break
                    result_list[idx][mode_log_dic[mode]] = log_list[start_idx: end_idx+1]
                    # print("start_idx", start_idx)
                    # print("end_idx", end_idx)
                    # print(common.date_str_to_timestamp(log_dic[time_key]))
                    # print(common.date_str_to_timestamp(start_time))
        else:
            start_time = min([worker_info[key]["start_time_obj"] for key in  worker_info.keys()])
            start_time = datetime.strftime(start_time, POD_RUN_TIME_DATE_FORMAT)
            end_time = max([worker_info[key]["end_time_obj"] for key in  worker_info.keys()])
            end_time = datetime.strftime(end_time, POD_RUN_TIME_DATE_FORMAT)
        # make temporary directory  
        tmp_dir_name = ''.join(random.choices(string.ascii_lowercase, k=8))
        save_dir_name = "{}/{}".format(deployment_path, tmp_dir_name)
        os.makedirs(save_dir_name)
        # print("cwd_original: ",str(os.getcwd()))
        os.chdir(save_dir_name)
        # print("cwd: ",str(os.getcwd()))
        # make download name
        WORKER_TIME = "{start_time}-{end_time}"
        log_time = "{start_time}-{end_time}".format(start_time=time_file_name(start_time), end_time=time_file_name(end_time))
        FILE_NAME = "{mode}_{worker_id}__{log_time}__{worker_time}.txt"
        # save logs
        file_name_list=[]
        for mode in mode_list:
            # save log by worker
            for log_dic in result_list:
                log_str = "\n".join([str(i) for i in log_dic[mode_log_dic[mode]]])
                # print("log str: ",log_str[:100])
                dic = worker_info[log_dic["deployment_worker_id"]]
                worker_time = WORKER_TIME.format(start_time=time_file_name(dic["start_time"]), end_time=time_file_name(dic["end_time"]))
                file_name = FILE_NAME.format(mode=mode,worker_id=log_dic["deployment_worker_id"], log_time=log_time, worker_time=worker_time)
                with open(file_name, mode="w") as f:
                    f.write(log_str)
                file_name_list.append(file_name)
        # send tar file
        worker_str = "-".join([str(i) for i in worker_info.keys()])
        tar_file_name = "{}_{}_{}.tar".format(deployment_name, worker_str, log_time)
        # print("tar file name: "+ tar_file_name)
        file_name_list_str = " ".join(file_name_list)
        os.system('tar -cvf {} {}'.format(tar_file_name, file_name_list_str))
        # res = FileResponse(path=save_dir_name + "/" + tar_file_name, media_type='application/x-tar', filename=tar_file_name)

        def remove_directory(directory: str):
            os.system(f'rm -r {directory}')

        # background_tasks = BackgroundTasks()
        background_tasks.add_task(remove_directory, save_dir_name)
        tar_file_path = os.path.join(save_dir_name, tar_file_name)

        def iterfile():
            with open(tar_file_path, mode="rb") as file_like:
                yield from file_like

        response = StreamingResponse(iterfile(), media_type="application/x-tar")
        response.headers["Content-Disposition"] = f"attachment; filename={tar_file_name}"
        response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"

        # TODO flask send from directory
        # result = send_from_directory(directory = save_dir_name, filename = tar_file_name, as_attachment= True)
        # result = {"message" : "TODO Flask -> FastAPI 전환"}
        # result.headers["Access-Control-Expose-Headers"] = 'Content-Disposition'
        return response
    except:
        traceback.print_exc()
        return None

def get_deployment_log_download(deployment_id, worker_list, start_time, end_time, nginx_log, api_log, background_tasks):
    try:
        info = db_deployment.get_deployment(deployment_id=deployment_id)
        workspace_name = info.get("workspace_name")
        workspace_id = info.get("workspace_id")
        deployment_name = info.get("name")
        # worker list 받기
        if worker_list != None:
            worker_list = [int(i.strip()) for i in worker_list.split(",")]
        else:
            # worker list 가 없는 경우
            log_dir_result = check_deployment_worker_log_dir(workspace_id=workspace_id, workspace_name=workspace_name, deployment_name=deployment_name, 
                                                            start_time=start_time, end_time=end_time)
            if log_dir_result["error"]==1:
                print(log_dir_result["message"])
                raise DeploymentWorkerLogDirNotExistError
                # return response(status=0, message=log_dir_result["message"])
            worker_list = [int(i) for i in log_dir_result["log_dir"]]
        main_storage_name = db_deployment.get_workspace_info_storage(workspace_name=workspace_name)["main_storage_name"]
        deployment_path = JF_DEPLOYMENT_PATH.format(main_storage_name=main_storage_name, workspace_name=workspace_name, deployment_name=deployment_name)
        if check_worker_dir_and_install(workspace_name=workspace_name, deployment_name=deployment_name, worker_dir_list=worker_list)==False:
            raise DeploymentWorkerDirNotExistError
            # return response(status=0, message="worker directory does not exist")
        # get log filter by worker => log_worker_list
        worker_info = get_worker_info_dic(start_time, end_time, worker_list, deployment_path, deployment_id, workspace_id)
        if len(worker_info)==0:
            raise DeploymentNoLogError
            # return response(status=0, message="No log in input time range")
        log_worker_list = worker_info.keys()
        # log worker list 통해 log list 받기 => [{"nginx_access_log":[], "monitor_log":[], "deployment_worker_id": },..]
        result_list = get_graph_log(start_time=start_time, end_time=end_time, deployment_id=deployment_id, deployment_worker_id=None, 
                                    worker_list=log_worker_list, nginx_log=nginx_log, api_log=api_log)
        
        if len(result_list)==0:
            return response(status=0, message="unknown error")
        # worker 없는경우
        if len(result_list)==sum(result_list[i].get("error") for i in range(len(result_list))):
            raise DeploymentNoWorkerInTimeRangeError
            # return response(status=0, message=result_list[0]["message"])
        # log file download
        result = download_logfile(result_list=result_list, worker_info=worker_info, deployment_path=deployment_path,
                                start_time=start_time, end_time=end_time, nginx_log=nginx_log, 
                                api_log=api_log, deployment_name=deployment_name, background_tasks=background_tasks)
        # os.chdir("/jf-src/master")
        # print(result)
        return result
    except Exception as e:
        traceback.print_exc()
        return None

def get_deployment_log_delete(deployment_id, end_time, worker_list=None, get_worker_list=False):
    # from deployment.service_worker import check_deployment_worker_log_dir, get_graph_log, delete_deployment_worker
    from datetime import datetime
    try:
        deployment_name_info = db_deployment.get_deployment(deployment_id=deployment_id)
        workspace_name = deployment_name_info.get("workspace_name")
        workspace_id = deployment_name_info.get("workspace_id")
        deployment_name = deployment_name_info.get("name")
        main_storage_name = db_deployment.get_workspace_info_storage(workspace_name=workspace_name)["main_storage_name"]

        # worker list 가 없는 경우
        log_dir_result = check_deployment_worker_log_dir(workspace_id=workspace_id, workspace_name=workspace_name, deployment_name=deployment_name, 
                                                        end_time=end_time)
        if log_dir_result["error"]==1:
            return response(status=0, message=log_dir_result["message"])
        running_worker_dir = get_running_worker_dir(workspace_id=workspace_id, deployment_id=deployment_id)
        if worker_list ==None:
            worker_list=log_dir_result["log_dir"]
        else:
            worker_list = [i.strip() for i in worker_list.split(',')]
        # edit_file_list = [POD_API_LOG_FILE_NAME, POD_API_LOG_COUNT_FILE_NAME, 
        #                 POD_NGINX_ACCESS_LOG_FILE_NAME, POD_RUN_TIME_FILE_NAME]
        edit_file_list = [POD_API_LOG_FILE_NAME, POD_NGINX_ACCESS_LOG_FILE_NAME]
        # 기준 시간 없는 경우
        if end_time==None:
            for log_dir in worker_list:
                deployment_worker_log_dir = JF_DEPLOYMENT_WORKER_LOG_DIR_PATH.format(main_storage_name=main_storage_name,
                                                                                    workspace_name=workspace_name,
                                                                                    deployment_name=deployment_name,
                                                                                    deployment_worker_id=log_dir)
                # running 아닌 worker 의 경우 worker 삭제
                if log_dir not in running_worker_dir["running_worker_list"]:
                    if os.path.isdir(deployment_worker_log_dir):
                        os.system("rm -r {}".format(deployment_worker_log_dir))
                    # result=delete_deployment_worker(int(log_dir))
                else:
                    for file_name in edit_file_list:
                        file_path = "{}/{}".format(deployment_worker_log_dir, file_name)
                        # nginx log 의 경우 빈 파일로 남겨둠
                        # if file_name==POD_NGINX_ACCESS_LOG_FILE_NAME:
                        with open(file_path, "w") as f:
                            f.write("")
                        # nginx 아닌경우 삭제
                        # elif os.path.exists(file_path):
                        #     os.system("rm {}".format(file_path))
        # 시간 정해진 경우
        else:
            complete_delete_list=[] # 완전삭제
            partial_delete_list=[] # 부분삭제
            # stop worker 만 해당됨
            result_worker_dir=list(set(worker_list)-set(running_worker_dir["running_worker_list"]))
            # 모든 worker 가 running 인 경우
            if len(result_worker_dir)==0:
                return response(status=0, message="all workers are running")
            result_list = get_graph_log(end_time=end_time, deployment_id=deployment_id, worker_list=list(result_worker_dir))
            if len(result_list)==0:
                return response(status=0, message="unknown error")
            # worker 없는경우
            if len(result_list)==sum(result_list[i].get("error") for i in range(len(result_list))):
                return response(status=0, message=result_list[0]["message"])
            
            mode_log_dic = {"nginx": "nginx_access_log", "api": "monitor_log"}
            mode_time_dic = {"nginx": "time_local", "api": "time"}
            mode_path_dic = {"nginx": POD_NGINX_ACCESS_LOG_FILE_NAME, "api": POD_API_LOG_FILE_NAME}
            split_str_dic = {"nginx": '"time_local":"{}"', "api": "'time': '{}'"}
            for result_dic in result_list:
                deployment_worker_log_dir = JF_DEPLOYMENT_WORKER_LOG_DIR_PATH.format(
                                                                    main_storage_name=main_storage_name,
                                                                    workspace_name=workspace_name,
                                                                    deployment_name=deployment_name,
                                                                    deployment_worker_id=str(result_dic["deployment_worker_id"]))
                with open("{}/{}".format(deployment_worker_log_dir, POD_RUN_TIME_FILE_NAME), mode="r", encoding="utf8") as f:
                    run_time_dic = json.load(f)
                # if end_time >= worker pod run time -> delete worker
                if common.date_str_to_timestamp(run_time_dic["end_time"], POD_RUN_TIME_DATE_FORMAT)<=common.date_str_to_timestamp(end_time, POD_RUN_TIME_DATE_FORMAT):
                    if get_worker_list:
                        complete_delete_list.append(int(result_dic["deployment_worker_id"]))
                    else:
                        # result=delete_deployment_worker(int(result_dic["deployment_worker_id"]))
                        res, message = stop_deployment_worker(deployment_worker_id=int(result_dic["deployment_worker_id"]))
                # if start_time > end time 일때 pass
                elif common.date_str_to_timestamp(run_time_dic["start_time"], POD_RUN_TIME_DATE_FORMAT)>common.date_str_to_timestamp(end_time, POD_RUN_TIME_DATE_FORMAT):
                    pass
                else:
                    if get_worker_list:
                        partial_delete_list.append(int(result_dic["deployment_worker_id"]))
                    else:
                        for mode in ['nginx', 'api']:
                            time_key=mode_time_dic[mode]
                            for log_dic in result_dic[mode_log_dic[mode]]:
                                if common.date_str_to_timestamp(log_dic[time_key])>=common.date_str_to_timestamp(end_time):
                                    break


                            split_str = split_str_dic[mode].format(log_dic[time_key])
                            with open("{}/{}".format(deployment_worker_log_dir, mode_path_dic[mode]), mode="r", encoding="utf8") as f:
                                log_str_list=f.read().split(split_str)[1:]
                            with open("{}/{}".format(deployment_worker_log_dir, mode_path_dic[mode]), mode="w", encoding="utf8") as f:
                                f.write("{"+split_str+split_str.join(log_str_list))
                            # if mode=="api":
                            #     idx = result_dic[mode_log_dic[mode]].index(log_dic)
                            #     status_dic={
                            #             "success":len([dic for dic in result_dic[mode_log_dic[mode]][idx:] if dic["status"]=="success"]),
                            #             "error":len([dic for dic in result_dic[mode_log_dic[mode]][idx:] if dic["status"]=="error"])
                            #         }
                            #     with open("{}/{}".format(deployment_worker_log_dir, POD_API_LOG_COUNT_FILE_NAME), mode="w", encoding="utf8") as f:
                            #         json.dump(status_dic, f, indent=4, ensure_ascii=False)
                            #     run_time_dic["start_time"]=datetime.strftime(datetime.now(), POD_RUN_TIME_DATE_FORMAT)
                            #     with open("{}/{}".format(deployment_worker_log_dir, POD_RUN_TIME_FILE_NAME), mode="w", encoding="utf8") as f:
                            #         json.dump(run_time_dic, f, ensure_ascii=False)
        if get_worker_list:
            if len(complete_delete_list)==0 and len(partial_delete_list)==0:
                return response(status=0, message="No worker in time range to delete")
            else:
                result={
                    "complete":complete_delete_list,
                    "partial":partial_delete_list
                }
                return response(status=1, result=result, message="success getting worker list")
        else:
            return response(status=1, message="success deleting log")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="deleting log error")

def get_running_worker_dir(workspace_id, deployment_id):
    error_worker_list=[]
    running_worker_list=[]

    # deployment_status_list = deployment_redis.get_deployment_worker_status_list(workspace_id=workspace_id, deployment_id=deployment_id)
    deployment_status_list = []
    tmp_workspace_pod_status = redis_client.hget(WORKSPACE_PODS_STATUS, workspace_id)
    if tmp_workspace_pod_status is None:
        data = dict()
        if tmp_workspace_pod_status is None:
            data = dict()
        else:
            data = json.loads(tmp_workspace_pod_status)

        deployment_data = data.get('deployment', dict())
        for data_deployment_id, data_deployment_list in deployment_data.items():
            try:
                if int(data_deployment_id) == deployment_id:
                    deployment_status_list = data_deployment_id
                    break
            except:
                pass

    if len(deployment_status_list) > 0:
        for key, value in deployment_status_list.items():
            if value["status"] == "running":
                running_worker_list.append(key)
            else:
                error_worker_list.append(key)

    return {
        "running_worker_list" : running_worker_list,
        "error_worker_list" : error_worker_list
    }

def check_worker_dir_and_install(workspace_name, deployment_name, worker_dir_list): 
    worker_dir_list=[str(i) for i in worker_dir_list]
    status_list=[]
    main_storage_name = db_deployment.get_workspace_info_storage(workspace_name=workspace_name)["main_storage_name"]
    for worker_id_str in worker_dir_list:
        deployment_worker_log_dir = JF_DEPLOYMENT_WORKER_LOG_DIR_PATH.format(main_storage_name=main_storage_name,
                                                                            workspace_name=workspace_name, 
                                                                            deployment_name=deployment_name, 
                                                                            deployment_worker_id=int(worker_id_str))
        try:
            if POD_NGINX_ACCESS_LOG_FILE_NAME not in os.listdir(deployment_worker_log_dir):
                # return False
                status_list.append(False)
        except FileNotFoundError:
            status_list.append(False)

    if len(status_list)==len(worker_dir_list):
        return False
    return True

def check_deployment_worker_log_dir(workspace_id, workspace_name, deployment_name, start_time=None, end_time=None, deployment_worker_id=None):
    result = {
        "error":1,
        "message":"No worker made",
        "log_dir":[]
    }
    if start_time==None:
        start_time_ts=0
    else:
        start_time_ts=common.date_str_to_timestamp(start_time)
    if end_time==None:
        end_time_ts=30000000000
    else:
        end_time_ts=common.date_str_to_timestamp(end_time)
    
    workspace_info = db_deployment.get_workspace_info_storage(workspace_name=workspace_name)
    deployment_info = db_deployment.get_deployment(deployment_name=deployment_name, workspace_id=workspace_id)
    
    main_storage_name = workspace_info["main_storage_name"]
    log_dir_path = JF_DEPLOYMENT_PATH.format(main_storage_name=main_storage_name, workspace_name=workspace_name, deployment_name=deployment_name)+"/log"

    # print( workspace_info.get("workspace_id"))
    tmp_workspace_pod_status = redis_client.hget(WORKSPACE_PODS_STATUS, workspace_info.get("id"))
    redis_pod_list = json.loads(tmp_workspace_pod_status)
    deployment_redis_list = redis_pod_list.get('deployment', dict())
    deployment_worker_redis_list = deployment_redis_list.get(str(deployment_info.get("id")))

    if os.path.exists(log_dir_path)==False:
        return result
    if deployment_worker_id!=None:
        log_dir_list = [str(deployment_worker_id)]
    else:
        log_dir_list = os.listdir(log_dir_path)
        
    for log_dir in log_dir_list:
        if os.path.isdir(os.path.join(log_dir_path, str(log_dir))):
            deployment_worker_run_time_file_path = GET_POD_RUN_TIME_FILE_PATH_IN_JF_API(main_storage_name=main_storage_name,
                                                                                        workspace_name=workspace_name,
                                                                                        deployment_name=deployment_name,
                                                                                        deployment_worker_id=int(log_dir))
            if os.path.exists(deployment_worker_run_time_file_path):
                run_time_info=common.load_json_file(deployment_worker_run_time_file_path) # 경우에 따라서는 retry를 하지 않아도 되는 상황이 생길 수 있음
                if run_time_info !=None:
                # try:
                    run_start_ts = common.date_str_to_timestamp(run_time_info["start_time"])
                    run_end_ts = common.date_str_to_timestamp(run_time_info["end_time"])
                    if run_start_ts>end_time_ts or run_end_ts<start_time_ts:
                        result["message"]="No worker in time range"
                    else:
                        result["log_dir"].append(log_dir)
                # try:
                #     with open(deployment_worker_run_time_file_path, "r") as f:
                #         run_time_data = f.read()
                #         run_time_info = json.loads(run_time_data)
                #     run_start_ts = common.date_str_to_timestamp(run_time_info["start_time"])
                #     run_end_ts = common.date_str_to_timestamp(run_time_info["end_time"])
                #     if run_start_ts>end_time_ts or run_end_ts<start_time_ts:
                #         result["message"]="No worker in time range"
                #     else:
                #         result["log_dir"].append(log_dir)
                # except:
                #     traceback.print_exc()
                #     continue
            # elif check_worker_dir_and_install(workspace_name, deployment_name, [log_dir])==False:
            elif deployment_worker_redis_list is not None and str(log_dir) in deployment_worker_redis_list:
                if deployment_worker_redis_list.get(str(log_dir)).get("status") == "installing":
                    result["message"]="Worker Installing"
                    
    if len(result["log_dir"])==0:
        return result
    result["error"]=0
    result["message"]=""
    return result

# API 코드 생성 =============================================================================================
custom_deployment_json_str_ex={
    "api_file_name":"dddkfsdf.py",
    "checkpoint_load_dir_path_parser":"weight_dir", # 모놀리식 - 체크포인트를 불러올 디렉토리 경로 입력용 파서
    "checkpoint_load_file_path_parser":"weight",    # 모놀리식 - 특정 체크포인트를 지정한 파일 경로 입력용 파서
    "deployment_num_of_gpu_parser":None,            # 모놀리식 - 배포에 사용할 총 GPU 개수 입력용 파서

    "deployment_input_data_form_list": [
        {
            "method": "POST",
            "location": "form",
            "api_key": "coordinate",
            "value_type": "str",
            "category": "canvas-coordinate",
            "category_description": "IMG (jpg, jpeg, png, bmp)"
        }
    ],
    "deployment_output_types": [
        "text",
        "columnchart",
        "piechart"
    ]
}

def create_deployment_api(custom_deployment_json_str):
    try:
        custom_deployment_json_rep = custom_deployment_json_str.replace("\'", "\"")
        # print(custom_deployment_json_rep)
        custom_deployment_json = json.loads(custom_deployment_json_rep)
        system_info_json={}
        for key in custom_deployment_json.keys():
            if key in ["api_file_name","deployment_output_types"]:
                pass
            else:
                system_info_json[key] = custom_deployment_json[key]
        for key in DEFAULT_CUSTOM_DEPLOYMENT_JSON:
            if key not in custom_deployment_json.keys():
                custom_deployment_json[key]=None

        # training_path = '/jf-data/workspaces/{}/trainings/{}/src'.format(workspace_name, training_name)
        # with open(os.path.join(JF_BUILT_IN_MODELS_PATH,'jf_auto_gen_api_example.py'), mode="r", encoding="utf8") as f:
        with open("/app/src/deployment/jf_auto_gen_api_example.py", mode="r", encoding="utf8") as f:
            jf_api_guide = f.read().splitlines()
        base_idx = jf_api_guide.index("시스템 정보")+3
        jf_api_guide.insert(base_idx, json.dumps(system_info_json, indent=4))


        # if "checkpoint_load_dir_path_parser" in custom_deployment_json.keys():
        if custom_deployment_json["checkpoint_load_dir_path_parser"]:
            idx = jf_api_guide.index("배포 실행 명령어 관련 자동생성 영역")
            jf_api_guide.insert(idx+2, "parser.add_argument('--{}', type=str, default='/job-checkpoints')".format(custom_deployment_json["checkpoint_load_dir_path_parser"]))
        # if "checkpoint_load_file_path_parser" in custom_deployment_json.keys():
        if custom_deployment_json["checkpoint_load_file_path_parser"]:
            idx = jf_api_guide.index("배포 실행 명령어 관련 자동생성 영역")
            jf_api_guide.insert(idx+2, "parser.add_argument('--{}', type=str, default='/job-checkpoints/ckpt')".format(custom_deployment_json["checkpoint_load_file_path_parser"]))
        # if "deployment_num_of_gpu_parser" in custom_deployment_json.keys():
        if custom_deployment_json["deployment_num_of_gpu_parser"]:
            idx = jf_api_guide.index("배포 실행 명령어 관련 자동생성 영역")
            jf_api_guide.insert(idx+2, "parser.add_argument('--{}', type=int, default=None)".format(custom_deployment_json["deployment_num_of_gpu_parser"]))
        
        if "deployment_input_data_form_list" in custom_deployment_json.keys():
            location_dic = {"body":"json", "args":"args.get", "file":"files", "form":"form"}
            input_form_list = custom_deployment_json["deployment_input_data_form_list"]
            idx = jf_api_guide.index("    TEST API 받아오는 부분 자동 생성 영역") + 2
            category_index={}
            for input_form in reversed(input_form_list):
                if input_form["category"] not in category_index.keys():
                    category_index[input_form["category"]]=1
                input_form["category_idx"]=category_index[input_form["category"]]
                category_index[input_form["category"]]+=1

            file_declared = False 
            other_declared = False
            for input_form in input_form_list:
                request_line=""
                category = input_form["category"].replace('-','_')
                if input_form["location"]=="args":
                    request_line = "    jf_{category}{category_idx} = request.query_params.get('{api_key}')"
                elif input_form["location"]=="file":
                    if not file_declared:
                        request_line = "    form_data = await request.form()"
                        file_declared = True
                    request_line += "\n    jf_{category}{category_idx}_files = form_data.getlist('{api_key}')"
                    request_line += "\n    jf_{category}{category_idx} = form_data.get('{api_key}')"
                else:
                    if not other_declared:
                        request_line = "    data = await request.{location}()"
                        other_declared = True
                    request_line += "\n    jf_{category}{category_idx} = data['{api_key}']"
                request_line = request_line.format(category = category, category_idx = input_form["category_idx"],
                                                                location = location_dic[input_form["location"]],
                                                                api_key = input_form["api_key"])
                jf_api_guide.insert(idx, request_line)
                idx = jf_api_guide.index(request_line) + 1
                
        if "deployment_output_types" in custom_deployment_json.keys():
            output_types = custom_deployment_json["deployment_output_types"]
            idx = jf_api_guide.index("    return output")-1
            jf_api_guide.insert(idx, "      }")
            jf_api_guide.insert(idx, "    output = {")
            for output_type in output_types:
                idx = jf_api_guide.index("    return output")-2
                output_idx = jf_api_guide.index('        "{}": ['.format(output_type))
                for i in range(5):
                    jf_api_guide.insert(idx+i, jf_api_guide[output_idx+i])
            idx = jf_api_guide.index("    return output")-1
            jf_api_guide[idx-2]=jf_api_guide[idx-2][:-1]

        form_example_index = jf_api_guide.index("    Output 자동 생성 영역 (OUTPUT Category)")
        del_end_index = jf_api_guide.index('        "table": [')
        for rm_idx in range(del_end_index-form_example_index + 5):
            del jf_api_guide[form_example_index+1]
        # with open(os.path.join(training_path,custom_deployment_json["run_code_name"]), mode="w", encoding="utf8") as f:
        #     f.write("\n".join(jf_api_guide))
        # os.system('chmod 664 {}/{}'.format(training_path,custom_deployment_json["run_code_name"]))
        result = {
            "custom_api_script":"\n".join(jf_api_guide),
            "api_file_name":custom_deployment_json["api_file_name"]
        }
        return response(status=1, result = result, message="Created default deployment api" )
    except:
        traceback.print_exc()
        return response(status=0, message="Creating default deployment api error")




# ========================================================
# HELM
# ========================================================

def uninstall_pod_deployment(workspace_id, deployment_id, deployment_worker_id):
    helm_namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
    command=f"helm uninstall -n {helm_namespace} deployment-pod-{deployment_id}-{deployment_worker_id} "
    try:
        # os.chdir("/app/helm/")
        subprocess.run(
            command, shell=True, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return True, ""
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip()
        print(e.stdout)
        print(err_msg)
        print(command)
        return False, err_msg

def uninstall_all_deployment(workspace_id, deployment_id):
    helm_namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)

    # deployment-pod-{deployment_id}- 끝에 '-' 없으면 안됨
    command_pod=f"helm list -n {helm_namespace} | grep deployment-pod-{deployment_id}- | \
        awk \'{{print $1}}\' | xargs helm uninstall -n {helm_namespace}  "

    try:
        # os.chdir("/app/helm/")
        subprocess.run(
            command_pod, shell=True, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        print(e.stdout)
        print(e.stderr)
        print(command_pod)
    
    command_svc_ing=f"helm list -n {helm_namespace} | grep deployment-svc-ing-{deployment_id} | \
        awk \'{{print $1}}\' | xargs helm uninstall -n {helm_namespace} "

    try:
        # os.chdir("/app/helm/")
        subprocess.run(
            command_svc_ing, shell=True, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return True, ""
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip()
        print(e.stdout)
        print(err_msg)
        print(command_svc_ing)
        return False, err_msg


# ====================================================================================








# ========================================================
# CODE BACKUP
# ========================================================
    
# class DeploymentStatus():
#     """워커마다의 status가 아닌, Deployment 배포 전체의 상태를 보여줌"""
#     def __init__(self):
#         self.deployment_status = KUBE_POD_STATUS_STOP
#         self.worker_count = 0
#         self.worker_status_dict = {KUBE_POD_STATUS_RUNNING: 0, KUBE_POD_STATUS_INSTALLING:0, KUBE_POD_STATUS_ERROR: 0, KUBE_POD_STATUS_PENDING : 0}
#         self.worker_usage_case = {"gpu":0 , "cpu": 0}
#         self.worker_configurations = [] # 필요 -> 배포 화면 워커 파란색 부분 표시 클릭시 나타남
#         self.running_worker_list = [] # TODO -> admin 에서 사용

#     def set_status(self, workspace_id, deployment_id):
#         deployment_worker_db_list = db_deployment.get_deployment_worker_list(deployment_id=deployment_id, running=True)
#         deployment_worker_redis_list = deployment_redis.get_deployment_worker_status_list(workspace_id=workspace_id, deployment_id=deployment_id)
#         worker_status_dict = self.worker_status_dict
#         # deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
        
#         # if deployment_info:
#         #     self.worker_configurations = None #[deployment_info["resource_name"]]

#         for deployment_worker_info in deployment_worker_db_list:
#             if str(deployment_worker_info["id"]) in deployment_worker_redis_list:
#                 deployment_worker_status = deployment_worker_redis_list[str(deployment_worker_info["id"])]
#             else:
#                 # TODO DB에는 있는데 redis에 없는 경우, 아직 redis에서 status 가 업데이트 안된 경우
#                 deployment_worker_status = {"status" : "installing"}

#             # if deployment_worker_status == KUBE_POD_STATUS_RUNNING:
#                 # 'wokrer' : {'count' : 1, 'status': {'running': 0, 'installing': 1, 'error': 0}}
#             self.worker_count += 1
#             if deployment_worker_status["status"] != None:
#                 self.worker_status_dict[deployment_worker_status["status"]] += 1
#             else:
#                 self.worker_status_dict["installing"] += 1
#             # 'status' : 'stop', 'installing', 'ruuning'
#             _worker_status = 'stop'
#             if worker_status_dict[KUBE_POD_STATUS_RUNNING] > 0 : #and worker_status_dict[KUBE_POD_STATUS_ERROR] == 0:
#                 self.deployment_status = KUBE_POD_STATUS_RUNNING
#             elif worker_status_dict[KUBE_POD_STATUS_ERROR] > 0:
#                 self.deployment_status = KUBE_POD_STATUS_ERROR
#             elif worker_status_dict[KUBE_POD_STATUS_INSTALLING] > 0:
#                 self.deployment_status = KUBE_POD_STATUS_INSTALLING
#             else:
#                 self.deployment_status = KUBE_POD_STATUS_PENDING
                
#             if deployment_worker_info['instance_type'] == "gpu":
#                 self.worker_usage_case["gpu"] += 1
#             elif deployment_worker_info['instance_type'] == "cpu":
#                 self.worker_usage_case["cpu"] += 1
            
#             # running_worker_list
#             self.running_worker_list.append({
#                 "id": deployment_worker_info.get("id"), # For stop button
#                 "status" : deployment_worker_status["status"],
#                 "gpu_count": deployment_worker_info.get("gpu_per_worker"),
#                 "configurations": deployment_worker_info.get("gpu_name"),
#                 "description": deployment_worker_info.get("description"),
#                 "create_datetime": deployment_worker_info.get("start_datetime")
#             })
#     def get_status(self):
#         # configurations = common.configuration_list_to_db_configuration_form(self.worker_configurations).split(",")
#         return {
#             "status": self.deployment_status,
#             "worker":{
#                 "count": self.worker_count,
#                 "status": self.worker_status_dict,
#                 "resource_usage": self.worker_usage_case,
#                 "configurations": self.worker_configurations # 워커 파란색 부분 표시 클릭시 나타남
#             },
#         }
#     def get_running_worker_list(self):
#         return self.running_worker_list


# ***********************************************************************************************
# TODO 삭제 코드
# ***********************************************************************************************
# def get_deployment_run_time_list(deployment_id=None, workspace_name=None, deployment_name=None, *args, **kwargs):
#     """
#     Description : deployment_id or workspace_name deployment_name 조합으로 해당 조건에 맞는 worker 들의 run time 정보를 list로 가져오는 함수

#     Args :
#         deployment_id (int) : 
#         ----------------------
#         workspace_name (str) :
#         deployment_name (str) :

#     Returns :
#         (list): [ { "start_time": "2022-03-10 03:24:13", "end_time": "2022-03-10 05:49:31" } ... ]
#     """
    
#     if deployment_id is not None:
#         deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
#         if deployment_info is None:
#             return []
#         workspace_name = deployment_info["workspace_name"]
#         deployment_name = deployment_info["name"]

#     run_time_info_list = []
#     for deployment_worker_id in get_deployment_worker_list_from_folder(workspace_name=workspace_name, deployment_name=deployment_name):
#         run_time_info = get_deployment_worker_run_time_info(workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id, *args, **kwargs)
#         if run_time_info is not None:
#             run_time_info_list.append(run_time_info)

#     return run_time_info_list

# def get_deployment_run_time(deployment_id=None, workspace_name=None, deployment_name=None, *args, **kwargs):
#     """
#     Description : deployment_id or workspace_name deployment_name 조합으로 해당 조건에 맞는 deployment의 run_time의 ts 값 내려주는 함수

#     Args :
#         deployment_id (int) : 
#         ----------------------
#         workspace_name (str) :
#         deployment_name (str) :

#     Returns :
#         (int): run time timestamp
#     """
#     import utils.common as common
#     run_time_list = get_deployment_run_time_list(deployment_id=deployment_id, workspace_name=workspace_name, deployment_name=deployment_name, *args, **kwargs)
#     # print("RUN TIME LIST" , run_time_list)
#     run_time_list = [dic for dic in run_time_list if dic!={}]
#     run_time_list = sorted(run_time_list, key=lambda run_time: (run_time["start_time"], run_time["end_time"]))

#     base_start_time_ts = -1
#     base_end_time_ts = -1
#     run_time_ts = 0
#     for i, run_time in enumerate(run_time_list):
#         current_start_time_ts = common.date_str_to_timestamp(run_time["start_time"])
#         current_end_time_ts = common.date_str_to_timestamp(run_time["end_time"])
        
#         if base_start_time_ts == -1:
#             base_start_time_ts = current_start_time_ts
#         if base_end_time_ts == -1:
#             base_end_time_ts = current_end_time_ts
            
#         if (base_start_time_ts <= current_start_time_ts and current_start_time_ts <= base_end_time_ts) and i != len(run_time_list) -1 :
#             base_end_time_ts = current_end_time_ts
#         else:
#             if i == len(run_time_list) -1:
#                 base_end_time_ts = current_end_time_ts
#             run_time_ts += base_end_time_ts - base_start_time_ts
#             base_start_time_ts = -1
#             base_end_time_ts = -1
#     return run_time_ts


# def get_deployment_instance_gpu_list(workspace_id, deployment_id):
#     # deployment에서 단일 인스턴스만 선택했으므로 한종류 GPU 만 나옴
#     res = dict()
#     try:
#         # deployment의 instance gpu 정보
#         deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
#         res = {
#             "instance_type" : deployment_info["instance_type"],
#             "instance_id" : deployment_info["instance_id"], # DB에서 instance_id를 저장함 -> resource_group_id 조회가능
#             "gpu_name" : deployment_info.get("gpu_name"),
#             "gpu_total" : deployment_info.get("instance_allocate", 0) * deployment_info.get("gpu_allocate", 0) 
#                 if deployment_info["instance_type"] == INSTANCE_TYPE_GPU else None,
#             "gpu_allocate" : deployment_info.get("gpu_per_worker", None)
#         }
#     except Exception as e:
#         traceback.print_exc()
#     return res

# def get_run_code_list_from_src(workspace_name, project_name, storage_name, ignore_folders=None):
#     config_file_list = []
#     try:
#         # example) /jf-data/workspaces/no-delete/projects/test/src
#         # X training_src_path = f"/jf-data/{storage_name}/main/{workspace_name}/projects/{project_name}/src"
#         # training_src_path = f"/jf-data/{storage_name}/main/{workspace_name}/projects/{project_name}"
        

#         run_code_list = []
#         config_file_list = []
#         training_src_path = get_project_src_path(storage_name=storage_name, workspace_name=workspace_name, project_name=project_name)
#         APP_POD_BASE_PATH = f"/jf-data/{storage_name}/main/{workspace_name}/projects/"
        
#         if ignore_folders is None:
#             ignore_folders = ['datasets', 'training_logs', '.ipynb_checkpoints']

#         for (path, dirs, files) in os.walk(training_src_path):
#             # 특정 폴더를 무시하기 위해 dirs 리스트 수정
#             dirs[:] = [d for d in dirs if all(ignored not in d for ignored in ignore_folders)]
            
#             # if JF_TRAINING_JOB_LOG_DIR_POD_PATH == path.replace(training_src_path,''):
#             #     continue 
#             if ".ipynb_checkpoints" in path:
#                 continue
            
#             for filename in files:
#                 if filename.split(".")[-1] in ["py", "sh"]:
#                     """ example)
#                     path /jf-data/storage-local-nfs/main/wsnew/projects/newtraining
#                     filename api.py
#                     training_src_path /jf-data/storage-local-nfs/main/wsnew/projects/newtraining
#                     """
#                     run_code_list.append("/root/project{}/{}".format(path, filename).replace(training_src_path,''))
#                 else:
#                     config_file_list.append("/root/project{}/{}".format(path, filename).replace(training_src_path,''))
#         return run_code_list, config_file_list
#     except Exception as e:
#         traceback.print_exc()
#         return [], []

# def get_project_src_path(storage_name=None, workspace_name=None, project_name=None, run_code=None):
#     if run_code:
#         run_code_src = run_code.replace("/root/project/", "")
#         project_src_path = f"/jf-data/{storage_name}/main/{workspace_name}/projects/{project_name}/{run_code_src}"
#     else:
#         project_src_path = f"/jf-data/{storage_name}/main/{workspace_name}/projects/{project_name}" # /src
#     return project_src_path



# ***********************************************************************************************
# nginx call 차트: 배포 카드리스트 아래 call 그래프, 워커 목록 nginx call 그래프
# ***********************************************************************************************
# def get_deployment_worker_nginx_access_log_per_hour_info_list(deployment_worker_id, workspace_name, deployment_name):
#     """
#     기존코드
#         main_storage_name = db_deployment.get_workspace_info_storage(workspace_name=workspace_name)["main_storage_name"]
#         deployment_worker_nginx_access_log_per_hour_file_path = GET_POD_NGINX_ACCESS_LOG_PER_HOUR_FILE_PATH_IN_JF_API(main_storage_name=main_storage_name, workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
#         nginx_access_log_per_hour_info_list = []
#         with open(deployment_worker_nginx_access_log_per_hour_file_path, "r") as f:
#             per_hour_data_list = f.readlines()
#             for per_hour_data in per_hour_data_list:
#                 nginx_access_log_per_hour_info_list.append(json.loads(per_hour_data))
#     데이터
#     nginx_access_log_per_hour_info_list
#         [{'time': '2024-12-05T01', 'count': 5, 'median': 0.009, 'nginx_abnormal_count': 0, 'api_monitor_abnormal_count': 0},
#          {'time': '2024-12-05T02', 'count': 5, 'median': 0.006, 'nginx_abnormal_count': 0, 'api_monitor_abnormal_count': 0}]
#     """
#     try:
#         # 0.018677711486816406 total 2~3s
#         start_time = time.time()
#         # main_storage_name = db_deployment.get_workspace_info_storage(workspace_name=workspace_name)["main_storage_name"]
#         # deployment_worker_nginx_access_log_per_hour_file_path = GET_POD_NGINX_ACCESS_LOG_PER_HOUR_FILE_PATH_IN_JF_API(main_storage_name=main_storage_name, workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
#         # nginx_access_log_per_hour_info_list = []
#         # with open(deployment_worker_nginx_access_log_per_hour_file_path, "r") as f:
#         #     per_hour_data_list = f.readlines()
#         #     for per_hour_data in per_hour_data_list:
#         #         nginx_access_log_per_hour_info_list.append(json.loads(per_hour_data))
#         nginx_access_per_hour_data = svc_mon.get_efk_deployment_worker_log(worker_id=deployment_worker_id, key="nginxAccessPerHour")
#         if nginx_access_per_hour_data is None:
#             return []
#         data = nginx_access_per_hour_data.split(' ')
#         nginx_access_log_per_hour_info_list = [json.loads(x) for x in data]
#         print("process time : ", time.time() - start_time)
#     except FileNotFoundError as fne:
#         return []
#     except json.decoder.JSONDecodeError as je:
#         return []
#     except Exception as e:
#         traceback.print_exc()
#         return []
#     return nginx_access_log_per_hour_info_list

# def get_deployment_worker_nginx_call_count(workspace_name, deployment_name, deployment_worker_id):
#     result = {'total_count': 0, 'success_count': 0}
#     main_storage_name = db_deployment.get_workspace_info_storage(workspace_name=workspace_name)["main_storage_name"]
#     nginx_log_count_file = GET_POD_NGINX_LOG_COUNT_FILE_PATH_IN_JF_API(main_storage_name=main_storage_name, workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
#     try:
#         nginx_log_count_info = common.load_json_file(file_path=nginx_log_count_file)
#         if nginx_log_count_info is None:
#             return result

#         result["total_count"] =  nginx_log_count_info.get("total_count")
#         result["success_count"] =  nginx_log_count_info.get("success_count")
#         return result
#     except:
#         traceback.print_exc()
#         return result

# def get_nginx_access_per_hour_chart(time_table, log_per_hour_info_list, data_key):
#     time_table = dict(time_table)
#     for data in log_per_hour_info_list:
#         try:
#             common.update_dict_key_count(dict_item=time_table, key=data[DEPLOYMENT_NGINX_PER_TIME_KEY], add_count=data[data_key], exist_only=True)        
#         except KeyError as ke:
#             # traceback.print_exc()
#             pass
#     chart_data = list(time_table.values())
#     chart_data.reverse()
#     # 최소 개수가 24개
#     if len(chart_data) < 24:
#         dummy = [0] * ( 24 - len(chart_data) )
#         chart_data = dummy + chart_data
#     return chart_data       

# def get_call_count_per_hour_chart(time_table, log_per_hour_info_list):
#     return get_nginx_access_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list, data_key=DEPLOYMENT_NGINX_PER_TIME_NUM_OF_CALL_LOG_KEY)

# def get_median_per_hour_chart(time_table, log_per_hour_info_list):
#     return get_nginx_access_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list, data_key=DEPLOYMENT_NGINX_PER_TIME_RESPONSE_TIME_MEDIAN_KEY)

# def get_nginx_abnormal_call_count_per_hour_chart(time_table, log_per_hour_info_list):
#     return get_nginx_access_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list, data_key=DEPLOYMENT_NGINX_PER_TIME_NUM_OF_ABNORMAL_LOG_COUNT_KEY)

# def get_api_monitor_abnormal_call_count_per_hour_chart(time_table, log_per_hour_info_list):
#     return get_nginx_access_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list, data_key=DEPLOYMENT_API_MONITOR_PER_TIME_NUM_OF_ABNORMAL_LOG_COUNT_KEY)
# ----------------------------------------------------------------------------------------------------------------------------------------------------------

# def get_nginx_per_hour_time_table_dict(log_per_hour_info_list, time_time_count=24):
#     if len(log_per_hour_info_list) == 0:
#         return {}
#     try:
#         sorted_log_per_hour_info_list = sorted(log_per_hour_info_list, key=lambda log_per_hour_info_list: (log_per_hour_info_list[DEPLOYMENT_NGINX_PER_TIME_KEY]))
#     except KeyError as ke:
#         traceback.print_exc()
#         return {}
#     last_time = sorted_log_per_hour_info_list[-1][DEPLOYMENT_NGINX_PER_TIME_KEY]
#     last_timestamp = common.date_str_to_timestamp(date_str=last_time, date_format=DEPLOYMENT_NGINX_NUM_OF_LOG_PER_HOUR_DATE_FORMAT)
#     time_table = {}
#     time_interval = 60 * 60 # test - (hour = 60 * 60)
#     # last 24 item time list
#     for i in range(time_time_count):
#         date_time = common.get_date_time(timestamp=last_timestamp - time_interval * i, date_format=DEPLOYMENT_NGINX_NUM_OF_LOG_PER_HOUR_DATE_FORMAT)
#         time_table[str(date_time)] = 0
#     return time_table

# def get_deployment_nginx_access_log_per_hour_list(deployment_id, workspace_name, deployment_name):
#     deployment_worker_id_list = [str(i.get("id")) for i in db_deployment.get_deployment_worker_list(deployment_id=deployment_id, running="ALL")]
#     worker_num_of_log_per_hour_info_list = []
#     for deployment_worker_id in deployment_worker_id_list:
#         per_hour_info_list = get_deployment_worker_nginx_access_log_per_hour_info_list(workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
#         if per_hour_info_list:
#             worker_num_of_log_per_hour_info_list += per_hour_info_list
#     return worker_num_of_log_per_hour_info_list
