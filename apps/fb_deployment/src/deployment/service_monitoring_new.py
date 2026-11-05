import traceback, os, json, subprocess, statistics, time, logging, functools, threading, requests
from datetime import datetime

from utils.resource import response
from utils.exception.exceptions import *
from utils.exception.exceptions_deployment import *

from utils.TYPE import *
from utils import settings
import utils.common as common
from utils.msa_db import db_user, db_deployment
from utils.redis_key import DEPLOYMENT_WORKER_RESOURCE_LIMIT, GPU_RESOUCE_UTILIZATION, WORKSPACE_PODS_STATUS, DEPLOYMENT_WORKER_RESOURCE, GPU_INFO_RESOURCE
from utils.redis import get_redis_client
from utils.common import byte_to_gigabyte
from collections import defaultdict

# REDIS ==================================================================
"""
DEPLOYMENT_WORKER_RESOURCE
[worker] 971 :{'cpu_cores': {'total': 0, 'usage': 0, 'percentage': 0}, 'ram': {'total': 0, 'usage': 0, 'percentage': 0}, 'gpus': 0, 'cpu_history': [], 'mem_history': [], 'gpu_history': []}
"""

# ===================================================================================
# 배포 > 모니터링
# ===================================================================================
# 배포 > 모니터링 > 상단 박스 8개
def get_deployment_dashboard_status(deployment_id, start_time=None, end_time=None):
    """
    total_info(dict): 맨 위 4개
        deployment_run_time: 배포작동시간
        total_call_count: 전체 콜 수
        * total_log_size: 전체콜수 옆 로그 사이즈
        total_success_rate: 응답 성공률
        running_worker_count: 작동 중인 워커
        * error_worker_count: 에러워커 수
        * restart_count: 재시작 워커 수 
    resource_info: 위에서 2번째 (4개 게이지 차트) - min, max, average
        cpu_usage_rate(cpu사용률)
        ram_usage_rate(ram 사용률)
        gpu_core_usage_rate(gpu core 사용률)
        gpu_mem_usage_rate(gpu mem 사용률)
    worker_start_time: 가운데 - 범위(UTC+9) 에 들어감
    """
    init_rate = {"min" : 0, "max" : 0, "average" : 0}
    res = {
        "total_info" : {
            "restart_count": 0, 
            "running_worker_count": 0, # 작동중인 워커
            "error_worker_count":   0, # 0보다 크면 작동중인 워커 옆에 빨간색으로 표시됨
            "deployment_run_time" : 0, # 배포 작동시간
        },
        "resource_info" : {
            "cpu_usage_rate" : init_rate,
            "ram_usage_rate" : init_rate,
            "gpu_core_usage_rate" : init_rate,
            "gpu_mem_usage_rate" : init_rate,
            "gpu_use_mem": 0, # TODO
            "gpu_total_mem": 0, # TODO
            "gpu_mem_unit": "MB" # prometheus 수집 단위
        },
        "worker_start_time" : None
    }
    try:
        # DB, REDIS
        redis_client = get_redis_client()
        deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)
        workspace_name = deployment_info.get("workspace_name")
        deployment_name = deployment_info.get("name")
        workspace_id = deployment_info.get("workspace_id")
        deployment_worker_running_list = db_deployment.get_deployment_worker_list(deployment_id=deployment_id, running=True)

        tmp_workspace_pod_status = redis_client.hget(WORKSPACE_PODS_STATUS, workspace_id)
        redis_pod_list = json.loads(tmp_workspace_pod_status)
        deployment_redis_list = redis_pod_list.get('deployment', dict())
        deployment_worker_redis_list = deployment_redis_list.get(str(deployment_id))
        
        # total_info - worker count ============================================================
        restart_count = 0
        running_worker_count = 0
        error_worker_count = 0
        try:
            if deployment_worker_redis_list:
                for key, value in deployment_worker_redis_list.items():
                    restart_count += int(value['restart_count'])
                    if value['status'] == 'running':
                        running_worker_count += 1
                    if value['status'] == 'error':
                        error_worker_count += 1
        except:
            traceback.print_exc()
        res["total_info"]["restart_count"] = restart_count
        res["total_info"]["running_worker_count"] = running_worker_count
        res["total_info"]["error_worker_count"] = error_worker_count
        
        # total_info - worker running time & worker_start_time ===================================
        time_info = get_deployment_total_running_time_and_worker_start_time(deployment_id)
        res["total_info"]["deployment_run_time"] = time_info["total_running_time"]
        res["worker_start_time"] = time_info["worker_start_time"]

        # TODO total_info - call ======================================================================
        # log_dir_result = check_deployment_worker_log_dir(workspace_name=workspace_name, deployment_name=deployment_name)
        worker_id_list = [str(i.get("id")) for i in db_deployment.get_deployment_worker_list(deployment_id=deployment_id, running="ALL")]
        total_info = get_deployment_api_total_count_info(worker_dir_list=worker_id_list)
        res["total_info"]["total_call_count"] = total_info["total_call_count"]
        res["total_info"]["total_success_rate"] = total_info["total_success_rate"]
        res["total_info"]["total_log_size"] = total_info["total_log_size"]
        
        # resource_info - worker count ============================================================
        cpu_usage_list = []
        ram_usage_list = []
        gpu_core_usage_list = [] # TODO DCGM
        gpu_mem_usage_list = [] # TODO DCGM
        try:
            redis_all_worker_resource = redis_client.hgetall(DEPLOYMENT_WORKER_RESOURCE) # 워커 전체 가져옴, 계속 redis 연결 X
            tmp_gpu_info = redis_client.get(GPU_INFO_RESOURCE)
            if tmp_gpu_info is not None and len(tmp_gpu_info) > 0:
                gpu_info = json.loads(tmp_gpu_info)

            if redis_all_worker_resource is not None and len(redis_all_worker_resource) > 0:
                for worker in deployment_worker_running_list:
                    str_worker_id = str(worker.get("id"))
                    
                    ## cpu, ram
                    tmp_worker_resource = redis_all_worker_resource.get(str_worker_id)
                    if tmp_worker_resource is not None:
                        worker_resource = json.loads(tmp_worker_resource)
                        cpu_usage_list.append(float(worker_resource["cpu_cores"]["percentage"]))
                        ram_usage_list.append(float(worker_resource["ram"]["percentage"]))

                    ## gpu
                    worker_gpu_uuid = None
                    for _node, _node_gpu_list in gpu_info.items():
                        # uuid 조회
                        for uuid, uuid_gpu_info in _node_gpu_list.items():
                            if uuid_gpu_info['used_type'] == 'deployment' and 'used_deployment_worker' and uuid_gpu_info['used_info'] \
                                and uuid_gpu_info['used_info']['used_deployment_worker'] == str_worker_id:
                                    worker_gpu_uuid = uuid
                                    break

                        # GPU utilization 조회
                        if worker_gpu_uuid is not None:
                            tmp_gpu_utilization = redis_client.hget(GPU_RESOUCE_UTILIZATION, worker_gpu_uuid)
                            if tmp_gpu_utilization is not None and len(tmp_gpu_utilization) > 0:
                                gpu_utilization = json.loads(tmp_gpu_utilization)
                                gpu_core_usage_list.append(float(gpu_utilization["gpu_core"]))
                                gpu_mem_usage_list.append(gpu_utilization["gpu_mem"])
                
            res["resource_info"]["cpu_usage_rate"] = {"max" : max(cpu_usage_list, default=0) , "min" : min(cpu_usage_list, default=0), "average" : sum(cpu_usage_list) / len(cpu_usage_list) if len(cpu_usage_list) > 0 else 0}
            res["resource_info"]["ram_usage_rate"] = {"max" : max(ram_usage_list, default=0), "min" : min(ram_usage_list, default=0), "average" : sum(ram_usage_list) / len(ram_usage_list) if len(ram_usage_list) > 0 else 0}
            res["resource_info"]["gpu_core_usage_rate"] = {"max" : max(gpu_core_usage_list, default=0), "min" : min(gpu_core_usage_list, default=0), "average" : sum(gpu_core_usage_list) / len(gpu_core_usage_list) if len(gpu_core_usage_list) > 0 else 0} 
            res["resource_info"]["gpu_mem_usage_rate"] = {
                "max" : max(gpu_mem_usage_list, key=lambda x: x.get('percentage', 0)).get("percentage", 0) if len(gpu_mem_usage_list) > 0 else 0,
                "min" : min(gpu_mem_usage_list, key=lambda x: x.get('percentage', 0)).get("percentage", 0) if len(gpu_mem_usage_list) > 0 else 0, 
                "average" : sum(item.get("percentage", 0) for item in gpu_mem_usage_list) / len(gpu_mem_usage_list) if len(gpu_mem_usage_list) > 0 else 0
            }
            # gpu_use_mem, gpu_total_mem 현재는 워커들 평균값 보여줌
            res["resource_info"]["gpu_use_mem"] = sum(item.get("used", 0) for item in gpu_mem_usage_list) if len(gpu_mem_usage_list) > 0 else 0
            res["resource_info"]["gpu_total_mem"] = sum(item.get("total", 0) for item in gpu_mem_usage_list)  / len(gpu_mem_usage_list) if len(gpu_mem_usage_list) > 0 else 0
            
        except:
            traceback.print_exc()
        # ========================================================================================================================
        return response(status=1, message="success", result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, result=res, message="get dashboard status error")

