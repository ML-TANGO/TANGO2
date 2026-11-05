from calendar import month
import requests
import traceback

from utils.resource import response
import datetime
import random
import json
from utils.msa_db import db_workspace, db_project
from utils import settings
from utils import common

from utils.redis import get_redis_client
from utils.redis_key import STORAGE_LIST_RESOURCE

instance_ids = [*range(1, 999)]
random.shuffle(instance_ids)

def attach_prefix_postfix(original: str):
    return f'{random.choice(["", "", "", "a-", "long-", "quite-long-", "long-long-and-also-very-long-long-"])}{original}{random.choice(["", "", "-name"])}'

def generate_instance_id():
    global instance_ids
    if len(instance_ids) == 0:
        instance_ids = [*range(1, 999)]
        random.shuffle(instance_ids)
    return instance_ids.pop()


def generate_instance_info(type: str = None):
    current_data = {}

    current_data["instance_name"] = f'{attach_prefix_postfix("instance")}-{generate_instance_id()}'
    current_data["instance_count"] = random.randint(1, 10)
    current_data["instance_type"] = type if type else random.choice(["cpu", "gpu"])
    current_data["instance_validation"] = random.choice([True, False])
    current_data["cpu_allocate"] = random.randint(2, 16)
    current_data["ram_allocate"] = random.randint(1, 16) * 2
    current_data["free_cpu"] = random.randint(0, current_data["cpu_allocate"])
    current_data["free_ram"] = random.randint(0, current_data["ram_allocate"])
    if current_data["instance_type"] == "gpu":
        current_data["gpu_name"] = f"ACR{random.randint(10, 800) * 10}"
        current_data["gpu_total"] = random.randint(1, 16)
        current_data["gpu_vram"] = random.randint(1, 10) * 1024
        current_data["gpu_group_id"] = random.randint(1, 99)
        current_data["gpu_allocate"] = random.randint(1, current_data["gpu_total"])
    
    return current_data


def generate_workspace_info(workspace_name: str, active: bool):
    current_data = {}
    current_data["status"] = "active" if active else "inactive"
    current_data["workspace_name"] = workspace_name
    today = datetime.datetime.now()
    create_datetime = today - datetime.timedelta(days=random.randint(100, 365), hours=random.randint(0, 23), minutes=random.randint(0, 59), seconds=random.randint(0, 59))
    current_data["create_datetime"] = create_datetime.strftime("%Y-%m-%d %H:%M:%S")
    start_datetime = today - datetime.timedelta(days=random.randint(100, 365), hours=random.randint(0, 23), minutes=random.randint(0, 59), seconds=random.randint(0, 59))
    current_data["start_datetime"] = start_datetime.strftime("%Y-%m-%d %H:%M")
    end_datetime = today + datetime.timedelta(days=random.randint(100, 365), hours=random.randint(0, 23), minutes=random.randint(0, 59), seconds=random.randint(0, 59))
    current_data["end_datetime"] = end_datetime.strftime("%Y-%m-%d %H:%M")
    activation_time = (int)((today - start_datetime).total_seconds())
    current_data["activation_time"] = str(activation_time)
    current_data["storage_usage"] = []
    storage_nums = [*range(1, 99999)]
    random.shuffle(storage_nums)
    for i in range(random.randint(2, 7)):
        current_storage_data = {}
        current_storage_data["storage_name"] = f'{attach_prefix_postfix("storage")}-{storage_nums.pop()}'
        current_storage_data["storage_utilization"] = (int)(random.random() * (10.0 ** random.randint(1, 7)))
        current_data["storage_usage"].append(current_storage_data)
    current_data["instance_usage"] = []
    instance_nums = [*range(1, 999)]
    random.shuffle(instance_nums)
    for i in range(random.randint(1, 15)):
        current_instance_data = {}
        current_instance_data["instance_name"] = f'{attach_prefix_postfix("instance")}-{instance_nums.pop()}'
        current_instance_data["instance_time"] = (int)((float)(current_data["activation_time"]) * random.random() * 5.0)
        current_data["instance_usage"].append(current_instance_data)        
    return current_data


