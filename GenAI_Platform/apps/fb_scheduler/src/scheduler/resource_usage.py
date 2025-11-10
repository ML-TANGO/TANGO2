from utils import TYPE, PATH, settings, topic_key, redis_key, common
from utils.msa_db import db_project, db_workspace, db_deployment, db_node, db_instance, db_prepro, db_analyzing, db_collect

#############################################
# 항목별 자원 사용량 계산 함수
#############################################
def calculate_project_usage(project):
    used_cpu = used_ram = used_gpu = 0
    tools = db_project.get_project_tools(project_id=project["id"], is_running=True)
    for t in tools:
        pod_per_gpu = t["gpu_count"] / t["pod_count"] if t["gpu_count"] > 1 else 1
        used_gpu += t["gpu_count"]
        used_ram += project["tool_ram_limit"] * t["pod_count"] * pod_per_gpu
        used_cpu += project["tool_cpu_limit"] * t["pod_count"] * pod_per_gpu

    trainings = db_project.get_training_is_running(project_id=project["id"])
    for tr in trainings:
        pod_per_gpu = tr["gpu_count"] / tr["pod_count"] if tr["gpu_count"] > 1 else 1
        used_gpu += tr["gpu_count"]
        used_ram += project["job_ram_limit"] * tr["pod_count"] * pod_per_gpu
        used_cpu += project["job_cpu_limit"] * tr["pod_count"] * pod_per_gpu

    hps_list = db_project.get_hps_is_running(project_id=project["id"])
    for hps in hps_list:
        pod_per_gpu = hps["gpu_count"] / hps["pod_count"] if hps["gpu_count"] > 1 else 1
        used_gpu += hps["gpu_count"]
        used_ram += project["hps_ram_limit"] * hps["pod_count"] * pod_per_gpu
        used_cpu += project["hps_cpu_limit"] * hps["pod_count"] * pod_per_gpu

    return used_cpu, used_ram, used_gpu


def calculate_deployment_usage(deployment):
    used_cpu = used_ram = used_gpu = 0
    deployment_workers = db_deployment.get_deployment_worker_running(deployment_id=deployment["id"])
    for w in deployment_workers:
        used_gpu += w["gpu_per_worker"]
        used_ram += deployment["deployment_ram_limit"]
        used_cpu += deployment["deployment_cpu_limit"]
    return used_cpu, used_ram, used_gpu


def calculate_preprocessing_usage(preprocessing):
    used_cpu = used_ram = used_gpu = 0
    tools = db_prepro.get_preprocessing_tools_sync(preprocessing_id=preprocessing["id"])
    for t in tools:
        pod_per_gpu = t["gpu_count"] / t["pod_count"] if t["gpu_count"] > 1 else 1
        used_gpu += t["gpu_count"]
        used_ram += preprocessing["tool_ram_limit"] * t["pod_count"] * pod_per_gpu
        used_cpu += preprocessing["tool_cpu_limit"] * t["pod_count"] * pod_per_gpu

    jobs = db_prepro.get_job_is_running(preprocessing_id=preprocessing["id"])
    for j in jobs:
        pod_per_gpu = j["gpu_count"] / j["pod_count"] if j["gpu_count"] > 1 else 1
        used_gpu += j["gpu_count"]
        used_ram += preprocessing["job_ram_limit"] * j["pod_count"] * pod_per_gpu
        used_cpu += preprocessing["job_cpu_limit"] * j["pod_count"] * pod_per_gpu

    return used_cpu, used_ram, used_gpu


def calculate_analyzer_usage(analyzer):
    used_cpu = used_ram = used_gpu = 0
    graph_worker = db_analyzing.get_analyzer_graph_list_sync(analyzer_id=analyzer["id"], running=True)
    for worker_info in graph_worker:
        # analyzer gpu 사용 X라고 가정
        used_ram += analyzer["graph_ram_limit"]
        used_cpu += analyzer["graph_cpu_limit"]
    return used_cpu, used_ram, used_gpu