def get_deployment_total_running_time_and_worker_start_time(deployment_id):
    # admin 배포 작동시간, user 배포 모니터링 사용
    try:
        total_running_time = 0
        worker_start_time = 0
        now = datetime.now()
        
        deployment_worker_all_list = db_deployment.get_deployment_worker_list(deployment_id=deployment_id, running="ALL")
        time_list = []
        for item in deployment_worker_all_list:
            if item.get("start_datetime") is not None:
                item_start_datetime = datetime.strptime(item.get("start_datetime"), '%Y-%m-%d %H:%M:%S')
            else:
                continue # start_datetime None인 경우 Pass
            
            if item.get("end_datetime") is not None:
                item_end_datetime = datetime.strptime(item.get("end_datetime"), '%Y-%m-%d %H:%M:%S')
            else:
                item_end_datetime = now
            time_list.append((item_start_datetime, item_end_datetime))
        time_list.sort(key=lambda x: x[0]) # 시작 시간 기준으로 정렬
    
        if len(time_list) > 0 and time_list[0][0] != None:
            ### worker_start_time
            worker_start_time = time_list[0][0].strftime('%Y-%m-%d %H:%M:%S')
                
            ### worker_running_time
            merged_ranges = [] # 겹치는 구간 병합
            current_start, current_end = time_list[0]
            for start, end in time_list[1:]:
                if start <= current_end: # 겹치는 구간이 있으면
                    current_end = max(current_end, end)  # 종료 시간을 업데이트
                else:
                    merged_ranges.append((current_start, current_end))  # 현재 구간을 추가
                    current_start, current_end = start, end
            merged_ranges.append((current_start, current_end)) # 마지막 구간 추가
            total_running_time = sum(round((end - start).total_seconds()) for start, end in merged_ranges)
        else:
            worker_start_time = now.strftime('%Y-%m-%d %H:%M:%S')
    except:
        traceback.print_exc()
        
    return {
        "total_running_time" : total_running_time,
        "worker_start_time" : worker_start_time
    }

# 배포 > 모니터링 > 게이지 차트 하단 > 워커 체크박스 리스트
def get_deployment_dashboard_running_worker(deployment_id, start_time=None, end_time=None):
    res = {
        "deployment_running_worker" : []
    }
    try:
        for item in db_deployment.get_deployment_worker_list(deployment_id=deployment_id,running="ALL"):
            res["deployment_running_worker"].append(item["id"])
        return response(status=1, result=res, message="success")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, result=res, message="get dashboard running worker error")

# 배포 > 워커 > 상단 4개 박스 (특정 워커일 경우) 
# 1. 작동중인 워커 조회
# 2. 중지된 워커 조회
def get_deployment_worker_dashboard_status(deployment_worker_id):
    result = {
        "total_info": {
            "total_call_count": 0,
            "total_success_rate": 0,
            "total_log_size": 0,
            "restart_count": "0",
            "deployment_run_time": 0
        },
        "worker_start_time": None
    }
    try:
        # DB, REDIS 정보
        info = db_deployment.get_deployment_worker(deployment_worker_id=deployment_worker_id)
        workspace_name = info.get("workspace_name")
        deployment_name = info.get("deployment_name")
        create_datetime = info.get("create_datetime")
        start_datetime = info.get("start_datetime")
        end_datetime = info.get("end_datetime")

        # 실제로 시작되지 않은 워커의 경우 start_datetime이 None임
        if start_datetime is None:
            start_datetime = create_datetime

        # worker_start_time, deployment_run_time
        result["worker_start_time"] = start_datetime
        if end_datetime is None:
            running_status = True
            result["total_info"]["deployment_run_time"] = round(
                (datetime.now() - datetime.strptime(start_datetime, '%Y-%m-%d %H:%M:%S')).total_seconds())
        else:
            running_status = False
            result["total_info"]["deployment_run_time"] = round(
                (datetime.strptime(end_datetime, '%Y-%m-%d %H:%M:%S') - datetime.strptime(start_datetime, '%Y-%m-%d %H:%M:%S')).total_seconds())
        
        # TODO EFK restart_count, total_call_count, total_success_rate, total_log_size ???
        # 중지된워커?? !!!!!!!!!! EFK에 정보가 저장되도록 해야함 !!!!!!!!!!!!!!!!!!!
        # TODO 중지된 워커는 redis에서 조회 불가능
        total_info = get_deployment_api_total_count_info(worker_dir_list=[deployment_worker_id])
        result["total_info"]["total_call_count"] = total_info.get("total_call_count")
        result["total_info"]["total_success_rate"] = total_info.get("total_success_rate")
        result["total_info"]["total_log_size"] = total_info.get("total_log_size")
        result["total_info"]["restart_count"] = total_info.get("restart_count")

        return response(status=1, result=result, message="success getting worker dashboard status")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, result=result, message="get worker dashboard status error")