def options_workspaces(headers_user):
    try:
        if False and headers_user != settings.ADMIN_NAME: # TODO 권한체크 스킵 (and False) 제거
            return response(status=0, message="permission denied")
        workspace_list = db_workspace.get_workspace_list()
        return response(status=1, result=workspace_list)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Get Option error : {}".format(e))


def options_trainings(workspace_id, headers_user):
    try:
        if headers_user != settings.ADMIN_NAME and False: # TODO 권한체크 스킵 (and False) 제거
            return response(status=0, message="permission denied")
        return response(status=1, result=db_project.get_workspace_tools(workspace_id))
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Get Option error : {}".format(e))
    

def records_history(page: int, size: int, sort: str, order: str, action: str, task: str, search_key: str, search_value: str):
    offset = (page - 1) * size
    if search_value:
        if not search_key:
            search_key = "workspace"
    if search_key:
        if search_key not in ["workspace", "user", "task_name"]:
            return response(status=0, message="Invalid search key") 
    
    try:
        history_url = f"http://log-middleware-rest-debug.jonathan-efk:8080/v1/dashboard/admin/detail"
        history_response = requests.post(history_url, json={
            "timeSpan": "1y", 
            "count": size, 
            "offset": offset, 
            "ascending": (True if order == "asc" else False),
            "action": action,
            "task": task,
            "searchKey": search_key,
            "searchTerm": search_value
        })
        history_raw = history_response.json()
        histories = []
        for history in history_raw["logs"]:
            current_document = history["fields"]
            current_document["update_details"] = "-"
            histories.append(current_document)
    except:
        return response(status=0, result={})
        
    return response(status=1, result={"list": histories, "total": history_raw["totalCount"]})
    """
    histories = [
        {
            "time_stamp": "2024-07-15 01:23:45",
            "task": "job",
            "action": "create",
            "task_name": "long-training-name-123 / very-long-and-long-long-job-987",
            "workspace": "long-workspace-name-and-it-is-workspace-555",
            "user": "long-long-long-user-name",
            "update_details": "Not Implemented yet but this is long description"
        },
        {
            "time_stamp": "2021-09-01 12:34:56",
            "task": "workspace",
            "action": "create",
            "task_name": "workspace-1",
            "user": "min",
            "update_details": "Not Implemented"
        }
    ]
    history_raw = {"totalCount": 2}
    """
        
    return response(status=1, result={"list": histories, "total": history_raw["totalCount"]})


STORAGE_TYPE_TOTAL = "total"
def generate_typed_storage_name(storage_name, storage_type):
    storage_type_conversion_map = { 
        "main": "(메인 스토리지)",
        "data": "(데이터 스토리지)",
        "total": "[전체 사용량]"
    }
    type_string = storage_type_conversion_map[storage_type] if storage_type in storage_type_conversion_map else f"({storage_type} 스토리지)"
    
    return f'{storage_name} {type_string}'