def calculate_collector_usage(collect):
    """
    Collector는 start_datetime이 있으면 cpu, ram 사용 중, etc.
    """
    used_cpu = used_ram = used_gpu = 0
    # 예: 만약 collect["start_datetime"] and collect["end_datetime"] is None 이면 사용 중
    if collect["start_datetime"] and collect["end_datetime"] is None:
        used_cpu += collect["cpu_allocate"]
        used_ram += collect["ram_allocate"]
    return used_cpu, used_ram, used_gpu


def calculate_fine_tuning_usage(model):
    """
    LLM Fine-Tuning 중이면 cpu,ram,gpu 사용
    """
    used_cpu = used_ram = used_gpu = 0
    if model["latest_fine_tuning_status"] in [TYPE.KUBE_POD_STATUS_RUNNING, TYPE.KUBE_POD_STATUS_INSTALLING]:
        used_gpu = model["gpu_count"]
        used_cpu = model["cpu_allocate"] * model["instance_count"] # TODO 해당 부분은 추후 기획 추가 시 변경될 수 있음
        used_ram = model["ram_allocate"] * model["instance_count"]
    return used_cpu, used_ram, used_gpu


#############################################
# 항목별 CPU/RAM Limit값 조회 함수
#############################################
def get_project_limits(project, pod_info):
    if pod_info["work_func_type"] == TYPE.TRAINING_ITEM_A:
        return project["job_cpu_limit"], project["job_ram_limit"]
    elif pod_info["work_func_type"] == TYPE.TRAINING_ITEM_C:
        return project["hps_cpu_limit"], project["hps_ram_limit"]
    elif pod_info["work_func_type"] == TYPE.TRAINING_ITEM_B:
        return project["tool_cpu_limit"], project["tool_ram_limit"]
    return 0, 0


def get_deployment_limits(deployment, pod_info):
    """
    Deployment는 보통 deployment_cpu_limit, deployment_ram_limit
    """
    return deployment["deployment_cpu_limit"], deployment["deployment_ram_limit"]


def get_preprocessing_limits(preprocessing, pod_info):
    if pod_info["work_func_type"] == TYPE.PREPROCESSING_ITEM_B:
        return preprocessing["job_cpu_limit"], preprocessing["job_ram_limit"]
    elif pod_info["work_func_type"] == TYPE.PREPROCESSING_ITEM_A:
        return preprocessing["tool_cpu_limit"], preprocessing["tool_ram_limit"]
    return 0, 0


def get_analyzer_limits(analyzer, pod_info):
    # 예: analyzer["graph_cpu_limit"], analyzer["graph_ram_limit"]
    return analyzer["graph_cpu_limit"], analyzer["graph_ram_limit"]


def get_collector_limits(collect, pod_info):
    # Collector의 cpu_allocate, ram_allocate
    # (pod_info["pod_type"] == TYPE.COLLECT_TYPE)
    return collect["cpu_allocate"], collect["ram_allocate"]

def get_fine_tuning_limits(model, pod_info):
    """
    Fine Tuning (LLM) pod의 자원 제한값을 반환.
    - model: Fine Tuning 모델 정보
    - pod_info: 현재 실행하려는 pod의 정보
    """
    instance_count = model["instance_count"]
    cpu_limit = model["cpu_allocate"] * instance_count
    ram_limit = model["ram_allocate"] * instance_count
    # gpu_limit = model["gpu_count"]  # Fine Tuning은 기본적으로 모델당 고정 GPU 개수 사용

    return cpu_limit, ram_limit #, gpu_limit