# 배포 > 워커 > 상단 4개 박스 아래 resoource(cpu, gpu) graph
def get_deployment_worker_resource_usage_graph(deployment_worker_id, interval=None):
    result = {
        "cpu_cores": {
            "cpu_cores_total" : 0,
            "cpu_cores_usage" : 0
        },
        "ram": {
            "ram_total": 0,
            "ram_usage": 0
        },
        "gpus": 0,
        "cpu_history" : [], "mem_history" : [], "gpu_history" : [], "network": None, # TODO 삭제
        "status": {"status" : "stop"}
    }
    try:
        redis_client = get_redis_client()
        worker_info = db_deployment.get_deployment_worker(deployment_worker_id=deployment_worker_id)
        workspace_id = worker_info.get("workspace_id")
        deployment_id = worker_info.get("deployment_id")
        
        workspace_namespace = settings.JF_SYSTEM_NAMESPACE + "-" + str(workspace_id)
        deployment_list = redis_client.hget(WORKSPACE_PODS_STATUS, workspace_id)
        redis_deployment_worker_status = json.loads(deployment_list).get("deployment")

        deployment_worker_status = {"status" : "stop"}
        if redis_deployment_worker_status is not None:
            deployment_list = redis_deployment_worker_status.get(str(deployment_id))
            if deployment_list is not None:
                if str(deployment_worker_id) not in deployment_list:
                    deployment_worker_status = {"status" : "stop"}
                else:
                    deployment_worker_status = deployment_list.get(str(deployment_worker_id))
        
        tmp_redis_worker_resource = redis_client.hget(DEPLOYMENT_WORKER_RESOURCE, str(deployment_worker_id))
        if tmp_redis_worker_resource is not None:
            redis_worker_resource = json.loads(tmp_redis_worker_resource)
        else:
            redis_worker_resource = {'cpu_cores' :  {'total' : 0, 'usage' : 0, 'percentage' : 0},
                                     'ram' : {'total' : 0, 'usage' : 0, 'percentage' : 0}, 'gpus' : 0}

        result = {
            "cpu_cores": {
                "cpu_cores_total" : redis_worker_resource['cpu_cores']["total"], 
                "cpu_cores_usage" : redis_worker_resource['cpu_cores']["percentage"]
            },
            "ram": {
                "ram_total": byte_to_gigabyte(float(redis_worker_resource["ram"]['total'])),
                "ram_usage": redis_worker_resource["ram"]['percentage']
            },
            "gpus": redis_worker_resource.get("gpus"),
            "cpu_history" : redis_worker_resource.get("cpu_history"),
            "mem_history" : redis_worker_resource.get("mem_history"),
            "gpu_history" : redis_worker_resource.get("gpu_history"),
            "network": None, # TODO 삭제
            "status": deployment_worker_status
        }
        return response(status=1, result=result)
    except:
        traceback.print_exc()
        return response(status=0, result=result)

# 배포 > 워커 > 중간 워커 정보 (자세히보기) 
def get_deployment_worker_dashboard_worker_info(deployment_worker_id):
    result = {
            "description": None,
            "resource_info": {
                "configuration": [None], 
                "cpu_cores": None, 
                "ram": None,
                "gpu" : {"name" : None, "count" : 0}
                # "node": None,
            },
            "version_info": {
                "type": None, # TODO 삭제 version_type 모놀리식 코드
                "create_datetime": None,
                "docker_image": None,
                "training_name": None, 
                "run_code": None,
                "end_datetime": None
                # "job_info": None, 
                # "checkpoint": None, 
            },
            "version_info_changed": {
                "changed": False,
                "changed_items": []
            },
            # "running_info": deployment_worker_running_info # 모놀리식?
        }
    try:
        info = db_deployment.get_deployment_worker(deployment_worker_id=deployment_worker_id)
        result["description"] = info["description"]
        result["resource_info"]["configuration"] = [info["instance_name"]] # type list 아니면 터짐
        result["resource_info"]["cpu_cores"] = info["deployment_cpu_limit"]
        result["resource_info"]["ram"] = info["deployment_ram_limit"]
        result["resource_info"]["gpu"]["name"] = info["gpu_name"]
        result["resource_info"]["gpu"]["count"] = info["gpu_per_worker"]
        result["version_info"]["run_code"] = json.loads(info["command"])["script"] if info["command"] is not None else None,
        result["version_info"]["training_name"] = info["project_name"]
        result["version_info"]["docker_image"] = info["image_name"]
        result["version_info"]["create_datetime"] = info["start_datetime"]
        result["version_info"]["end_datetime"] = info["end_datetime"]
        
        return response(status=1, result=result)
    except:
        traceback.print_exc()
        return response(status=0, result=result, message="Dashboard Worker info get error")

# 배포 > 모니터링 & 워커 > API 호출 테이블 & 그래프
def get_deployment_api_monitor_graph(deployment_id, start_time, end_time, interval, absolute_location, worker_list, search_type="range", get_csv=False):
    """
    search_type
        range: 모니터링 부분 -> 유형 -> 범위검색
        live: 모니터링 부분 -> 유형 -> 실시간,
    worker_list
        일반적으로 조회할때 사용
        중지된 워커 조회할때 사용
    """
    try:
        info = db_deployment.get_deployment(deployment_id=deployment_id)
        workspace_name = info.get("workspace_name") 
        deployment_name = info.get("name")
        message = "Success getting dashboard history info"

        # 워커 리스트 check ==============================================================================
        if worker_list != None:
            worker_list = [int(i.strip()) for i in worker_list.split(",")]
        
        """
        # 파일 -> EFK
        else:
            # worker 없는경우
            log_dir_result = check_deployment_worker_log_dir(workspace_name=workspace_name, deployment_name=deployment_name,
                                                            start_time=start_time, end_time=end_time)
            if log_dir_result["error"]==1:
                message = log_dir_result["message"]
                # return response(status=0, message=log_dir_result["message"])
            else:
                worker_list = [int(i) for i in log_dir_result["log_dir"]]
        # check worker installing
        if worker_list !=None:
            
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
            
            if check_worker_dir_and_install(workspace_name, deployment_name, worker_list)==False:
                message = "Worker Installing"
            # return response(status=0, message="Worker Installing")
        """

        # Get info ==============================================================================
        result = get_result_from_history_file(workspace_name=workspace_name, deployment_name=deployment_name,
                                            worker_list=worker_list, start_time=start_time, end_time=end_time, 
                                            interval=interval, absolute_location=absolute_location, search_type=search_type)

        # 다운로드 기능 ==============================================================================
        if get_csv==True:
            if len(result["error_log_list"])==0:
                # raise DeploymentAbnormalHistoryCSVNotExistError
                return response(status=0, message="No abnormal history result")
            csv_result=[]
            csv_result.append(list(result["error_log_list"][0].keys()))
            for error_dic in result["error_log_list"]:
                csv_result.append(list(error_dic.values()))
                
            return common.csv_response_generator(data_list=csv_result)
            # return response(status=1, result=csv_result, message="Success getting abnormal history csv")
        return response(status=1, result=result, message=message)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="get dashboard history error")

