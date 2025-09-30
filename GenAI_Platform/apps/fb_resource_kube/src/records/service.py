from calendar import month
import requests
import traceback

from utils.resource import response
import datetime
import random
from utils.msa_db import db_workspace, db_project
from utils import settings

# Min / 임시로 기록 구현한 내용, 추후 분리 필요! TODO

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
        if headers_user != settings.ADMIN_NAME and False: # TODO 권한체크 스킵 (and False) 제거
            return response(status=0, message="permission denied")
        return response(status=1, result=db_workspace.get_workspace_list())
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


def records_history(page: int, size: int, sort: str, order: str, action: str, task: str):
    offset = (page - 1) * size

    try:
        history_url = f"http://log-middleware-rest.jonathan-efk:8080/v1/dashboard/admin/detail"
        history_response = requests.post(history_url, json={
            "timespan": "1y",
            "count": size,
            "offset": offset,
            "ascending": (True if order == "asc" else False),
            "action": action,
            "task": task
        })
        history_raw = history_response.json()
        histories = []
        for history in history_raw["logs"]:
            current_document = history["fields"]
            current_document["update_details"] = "-"
            histories.append(current_document)
    except:
        return response(status=1, result={"list": [], "total": 0})

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



def summary():
    workspaces = db_workspace.get_workspace_list()
    result = []
    for workspace in workspaces:
        id = workspace["id"]
        name = workspace["name"]
        activate = True # 임시로 상항 Activate 설정, 어떤 값이 들어가야 하는지 TODO
        result.append(generate_workspace_info(name, activate))
    return response(status=1, result=result)

def utilization_figure(workspace_id, start_datetime, end_datetime, aggregation):
    data_util = []
    start_datetime = datetime.datetime.strptime(start_datetime, "%Y-%m-%d %H:%M:%S") if start_datetime else datetime.datetime.now() - datetime.timedelta(hours=2)
    end_datetime = datetime.datetime.strptime(end_datetime, "%Y-%m-%d %H:%M:%S") if end_datetime else datetime.datetime.now()
    current_datetime = start_datetime
    cpu = random.randint(1, 10)
    cpu_tend = random.randint(-1, 1)
    gpu = (cpu + random.randint(1, 4)) // 2
    gpu_tend = (cpu_tend + random.randint(-1, 1)) // 2
    ram = random.randint(1, 16) * 2
    ram_tend = (cpu_tend * 2 + random.randint(-2, 2)) // 2 * 2
    storage = random.randint(10, 5000)
    storage_tend = random.randint(-9_999, 9_999)
    timetable = {
        "minute": datetime.timedelta(minutes=1),
        "hour": datetime.timedelta(hours=1),
        "day": datetime.timedelta(days=1),
        "week": datetime.timedelta(weeks=1),
        "month": datetime.timedelta(days=30),
        "quarter": datetime.timedelta(days=90),
        "year": datetime.timedelta(days=365)
    }
    while current_datetime < end_datetime:
        current_data = {}
        current_data["timestamp"] = current_datetime.strftime("%Y-%m-%d %H:%M")
        reset_flag = random.random()
        cpu += random.randint(-2, 3) if workspace_id else random.randint(-3, 6)
        cpu += cpu_tend
        if cpu < 0 or (workspace_id and cpu > 20) or cpu > 50 or reset_flag < 0.03:
            cpu = (cpu + (random.randint(5, 15) if workspace_id else random.randint(10, 40))) // 2
        current_data["cpu"] = cpu
        gpu += random.randint(-1, 2) if workspace_id else random.randint(-4, 6)
        gpu += gpu_tend
        if gpu < 0 or (workspace_id and gpu > 15) or gpu > 40 or reset_flag < 0.03:
            gpu = (gpu + (random.randint(3, 12) if workspace_id else random.randint(5, 25))) // 2
        current_data["gpu"] = gpu
        ram += random.randint(-5, 12) if workspace_id else random.randint(-8, 16)
        ram += ram_tend
        if ram < 0 or (workspace_id and ram > 64) or ram > 256 or reset_flag < 0.02:
            ram = (ram + (random.randint(16, 48) if workspace_id else random.randint(32, 128)) * 3) // 8 * 2
        current_data["ram"] = ram
        storage += random.randint(-400_000, 900_000) if workspace_id else random.randint(-1_000_000, 2_500_000)
        storage += storage_tend
        if storage < 0 or (workspace_id and storage > 9_999_999) or storage > 59_999_999 or reset_flag < 0.035:
            storage = random.randint(100_000, 5_500_000) if workspace_id else random.randint(1_000_000, 30_000_000)
        current_data["storage"] = storage
        data_util.append(current_data)
        current_datetime += timetable[aggregation]
    return response(status=1, result=data_util)


