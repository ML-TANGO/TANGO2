# Deployment Simulation
from utils.resource import response
from utils.TYPE import *
from utils.exception.exceptions import *
# from utils import settings

from utils.redis_key import WORKSPACE_PODS_STATUS
from utils.msa_db import db_deployment
import random
import traceback
from deployment import service as deployment_svc

# 전체 조회
def get_simulation_list(workspace_id):
    res = []
    try:
        deployment_list = db_deployment.get_service_list(workspace_id=workspace_id)

        # redis deployment
        redis_pod_list = json.loads(deployment_svc.redis_client.hget(WORKSPACE_PODS_STATUS, workspace_id))
        deployment_redis_list = redis_pod_list.get('deployment', dict())
        
        # db workspace deployment list
        db_ws_dp_worker_list = db_deployment.get_deployment_worker_list(workspace_id=workspace_id, running=True) 
        # db_worker_list = {item["id"] : item for item in db_ws_dp_worker_list}
        db_workers_grouped_deployment_id = {
            deployment_id: [d for d in db_ws_dp_worker_list if d['deployment_id'] == deployment_id] 
                    for deployment_id in set(d['deployment_id'] for d in db_ws_dp_worker_list)
        }
        
        active_service_list = []
        other_service_list = []
        
        for item in deployment_list:
            if item.get("llm") == 1:
                continue

            # status ============================================================================
            deployment_worker_redis_list = deployment_redis_list.get(str(item["id"]))
            deployment_worker_db_list = db_workers_grouped_deployment_id.get(item["id"])
            status = {"status" : "stop", "reason" : None}
            if deployment_worker_db_list is not None:
                for db_worker_info in deployment_worker_db_list:
                    # status.worker.status
                    if deployment_worker_redis_list and str(db_worker_info.get("id")) in deployment_worker_redis_list:
                        if deployment_worker_redis_list.get(str(db_worker_info.get("id"))).get("status") == KUBE_POD_STATUS_RUNNING:
                            status["status"] = "running"
                            break
                        else:
                            status["status"] = deployment_worker_redis_list.get(str(db_worker_info.get("id"))).get("status")
            tmp_list = active_service_list if status["status"] == "running" else other_service_list

            # model ============================================================================


            # result ============================================================================
            tmp_list.append({
                "id" : item["id"],
                "name" : item["name"],
                "description" : item["description"],
                "creator" : item["creator"],
                "create_datetime" : item["create_datetime"],
                "input_type": item["input_type_list"],
                "status" : status,
                "type" : item.get("model_type")
            })

        res = active_service_list + other_service_list
    except Exception as e:
        traceback.print_exc()
    return res


# 상세조회
def get_service(service_id):
    """
    data_input_form_list example
        [{  
            "deployment_id": 670,
            "location": "body",
            "method": "GET",                # list에서 바로 이 값을 사용 X -> api_method라는 key에서 값을 사용함
            "api_key": "test111",           # 입력데이터 - API Key: value 부분
            "category": "text",             # 입력데이터 - API Key: 타원부분 (이 값에 따라 input 타입 결정)
            "category_description": "설명", # 입력데이터 - API Key: value 옆에 설명이 있을경우 i 아이콘이 생김
            "value_type": "image", 
        },...]
    """
    service_info = db_deployment.get_service(deployment_id=service_id)
    data_input_form_list = service_info.get("data_input_form_list")
    if data_input_form_list is not None:
        tmp = "[" + data_input_form_list + "]"
        data_input_form_list = json.loads(tmp)
    
    if service_info is not None:
        result = {
            "name": service_info["name"],
            "id": service_info["id"],
            "creator": service_info["creator"],
            "description": service_info["description"],
            "type": "custom", # builtin / custom (name 위에 있음)
            "date": service_info["create_datetime"], # TODO 현재는 worker create time -> 워커시간으로 변경 필요
            "api_address": deployment_svc.get_deployment_full_api_address(deployment_id=service_id), #api_address, # From Node
            # "built_in_model_name" : service_info["built_in_model_id"], # "모델 이름" TODO 나중에 name으로 변경
            "data_input_form_list" : data_input_form_list,
            "api_method" : "POST",
            # TODO 개선 -> 여러개 list, str 둘다 안됨 + method 에 따라서 input type도 바껴야되는데 안됨
            # -> ex) { "POST" : [post input list], "GET" : [get input list]}
            # "api_method" : ",".join(set([data_input_form["method"] for data_input_form in data_input_form_list])), # 여러개 안됨??? ex) "POST,GET"
            # TODO ???? =====================================
            # "input_type": "image", # 적용 X -> data_input_form_list 사용
            # "input_type_description": "aaaaaaaaa", # 적용 X -> data_input_form_list 사용
            # "status": status, # 사용하는 곳 없음??
            # "ports" : ports, # 삭제 확정
        }
        return result
    else:
        raise Exception("Not Exist Service")
        # return response(status=0, message="Not Exist Service")