# ===================================================================================
# EFK 대체, 실제 파일 호출하는 함수
# ===================================================================================
# EFK API
def get_efk_deployment_worker_log(worker_id, time=None, key=None):
    try:
        url = f"{settings.LOG_MIDDLEWARE_DNS}/v1/worker/{worker_id}"
        response = requests.post(url)
        response = response.json()
        return response.get(key) if key else response
    except Exception as e:
        print(e)
        return None

# 파일 사용 했던 함수 -----------------------------------------------------------------
# POD_NGINX_ACCESS_LOG_PER_HOUR_FILE_NAME="nginx_access_per_hour.log"
def get_deployment_worker_nginx_access_log_per_hour_info_list(deployment_worker_id, workspace_name=None, deployment_name=None):
    """
    기존코드
        main_storage_name = db_deployment.get_workspace_info_storage(workspace_name=workspace_name)["main_storage_name"]
        deployment_worker_nginx_access_log_per_hour_file_path = GET_POD_NGINX_ACCESS_LOG_PER_HOUR_FILE_PATH_IN_JF_API(main_storage_name=main_storage_name, workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
        nginx_access_log_per_hour_info_list = []
        with open(deployment_worker_nginx_access_log_per_hour_file_path, "r") as f:
            per_hour_data_list = f.readlines()
            for per_hour_data in per_hour_data_list:
                nginx_access_log_per_hour_info_list.append(json.loads(per_hour_data))
    데이터
    nginx_access_log_per_hour_info_list
        [{'time': '2024-12-05T01', 'count': 5, 'median': 0.009, 'nginx_abnormal_count': 0, 'api_monitor_abnormal_count': 0},
         {'time': '2024-12-05T02', 'count': 5, 'median': 0.006, 'nginx_abnormal_count': 0, 'api_monitor_abnormal_count': 0}]
    """
    try:
        # start_time = time.time()

        # main_storage_name = db_deployment.get_workspace_info_storage(workspace_name=workspace_name)["main_storage_name"]
        # deployment_worker_nginx_access_log_per_hour_file_path = GET_POD_NGINX_ACCESS_LOG_PER_HOUR_FILE_PATH_IN_JF_API(main_storage_name=main_storage_name, workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
        # nginx_access_log_per_hour_info_list = []
        # with open(deployment_worker_nginx_access_log_per_hour_file_path, "r") as f:
        #     per_hour_data_list = f.readlines()
        #     for per_hour_data in per_hour_data_list:
        #         nginx_access_log_per_hour_info_list.append(json.loads(per_hour_data))

        nginx_access_per_hour_data = get_efk_deployment_worker_log(worker_id=deployment_worker_id, key="nginxAccessPerHour")
        if nginx_access_per_hour_data is None:
            return []
        data = nginx_access_per_hour_data.split(' ')
        nginx_access_log_per_hour_info_list = [json.loads(x) for x in data]
        # print("process time : ", time.time() - start_time)
        return nginx_access_log_per_hour_info_list
    except FileNotFoundError as fne:
        return []
    except json.decoder.JSONDecodeError as je:
        return []
    except Exception as e:
        traceback.print_exc()
        return []

# POD_NGINX_LOG_COUNT_FILE_NAME="nginx_count.json"
def get_deployment_worker_nginx_call_count(deployment_worker_id):
# def get_deployment_worker_nginx_call_count(workspace_name, deployment_name, deployment_worker_id):
    result = {'total_count': 0, 'success_count': 0}
    """
    main_storage_name = db_deployment.get_workspace_info_storage(workspace_name=workspace_name)["main_storage_name"]
    nginx_log_count_file = GET_POD_NGINX_LOG_COUNT_FILE_PATH_IN_JF_API(main_storage_name=main_storage_name, workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
        nginx_log_count_info = common.load_json_file(file_path=nginx_log_count_file)
    """
    try:
        # nginx_log_count_info = common.load_json_file(file_path=nginx_log_count_file)
        nginx_log_count_info = get_efk_deployment_worker_log(worker_id=deployment_worker_id, key="nginxCount")
        if nginx_log_count_info is None:
            return result

        result["total_count"] =  nginx_log_count_info.get("total_count")
        result["success_count"] =  nginx_log_count_info.get("success_count")
        return result
    except:
        traceback.print_exc()
        return result