def instance_info(workspace_id):
    result = {}
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


history_map = {}
def instance_history(
    workspace_id,
    start_datetime, end_datetime,
    page, size,
    type,
    search_key, search_term
):
    global history_map
    """
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
    start_datetime = datetime.datetime.strptime(start_datetime, "%Y-%m-%d %H:%M:%S") if start_datetime else None
    end_datetime = datetime.datetime.strptime(end_datetime, "%Y-%m-%d %H:%M:%S") if end_datetime else None

    result = {}
    histories = []
    workspaces = db_workspace.get_workspace_list()
    workspace_name = "not_found_internal_err"
    if workspace_id:
        for workspace in workspaces:
            if workspace["id"] == workspace_id:
                workspace_name = workspace["name"]
                break
    else:
        workspace_name = "all-placeholder"

    if workspace_name in history_map:
        if random.random() < 0.35:
            history = generate_history(random.choice(workspaces)["name"], datetime.datetime.now())
            history_map[workspace_name].append(history)
    else:
        if workspace_name == "all-placeholder":
            current_time = datetime.datetime.now()
            history_map[workspace_name] = []
            for _ in range(random.randint(20, 120)):
                current_time += datetime.timedelta(days=random.randint(-10, -1), hours=random.randint(0, 23), minutes=random.randint(0, 59), seconds=random.randint(0, 59))
                history = generate_history(random.choice(workspaces)["name"], current_time)
                history_map[workspace_name].append(history)
        else:
            current_time = datetime.datetime.now()
            history_map[workspace_name] = []
            for _ in range(random.randint(20, 80)):
                current_time += datetime.timedelta(days=random.randint(-10, -1), hours=random.randint(0, 23), minutes=random.randint(0, 59), seconds=random.randint(0, 59))
                history = generate_history(workspace_name, current_time)
                history_map[workspace_name].append(history)

    for history in history_map[workspace_name]:
        if type and history["type"] != type:
            continue
        if start_datetime and datetime.datetime.strptime(history["end_datetime"], "%Y-%m-%d %H:%M:%S") < start_datetime:
            continue
        if end_datetime and datetime.datetime.strptime(history["start_datetime"], "%Y-%m-%d %H:%M:%S") > end_datetime:
            continue
        if search_key and search_term:
            if search_key == "workspace":
                if search_term not in history["workspace_name"]:
                    continue
            elif search_key == "training":
                if history["type"] not in ["job", "hyperparamsearch"]:
                    continue
                if search_term not in history["type_detail"].split(" / ")[0]:
                    continue
            elif search_key == "deployment":
                if history["type"] != "deployment":
                    continue
                if search_term not in history["type_detail"]:
                    continue
        histories.append(history)

    result["total"] = len(histories)
    histories = histories[(page - 1) * size:page * size]
    result["count"] = len(histories)
    result["histories"] = histories
    result["last_idx"] = {"not": "implemented"}

    return response(status=0, result=result)


def retrieve_instances(): # TODO 제거
    return response(status=0, result=db_workspace.get_workspace_list())