def summary():
    workspaces = db_workspace.get_workspace_list()
    
    redis = get_redis_client()
    storage_result = redis.get(STORAGE_LIST_RESOURCE)
    workspace_storage_map = {} # 해당 맵에 redis에서 가져온 사용량 데이터를 workspace name -> {"storage_name": size} 형태로 저장
    
    # storage_result를 json으로 변환해서 사용
    try:
        storage_result = json.loads(storage_result)
    except:
        storage_result = {}    
    
    for storage_id, storage_data in storage_result.items():
        storage_name = storage_data["name"]
        for storage_type, usage_list in storage_data["workspaces"].items():
            for usage_data in usage_list:
                workspace_name = usage_data["workspace_name"]
                used_size = usage_data["used_size"]
                
                # dict 유효성 검사
                if workspace_name not in workspace_storage_map:
                    workspace_storage_map[workspace_name] = {}
                
                # 전체 사용량 유효성 검사 후 누적
                total_storage_name = generate_typed_storage_name(storage_name, STORAGE_TYPE_TOTAL)
                if total_storage_name not in workspace_storage_map[workspace_name]:
                    workspace_storage_map[workspace_name][total_storage_name] = 0
                workspace_storage_map[workspace_name][total_storage_name] += used_size
                
                # storage_type에 따른 사용량 누적
                typed_storage_name = generate_typed_storage_name(storage_name, storage_type)                
                workspace_storage_map[workspace_name][typed_storage_name] = used_size
                
    result = []
    for workspace in workspaces:
        current_data = {
            "workspace_name": workspace["name"],
            "status": common.get_workspace_status(workspace),
            "create_datetime": workspace["create_datetime"],
            "start_datetime": workspace["start_datetime"],
            "end_datetime": workspace["end_datetime"],
            "activation_time": 0,
            "storage_usage": [],
            "instance_usage": []
        }
        
        # activation time 계산
        workspace_name = workspace["name"]
        
        # datetime 파싱을 더 유연하게 처리
        def parse_datetime_flexible(date_string):
            # 먼저 초가 포함된 형식으로 시도
            try:
                return datetime.datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # 초가 없는 형식으로 시도
                try:
                    return datetime.datetime.strptime(date_string, "%Y-%m-%d %H:%M")
                except ValueError:
                    # 그래도 실패하면 현재 시간 반환
                    return datetime.datetime.now()
        
        current_start_time = parse_datetime_flexible(current_data["start_datetime"])
        modification_log = common.post_request_sync(url=f"{settings.LOG_MIDDLEWARE_DNS}/v1/workspace/modifyTime/{workspace_name}", data={})
        modify_time = current_start_time
        try:
            modify_time_string = modification_log.get("modifyTime")
            if modify_time_string:
                modify_time = parse_datetime_flexible(modify_time_string)
        except Exception as e:
            modify_time = current_start_time
        
        current_end_time = parse_datetime_flexible(current_data["end_datetime"])
        current_time = datetime.datetime.now()
        
        current_init_time = current_start_time if current_start_time > modify_time else modify_time
        current_term_time = current_end_time if current_end_time < current_time else current_time
        
        time_gap = current_term_time - current_init_time
        current_data["activation_time"] = time_gap.total_seconds() if time_gap.total_seconds() > 0 else 0        
        
        # storage_usage 추가
        if current_data["workspace_name"] in workspace_storage_map:
            for storage_name, storage_size in workspace_storage_map[current_data["workspace_name"]].items():
                current_data["storage_usage"].append({
                    "storage_name": storage_name,
                    "storage_utilization": storage_size // 1_000_000 # MB로 변환
                })
        
        result.append(current_data)
        # result.append(generate_workspace_info(name, activate))
    return response(status=1, result=result)