# POD_DASHBOARD_HISTORY_FILE_NAME="dashboard_history.json"
# POD_DASHBOARD_LIVE_HISTORY_FILE_NAME="dashboard_live_history.json"
def get_result_from_history_file(worker_list, start_time, end_time, interval, 
                                absolute_location, search_type, workspace_name=None, deployment_name=None):
    history_list=[]
    ndigits=5
    processing_response_key_list = ["min", "max", "average", "median", "99", "95", "90"]

    # ==============================================================================================================================
    # 파일 -> EFK
    # main_storage_name = db_deployment.get_workspace_info_storage(workspace_name=workspace_name)["main_storage_name"]
    if worker_list!=None:
        for deployment_worker_id in worker_list:
            """
            deployment_worker_log_dir = JF_DEPLOYMENT_WORKER_LOG_DIR_PATH.format(main_storage_name=main_storage_name,
                                                                                 workspace_name=workspace_name, 
                                                                                deployment_name=deployment_name, 
                                                                                deployment_worker_id=deployment_worker_id)
            if search_type=="range":
                history_file_path = "{}/{}".format(deployment_worker_log_dir, POD_DASHBOARD_HISTORY_FILE_NAME)
                history_file_back_path = "{}/{}".format(deployment_worker_log_dir, POD_DASHBOARD_HISTORY_BACK_FILE_NAME)
            else:
                history_file_path = "{}/{}".format(deployment_worker_log_dir, POD_DASHBOARD_LIVE_HISTORY_FILE_NAME)
                history_file_back_path = "{}/{}".format(deployment_worker_log_dir, POD_DASHBOARD_LIVE_HISTORY_BACK_FILE_NAME)

            if os.path.exists(history_file_path):
                data = common.load_json_file(file_path=history_file_path)
                if data is not None:
                    history_list.append(data)
                else:
                    data = common.load_json_file(file_path=history_file_back_path)
                    if data is not None:
                        history_list.append(data)
                    else:
                        raise Exception("Json Decode error")
                # with open(history_file_path, "r") as f:
                #     # history_dic=json.load(f)
                #     history_list.append(json.load(f))
            """
            if search_type=="range":
                key = "dashboardHistory"
            else:
                key = "dashboardLiveHistory"
            data = get_efk_deployment_worker_log(worker_id=deployment_worker_id, key=key)
            if data is not None:
                history_list.append(data)
    # ==============================================================================================================================

    # from datetime import datetime, timedelta
    time_variable_result = get_time_variables(start_time, end_time, interval, absolute_location)
    start_timestamp = time_variable_result["start_timestamp"]
    # end_timestamp=time_variable_result["end_timestamp"]
    additional_start_sec = time_variable_result["additional_start_sec"]
    # additional_start_count=time_variable_result["additional_start_count"]
    total_idx_count = time_variable_result["total_idx_count"]
    
    # 기본 time 만 포함한 graph 틀
    result = []
    # 초기 gpu list 받기
    gpu_num_list = []
    if len(history_list) > 0 :
        for result_dic in history_list:
            key_list = list(result_dic.keys())
            if len(key_list)>0:
                graph_result = result_dic[key_list[0]]["graph_result"]
                if len(graph_result)>0:
                    tmp_num_list = list(graph_result["gpu_resource"].keys())
                    gpu_num_list = tmp_num_list if len(tmp_num_list)>len(gpu_num_list) else gpu_num_list

    # 앞에 추가 start sec 이 있는경우
    if additional_start_sec > 0:
        for i in range(total_idx_count):
            time_stamp = start_timestamp+interval*(i-1)+additional_start_sec
            dic = get_default_api_monitor_graph_result(time=time_stamp, gpu_num_list=gpu_num_list, 
                                                        interval=interval, search_type=search_type, 
                                                        processing_response_key_list=processing_response_key_list)
            if len(gpu_num_list)>=1:
                for gpu_num in gpu_num_list:
                    dic["gpu_resource"][gpu_num]["gpu_memory_total"]=[]
                    dic["gpu_resource"][gpu_num]["average_gpu_memory_used"]=[]
                    dic["gpu_resource"][gpu_num]["average_gpu_memory_used_per"]=[]
                    dic["gpu_resource"][gpu_num]["average_util_gpu"]=[]
                    dic["gpu_resource"][gpu_num]["average_util_gpu_memory"]=[]
                    dic["gpu_resource"][gpu_num]["count"]=[]
            result.append(dic)
        # 첫번째 시간 start_time_obj 로 받기
        result[0]["time"] = start_timestamp
    # 앞에 추가 sec 이 없는 경우
    else:
        for i in range(total_idx_count):
            time_stamp = start_timestamp+interval*i
            dic = get_default_api_monitor_graph_result(time=time_stamp, gpu_num_list=gpu_num_list,
                                                        interval=interval, search_type=search_type, 
                                                        processing_response_key_list=processing_response_key_list)
            if len(gpu_num_list)>=1:
                for gpu_num in gpu_num_list:
                    dic["gpu_resource"][gpu_num]["gpu_memory_total"]=[]
                    dic["gpu_resource"][gpu_num]["average_gpu_memory_used"]=[]
                    dic["gpu_resource"][gpu_num]["average_gpu_memory_used_per"]=[]
                    dic["gpu_resource"][gpu_num]["average_util_gpu"]=[]
                    dic["gpu_resource"][gpu_num]["average_util_gpu_memory"]=[]
                    dic["gpu_resource"][gpu_num]["count"]=[]
            result.append(dic)
    key_list = list(result[0].keys())
    rm_key_list = ["time", "time_local", "gpu_resource", "worker_count", "time_list", "error_rate", "nginx_error_rate", "monitor_error_rate"]
    for res_key in ["processing_time", "response_time"]:
        for key in processing_response_key_list:
            rm_key_list.append("{}_{}".format(key, res_key))
    for rm_k in rm_key_list:
        key_list.remove(rm_k)
    if len(gpu_num_list)>=1:
        key_gpu_list = list(result[0]["gpu_resource"]['0'].keys())

    nginx_access_count_info={}
    error_log_list=[]
    total_code_dic={}
    processing_response_key_list_count = ["min", "max", "average", "median", "99", "95", "90", "count"]
    response_value_list = [[] for i in processing_response_key_list_count]
    processing_value_list = [[] for i in processing_response_key_list_count]
    response_time_info={
        "response_time":dict(zip(processing_response_key_list_count, response_value_list)),
        "processing_time":dict(zip(processing_response_key_list_count, processing_value_list)),
        "time":[]
    }
    # result 내의 result_dic 에 각 값의 list 담기
    for result_dic in result:
        time_iter=0
        for t_stamp in result_dic["time_list"]:

            time_str = str(t_stamp)
            for history_dic in history_list:
                if history_dic.get(time_str) !=None:
                    graph_result = history_dic[time_str]["graph_result"]
                    for key in key_list:
                        append_value = graph_result[key]
                        result_dic[key].append(append_value if append_value!=[] else 0)
                    if len(gpu_num_list)>=1:
                        for gpu_num in gpu_num_list:
                            if graph_result["gpu_resource"].get(gpu_num)!=None:
                                for key_gpu in key_gpu_list:
                                    append_value = graph_result["gpu_resource"][gpu_num][key_gpu]
                                    result_dic["gpu_resource"][gpu_num][key_gpu].append(append_value if append_value!=[] else 0)
                    result_dic["worker_count"][time_iter]+=1
                    error_log_list.extend(history_dic[time_str]["error_log_list"])

                    for key in history_dic[time_str]["total_code_dic"].keys():
                        if total_code_dic.get(key)!=None:
                            for detail_key in history_dic[time_str]["total_code_dic"][key].keys():
                                if total_code_dic[key].get(detail_key) != None:
                                    total_code_dic[key][detail_key]+=history_dic[time_str]["total_code_dic"][key][detail_key]
                                else:
                                    total_code_dic[key][detail_key]=history_dic[time_str]["total_code_dic"][key][detail_key]
                        else:
                            total_code_dic[key]=history_dic[time_str]["total_code_dic"][key]
                            
                    for key in history_dic[time_str]["nginx_access_count_info"].keys():
                        if nginx_access_count_info.get(key)!=None:
                            nginx_access_count_info[key]+=history_dic[time_str]["nginx_access_count_info"][key]
                        else:
                            nginx_access_count_info[key]=history_dic[time_str]["nginx_access_count_info"][key]
                    for res_key in ["processing_time", "response_time"]:
                        for key in processing_response_key_list:
                            # response_time_info[res_key][key].append(history_dic[time_str]["total_info"][res_key][key])
                            result_dic["{}_{}".format(key,res_key)].append(history_dic[time_str]["total_info"][res_key][key])
            time_iter+=1
    # list 값들 합치기 (average or sum)
    if len(gpu_num_list)>=1:
        key_gpu_list.remove("count")
        key_gpu_list.remove("gpu_memory_total")
    cpu_key_list=["average_mem_usage_per", "average_cpu_usage_on_pod"]
    # api_response_key_list=[i+"_response_time" for i in ["min", "max", "average"]]
    # nginx_response_key_list=[i+"_nginx_response_time" for i in ["min", "max", "average"]]
    api_response_key_list=[]
    nginx_response_key_list=[]
    for key in processing_response_key_list:
        nginx_response_key_list.append("{}_{}".format(key, "response_time"))
        api_response_key_list.append("{}_{}".format(key, "processing_time"))
    count_dic = {"processing_time":"success_count", "response_time":"nginx_count"}

    total_error_count_list=[]
    total_call_count_list=[]
    nginx_error_count_list=[]
    monitor_error_count_list=[]
    monitor_call_count_list=[]
    for result_dic in result:
        del result_dic["time_list"]
        result_dic["worker_count"]=max(result_dic["worker_count"])
        monitor_count = sum(result_dic["monitor_count"])
        success_count = sum(result_dic["success_count"])
        nginx_count=sum(result_dic["nginx_count"])
        result_dic["error_count"]=sum(result_dic["error_count"])
        result_dic["nginx_error_count"]=sum(result_dic["nginx_error_count"])
        result_dic["monitor_error_count"]=sum(result_dic["monitor_error_count"])
        # result_dic["error_rate"]=round(result_dic["error_count"]/nginx_count, ndigits)
        # result_dic["nginx_error_rate"]=round(result_dic["nginx_error_count"]/nginx_count, ndigits)
        # result_dic["monitor_error_rate"]=round(result_dic["monitor_error_count"]/count, ndigits)
        if nginx_count>0:
            range_list=list(range(len(result_dic["nginx_count"])))
            result_dic["error_rate"]=round(result_dic["error_count"]/(nginx_count+result_dic["error_count"]), ndigits)
            result_dic["nginx_error_rate"]=round(result_dic["nginx_error_count"]/(nginx_count+result_dic["error_count"]), ndigits)
            for key in nginx_response_key_list:
                logic=key.split("_")[0]
                if logic=="average":
                    average_dic = [result_dic[key][i]*result_dic["nginx_count"][i] for i in range_list if result_dic["nginx_count"][i]>0]
                    result_dic[key]=round(sum(average_dic)/nginx_count, ndigits)
                elif logic in [ "99", "95", "90"]:
                    result_dic[key]=get_statistic_result([i for i in result_dic[key] if i>0],logic="median", ndigits=ndigits)

                else:
                    result_dic[key]=get_statistic_result([i for i in result_dic[key] if i>0],logic=logic, ndigits=ndigits)
        else:
            for key in nginx_response_key_list:
                result_dic[key]=0
        if monitor_count>0:
            result_dic["monitor_error_rate"]=round(result_dic["monitor_error_count"]/monitor_count, ndigits)
            range_list=list(range(len(result_dic["monitor_count"])))
            for key in cpu_key_list:
                average_dic=[result_dic[key][i]*result_dic["monitor_count"][i] for i in range_list]
                result_dic[key]=round(sum(average_dic)/monitor_count, ndigits)
            if len(gpu_num_list)>=1:
                for gpu_num in gpu_num_list:
                    for key in key_gpu_list:
                        if sum(result_dic["gpu_resource"][gpu_num]["count"])>0:
                            gpu_range_list=range(len(result_dic["gpu_resource"][gpu_num]["count"]))
                            average_dic=[result_dic["gpu_resource"][gpu_num][key][i]*result_dic["gpu_resource"][gpu_num]["count"][i] for i in gpu_range_list]
                            result_dic["gpu_resource"][gpu_num][key]=round(sum(average_dic)/sum(result_dic["gpu_resource"][gpu_num]["count"]), ndigits)
                        else:
                            result_dic["gpu_resource"][gpu_num][key]=0
                    result_dic["gpu_resource"][gpu_num]["gpu_memory_total"]=sum(set(result_dic["gpu_resource"][gpu_num]["gpu_memory_total"]))
                    result_dic["gpu_resource"][gpu_num]["count"]=sum(result_dic["gpu_resource"][gpu_num]["count"])
        else:
            for key in cpu_key_list:
                result_dic[key]=0
            if len(gpu_num_list)>=1:
                for gpu_num in gpu_num_list:
                    for key in key_gpu_list:
                        result_dic["gpu_resource"][gpu_num][key]=0
                    result_dic["gpu_resource"][gpu_num]["gpu_memory_total"]=sum(set(result_dic["gpu_resource"][gpu_num]["gpu_memory_total"]))
                    result_dic["gpu_resource"][gpu_num]["count"]=sum(result_dic["gpu_resource"][gpu_num]["count"])
        if success_count>0:
            range_list=list(range(len(result_dic["success_count"])))
            for key in api_response_key_list:
                logic=key.split("_")[0]
                if logic=="average":
                    average_dic = [result_dic[key][i]*result_dic["success_count"][i] for i in range_list if result_dic["success_count"][i]>0]
                    result_dic[key]=sum(average_dic)/success_count
                elif logic in [ "99", "95", "90"]:
                    result_dic[key]=get_statistic_result([i for i in result_dic[key] if i>0],logic="median", ndigits=ndigits)
                else:
                    result_dic[key]=get_statistic_result([i for i in result_dic[key] if i>0],logic=logic, ndigits=ndigits)
        else:
            for key in api_response_key_list:
                result_dic[key]=0
        
        result_dic["monitor_count"]=monitor_count
        result_dic["success_count"]=success_count
        result_dic["nginx_count"]=nginx_count
        total_call_count_list.append(result_dic["nginx_count"]+result_dic["nginx_error_count"])
        total_error_count_list.append(result_dic["error_count"])
        nginx_error_count_list.append(result_dic["nginx_error_count"])
        monitor_error_count_list.append(result_dic["monitor_error_count"])
        monitor_call_count_list.append(result_dic["monitor_count"])

        # for key in ["min", "max", "average"]:
            # response_time_info["processing_time"][key].append(result_dic[key+"_response_time"])
            # response_time_info["response_time"][key].append(result_dic[key+"_nginx_response_time"])


        for res_key in ["processing_time", "response_time"]:
            response_time_info[res_key]["count"].append(result_dic[count_dic[res_key]])
            for key in processing_response_key_list:
                response_time_info[res_key][key].append(result_dic["{}_{}".format(key,res_key)])
                # response_time_info[res_key][key].append(result_dic["{}_{}".format(key,res_key)])

        response_time_info["time"].append(result_dic["time"])

    # print("response_time_info: ",response_time_info)
    for key in ["processing_time", "response_time"]:
        response_time_info[key]["total_average"]=[response_time_info[key]["average"][i]*response_time_info[key]["count"][i] 
                        for i in range(len(response_time_info[key]["count"])) if response_time_info[key]["count"][i]>0]
        if len(response_time_info[key]["total_average"])>0:
            response_time_info[key]["total_average"]=sum(response_time_info[key]["total_average"])/sum(response_time_info[key]["count"])
        else:
            response_time_info[key]["total_average"]=0
        if len(response_time_info[key]["max"])>0:
            max_idx = response_time_info[key]["max"].index(max(response_time_info[key]["max"]))
            response_time_info[key]["max_time"]=response_time_info["time"][max_idx]
    total_error_rate_list=[total_error_count_list[i]/total_call_count_list[i] for i in range(total_idx_count) if total_error_count_list[i]>0]
    nginx_error_rate_list=[nginx_error_count_list[i]/total_call_count_list[i] for i in range(total_idx_count) if nginx_error_count_list[i]>0]
    monitor_error_rate_list=[monitor_error_count_list[i]/monitor_call_count_list[i] for i in range(total_idx_count) if monitor_error_count_list[i]>0]

    return_result = {
        "graph_result":result,
        "nginx_access_count_info": nginx_access_count_info,
        "error_log_list": error_log_list,
        "code_list": total_code_dic,
        "total_info":{
            "call":{
                "total":sum(total_call_count_list),
                "min":get_statistic_result([i for i in total_call_count_list if i>0], "min", ndigits),
                "max":get_statistic_result(total_call_count_list, "max", ndigits)
            },
            "abnormal":{
                "total":{
                    "count":sum(total_error_count_list),
                    "max_count":get_statistic_result(total_error_count_list, "max", ndigits),
                    "rate":round(sum(total_error_count_list)/sum(total_call_count_list), ndigits) if sum(total_call_count_list)>0 else 0,
                    "max_rate":get_statistic_result(total_error_rate_list, "max", ndigits)
                },
                "nginx":{
                    "count":sum(nginx_error_count_list),
                    "max_count":get_statistic_result(nginx_error_count_list, "max", ndigits),
                    "rate":round(sum(nginx_error_count_list)/sum(total_call_count_list), ndigits) if sum(total_call_count_list)>0 else 0,
                    "max_rate":get_statistic_result(nginx_error_rate_list, "max", ndigits)
                },
                "api":{
                    "count":sum(monitor_error_count_list),
                    "max_count":get_statistic_result(monitor_error_count_list, "max", ndigits),
                    "rate":round(sum(monitor_error_count_list)/sum(monitor_call_count_list), ndigits) if sum(monitor_call_count_list)>0 else 0,
                    "max_rate":get_statistic_result(monitor_error_rate_list, "max", ndigits)
                }
            },
            "processing_time":{
                "average":round(response_time_info["processing_time"]["total_average"], ndigits),
                "median":get_statistic_result([i for i in response_time_info["processing_time"]["median"] if i>0], "median", ndigits),
                "99":get_statistic_result([i for i in response_time_info["processing_time"]["99"] if i>0], "median", ndigits),
                "95":get_statistic_result([i for i in response_time_info["processing_time"]["95"] if i>0], "median", ndigits),
                "90":get_statistic_result([i for i in response_time_info["processing_time"]["90"] if i>0], "median", ndigits),
                "min":get_statistic_result([i for i in response_time_info["processing_time"]["min"] if i>0], "min", ndigits),
                "max":get_statistic_result(response_time_info["processing_time"]["max"], "max", ndigits),
                "max_timestamp":response_time_info["processing_time"].get("max_time")
            },
            "response_time":{
                "average":round(response_time_info["response_time"]["total_average"], ndigits),
                "median":get_statistic_result([i for i in response_time_info["response_time"]["median"] if i>0], "median", ndigits),
                "99":get_statistic_result([i for i in response_time_info["response_time"]["99"] if i>0], "median", ndigits),
                "95":get_statistic_result([i for i in response_time_info["response_time"]["95"] if i>0], "median", ndigits),
                "90":get_statistic_result([i for i in response_time_info["response_time"]["90"] if i>0], "median", ndigits),
                "min":get_statistic_result([i for i in response_time_info["response_time"]["min"] if i>0], "min", ndigits),
                "max":get_statistic_result(response_time_info["response_time"]["max"], "max", ndigits),
                "max_timestamp":response_time_info["response_time"].get("max_time")
            }
        }
    }
    return return_result