#############################################
# Pending 중인 항목별 자원 사용량 측정 함수
#############################################
def usage_for_project(item, qpod, pod_count):
    """
    Project 항목에서 qpod(work_func_type)에 따라
    job/tool/hps CPU, RAM 사용량을 리턴
    """
    cpu = 0
    ram = 0
    wft = qpod["work_func_type"]
    if wft == TYPE.TRAINING_ITEM_A:
        cpu = item["job_cpu_limit"] * pod_count * (qpod["pod_per_gpu"] if qpod["pod_per_gpu"] > 1 else 1)
        ram = item["job_ram_limit"] * pod_count * (qpod["pod_per_gpu"] if qpod["pod_per_gpu"] > 1 else 1)
    elif wft == TYPE.TRAINING_ITEM_B:
        cpu = item["tool_cpu_limit"] * pod_count * (qpod["pod_per_gpu"] if qpod["pod_per_gpu"] > 1 else 1)
        ram = item["tool_ram_limit"] * pod_count * (qpod["pod_per_gpu"] if qpod["pod_per_gpu"] > 1 else 1)
    elif wft == TYPE.TRAINING_ITEM_C:
        cpu = item["hps_cpu_limit"] * pod_count * (qpod["pod_per_gpu"] if qpod["pod_per_gpu"] > 1 else 1)
        ram = item["hps_ram_limit"] * pod_count * (qpod["pod_per_gpu"] if qpod["pod_per_gpu"] > 1 else 1)
    return cpu, ram

def usage_for_deployment(item, qpod, pod_count):
    """
    Deployment 항목에서 deployment_cpu_limit, deployment_ram_limit를 적용
    """
    # pod_count가 여러 개라도, 보통 deployment는 worker 하나당 cpu/ram 이 동일
    # 단순 계산: item["deployment_cpu_limit"], item["deployment_ram_limit"]
    cpu = item["deployment_cpu_limit"]
    ram = item["deployment_ram_limit"]
    # 만약 여러 Worker가 동시에 생긴다면 pod_count 배수로 적용할 수도 있음
    return cpu, ram

def usage_for_preprocessing(item, qpod, pod_count):
    """
    Preprocessing에서 tool(job_cpu_limit) / job(tool_ram_limit) 구분
    """
    cpu = 0
    ram = 0
    wft = qpod["work_func_type"]
    if wft == TYPE.PREPROCESSING_ITEM_A:  # tool
        cpu = item["tool_cpu_limit"] * pod_count * (qpod["pod_per_gpu"] if qpod["pod_per_gpu"] > 1 else 1)
        ram = item["tool_ram_limit"] * pod_count * (qpod["pod_per_gpu"] if qpod["pod_per_gpu"] > 1 else 1)
    elif wft == TYPE.PREPROCESSING_ITEM_B:  # job
        cpu = item["job_cpu_limit"] * pod_count * (qpod["pod_per_gpu"] if qpod["pod_per_gpu"] > 1 else 1)
        ram = item["job_ram_limit"] * pod_count * (qpod["pod_per_gpu"] if qpod["pod_per_gpu"] > 1 else 1)
    return cpu, ram

def usage_for_analyzer(item, qpod, pod_count):
    """
    Analyzer 항목에서 graph_cpu_limit, graph_ram_limit
    GPU는 보통 0
    """
    # 보통 Analyzer는 pod_count=1인 경우가 많음
    cpu = item["graph_cpu_limit"]
    ram = item["graph_ram_limit"]
    return cpu, ram

def usage_for_collector(item, qpod, pod_count):
    """
    Collector에서는 collect["cpu_allocate"], collect["ram_allocate"] 등
    """
    cpu = item["cpu_allocate"]  # 여러 개를 동시에 띄운다면 * pod_count
    ram = item["ram_allocate"]
    return cpu, ram

def usage_for_fine_tuning(model, qpod, pod_count):
    """
    Fine Tuning (LLM) pod이 사용하는 CPU, RAM, GPU 사용량을 계산.
    - model: Fine Tuning 모델 정보 (db_model.get_models_sync)
    - qpod: 현재 실행하려는 pod 정보
    - pod_count: GPU 클러스터링을 적용했을 때 pod 개수
    """
    instance_count = model["instance_count"]
    used_cpu = model["cpu_allocate"] * instance_count * pod_count
    used_ram = model["ram_allocate"] * instance_count * pod_count
    used_gpu = model["gpu_count"]  # Fine Tuning은 GPU 고정량 사용

    return used_cpu, used_ram, used_gpu