def utilization_figure(workspace_id, start_datetime, end_datetime, aggregation):
    # FORCE aggregation to automatically adjust to #buckets to be maximum value less than 500
    start_time_string = start_datetime
    end_time_string = end_datetime
    start_datetime = datetime.datetime.strptime(start_datetime, "%Y-%m-%d %H:%M:%S")
    end_datetime = datetime.datetime.strptime(end_datetime, "%Y-%m-%d %H:%M:%S")
    if end_datetime > datetime.datetime.now():
        end_datetime = datetime.datetime.now()
    
    duration = end_datetime - start_datetime
    if duration.total_seconds() < 60 * 500:
        aggregation = "1m"
    elif duration.total_seconds() < 60 * 60 * 500:
        aggregation = "1h"
    elif duration.total_seconds() < 60 * 60 * 24 * 500:
        aggregation = "1d"
    elif duration.total_seconds() < 60 * 60 * 24 * 30 * 500:
        aggregation = "30d"
    
    try:
        resource_usage_log = {}    
        if workspace_id:
            resource_usage_log = common.post_request_sync(url=f"{settings.LOG_MIDDLEWARE_DNS}/v1/resource/workspace/{workspace_id}", data={
                "startTime": start_time_string,
                "endTime": end_time_string,
                "interval": aggregation            
            })
        else:
            resource_usage_log = common.post_request_sync(url=f"{settings.LOG_MIDDLEWARE_DNS}/v1/resource/cluster", data={
                "startTime": start_time_string,
                "endTime": end_time_string,
                "interval": aggregation
            })
            
        #print(f"seconds: {duration.total_seconds()}, aggretation: {aggregation}, resource_usage_log: {resource_usage_log}")

        util_data = {}    
        for k, v in resource_usage_log.items():
            if k == "cpu":
                for item in v:
                    if item["date"] not in util_data:
                        util_data[item["date"]] = {}
                    util_data[item["date"]]["cpu"] = item["used_cpu"]
            elif k == "gpu":
                for item in v:
                    if item["date"] not in util_data:
                        util_data[item["date"]] = {}
                    util_data[item["date"]]["gpu"] = item["used_gpu"]
            elif k == "ram":
                for item in v:
                    if item["date"] not in util_data:
                        util_data[item["date"]] = {}
                    util_data[item["date"]]["ram"] = item["used_ram"]
        
        resp_array = []
        for k, v in util_data.items():
            resp_array.append({
                "timestamp": k,
                "cpu": v.get("cpu", 0),
                "gpu": v.get("gpu", 0),
                "ram": v.get("ram", 0)
            })
        return response(status=1, result=resp_array)
    except Exception as e:
        print(f"[ERROR] utilization_figure failed: {e}")
        traceback.print_exc()
        return response(status=0, result=[])


def instance_info(workspace_id):
    result = {
        "summary": {
                "activation_time": 0,
                "storage_usage": [],
                "instance_usage": []
            },
        "instance_allocation_histories": []
    }
    
    workspaces = db_workspace.get_workspace_list()
    if workspace_id:
        workspace_name = "not_found_internal_err"
        for workspace in workspaces:
            if workspace["id"] == workspace_id:
                workspace_name = workspace["name"]
                break
        summary_raw = generate_workspace_info(workspace_name, True)
        del summary_raw["status"]
        del summary_raw["workspace_name"]
        del summary_raw["create_datetime"]
        del summary_raw["start_datetime"]
        del summary_raw["end_datetime"]
        result["summary"] = summary_raw
    else:     
        summary_raw = generate_workspace_info("all-placeholder", True)
        del summary_raw["status"]
        del summary_raw["workspace_name"]
        del summary_raw["create_datetime"]
        del summary_raw["start_datetime"]
        del summary_raw["end_datetime"]
        random_multiplier = 2 + random.random() * 3
        summary_raw["activation_time"] = (int)((float)(summary_raw["activation_time"]) * random_multiplier)
        for storage in summary_raw["storage_usage"]:
            storage["storage_utilization"] = (int)((float)(storage["storage_utilization"]) * random_multiplier)
        for instance in summary_raw["instance_usage"]:
            instance["instance_time"] = (int)((float)(instance["instance_time"]) * random_multiplier)
        result["summary"] = summary_raw
        
    instance_allocation_histories = []
    for i in range(random.randint(1, 12) if workspace_id else random.randint(3, 40)):
        current_history = {}
        today = datetime.datetime.now()
        start_datetime = today + datetime.timedelta(days=random.randint(-365, -2), hours=random.randint(0, 23), minutes=random.randint(0, 59), seconds=random.randint(0, 59))
        current_history["start_datetime"] = start_datetime.strftime("%Y-%m-%d %H:%M")
        end_datetime = start_datetime + datetime.timedelta(days=random.randint(1, 800), hours=random.randint(0, 23), minutes=random.randint(0, 59), seconds=random.randint(0, 59))
        current_history["end_datetime"] = end_datetime.strftime("%Y-%m-%d %H:%M")
        current_history["workspace_name"] = workspace_name if workspace_id else random.choice(workspaces)["name"]
        current_instances = []
        for j in range(random.randint(1, 4)):
            current_instance = {}
            current_instance["instance_info"] = generate_instance_info()
            current_instance["allocated_count"] = random.randint(1, current_instance["instance_info"]["instance_count"])
            current_instances.append(current_instance)
        current_history["instances"] = current_instances  
        instance_allocation_histories.append(current_history)          
    result["instance_allocation_histories"] = instance_allocation_histories
    
    return response(status=0, result=result)