# ===================================================================================
# get_nginx_access_per_hour_chart
# ===================================================================================
# get_nginx_access_per_hour_chart
def get_nginx_access_per_hour_chart(time_table, log_per_hour_info_list, data_key):
    time_table = dict(time_table)
    for data in log_per_hour_info_list:
        try:
            common.update_dict_key_count(dict_item=time_table, key=data[DEPLOYMENT_NGINX_PER_TIME_KEY], add_count=data[data_key], exist_only=True)        
        except KeyError as ke:
            # traceback.print_exc()
            pass
    chart_data = list(time_table.values())
    chart_data.reverse()
    # 최소 개수가 24개
    if len(chart_data) < 24:
        dummy = [0] * ( 24 - len(chart_data) )
        chart_data = dummy + chart_data
    return chart_data       

# - param1. time_table
def get_nginx_per_hour_time_table_dict(log_per_hour_info_list, time_time_count=24):
    if len(log_per_hour_info_list) == 0:
        return {}
    try:
        sorted_log_per_hour_info_list = sorted(log_per_hour_info_list, key=lambda log_per_hour_info_list: (log_per_hour_info_list[DEPLOYMENT_NGINX_PER_TIME_KEY]))
    except KeyError as ke:
        traceback.print_exc()
        return {}
    last_time = sorted_log_per_hour_info_list[-1][DEPLOYMENT_NGINX_PER_TIME_KEY]
    last_timestamp = common.date_str_to_timestamp(date_str=last_time, date_format=DEPLOYMENT_NGINX_NUM_OF_LOG_PER_HOUR_DATE_FORMAT)
    time_table = {}
    time_interval = 60 * 60 # test - (hour = 60 * 60)
    # last 24 item time list
    for i in range(time_time_count):
        date_time = common.get_date_time(timestamp=last_timestamp - time_interval * i, date_format=DEPLOYMENT_NGINX_NUM_OF_LOG_PER_HOUR_DATE_FORMAT)
        time_table[str(date_time)] = 0
    return time_table

# - param2. log_per_hour_info_list
def get_deployment_nginx_access_log_per_hour_list(deployment_id, workspace_name=None, deployment_name=None):
    # 24시간 이내 워커만 가져옴
    deployment_worker_id_list = [str(i.get("id")) for i in db_deployment.get_deployment_worker_list(deployment_id=deployment_id, running="ALL", day=True)]
    worker_num_of_log_per_hour_info_list = []
    for deployment_worker_id in deployment_worker_id_list:
        # per_hour_info_list = get_deployment_worker_nginx_access_log_per_hour_info_list(workspace_name=workspace_name, deployment_name=deployment_name, deployment_worker_id=deployment_worker_id)
        per_hour_info_list = get_deployment_worker_nginx_access_log_per_hour_info_list(deployment_worker_id=deployment_worker_id)
        if per_hour_info_list:
            worker_num_of_log_per_hour_info_list += per_hour_info_list
    return worker_num_of_log_per_hour_info_list

# get_nginx_access_per_hour_chart 호출 ----------------------------------------------
def get_deployment_call_count_per_hour_chart(deployment_id, deployment_name=None, workspace_name=None):
    # start_time = time.time()
    log_per_hour_info_list = get_deployment_nginx_access_log_per_hour_list(deployment_id=deployment_id)
    time_table = get_nginx_per_hour_time_table_dict(log_per_hour_info_list=log_per_hour_info_list)
    # print("process time : ", time.time() - start_time)
    return get_nginx_access_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list,
                                           data_key=DEPLOYMENT_NGINX_PER_TIME_NUM_OF_CALL_LOG_KEY)

def get_call_count_per_hour_chart(time_table, log_per_hour_info_list):
    return get_nginx_access_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list,
                                           data_key=DEPLOYMENT_NGINX_PER_TIME_NUM_OF_CALL_LOG_KEY)

def get_median_per_hour_chart(time_table, log_per_hour_info_list):
    return get_nginx_access_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list,
                                           data_key=DEPLOYMENT_NGINX_PER_TIME_RESPONSE_TIME_MEDIAN_KEY)

def get_nginx_abnormal_call_count_per_hour_chart(time_table, log_per_hour_info_list):
    return get_nginx_access_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list,
                                           data_key=DEPLOYMENT_NGINX_PER_TIME_NUM_OF_ABNORMAL_LOG_COUNT_KEY)