def generate_history(workspace_name, start_time):
    current_data = {}
    current_data["node_name"] = f'{attach_prefix_postfix("node")}-{random.randint(1, 999)}'
    current_data["instance_allocated_count"] = random.randint(1, 10)
    current_data["instance_info"] = generate_instance_info()
    current_data["workspace_name"] = workspace_name
    current_data["type"] = random.choice(["editor", "job", "hyperparamsearch", "deployment"])
    current_data["type_detail"] = "Not found"
    if current_data["type"] == "editor":
        current_data["type_detail"] = random.choice(["jupyter", "code", "ssh"])
    elif current_data["type"] == "deployment":
        current_data["type_detail"] = f'{attach_prefix_postfix("deployment")}-{random.randint(1, 999)}'
    elif current_data["type"] == "job" or current_data["type"] == "hyperparamsearch":
        current_data["type_detail"] = f'{attach_prefix_postfix("training")}-{random.randint(1, 999)} / {current_data["type"]}-{random.randint(1, 999)}'
    today = datetime.datetime.now()
    start_datetime = start_time
    current_data["start_datetime"] = start_datetime.strftime("%Y-%m-%d %H:%M:%S")
    end_datetime = start_datetime + datetime.timedelta(days=random.randint(2, 365), hours=random.randint(0, 23), minutes=random.randint(0, 59), seconds=random.randint(0, 59))
    current_data["end_datetime"] = end_datetime.strftime("%Y-%m-%d %H:%M:%S")
    current_data["period"] = (int)((end_datetime - start_datetime).total_seconds())
    return current_data