def get_api_monitor_abnormal_call_count_per_hour_chart(time_table, log_per_hour_info_list):
    return get_nginx_access_per_hour_chart(time_table=time_table, log_per_hour_info_list=log_per_hour_info_list,
                                           data_key=DEPLOYMENT_API_MONITOR_PER_TIME_NUM_OF_ABNORMAL_LOG_COUNT_KEY)

# ===================================================================================
# API - api_monitor, api_call
# ===================================================================================
def get_default_api_monitor_graph_result(time, gpu_num_list, processing_response_key_list, 
                                        interval=None, search_type="range"):
    search_dic={
        "range":600,
        "live":1
    }
    dic = {
        "time": time,
        "time_local": 0,
        "monitor_count": [],
        "nginx_count": [], # nginx count
        "success_count": [],
        "error_count": [], # abnormal processing
        "monitor_error_count": [], # abnormal processing api
        "nginx_error_count": [], # abnormal processing nginx
        "error_rate": 0,
        "monitor_error_rate": 0,
        "nginx_error_rate": 0,
        "average_cpu_usage_on_pod": [], # cpu
        "average_mem_usage_per": [], # ram
        "worker_count": [0], # worker
        "time_list":[time],
        "gpu_resource":{}
    }
    for res_key in ["processing_time", "response_time"]:
        for key in processing_response_key_list:
            dic["{}_{}".format(key, res_key)]=[]
    for gpu_num in gpu_num_list:
        dic["gpu_resource"][gpu_num]={}
        dic["gpu_resource"][gpu_num]["gpu_memory_total"]=0
        dic["gpu_resource"][gpu_num]["average_gpu_memory_used"]=0
        dic["gpu_resource"][gpu_num]["average_gpu_memory_used_per"]=0 # gpu mem
        dic["gpu_resource"][gpu_num]["average_util_gpu"]=0 # gpu core
        dic["gpu_resource"][gpu_num]["average_util_gpu_memory"]=0
        dic["gpu_resource"][gpu_num]["count"]=0
    if interval<=search_dic[search_type]:
        return dic
    else:
        dic["time_list"]=[time+i*search_dic[search_type] for i in range(interval//search_dic[search_type])]
        dic["worker_count"]=[0 for i in range(interval//search_dic[search_type])]
        return dic

def get_deployment_api_total_count_info(worker_dir_list):
# def get_deployment_api_total_count_info(worker_dir_list, workspace_name, deployment_name):
    import time
    ndigits=3
    result={
        "total_call_count": 0,
        "total_success_rate":0,
        "total_log_size":0,
        "restart_count": str(0) # str 해야지 됨???
    }
    total_call_count=0
    # total_success=0
    total_nginx_success=0
    total_log_size_list=[]
    check_import_list=[] # ????
    # main_storage_name = db_deployment.get_workspace_info_storage(workspace_name=workspace_name)["main_storage_name"]
    
    for worker_id_str in worker_dir_list:
        nginx_count_info={
            "total_count":0,
            "success_count":0
        }
        """
        # 파일 -> EFK
        deployment_worker_log_dir = JF_DEPLOYMENT_WORKER_LOG_DIR_PATH.format(
            main_storage_name=main_storage_name, workspace_name=workspace_name,
            deployment_name=deployment_name, deployment_worker_id=int(worker_id_str))
        try:
            file_list = os.listdir(deployment_worker_log_dir)
        except FileNotFoundError as fne:
            continue
        
        nginx_log_count_file = GET_POD_NGINX_LOG_COUNT_FILE_PATH_IN_JF_API(
            main_storage_name=main_storage_name, workspace_name=workspace_name,
            deployment_name=deployment_name, deployment_worker_id=int(worker_id_str))

        if os.path.exists(nginx_log_count_file):
            data = common.load_json_file(file_path=nginx_log_count_file)
            if data is not None:
                nginx_count_info = data

        log_size = get_dir_size(deployment_worker_log_dir)
        if log_size !=None:
            total_log_size_list.append(log_size)
        check_import = True if POD_API_LOG_IMPORT_CHECK_FILE_NAME in file_list else False
        check_import_list.append(check_import)
        """
        nginx_count_info = get_deployment_worker_nginx_call_count(deployment_worker_id=int(worker_id_str))
        nginx_count=nginx_count_info["total_count"]
        total_call_count+=nginx_count
        nginx_success = nginx_count_info["success_count"]
        total_nginx_success+=nginx_success

    result["total_call_count"]=total_call_count
    result["total_success_rate"]=round((total_nginx_success/total_call_count)*100, ndigits=ndigits) if total_call_count>0 else 0
    result["total_log_size"]=sum(total_log_size_list)
    # result["restart_count"]="dummy"
    return result

# ===================================================================================
# 기타
# ===================================================================================
def get_time_variables(start_time, end_time, interval, absolute_location):
    from datetime import datetime, timedelta
    # time string type 에서 datetime type 으로 변경
    # start_time_obj = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    # end_time_obj = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    start_timestamp = common.date_str_to_timestamp(start_time, POD_RUN_TIME_DATE_FORMAT)
    end_timestamp = common.date_str_to_timestamp(end_time, POD_RUN_TIME_DATE_FORMAT)
    # 프론트 요청에서 time 범위 꼬이는 경우가 자주 발생해 예외처리
    if start_timestamp>end_timestamp:
        end_timestamp=start_timestamp+interval
    # interval time delta 로 변경
    # interval_timedelta = timedelta(seconds = interval)
    additional_start_sec = 0
    if absolute_location:
        # interval 기준으로 범위 나누기: start time 의 timestamp 을 interval 로 나누어 나머지값 구함
        additional_start_sec = interval-start_timestamp%interval
    # additional_start_sec = timedelta(seconds = additional_start_sec)
    total_idx_count = (end_timestamp-start_timestamp-additional_start_sec)//interval
    additional_end_count = 1 if (end_timestamp-start_timestamp-additional_start_sec)%interval else 0
    additional_start_count = 1 if additional_start_sec else 0
    total_idx_count += additional_end_count+additional_start_count
    result = {
        "start_timestamp":start_timestamp,
        "end_timestamp":end_timestamp,
        "additional_start_sec":additional_start_sec,
        "additional_start_count":additional_start_count,
        "total_idx_count":int(total_idx_count),
    }
    return result

def get_statistic_result(result, logic="mean", ndigits=3):
    import math
    def calculate_percentile(arry, percentile):
        size = len(arry)
        return sorted(arry)[int(math.ceil((size * percentile) / 100)) - 1]
    if len(result)==0:
        return 0
    elif logic in ["mean","average"]:
        return round(statistics.mean(result), ndigits=ndigits)
    elif logic == "median":
        return round(statistics.median(result), ndigits=ndigits)
    elif logic == "min":
        return round(min(result), ndigits=ndigits)
    elif logic == "max":
        return round(max(result), ndigits=ndigits)
    elif logic[:10]=="percentile":
        return round(calculate_percentile(arry=result, percentile=int(logic[10:])), ndigits=ndigits)