async def instance_history(
    workspace_id, 
    start_datetime, end_datetime, 
    page, size, 
    type,
    search_key, search_term
):
    """
    워크스페이스별 사용 정보 상세 조회, 하단 히스토리용 
    
    반환:
    - result: {}
        - total: int, 전체 기록 수
        - count: int, 현재 페이지 기록 수
        - last_idx: {}, 현재 미정, 실제 구현 시 다음 페이지 요청 시 백으로 재전달 필요할 수 있음. 
        - histories: []
            - {}
                - node_name: str, 노드 이름
                - instance_allocated_count: int, 할당된 인스턴스 개수
                - instance_info: {}
                    - instance_name: str, 인스턴스명
                    - instance_count: int, 총 인스턴스 수
                    - instance_type: str, 인스턴스 타입, CPU/GPU
                    - instance_validation: bool, 인스턴스 유효성 여부
                    - gpu_name: str, GPU명
                    - gpu_allocate: int, 할당 GPU 수
                    - cpu_allocate: int, 할당 CPU 수
                    - ram_allocate: int, 할당 RAM, GB
                - workspace_name: str, 워크스페이스 이름
                - type: str, 사용 유형, editor/job/hyperparamsearch/deployment 중 하나
                - type_detail: str, 도구 이름, 아래 참조
                    - editor인 경우) editor 이름
                    - job이나 hyperparamsearch인 경우) " / "로 구분해서 학습 이름과 job/hps 이름 연결
                    - deployment인 경우) 배포 이름
                - start_datetime: str, 시작 시간, YYYY-mm-dd HH:MM:SS
                - end_datetime: str, 종료 시간, YYYY-mm-dd HH:MM:SS
                - period: int, 사용 기간, 초            
    """
    result = {}
    histories = []
    current_time = datetime.datetime.now()
    current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
    
    # TODO: get_ongoing_usage 구현 필요
    # try:
    #     ongoing = await get_ongoing_usage(workspace_id=workspace_id, call_datetime=current_time)
    # except Exception as e:
    #     print("Failed retreving ongoing")
    #     traceback.print_exc()
    #     pass

    cbtp_type_map = {
        "deployment": "deployment",
        "editor": "tool",
        "job": "training",
        "hyperparamsearch": "training",
    }
    
    try:
        query_data = {}
        if workspace_id:
            workspace = db_workspace.get_workspace(workspace_id = workspace_id)
            if workspace:
                query_data["workspace"] = workspace["name"]
        if type:
            query_data["usageType"] = cbtp_type_map[type] if type in cbtp_type_map else type
        if start_datetime:
            query_data["startTime"] = start_datetime
        if end_datetime:
            query_data["endTime"] = end_datetime
        if size:
            query_data["count"] = size
            if page:
                query_data["offset"] = (size) * (page - 1)
        if search_key and search_term and search_term != "":
            query_data["searchKey"] = search_key
            query_data["searchTerm"] = search_term

        # TODO: ongoing data filtering 구현 필요
        filtered_ongoing = []
        # if ongoing:
        #     for item in ongoing:
        #         if (not type or item["type"] == type) and \
        #             ( (not start_datetime or start_datetime <= current_time_str) \
        #              and (not end_datetime or end_datetime >= item["start_datetime"]) ):
        #             if search_key and search_term:
        #                 if (search_key == "workspace" and search_term in item["workspace_name"]) or \
        #                     (search_key == "training" and item["type"] in ["tool", "job", "hps"] and search_term in item["type_detail"]) or \
        #                     (search_key == "deployment" and item["type"] in ["deployment"] and search_term in item["type_detail"]):
        #                     filtered_ongoing.append(item)
        #             else:
        #                 filtered_ongoing.append(item)
        
        offset = query_data.get("offset", 0)
        count = query_data.get("count", 10) 
        filtered_size = len(filtered_ongoing)
        overlap = max(filtered_size - offset, 0)
        query_data["count"] = max(count - overlap, 0)
        query_data["offset"] = max(offset - filtered_size, 0)
            
        allocation_log = common.post_request_sync(url=f"{settings.LOG_MIDDLEWARE_DNS}/v1/allocation", data=query_data)
        
        for log in allocation_log["logs"]:
            current_history = log["fields"]
            if current_history.get("period"):
                try:
                    current_history["period"] = int(current_history["period"])
                except:
                    current_history["period"] = 0
            histories.append(current_history)
        
        result["total"] = int(allocation_log["totalCount"]) + len(filtered_ongoing)
        result["histories"] = filtered_ongoing[offset:min(offset+count,filtered_size)] + histories[:query_data["count"]]
        result["count"] = len(result["histories"])
        result["last_idx"] = {"not": "implemented"}    
            
    except Exception as e:
        print(f"[ERROR] instance_history failed: {e}")
        traceback.print_exc()
        result = {
            "total": 0,
            "count": 0,
            "histories": [],
            "last_idx": {"not": "implemented"}
        }
    
    return response(status=0, result=result)


def retrieve_instances(): # TODO 제거
    try:
        workspace_list = db_workspace.get_workspace_list()
        return response(status=1, result=workspace_list)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="error : {}".format(e))

def get_uptime_info(workspace_id: int, start_datetime: str, end_datetime: str):
    workspace_name = None
    if workspace_id:
        workspace = db_workspace.get_workspace(workspace_id=workspace_id)
        if workspace:
            workspace_name = workspace["name"]

    uptime_url = f"{settings.LOG_MIDDLEWARE_DNS}/v1/allocation/uptime"
    print(f"[DEBUG] Requesting uptime from: {uptime_url}")
    print(f"[DEBUG] Request payload: {{'workspaceName': '{workspace_name or ''}', 'startTime': '{start_datetime}', 'endTime': '{end_datetime}'}}")
    
    try:
        uptime_response = requests.post(uptime_url, json={
            "workspaceName": workspace_name or "",
            "startTime": start_datetime,
            "endTime": end_datetime,
        }, timeout=30)
        
        print(f"[DEBUG] Response status code: {uptime_response.status_code}")
        print(f"[DEBUG] Response headers: {dict(uptime_response.headers)}")
        print(f"[DEBUG] Response content: {uptime_response.text}")
        
        if uptime_response.status_code != 200:
            print(f"[ERROR] HTTP {uptime_response.status_code}: {uptime_response.text}")
            return {"workspaceUptimes": [], "projectUptimes": []}
        
        uptime_raw = uptime_response.json()
        print(f"[DEBUG] Parsed JSON: {uptime_raw}")
        
        # 응답 구조 확인
        if 'workspaceUptimes' not in uptime_raw or 'projectUptimes' not in uptime_raw:
            print(f"[DEBUG] Expected keys missing. Available keys: {list(uptime_raw.keys()) if isinstance(uptime_raw, dict) else 'Not a dict'}")
            # 빈 응답 구조로 대체
            return {"workspaceUptimes": [], "projectUptimes": []}
        
        return uptime_raw
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request failed: {e}")
        return {"workspaceUptimes": [], "projectUptimes": []}
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON decode failed: {e}")
        return {"workspaceUptimes": [], "projectUptimes": []}
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return {"workspaceUptimes": [], "projectUptimes": []}

def uptime(workspace_id: int, start_datetime: str, end_datetime: str):
    try:
        uptime_info = get_uptime_info(workspace_id, start_datetime, end_datetime)
        
        # 기본 구조 확인
        if not isinstance(uptime_info, dict):
            print(f"[ERROR] uptime_info is not a dict: {type(uptime_info)}")
            return response(status=0, result={})
        
        # workspaceUptimes 처리
        workspace_uptimes = uptime_info.get("workspaceUptimes", [])
        if not isinstance(workspace_uptimes, list):
            print(f"[ERROR] workspaceUptimes is not a list: {type(workspace_uptimes)}")
            workspace_uptimes = []
        
        # projectUptimes 처리 및 tool 매핑
        project_uptimes = uptime_info.get("projectUptimes", [])
        if not isinstance(project_uptimes, list):
            print(f"[ERROR] projectUptimes is not a list: {type(project_uptimes)}")
            project_uptimes = []
        
        # tool 매핑 테이블
        tool_map = {
            "tool": "training",
            "job": "training", 
            "training": "training",
            "hyperparamsearch": "training",
            "hps": "hps",
            "deployment": "deployment",
        }
        
        # 프로젝트 데이터 처리 및 통합
        project_map = {}
        for info in project_uptimes:
            if not isinstance(info, dict):
                continue
                
            project_name = info.get("projectName", "")
            if "/" in project_name:
                project_name = project_name.split("/")[0]
                
            workspace_name = info.get("workspaceName", "")
            info_type = info.get("type", "")
            mapped_type = tool_map.get(info_type, info_type)
            
            project_key = (workspace_name, mapped_type, project_name)
            
            if project_key not in project_map:
                project_map[project_key] = {
                    "workspaceName": workspace_name,
                    "type": mapped_type,
                    "projectName": project_name,
                    "globalUptimeSeconds": 0,
                    "officeHourUptimeSeconds": 0,
                }
            
            # 정수 변환 시 에러 처리
            try:
                global_seconds = int(info.get("globalUptimeSeconds", 0))
                office_seconds = int(info.get("officeHourUptimeSeconds", 0))
            except (ValueError, TypeError) as e:
                print(f"[ERROR] Failed to convert uptime seconds: {e}")
                global_seconds = 0
                office_seconds = 0
                
            project_map[project_key]["globalUptimeSeconds"] += global_seconds
            project_map[project_key]["officeHourUptimeSeconds"] += office_seconds
        
        result = {
            "workspaceUptimes": workspace_uptimes,
            "projectUptimes": list(project_map.values()),
        }
        
        print(f"[DEBUG] Final result: {result}")
        return response(status=1, result=result)
        
    except Exception as e:
        print(f"[ERROR] uptime function failed: {e}")
        traceback.print_exc()
        return response(status=0, result={})
