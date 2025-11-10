from utils import TYPE, PATH, settings, topic_key, redis_key, common
from utils.msa_db import db_project, db_workspace, db_deployment, db_node, db_instance, db_prepro, db_analyzing, db_collect
from utils.redis import get_redis_client, RedisQueue
from scheduler.collect_run import create_crawling_collector, create_fb_deployment_collector, create_public_api_collector, create_remote_server_collector
from scheduler.project_tool_run import create_hps_pod, create_training_pod, create_project_tool
from scheduler.preprocessing_tool_run import create_preprocessing_tool, create_preprocessing_job
if settings.LLM_USED:
    from utils.llm_db import db_model
    from scheduler.llm_run import create_fine_tuning
    from scheduler.helm_run import uninstall_deployment_llm
from scheduler.helm_run import (install_deployment_pod, install_deployment_svc_ing, uninstall_pod_deployment,
                                delete_helm_project, delete_helm_fine_tuning, install_deployment_llm, delete_helm_preprocessing,
                                create_analyzer_pod, delete_helm_analyzer)

from typing import List
from collections import defaultdict
from functools import reduce

from confluent_kafka import Consumer
from confluent_kafka.admin import AdminClient
from kubernetes import config, client

import json, traceback, time, sys, threading
import random
import math, re
import logging

config.load_kube_config(config_file=settings.KUBER_CONFIG_PATH)
coreV1Api = client.CoreV1Api()
KAFKA_TIMEOUT = 0.5

"""
 자원 부족
 * pods "h27b0d4a3c2c549f1e8724f581859a595-518" is forbidden: exceeded quota: jfb-93-quota, requested: limits.memory=330Gi, used: limits.memory=6Gi, limited: limits.memory=20Gi


 이미 실행중 
  Error: INSTALLATION FAILED: release: already exists    
"""

# Consumer 설정
conf = {
    'bootstrap.servers': settings.JF_KAFKA_DNS,
    'group.id': 'mygroup',
    'auto.offset.reset': 'earliest',
    # 'enable.auto.commit' : True,
    'max.poll.interval.ms': 10000, # 첫번째 polling 시 느린 문제?
    'session.timeout.ms': 10000, # 최소값, 6000 이하로 설정시 JoinGroup failed: Broker: Invalid session timeout
}
kafka_admin_conf = {
    'bootstrap.servers' : settings.JF_KAFKA_DNS
}


class ThreadingLock:
    def __init__(self, lock):
        self.lock = lock

    def __enter__(self):
        self.lock.acquire()

    def __exit__(self, t, v, tb):
        self.lock.release()
        if tb is not None:
            traceback.print_exception(t, v, tb)
        return True

jf_tlock = ThreadingLock(threading.Lock())

# redis_client = get_redis_client(role="slave")


"""
{
    workspace_id : {
        instance_id: pod_info
    }
    
}

"""

def get_gpu_auto_select(gpu_count: int, pod_count: int, gpu_data: list):
    # 결과를 저장할 리스트
    result = []

    # GPU를 노드 이름별로 그룹화
    available_gpus = {}
    for gpu_info in gpu_data:
        node_name = gpu_info['node_name']
        gpu_uuid = gpu_info['gpu_uuid']
        if node_name not in available_gpus:
            available_gpus[node_name] = []
        available_gpus[node_name].append(gpu_uuid)

    # 필요한 GPU의 총 수
    total_required_gpus = pod_count * gpu_count

    # 사용할 수 있는 GPU를 할당
    allocated_gpus = 0
    for node_name, gpus in available_gpus.items():
        if len(gpus) < gpu_count: # 해당 노드에 pod에 같이 할당 할 수 있는 gpu 개수가 부족할 경우 pass
            continue
        while allocated_gpus < total_required_gpus and gpus:
            for _ in range(gpu_count):
                if gpus and allocated_gpus < total_required_gpus:
                    result.append({'node_name': node_name, 'gpu_uuid': gpus.pop(0)})
                    allocated_gpus += 1

        # 필요한 GPU의 수에 도달하면 루프 종료
        if allocated_gpus >= total_required_gpus:
            break

    # 필요한 GPU가 충분하지 않은 경우 예외 발생
    if allocated_gpus < total_required_gpus:
        return []

    return result

def get_optimal_gpus(data, num_gpus):
    nodes = defaultdict(list)
    for item in data:
        nodes[item["node_name"]].append(item["gpu_uuid"])
    
    # 노드를 내림차순으로 정렬하는 GPU 수를 기준으로 노드 정렬
    sorted_nodes = sorted(nodes.items(), key=lambda x: len(x[1]), reverse=True)
    
    result = []
    remaining_gpus = num_gpus

    for node, gpus in sorted_nodes:
        if remaining_gpus <= 0:
            break
        
        # 노드에 요청을 수행할 수 있는 충분한 GPU가 있으면 필요한 것만 가져갑니다
        if len(gpus) >= remaining_gpus:
            result.extend([{"node_name": node, "gpu_uuid": gpu} for gpu in gpus[:remaining_gpus]])
            remaining_gpus = 0
        else:
            # 그렇지 않으면 이 노드에서 모든 GPU를 가져가고 다음 노드로 계속 이동합니다
            result.extend([{"node_name": node, "gpu_uuid": gpu} for gpu in gpus])
            remaining_gpus -= len(gpus)
    
    return result



def gpu_auto_clustering(available_gpus : List[dict], pod_per_gpu : int = None):
    # 노드를 기준으로 데이터를 그룹화
    grouped_data = defaultdict(list)
    for item in available_gpus:
        grouped_data[item["node_name"]].append(item["gpu_uuid"])

    # 노드별 GPU UUID 개수를 셈
    node_counts = {node: len(uuids) for node, uuids in grouped_data.items()}

    # 최대 공약수를 계산하는 함수
    def gcd(a, b):
        while b:
            a, b = b, a % b
        return a

    # 여러 숫자의 최대 공약수를 계산하는 함수
    def gcd_multiple(numbers):
        return reduce(gcd, numbers)

    # 노드별 GPU UUID 개수 리스트
    counts = list(node_counts.values())

    # 최대 공약수 계산
    if pod_per_gpu:
        max_gcd = pod_per_gpu
    else:
        max_gcd = gcd_multiple(counts)

    # 최대 공약수에 맞춰 GPU UUID를 분리
    result = []
    for node, uuids in grouped_data.items():
        chunks = [uuids[i:i + max_gcd] for i in range(0, len(uuids), max_gcd)]
        for chunk in chunks:
            result.append({"node_name": node, "gpu_uuids": chunk})
    return result


def get_used_gpu_uuid(label_select : str):
        used_gpu_uuid = []
        live_pods = coreV1Api.list_pod_for_all_namespaces(label_selector=label_select).items
        for live_pod in live_pods:
            pod_labels = live_pod.metadata.labels
            pod_status = live_pod.status.phase
            if pod_status not in ["Succeeded", "Failed"]: # 동작 중인 pod만 검색 
                if "gpu_ids" in pod_labels:
                    for gpu_id in pod_labels["gpu_ids"].split("."):
                        if gpu_id:
                            used_gpu_uuid.append(db_node.get_node_gpu(gpu_id=gpu_id)["gpu_uuid"])
        return list(set(used_gpu_uuid))

def get_available_gpus_by_model(model_name, data, instance_id):
    
    node_list = db_node.get_node_instance_list(instance_id=instance_id)
    
    node_name_list = [node["node_name"] for node in node_list]
    
    available_gpus = [
        {"node_name": node_name, "gpu_uuid": gpu_uuid}
        for node_name, gpus in data.items()
        for gpu_uuid, gpu in gpus.items()
        if gpu['model_name'] == model_name and not gpu['used_info'] and node_name in node_name_list
    ]
    # return available_gpus[:num_gpus]
    return available_gpus
def acked(err, msg):
    if err is not None:
        print("Failed to deliver message: %s: %s" % (str(msg), str(err)))
    else:
        print("Message produced: %s" % (str(msg)))


def try_json_deserializer(data):
    try:
        return json.loads(data.decode('utf-8'))
    except (json.JSONDecodeError, AttributeError):
        print("디코드 오류", file=sys.stderr)
        return json.loads(data)


"""
scheduler 정리 

1. 각 project , deployment 에서 kafka 에 pod 생성 요청을 날림 

2. workspace_item_pod_check thread 에서 각 project, deployment 별로 추가로 생성 할 수 있는지 check
    2-1. redis WORKSPACE_ITEM_PENDING_POD 에서 각 project 및 deployment 별 pending에 걸린 pod 요청이 있는지 확인
    2-2. pending에 걸린 pod 요청이 없을 경우 kafka에서 요청된 pod 이 있는지 확인 
    2-3. 각 project, deployment 별로 cpu, ram 사용율을 계산  

3. pod_start_new 에서 workspace instance 별로 pod 실행 여부를 check 
    3-1 요청한 gpu model 이름과 해당 model 이 속한 instance를 가지고 있는 node 들 중에서 검색 후 사용가능한 gpu model 리스트를 조회
    3-2 요청한 gpu의 개수가 2개 이상일 경우 auto, select 기준으로 gpu model 선정 
    3-3 위 정보를 추가로 helm install 실행 실패 시  WORKSPACE_INSTANCE_PENDING_POD 에 pod 정보 추가 



"""

def pod_start_new():
    def pending_item_arrange(pending_items , item_ids):
        pending_item_ids = list(pending_items.keys())
        del_item_ids = set(pending_item_ids) - set(item_ids) 
        for del_item_id in list(del_item_ids):
            del pending_items[del_item_id]

    def db_sync(pending_pod : dict, pod_info : dict, pending_flag : bool = False, project = None, deployment = None, preprocessing = None, analyzer = None):
        if pod_info["pod_type"] == TYPE.PROJECT_TYPE:
            if pod_info["work_func_type"] == TYPE.TRAINING_ITEM_A:
                training_info = db_project.get_training(training_id=pod_info["id"])
                if training_info is None or training_info["end_datetime"]:
                    if pending_flag:
                        del pending_pod[str(project["id"])] # 이미 삭제된 요청이라면 pending에서 삭제
                    return False
            elif pod_info["work_func_type"] == TYPE.TRAINING_ITEM_C:
                hps_info = db_project.get_hps(hps_id=pod_info["id"])
                if hps_info is None or hps_info["end_datetime"]:
                    if pending_flag:
                        del pending_pod[str(project["id"])]
                    return False
            elif pod_info["work_func_type"] == TYPE.TRAINING_ITEM_B:
                tool_info =db_project.get_project_tool(project_tool_id=pod_info["id"])
                if tool_info is None or not tool_info['request_status'] or tool_info["end_datetime"]:
                    if pending_flag:
                        del pending_pod[str(project["id"])]
                    return False
        elif pod_info["pod_type"] == TYPE.PREPROCESSING_TYPE:
            if pod_info["work_func_type"] == TYPE.PREPROCESSING_ITEM_A:
                tool_info = db_prepro.get_preprocessing_tool_sync(preprocessing_tool_id=pod_info["id"])
                if tool_info is None or not tool_info['request_status']:
                    if pending_flag:
                        del pending_pod[str(preprocessing["id"])]
                    return False
            elif pod_info["work_func_type"] == TYPE.PREPROCESSING_ITEM_B:
                job_info = db_prepro.get_job_simple(preprocessing_job_id=pod_info["id"])
                if job_info is None or job_info["end_datetime"]:
                    if pending_flag:
                        del pending_pod[str(preprocessing["id"])] # 이미 삭제된 요청이라면 pending에서 삭제
                    return False
        elif pod_info["pod_type"] == TYPE.ANALYZER_TYPE:
            analyzer_graph_info = db_analyzing.get_analyzer_graph_sync(id=pod_info.get("graph_id"))
            if analyzer_graph_info is None or analyzer_graph_info.get("end_datetime"):
                if pending_flag:
                    del pending_pod[str(analyzer.get("id"))]
                return False
        elif pod_info["pod_type"] == TYPE.DEPLOYMENT_TYPE: # 배포
            worker_info = db_deployment.get_deployment_worker(deployment_worker_id=pod_info["deployment_worker_id"])
            if worker_info is None or worker_info["end_datetime"]:
                if pending_flag:
                    del pending_pod[str(deployment["id"])]
                return False         
        return True
    

    def workspace_db_sync(pod_info):
        if pod_info["pod_type"] == TYPE.PROJECT_TYPE:
            if pod_info["work_func_type"] == TYPE.TRAINING_ITEM_A:
                training_info = db_project.get_training(training_id=pod_info["id"])
                if training_info is None or training_info["end_status"] == TYPE.KUBE_POD_STATUS_STOP or training_info["instance_id"] is None or training_info["end_datetime"]:
                    return False    
            elif pod_info["work_func_type"] == TYPE.TRAINING_ITEM_C:
                hps_info = db_project.get_hps(hps_id=pod_info["id"])
                if hps_info is None or hps_info["end_datetime"]: # hps가 삭제 되었거나 중지되었을 떄 
                    return False    
            elif pod_info["work_func_type"] == TYPE.TRAINING_ITEM_B:
                tool_info =db_project.get_project_tool(project_tool_id=pod_info["id"])
                if tool_info is None or not tool_info['request_status'] or tool_info["gpu_count"] != pod_info["gpu_count"] \
                    or tool_info["image_real_name"] != pod_info["image_name"] or json.loads(tool_info["gpu_select"]) != pod_info["gpu_select"] or \
                        tool_info["instance_id"] is None or tool_info["end_datetime"]: # tool이 삭제 되었거나 , 중지 , gpu 개수가 변경 되었을 경우, gpu 클러스터링이 변경 되었을 경우 삭제
                    return False    
        elif pod_info["pod_type"] == TYPE.PREPROCESSING_TYPE:
            if pod_info["work_func_type"] == TYPE.PREPROCESSING_ITEM_A:
                tool_info = db_prepro.get_preprocessing_tool_sync(preprocessing_tool_id=pod_info["id"])
                if tool_info is None or not tool_info['request_status'] or tool_info["gpu_count"] != pod_info["gpu_count"] or \
                    tool_info["image_real_name"] != pod_info["image_name"] or json.loads(tool_info["gpu_select"]) != pod_info["gpu_select"] or \
                        tool_info["instance_id"] is None or tool_info["end_datetime"]:
                    return False
            elif pod_info["work_func_type"] == TYPE.PREPROCESSING_ITEM_B:
                job_info = db_prepro.get_job_simple(preprocessing_job_id=pod_info["id"])
                if job_info is None or job_info["end_datetime"] or job_info["instance_id"] is None:
                    return False
        elif pod_info.get("pod_type") == TYPE.ANALYZER_TYPE:
            analyzer_graph_info = db_analyzing.get_analyzer_graph_sync(id=pod_info.get("graph_id"))
            if analyzer_graph_info is None or analyzer_graph_info.get("end_datetime") or analyzer_graph_info.get("instance_id") is None:
                return False
        elif pod_info["pod_type"] == TYPE.DEPLOYMENT_TYPE:
            worker_info = db_deployment.get_deployment_worker(deployment_worker_id=pod_info["deployment_worker_id"])
            if worker_info is None or worker_info["end_datetime"] or worker_info["instance_id"] is None:
                return False    
        elif pod_info["pod_type"] == TYPE.COLLECT_TYPE:
            collect_info = db_collect.get_collect_info(collect_id=pod_info["collect_info"]["id"])
            if collect_info is None or collect_info["end_datetime"] or collect_info["instance_id"] is None:
                return False    
        if settings.LLM_USED:
            if pod_info["pod_type"] == TYPE.FINE_TUNING_TYPE:
                model_info = db_model.get_model_sync(model_id=pod_info["model_id"])
                if model_info is None or model_info["latest_fine_tuning_status"] == TYPE.KUBE_POD_STATUS_STOP:
                    return False
        return True
    
    # 로깅 설정
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    consumer = Consumer(conf)
    kafka_admin = AdminClient(kafka_admin_conf)
    
    
    while True:
        try:
            time.sleep(0.1)
            redis_client = get_redis_client()
            workspace_list = db_workspace.get_workspace_list()

            pod_info = dict()
            kafka_topic_list = [topic for topic in kafka_admin.list_topics().topics]
            kafka_topic_list = [x for x in kafka_topic_list if x != '__consumer_offsets']   
            try:
                if kafka_topic_list:
                    consumer.subscribe(kafka_topic_list)
                    msg = consumer.poll(timeout=KAFKA_TIMEOUT)
                    if msg:
                        # print(try_json_deserializer(msg.value()), file=sys.stderr)
                        pod_info = try_json_deserializer(msg.value())
            except Exception as e:
                logging.error("Exception occurred while fetching Kafka message", exc_info=True)
                continue
            # consumer.unsubscribe()
            
            for workspace in workspace_list:
                
                # print("kafla_topic_list : ", kafka_topic_list, file=sys.stderr)
                logging.info(f"workspace : {workspace["id"]}")
                print("pod_info 1: ", pod_info , file=sys.stderr)
                #======================================================================
                # workspace item queue
                #======================================================================
                
                workspace_instance_used_resource = {}
                
                workspace_item_pending_pod = redis_client.hget(redis_key.WORKSPACE_ITEM_PENDING_POD2, workspace["id"])
                if not workspace_item_pending_pod:
                    workspace_item_pending_pod = {
                        TYPE.PROJECT_TYPE : {
                            # "1" : [],
                        },
                        TYPE.DEPLOYMENT_TYPE : {},
                        TYPE.PREPROCESSING_TYPE : {},
                        TYPE.ANALYZER_TYPE : {},
                        TYPE.COLLECT_TYPE : {},
                    }
                else:
                    workspace_item_pending_pod = json.loads(workspace_item_pending_pod)

                logging.info(f"workspace pending pod : {workspace_item_pending_pod}")

                # [Project] 
                project_list = db_project.get_project_list(workspace_id=workspace["id"])
                project_pending_pod = workspace_item_pending_pod[TYPE.PROJECT_TYPE]
                
                for project in project_list:
                    project["gpu_allocate"] = project["gpu_allocate"] if project["gpu_allocate"] else 0
                    project["cpu_allocate"] = project["cpu_allocate"] if project["cpu_allocate"] else 0
                    project["ram_allocate"] = project["ram_allocate"] if project["ram_allocate"] else 0
                    
                    project_gpu_allocate = project["gpu_allocate"] * project["instance_allocate"]
                    project_cpu_allocate = project["cpu_allocate"] * project["instance_allocate"]
                    project_ram_allocate = project["ram_allocate"] * project["instance_allocate"]
                    used_gpu_allocate = 0
                    used_ram_allocate = 0
                    used_cpu_allocate = 0
                    pending_gpu_allocate = 0
                    pending_ram_allocate = 0
                    pending_cpu_allocate = 0
                    
                    tools = db_project.get_project_tools(project_id=project["id"], is_running=True)
                    trainings = db_project.get_training_is_running(project_id=project["id"])
                    hps_list = db_project.get_hps_is_running(project_id=project["id"])
                    for tool_info in tools:
                        used_gpu_allocate += tool_info["gpu_count"]
                        used_ram_allocate += project["tool_ram_limit"]*tool_info["pod_count"]
                        used_cpu_allocate += project["tool_cpu_limit"]*tool_info["pod_count"]
                    for training_info in trainings:
                        used_gpu_allocate += training_info["gpu_count"] 
                        used_ram_allocate += project["job_ram_limit"]*training_info["pod_count"]
                        used_cpu_allocate += project["job_cpu_limit"]*training_info["pod_count"]
                    
                    for hps in hps_list:
                        used_gpu_allocate += hps["gpu_count"] 
                        used_ram_allocate += project["hps_ram_limit"]*hps["pod_count"]
                        used_cpu_allocate += project["hps_cpu_limit"]*hps["pod_count"]
                    
                    
                    if workspace_instance_used_resource.get(project["instance_id"], None):
                        workspace_instance_used_resource[project["instance_id"]]["cpu"] += used_cpu_allocate
                        workspace_instance_used_resource[project["instance_id"]]["ram"] += used_ram_allocate
                        workspace_instance_used_resource[project["instance_id"]]["gpu"] += used_gpu_allocate
                    else:
                        workspace_instance_used_resource[project["instance_id"]] ={
                            "cpu" : used_cpu_allocate,
                            "ram" : used_ram_allocate,
                            "gpu" : used_gpu_allocate
                        }
                    # print("project : ", project["id"],file=sys.stderr)
                    # print(workspace_instance_used_resource.get(18, "없음"),file=sys.stderr)
                    # topic = topic_key.PROJECT_TOPIC.format(project["id"]) # TODO 포맷 변경
                    # pending_flag = False
                    project_id = str(project["id"])

                    if project_id not in project_pending_pod:
                        project_pending_pod[project_id] = []
                        if not (pod_info and pod_info.get("pod_type") == TYPE.PROJECT_TYPE and pod_info.get("project_id") == project["id"]):
                            continue

                    if pod_info and pod_info.get("pod_type") == TYPE.PROJECT_TYPE and pod_info.get("project_id") == project["id"]:
                        project_pending_pod[project_id].append(pod_info)

                    if not project_pending_pod[project_id]:
                        continue
                    pp_info = project_pending_pod[project_id].pop(0)

                    # if not db_sync(pending_pod=project_pending_pod, pod_info=pod_info, pending_flag=pending_flag, project=project):
                    #     continue
                    
                    instance_key = redis_key.WORKSPACE_INSTANCE_QUEUE.format(workspace["id"], project["instance_id"]) # TODO 포맷 변경
                    redis_queue = RedisQueue(redis_client=redis_client, key=instance_key)
                    
                    
                    # workspace로  대기중인 pod 확인 
                    # instance queue 확인 
                    instance_queue = redis_queue.fetch_queue_items()
                    # print("instance_queue : ", instance_queue, file=sys.stderr)
                    for instance_queue_pod in instance_queue:
                        # instance_pod = {}
                        instance_queue_pod = json.loads(instance_queue_pod)
                        if instance_queue_pod.get("project_id", None) == project["id"]:
                            
                            pending_gpu_allocate += instance_queue_pod["gpu_count"]
                            pod_count = 1
                            if instance_queue_pod["gpu_cluster_auto"]:
                                pod_count = instance_queue_pod["gpu_auto_cluster_case"]["server"]
                            elif instance_queue_pod["gpu_count"] > 1:
                                pod_count = instance_queue_pod["gpu_count"]/instance_queue_pod["pod_per_gpu"] if instance_queue_pod["pod_per_gpu"] != 0 else instance_queue_pod["gpu_count"]
                            
                            if instance_queue_pod.get("work_func_type", None) == TYPE.TRAINING_ITEM_A:
                                pending_ram_allocate += project["job_ram_limit"]*pod_count
                                pending_cpu_allocate += project["job_cpu_limit"]*pod_count
                            elif instance_queue_pod.get("work_func_type", None) == TYPE.TRAINING_ITEM_C:
                                pending_ram_allocate += project["hps_ram_limit"]*pod_count
                                pending_cpu_allocate += project["hps_cpu_limit"]*pod_count
                            elif instance_queue_pod.get("work_func_type", None) == TYPE.TRAINING_ITEM_B:
                                pending_ram_allocate += project["tool_ram_limit"]*pod_count
                                pending_cpu_allocate += project["tool_cpu_limit"]*pod_count

                    available_gpu = project_gpu_allocate - used_gpu_allocate - pending_gpu_allocate
                    available_cpu = project_cpu_allocate - used_cpu_allocate - pending_cpu_allocate
                    available_ram = project_ram_allocate - used_ram_allocate - pending_ram_allocate
                    # CPU 및 RAM 자원량 확인 
                    # job, tool 에 설정된 자원량보다 적으면 pending
                    pod_count = 1
                    if pp_info["gpu_cluster_auto"]:
                        pod_count = pp_info["gpu_auto_cluster_case"]["server"]
                    elif pp_info["gpu_count"] > 1:
                        pod_count = pp_info["gpu_count"]/pp_info["pod_per_gpu"] if pp_info["pod_per_gpu"] != 0 else pp_info["gpu_count"]
                    
                    logging.info(f"Project {project["id"]} 에서 사용 가능한 자원")
                    logging.info(f'available_cpu:{available_cpu}, available_ram : {available_ram}, available_gpu : {available_gpu} ')
                    
                    if pp_info["work_func_type"] == TYPE.TRAINING_ITEM_A:
                        pp_info["resource"] = {
                            "cpu" : project["job_cpu_limit"],
                            "ram" : project["job_ram_limit"]
                        }
                        
                        if available_cpu < (project["job_cpu_limit"]*pod_count) or available_ram < (project["job_ram_limit"]*pod_count) or available_gpu < pp_info["gpu_count"]:
                            project_pending_pod[str(project["id"])].insert(0,pp_info)
                            continue
                    elif pp_info["work_func_type"] == TYPE.TRAINING_ITEM_C:
                        pp_info["resource"] = {
                            "cpu" : project["hps_cpu_limit"],
                            "ram" : project["hps_ram_limit"]
                        }
                        
                        if available_cpu < (project["hps_cpu_limit"]*pod_count) or available_ram < (project["hps_ram_limit"]*pod_count) or available_gpu < pp_info["gpu_count"]:
                            project_pending_pod[str(project["id"])].insert(0,pp_info)
                            continue
                    elif pp_info["work_func_type"] == TYPE.TRAINING_ITEM_B:
                        pp_info["resource"] = {
                            "cpu" : project["tool_cpu_limit"],
                            "ram" : project["tool_ram_limit"]
                        }
                        
                        if available_cpu < (project["tool_cpu_limit"]*pod_count) or available_ram < (project["tool_ram_limit"]*pod_count) or available_gpu < pp_info["gpu_count"]:
                            project_pending_pod[str(project["id"])].insert(0,pp_info)
                            continue
                    print("pod_info 3 : ",  pp_info, file=sys.stderr)
                    redis_queue.rput(json.dumps(pp_info))
                
                pending_item_arrange(project_pending_pod, [str(p["id"]) for p in project_list])

                print("학습 총 사용량 : ", workspace_instance_used_resource, file=sys.stderr)
                # [deployment] 
                deployment_list = db_deployment.get_deployment_list_in_workspace(workspace_id=workspace["id"])
                deployment_pending_pod = workspace_item_pending_pod[TYPE.DEPLOYMENT_TYPE]
                    
                for deployment in deployment_list:             
                    deployment["gpu_allocate"] = deployment["gpu_allocate"] if deployment["gpu_allocate"] else 0
                    deployment["cpu_allocate"] = deployment["cpu_allocate"] if deployment["cpu_allocate"] else 0
                    deployment["ram_allocate"] = deployment["ram_allocate"] if deployment["ram_allocate"] else 0
                    
                    
                    deployment_gpu_allocate = deployment["gpu_allocate"] * deployment["instance_allocate"]
                    deployment_cpu_allocate = deployment["cpu_allocate"] * deployment["instance_allocate"]
                    deployment_ram_allocate = deployment["ram_allocate"] * deployment["instance_allocate"]
                    # worker_pod_status = deployment_pod_status.get(str(deployment["id"]), {})
                    used_gpu_allocate = 0
                    used_ram_allocate = 0
                    used_cpu_allocate = 0
                    pending_gpu_allocate = 0
                    pending_ram_allocate = 0
                    pending_cpu_allocate = 0
                    deployment_workers = db_deployment.get_deployment_worker_running(deployment_id=deployment["id"])
                    # 동작 중인 worker
                    for worker_info in deployment_workers:
                        used_gpu_allocate += worker_info["gpu_per_worker"]
                        used_ram_allocate += deployment["deployment_ram_limit"]
                        used_cpu_allocate += deployment["deployment_cpu_limit"]

                    if workspace_instance_used_resource.get(deployment["instance_id"], None):
                        workspace_instance_used_resource[deployment["instance_id"]]["cpu"] += used_cpu_allocate
                        workspace_instance_used_resource[deployment["instance_id"]]["ram"] += used_ram_allocate
                        workspace_instance_used_resource[deployment["instance_id"]]["gpu"] += used_gpu_allocate
                    else:
                        workspace_instance_used_resource[deployment["instance_id"]] ={
                            "cpu" : used_cpu_allocate,
                            "ram" : used_ram_allocate,
                            "gpu" : used_gpu_allocate
                        }

                    # pending_flag = False
                    deployment_id = str(deployment["id"])

                    if deployment_id not in deployment_pending_pod:
                        deployment_pending_pod[deployment_id] = []
                        if not (pod_info and pod_info.get("pod_type") == TYPE.DEPLOYMENT_TYPE and pod_info.get("deployment_id") == deployment["id"]):
                            continue

                    if pod_info and pod_info.get("pod_type") == TYPE.DEPLOYMENT_TYPE and pod_info.get("deployment_id") == deployment["id"]:
                        deployment_pending_pod[deployment_id].append(pod_info)

                    if not deployment_pending_pod[deployment_id]:
                        continue 

                    dp_info = deployment_pending_pod[deployment_id].pop(0)
                    
                    # print("deployment : ", deployment["id"],file=sys.stderr)
                    # print(workspace_instance_used_resource.get(18, "없음"),file=sys.stderr)
                    instance_key = redis_key.WORKSPACE_INSTANCE_QUEUE.format(workspace["id"], deployment["instance_id"])
                    redis_queue = RedisQueue(redis_client=redis_client, key=instance_key)
                    # new_instance_queue = workspace_instance_queue.get(str(project["instance_id"]), [])
                    # instance queue 확인 및 instance_pending 확인 
                    instance_queue = redis_queue.fetch_queue_items()
                    # print("instance_queue : ", instance_queue, file=sys.stderr)
                    for instance_queue_pod in instance_queue:
                        instance_queue_pod = json.loads(instance_queue_pod)
                        if instance_queue_pod.get("deployment_id") == deployment["id"]:
                            pending_gpu_allocate += instance_queue_pod["gpu_count"]   
                            pending_ram_allocate += deployment["deployment_ram_limit"]
                            pending_cpu_allocate += deployment["deployment_cpu_limit"]
                    
                    # print(pending_gpu_allocate, pending_cpu_allocate, pending_ram_allocate , file=sys.stderr)
                    
                    available_gpu = deployment_gpu_allocate - used_gpu_allocate - pending_gpu_allocate
                    available_cpu = deployment_cpu_allocate - used_cpu_allocate - pending_cpu_allocate
                    available_ram = deployment_ram_allocate - used_ram_allocate - pending_ram_allocate

                    logging.info(f"Deployment {deployment["id"]} 에서 사용 가능한 자원")
                    logging.info(f'available_cpu:{available_cpu}, available_ram : {available_ram}, available_gpu : {available_gpu} ')
                    logging.info(f'request_cpu:{deployment["deployment_cpu_limit"]}, request_ram : {deployment["deployment_ram_limit"]}, pending_gpu : {dp_info["gpu_count"]} ')


                    if available_cpu < deployment["deployment_cpu_limit"] or available_ram < deployment["deployment_ram_limit"] or available_gpu < dp_info["gpu_count"]:
                        deployment_pending_pod[str(deployment["id"])].insert(0,dp_info)
                        logging.info(f"Deployment {deployment['id']} 자원 부족으로 인한 pending")
                        continue
                    dp_info["resource"] = {
                            "cpu" : deployment["deployment_cpu_limit"],
                            "ram" : deployment["deployment_ram_limit"]
                        }        
                    
                    logging.info(f"Deployment {deployment['id']} 자원 충분으로 인한 배포")


                    redis_queue.rput(json.dumps(dp_info))
                
                pending_item_arrange(deployment_pending_pod, [str(d["id"]) for d in deployment_list])

                print("배포 총 사용량 : ", workspace_instance_used_resource, file=sys.stderr)

                # [preprocessing] 
                preprocessing_list = db_prepro.get_preprocessing_list_sync(workspace_id=workspace["id"])
                preprocessing_pending_pod = workspace_item_pending_pod[TYPE.PREPROCESSING_TYPE]
                
                for preprocessing in preprocessing_list:
                    preprocessing["gpu_allocate"] = preprocessing["gpu_allocate"] if preprocessing["gpu_allocate"] else 0
                    preprocessing["cpu_allocate"] = preprocessing["cpu_allocate"] if preprocessing["cpu_allocate"] else 0
                    preprocessing["ram_allocate"] = preprocessing["ram_allocate"] if preprocessing["ram_allocate"] else 0
                    
                    preprocessing_gpu_allocate = preprocessing["gpu_allocate"] * preprocessing["instance_allocate"]
                    preprocessing_cpu_allocate = preprocessing["cpu_allocate"] * preprocessing["instance_allocate"]
                    preprocessing_ram_allocate = preprocessing["ram_allocate"] * preprocessing["instance_allocate"]
                    used_gpu_allocate = 0
                    used_ram_allocate = 0
                    used_cpu_allocate = 0
                    pending_gpu_allocate = 0
                    pending_ram_allocate = 0
                    pending_cpu_allocate = 0
                    
                    tools = db_prepro.get_preprocessing_tools_sync(preprocessing_id=preprocessing["id"])
                    jobs = db_prepro.get_job_is_running(preprocessing_id=preprocessing["id"])
                    for tool_info in tools:
                        used_gpu_allocate += tool_info["gpu_count"]
                        used_ram_allocate += preprocessing["tool_ram_limit"]*tool_info["pod_count"]
                        used_cpu_allocate += preprocessing["tool_cpu_limit"]*tool_info["pod_count"]
                    for job in jobs:
                        used_gpu_allocate += job["gpu_count"] 
                        used_ram_allocate += preprocessing["job_ram_limit"]*job["pod_count"]
                        used_cpu_allocate += preprocessing["job_cpu_limit"]*job["pod_count"]
                    
                    if workspace_instance_used_resource.get(preprocessing["instance_id"], None):
                        workspace_instance_used_resource[preprocessing["instance_id"]]["cpu"] += used_cpu_allocate
                        workspace_instance_used_resource[preprocessing["instance_id"]]["ram"] += used_ram_allocate
                        workspace_instance_used_resource[preprocessing["instance_id"]]["gpu"] += used_gpu_allocate
                    else:
                        workspace_instance_used_resource[preprocessing["instance_id"]] ={
                            "cpu" : used_cpu_allocate,
                            "ram" : used_ram_allocate,
                            "gpu" : used_gpu_allocate
                        }
                    
                    # pending_flag = False
                    preprocessing_id = str(preprocessing["id"])

                    if preprocessing_id not in preprocessing_pending_pod:
                        preprocessing_pending_pod[preprocessing_id] = []
                        if not (pod_info and pod_info.get("pod_type") == TYPE.PREPROCESSING_TYPE and pod_info.get("preprocessing_id") == preprocessing["id"]):
                            continue

                    # pending_pods = preprocessing_pending_pod[preprocessing_id]

                    # if not pending_pods:
                    #     continue

                    if pod_info and pod_info.get("pod_type") == TYPE.PREPROCESSING_TYPE and pod_info.get("preprocessing_id") == preprocessing["id"]:
                        preprocessing_pending_pod[preprocessing_id].append(pod_info)
                    if not preprocessing_pending_pod[preprocessing_id]:
                        continue 
                    prp_info = preprocessing_pending_pod[preprocessing_id].pop(0)


                    # if str(preprocessing["id"]) in preprocessing_pending_pod:
                    #     pod_info = preprocessing_pending_pod[str(preprocessing["id"])]
                    #     pending_flag = True
                    # else:
                    #     if not(pod_info.get("pod_type", None) == TYPE.PREPROCESSING_TYPE and pod_info.get("preprocessing_id", None) == preprocessing["id"]):
                    #         continue
                    # if not db_sync(pending_pod=preprocessing_pending_pod, pod_info=pod_info, pending_flag=pending_flag, preprocessing=preprocessing):
                    #     continue
                    
                    instance_key = redis_key.WORKSPACE_INSTANCE_QUEUE.format(workspace["id"], preprocessing["instance_id"]) # TODO 포맷 변경
                    redis_queue = RedisQueue(redis_client=redis_client, key=instance_key)
                    
                    # workspace로  대기중인 pod 확인 
                    # instance queue 확인 
                    instance_queue = redis_queue.fetch_queue_items()
                    print(instance_queue, file=sys.stderr)
                    # print("instance_queue : ", instance_queue, file=sys.stderr)
                    for instance_queue_pod in instance_queue:
                        # instance_pod = {}
                        instance_queue_pod = json.loads(instance_queue_pod)
                        if instance_queue_pod.get("preprocessing_id", None) == preprocessing["id"]:
                            
                            pending_gpu_allocate += instance_queue_pod["gpu_count"]
                            pod_count = 1
                            if instance_queue_pod["gpu_cluster_auto"]:
                                pod_count = instance_queue_pod["gpu_auto_cluster_case"]["server"]
                            elif instance_queue_pod["gpu_count"] > 1:
                                pod_count = instance_queue_pod["gpu_count"]/instance_queue_pod["pod_per_gpu"] if instance_queue_pod["pod_per_gpu"] != 0 else instance_queue_pod["gpu_count"]
                            
                            if instance_queue_pod.get("work_func_type", None) == TYPE.PREPROCESSING_ITEM_B:
                                pending_ram_allocate += preprocessing["job_ram_limit"]*pod_count
                                pending_cpu_allocate += preprocessing["job_cpu_limit"]*pod_count
                                
                            elif instance_queue_pod.get("work_func_type", None) == TYPE.PREPROCESSING_ITEM_A:
                                pending_ram_allocate += preprocessing["tool_ram_limit"]*pod_count
                                pending_cpu_allocate += preprocessing["tool_cpu_limit"]*pod_count

                    available_gpu = preprocessing_gpu_allocate - used_gpu_allocate - pending_gpu_allocate
                    available_cpu = preprocessing_cpu_allocate - used_cpu_allocate - pending_cpu_allocate
                    available_ram = preprocessing_ram_allocate - used_ram_allocate - pending_ram_allocate
                    # CPU 및 RAM 자원량 확인 
                    # job, tool 에 설정된 자원량보다 적으면 pending
                    pod_count = 1
                    if prp_info["gpu_cluster_auto"]:
                        pod_count = prp_info["gpu_auto_cluster_case"]["server"]
                    elif prp_info["gpu_count"] > 1:
                        pod_count = prp_info["gpu_count"]/prp_info["pod_per_gpu"] if prp_info["pod_per_gpu"] != 0 else prp_info["gpu_count"]
                    
                    logging.info(f"Preprocessing {preprocessing["id"]} 에서 사용 가능한 자원")
                    logging.info(f'available_cpu:{available_cpu}, available_ram : {available_ram}, available_gpu : {available_gpu} ')
                    
                    if prp_info["work_func_type"] == TYPE.PREPROCESSING_ITEM_B:
                        prp_info["resource"] = {
                            "cpu" : preprocessing["job_cpu_limit"],
                            "ram" : preprocessing["job_ram_limit"]
                        }
                        
                        if available_cpu < (preprocessing["job_cpu_limit"]*pod_count) or available_ram < (preprocessing["job_ram_limit"]*pod_count) or available_gpu < prp_info["gpu_count"]:
                            preprocessing_pending_pod[str(preprocessing["id"])].insert(0,prp_info)
                            continue
                        else:
                            if str(preprocessing["id"]) in preprocessing_pending_pod:
                                del preprocessing_pending_pod[str(preprocessing["id"])]
                    elif prp_info["work_func_type"] == TYPE.PREPROCESSING_ITEM_A:
                        prp_info["resource"] = {
                            "cpu" : preprocessing["tool_cpu_limit"],
                            "ram" : preprocessing["tool_ram_limit"]
                        }
                        
                        if available_cpu < (preprocessing["tool_cpu_limit"]*pod_count) or available_ram < (preprocessing["tool_ram_limit"]*pod_count) or available_gpu < prp_info["gpu_count"]:
                            preprocessing_pending_pod[str(preprocessing["id"])] = prp_info
                            continue
                        else:
                            if str(preprocessing["id"]) in preprocessing_pending_pod:
                                del preprocessing_pending_pod[str(preprocessing["id"])]

                    redis_queue.rput(json.dumps(prp_info))
                
                pending_item_arrange(preprocessing_pending_pod, [str(p["id"]) for p in preprocessing_list])
                print("전처리기 총 사용량 : ", workspace_instance_used_resource, file=sys.stderr)
                # [analyzer] 
                analyzer_list = db_analyzing.get_analyzer_list(workspace_id=workspace["id"])
                analyzer_pending_pod = workspace_item_pending_pod.get(TYPE.ANALYZER_TYPE)
                for analyzer in analyzer_list:
                    analyzer["gpu_allocate"] = analyzer["gpu_allocate"] if analyzer["gpu_allocate"] else 0
                    analyzer["cpu_allocate"] = analyzer["cpu_allocate"] if analyzer["cpu_allocate"] else 0
                    analyzer["ram_allocate"] = analyzer["ram_allocate"] if analyzer["ram_allocate"] else 0
                    
                    # analyzer_gpu_allocate = analyzer["gpu_allocate"] * analyzer["instance_allocate"]
                    analyzer_cpu_allocate = analyzer["cpu_allocate"] * analyzer["instance_allocate"]
                    analyzer_ram_allocate = analyzer["ram_allocate"] * analyzer["instance_allocate"]
                    used_gpu_allocate = 0
                    used_ram_allocate = 0
                    used_cpu_allocate = 0
                    pending_gpu_allocate = 0
                    pending_ram_allocate = 0
                    pending_cpu_allocate = 0

                    graph_worker = db_analyzing.get_analyzer_graph_list_sync(analyzer_id=analyzer["id"], running=True)
                    # print(graph_worker)
                    # logging.info(f"graph_worker : {graph_worker}")
                    # # # 동작 중인 worker
                    for worker_info in graph_worker:
                        # used_gpu_allocate += 0 # 분석기 gpu 사용 X
                        used_ram_allocate += analyzer["graph_ram_limit"]
                        used_cpu_allocate += analyzer["graph_cpu_limit"]

                    if workspace_instance_used_resource.get(analyzer["instance_id"], None):
                        workspace_instance_used_resource[analyzer["instance_id"]]["cpu"] += used_cpu_allocate
                        workspace_instance_used_resource[analyzer["instance_id"]]["ram"] += used_ram_allocate
                        # workspace_instance_used_resource[analyzer["instance_id"]]["gpu"] += used_gpu_allocate
                    else:
                        workspace_instance_used_resource[analyzer["instance_id"]] ={
                            "cpu" : used_cpu_allocate,
                            "ram" : used_ram_allocate,
                            # "gpu" : used_gpu_allocate
                        }
                    
                    pending_flag = False
                    # logging.info(f"Analyzer {analyzer['id']} check")
                    analyzer_id = str(analyzer["id"])

                    if analyzer_id not in analyzer_pending_pod:
                        analyzer_pending_pod[analyzer_id] = []
                        if not (pod_info and pod_info.get("pod_type") == TYPE.ANALYZER_TYPE and pod_info.get("analyzer_id") == analyzer["id"]):
                            continue

                    # pending_pods = analyzer_pending_pod[analyzer_id]

                    # if not pending_pods:
                    #     continue

                    if pod_info and pod_info.get("pod_type") == TYPE.ANALYZER_TYPE and pod_info.get("analyzer_id") == analyzer["id"]:
                        analyzer_pending_pod[analyzer_id].append(pod_info)
                    if not analyzer_pending_pod[analyzer_id]:
                        continue 
                    ap_info = analyzer_pending_pod[analyzer_id].pop(0)

                    # if str(analyzer["id"]) in analyzer_pending_pod:
                    #     if analyzer_pending_pod[str(analyzer["id"])]:
                    #         if pod_info:
                    #             if pod_info.get("pod_type", None) == TYPE.ANALYZER_TYPE and pod_info.get("analyzer_id", None) == analyzer["id"]:
                    #                 analyzer_pending_pod[str(analyzer["id"])].append(pod_info)
                    #                 pod_info = analyzer_pending_pod[str(analyzer["id"])].pop(0)
                    #         else:
                    #             continue
                    # else:
                    #     analyzer_pending_pod[str(analyzer["id"])]=[]
                    #     if not(pod_info.get("pod_type", None) == TYPE.ANALYZER_TYPE and pod_info.get("analyzer_id", None) == analyzer["id"]):
                    #         continue


                    # if str(analyzer["id"]) in analyzer_pending_pod:
                    #     pod_info = analyzer_pending_pod[str(analyzer["id"])]
                    #     pending_flag = True
                    #     logging.info(f"Analyzer {analyzer['id']} Pending")
                    # else:
                    #     if not(pod_info.get("pod_type", None) == TYPE.ANALYZER_TYPE and pod_info.get("analyzer_id", None) == analyzer["id"]):
                    #         continue
                    # if not db_sync(pending_pod=analyzer_pending_pod, pod_info=pod_info, pending_flag=pending_flag, analyzer=analyzer):
                    #     continue
                    
                    instance_key = redis_key.WORKSPACE_INSTANCE_QUEUE.format(workspace["id"], analyzer["instance_id"])
                    redis_queue = RedisQueue(redis_client=redis_client, key=instance_key)
                    # new_instance_queue = workspace_instance_queue.get(str(project["instance_id"]), [])
                    # instance queue 확인 및 instance_pending 확인 
                    instance_queue = redis_queue.fetch_queue_items()
                    for instance_queue_pod in instance_queue:
                        instance_queue_pod = json.loads(instance_queue_pod)
                        if instance_queue_pod.get("analyzer_id") == analyzer["id"]:
                            pending_gpu_allocate += 0 # 분석기 gpu 사용 X
                            pending_ram_allocate += analyzer["graph_ram_limit"]
                            pending_cpu_allocate += analyzer["graph_cpu_limit"]

                    # # workspace로  대기중인 pod 확인 
                    # # instance queue 확인 
                    # instance_queue = redis_queue.fetch_queue_items()
                    # print(instance_queue, file=sys.stderr)
                    # # print("instance_queue : ", instance_queue, file=sys.stderr)
                    # for instance_queue_pod in instance_queue:
                    #     # instance_pod = {}
                    #     instance_queue_pod = json.loads(instance_queue_pod)
                    #     if instance_queue_pod.get("preprocessing_id", None) == preprocessing["id"]:
                            
                    #         pending_gpu_allocate += instance_queue_pod["gpu_count"]
                    #         pod_count = 1
                    #         if instance_queue_pod["gpu_cluster_auto"]:
                    #             pod_count = instance_queue_pod["gpu_auto_cluster_case"]["server"]
                    #         elif instance_queue_pod["gpu_count"] > 1:
                    #             pod_count = instance_queue_pod["gpu_count"]/instance_queue_pod["pod_per_gpu"] if instance_queue_pod["pod_per_gpu"] != 0 else instance_queue_pod["gpu_count"]
                            
                    #         if instance_queue_pod.get("work_func_type", None) == TYPE.PREPROCESSING_ITEM_B:
                    #             pending_ram_allocate += preprocessing["job_ram_limit"]*pod_count
                    #             pending_cpu_allocate += preprocessing["job_cpu_limit"]*pod_count
                                
                    #         elif instance_queue_pod.get("work_func_type", None) == TYPE.PREPROCESSING_ITEM_A:
                    #             pending_ram_allocate += preprocessing["tool_ram_limit"]*pod_count
                    #             pending_cpu_allocate += preprocessing["tool_cpu_limit"]*pod_count


                    # # print(pending_gpu_allocate, pending_cpu_allocate, pending_ram_allocate , file=sys.stderr)
                    
                    # available_gpu = analyzer_gpu_allocate - used_gpu_allocate - pending_gpu_allocate
                    logging.info(f"analyzer_cpu_allocate {analyzer_cpu_allocate}, used_cpu_allocate {used_cpu_allocate}, pending_cpu_allocate {pending_cpu_allocate}")

                    available_cpu = analyzer_cpu_allocate - used_cpu_allocate - pending_cpu_allocate
                    available_ram = analyzer_ram_allocate - used_ram_allocate - pending_ram_allocate

                    logging.info(f"analyzer graph {ap_info['graph_id']} 에서 사용 가능한 자원")
                    logging.info(f'available_cpu:{available_cpu}, available_ram : {available_ram}') #, available_gpu : {available_gpu} ')
                    logging.info(f'request_cpu:{analyzer["graph_cpu_limit"]}, request_ram : {analyzer["graph_ram_limit"]}') #, pending_gpu : {pod_info["gpu_count"]} ')

                    if available_cpu < analyzer["graph_cpu_limit"] or available_ram < analyzer["graph_ram_limit"]: #or available_gpu < pod_info["gpu_count"]:
                        analyzer_pending_pod[str(analyzer["id"])].insert(0,ap_info)
                        logging.info(f"analyzer graph {ap_info['graph_id']} 자원 부족으로 인한 pending")
                        continue
                    ap_info["resource"] = {
                            "cpu" : analyzer["graph_cpu_limit"],
                            "ram" : analyzer["graph_ram_limit"]
                        }
                    
                    logging.info(f"analyzer graph {ap_info['graph_id']} 자원 충분으로 인한 배포")
                    redis_queue.rput(json.dumps(ap_info))
                
                pending_item_arrange(analyzer_pending_pod, [str(a["id"]) for a in analyzer_list])
                print("분석기 총 사용량 : ", workspace_instance_used_resource, file=sys.stderr)
                # [collector]
                collect_list = db_collect.get_collect_list(workspace_id=workspace["id"])
                # collect_pending_pod = workspace_item_pending_pod.get(TYPE.COLLECT_TYPE)
                
                for collect in collect_list:
                    if collect["start_datetime"] and collect["end_datetime"] is None:
                        if workspace_instance_used_resource.get(collect["instance_id"], None):
                            # workspace_instance_used_resource[collect["instance_id"]]["gpu"] += model["gpu_count"]
                            workspace_instance_used_resource[collect["instance_id"]]["cpu"] += collect["cpu_allocate"]
                            workspace_instance_used_resource[collect["instance_id"]]["ram"] += collect["ram_allocate"]
                        else:
                            workspace_instance_used_resource[collect["instance_id"]] ={
                                "cpu" : collect["cpu_allocate"],
                                "ram" : collect["ram_allocate"],
                                "gpu" : 0
                            }
                        continue
                    if not(pod_info.get("pod_type", None) == TYPE.COLLECT_TYPE and pod_info.get("collect_id", None) == collect["id"]):
                        continue
                    print("collect id :", collect["id"], file=sys.stderr )
                    print("collect pod : ", pod_info , file=sys.stderr)
                    pod_info["resource"] = {
                        "cpu" : collect["cpu_allocate"],
                        "ram" : collect["ram_allocate"],
                        "gpu" : 0
                    }
                    instance_key = redis_key.WORKSPACE_INSTANCE_QUEUE.format(workspace["id"], collect["instance_id"]) # TODO 포맷 변경
                    redis_queue = RedisQueue(redis_client=redis_client, key=instance_key)
                    redis_queue.rput(json.dumps(pod_info))
                
                print("수집기 총 사용량 : ", workspace_instance_used_resource, file=sys.stderr)
                # [LLM] 
                if settings.LLM_USED:
                    # fine tuning
                    model_list = db_model.get_models_sync(workspace_id=workspace["id"])
                    for model in model_list:
                        
                        if model["latest_fine_tuning_status"] in [TYPE.KUBE_POD_STATUS_RUNNING, TYPE.KUBE_POD_STATUS_INSTALLING ]: # 동작 중인 것만 포함
                            if workspace_instance_used_resource.get(model["instance_id"], None):
                                workspace_instance_used_resource[model["instance_id"]]["gpu"] += model["gpu_count"]
                                workspace_instance_used_resource[model["instance_id"]]["cpu"] += model["cpu_allocate"]*model["instance_count"]
                                workspace_instance_used_resource[model["instance_id"]]["ram"] += model["ram_allocate"]*model["instance_count"]
                            else:
                                workspace_instance_used_resource[model["instance_id"]] ={
                                    "cpu" : model["gpu_count"],
                                    "ram" : model["cpu_allocate"]*model["instance_count"],
                                    "gpu" : model["ram_allocate"]*model["instance_count"]
                                }
                        if not(pod_info.get("pod_type", None) == TYPE.FINE_TUNING_TYPE and pod_info.get("model_id", None) == model["id"]):
                            continue
                        
                        pod_info["resource"] = {
                            "cpu" : model["cpu_allocate"]*model["instance_count"],
                            "ram" : model["ram_allocate"]*model["instance_count"],
                            "gpu" : model["gpu_count"]
                        }
                        # if model["instance_id"] not in workspace_instance_used_resource:
                        #     workspace_instance_used_resource[model["instance_id"]] = {
                        #         "cpu" : 0,
                        #         "ram" : 0,
                        #         "gpu" : 0
                        #     }
                        #     continue
                        
                        instance_key = redis_key.WORKSPACE_INSTANCE_QUEUE.format(workspace["id"], model["instance_id"]) # TODO 포맷 변경
                        redis_queue = RedisQueue(redis_client=redis_client, key=instance_key)
                        redis_queue.rput(json.dumps(pod_info))

                    # logging.info("==============fine tuning=============")
                    # logging.info(workspace_instance_used_resource.get(18,{}).__str__())
                    
                redis_client.hset(redis_key.WORKSPACE_ITEM_PENDING_POD2, workspace["id"], json.dumps(workspace_item_pending_pod))
                
                #======================================================================
                # instance queue
                #======================================================================
                workspace_instances = db_workspace.get_workspace_instance_list(workspace_id=workspace["id"])
                
                for instance in workspace_instances:
                    # 맞줘야 하는 key
                    # gpu_count , pod_type
                    print( "instance id : ", instance["instance_id"] ,workspace_instance_used_resource.get(instance["instance_id"], "없음"), file=sys.stderr)
                    try:
                        instance_key = redis_key.WORKSPACE_INSTANCE_QUEUE.format(workspace["id"], instance["instance_id"])
                        redis_queue = RedisQueue(redis_client=redis_client,key=instance_key)
                        pod_info_queue = redis_queue.pop_nowait()
                        if pod_info_queue:
                            pod_info = json.loads(pod_info_queue)
                        else:
                            continue
                    except Exception as e:
                        # redis key가 삭제 될 경우
                        logging.info("pod_info_queue 에러")
                        continue
                    
                    # print(pod_info, file=sys.stderr)
                    # DB sync
                    # logging.info("POD TYPE --> ", pod_info['pod_type'])
                    
                    print("pod_info 4", pod_info, file=sys.stderr)
                    # print(workspace_db_sync(pod_info), file=sys.stderr)
                    if not workspace_db_sync(pod_info):
                        print(redis_queue.fetch_queue_items(), file=sys.stderr)
                        # logging.info(f"instance queue {instance['instance_name']} DB sync 실패")
                        continue
                    print("workspace used resource :", workspace_instance_used_resource.get(instance["instance_id"], {}), file=sys.stderr)
                    #TODO
                    ## 인스턴스별 자원 스케줄링 추가
                    total_workspace_instance_cpu = instance["instance_allocate"] * instance["cpu_allocate"]
                    total_workspace_instance_ram = instance["instance_allocate"] * instance["ram_allocate"]
                    total_workspace_instance_gpu = instance["instance_allocate"] * instance["gpu_allocate"] 
                                
                    available_gpu = total_workspace_instance_gpu - workspace_instance_used_resource.get(instance["instance_id"], {}).get("gpu",0)
                    available_cpu = total_workspace_instance_cpu - workspace_instance_used_resource.get(instance["instance_id"], {}).get("cpu",0)
                    available_ram = total_workspace_instance_ram - workspace_instance_used_resource.get(instance["instance_id"], {}).get("ram",0)
                    logging.info(f"workspace instance")
                    logging.info(f"""workspace Used Resources - Instance: {instance["instance_name"]},- GPU: {workspace_instance_used_resource.get(instance["instance_id"], {}).get("gpu",0)}, \
                                  CPU: {workspace_instance_used_resource.get(instance["instance_id"], {}).get("cpu",0)}, RAM: {workspace_instance_used_resource.get(instance["instance_id"], {}).get("ram",0)}""")
                    logging.info(f"workspace Available Resources - GPU: {available_gpu}, CPU: {available_cpu}, RAM: {available_ram}")

                    # if settings.LLM_USED:
                    #     if pod_info["pod_type"] in TYPE.JONATHAN_FB_INSTANCE_USED_TYPES:
                    #         if available_cpu < pod_info["resource"]["cpu"] or available_gpu < pod_info["gpu_count"] or available_ram < pod_info["resource"]["ram"]:
                    #             logging.info(f"자원 부족으로 인한 workspace 단 pending  {pod_info["pod_type"]}")
                    #             redis_queue.lput(json.dumps(pod_info))
                    #             continue
                    #     elif pod_info["pod_type"] in [TYPE.FINE_TUNING_TYPE]: # 파인튜닝의 경우 해당 인스턴스의 자원 할당량 대로 할당
                    #         if available_cpu < instance["cpu_allocate"]*pod_info["instance_count"] or available_gpu < instance["gpu_allocate"] or available_ram < instance["ram_allocate"]*pod_info["instance_count"]:
                    #             logging.info(f"자원 부족으로 인한 workspace 단 pending  {pod_info["pod_type"]}")
                    #             redis_queue.lput(json.dumps(pod_info))
                    #             continue
                    # else:
                    #     if available_cpu < pod_info["resource"]["cpu"] or available_gpu < pod_info["gpu_count"] or available_ram < pod_info["resource"]["ram"]:
                    #         logging.info(f"자원 부족으로 인한 workspace 단 pending  {pod_info["pod_type"]}")
                    #         redis_queue.lput(json.dumps(pod_info))
                    #         continue
                    if available_cpu < pod_info["resource"]["cpu"] or available_gpu < pod_info["gpu_count"] or available_ram < pod_info["resource"]["ram"]:
                        logging.info(f"자원 부족으로 인한 workspace 단 pending  {pod_info["pod_type"]}")
                        redis_queue.lput(json.dumps(pod_info))
                        continue
                    
                    
                    # 자원 스케줄링
                    if pod_info["gpu_count"] > 0: # GPU
                        logging.info("GPU 사용")
                        
                        # 워크스페이스에서 해당 instance로 할당된 gpu 개수 
                        workspace_instance_gpu_count = instance["instance_allocate"] * instance["gpu_allocate"]
                        gpu_select = pod_info.get("gpu_select",[])
                        gpu_auto_cluster_case = pod_info["gpu_auto_cluster_case"]
                        gpu_cluster_auto = pod_info["gpu_cluster_auto"] # True -> 자동 , False -> 수동  
                        used_workspace_instance_gpu_count = 0
                        workspace_selector = "workspace_id={},instance_id={}".format(workspace["id"],instance["instance_id"])
                        used_gpu_uuid = get_used_gpu_uuid(label_select=workspace_selector)
                                    
                        
                        # 해당 인스턴스를 사용하는 모든 pod 조회
                        instance_selector = "instance_id={}".format(instance["instance_id"])
                        used_instance_gpu_uuid = get_used_gpu_uuid(label_select=instance_selector)      
                                    
                                    
                        # 워크스페이스 인스턴스 할당량 확인 
                        used_workspace_instance_gpu_count += len(used_gpu_uuid)   
                        free_workspace_gpu_count = workspace_instance_gpu_count - used_workspace_instance_gpu_count
                        
                        if pod_info["gpu_count"] > free_workspace_gpu_count:
                            redis_queue.lput(json.dumps(pod_info))
                            continue
                        # GPU INFO에서 사용가능한 GPU UUID 가져오기 
                        model_name = instance["resource_name"]
                        gpu_model_status = json.loads(redis_client.get(redis_key.GPU_INFO_RESOURCE))
                        available_gpus = get_available_gpus_by_model(model_name=model_name, data=gpu_model_status, instance_id=instance["instance_id"])
                        
                        # TODO
                        # GPU INFO의 상태 업데이트가 늦을 경우를 대비해 추가한 로직
                        real_available_gpus = []
                        for available_gpu in list(available_gpus):
                            if available_gpu["gpu_uuid"] not in used_instance_gpu_uuid:
                                real_available_gpus.append(available_gpu)

                        if not real_available_gpus:
                            # if not pending_flag:
                                # workspace_instance_pending_pod[resource_type][str(instance['instance_id'])] = pod_info
                            redis_queue.lput(json.dumps(pod_info))
                            continue
                        
                            
                        if pod_info["gpu_count"] == 1: # gpu가 하나일 경우
                            logging.info("GPU 1개")
                            real_available_gpus = get_optimal_gpus(data=real_available_gpus, num_gpus=1)
                            # 클러스터링
                            real_available_gpus = gpu_auto_clustering(real_available_gpus, pod_per_gpu=1)
        
                        elif gpu_cluster_auto and pod_info["gpu_count"] > 1:  # 자동 클러스터링 
                            # TODO
                            # real_available_gpus 를 가지고 gpu 선택 할 수 있도록 수정
                            logging.info("자동 클러스터링")
                            # logging.info("자동 옵션 : pod 당 gpu 개수 :", gpu_auto_cluster_case["gpu_count"], ", pod 개수 : ", gpu_auto_cluster_case["server"])
                            gpu_select = get_gpu_auto_select(gpu_count=gpu_auto_cluster_case["gpu_count"], pod_count=gpu_auto_cluster_case["server"], gpu_data=real_available_gpus)
                            
                            gpu_cluster_status = True
                            for gpu in gpu_select:
                                select_gpu_uuid = gpu["gpu_uuid"] 
                                if select_gpu_uuid in used_instance_gpu_uuid:
                                    gpu_cluster_status = False
                                    break
                            
                            if not gpu_cluster_status or gpu_select == []:
                                # if not pending_flag:
                                    # workspace_instance_pending_pod[resource_type][str(instance['instance_id'])] = pod_info
                                redis_queue.lput(json.dumps(pod_info))
                                continue
                            # 클러스터링
                            real_available_gpus = gpu_auto_clustering(available_gpus=gpu_select, pod_per_gpu=gpu_auto_cluster_case["gpu_count"])
                            # logging.info("자동 선택 : ", real_available_gpus.__str__)
                        
                        elif not gpu_cluster_auto and pod_info["gpu_count"] > 1:  # 수동 클러스터 구성일 경우 워크스페이스에서 해당 cluster를 사용중인지 확인
                            logging.info("수동 클러스터링")
                            gpu_cluster_status = True
                            pod_per_gpu = pod_info["pod_per_gpu"]
                            for gpu in gpu_select:
                                select_gpu_uuid = gpu["gpu_uuid"] 
                                if select_gpu_uuid in used_instance_gpu_uuid:
                                    gpu_cluster_status = False
                                    break
                            if not gpu_cluster_status:
                                redis_queue.lput(json.dumps(pod_info))
                                continue
                            real_available_gpus = gpu_auto_clustering(available_gpus=gpu_select, pod_per_gpu=pod_per_gpu)
                            # logging.info("수동 선택 : ", real_available_gpus.__str__)
                        pod_info["available_gpus"] = real_available_gpus
                    elif pod_info["gpu_count"] == 0 and  instance["instance_type"] == TYPE.INSTANCE_TYPE_GPU: # GPU 인스턴스인데 gpu 개수가 0개일 경우 해당 인스턴스 중 가중치가 높은 노드 지정 (가중치의 기준은 인스턴스의 개수)
                        node_list = db_node.get_node_instance_list(instance_id=instance["instance_id"])
                        nodes = [item['node_name'] for item in node_list]
                        weights = [item['instance_allocate'] for item in node_list]
                        
                        pod_info["available_node"] = random.choices(nodes, weights=weights, k=1)[0]
                
                    # CPU 인스턴스일 경우 
                    if instance["instance_type"] == TYPE.INSTANCE_TYPE_CPU:
                        logging.info("CPU 사용")
                        node_list = db_node.get_node_instance_list(instance_id=instance["instance_id"])
                        nodes = [item['node_name'] for item in node_list]
                        weights = [item['instance_allocate'] for item in node_list]
                        
                        pod_info["available_node"] = random.choices(nodes, weights=weights, k=1)[0]
                        pod_info["cpu_instance_name"] = instance["instance_name"]
                    
                    # NPU 인스턴스일 경우
                    if instance["instance_type"] == TYPE.INSTANCE_TYPE_NPU:
                        logging.info("NPU 사용")
                        pod_info["used_npu"] = True
                        pass
                    # helm 실행
                    res, message = None, None

                    print("요청", file=sys.stderr)
                    if pod_info["pod_type"] == TYPE.PROJECT_TYPE:       
                        if pod_info["work_func_type"] == TYPE.TRAINING_ITEM_A:
                            res, message = create_training_pod(pod_info=pod_info)
                        elif pod_info["work_func_type"] == TYPE.TRAINING_ITEM_C:
                            res, message = create_hps_pod(pod_info=pod_info)
                        elif pod_info["work_func_type"] == TYPE.TRAINING_ITEM_B:
                            res, message = create_project_tool(pod_info=pod_info)
                    elif pod_info["pod_type"] == TYPE.DEPLOYMENT_TYPE:
                        if settings.LLM_USED and pod_info.get("is_llm"):
                            res, message = install_deployment_llm(pod_info=pod_info)
                        else:
                            res1, message = install_deployment_pod(deployment_info=pod_info)
                            res2, message = install_deployment_svc_ing(deployment_info=pod_info)
                            res = True if res1 != False and res2 != False else False
                    elif pod_info["pod_type"] == TYPE.PREPROCESSING_TYPE:
                        if pod_info["work_func_type"] == TYPE.PREPROCESSING_ITEM_A:
                            res, message = create_preprocessing_tool(pod_info=pod_info)
                        elif pod_info["work_func_type"] == TYPE.PREPROCESSING_ITEM_B:
                            res, message = create_preprocessing_job(pod_info=pod_info)
                    elif pod_info.get("pod_type") == TYPE.COLLECT_TYPE:
                        if pod_info.get("work_func_type") == TYPE.PUBLICAPI_TYPE:
                            res, message = create_public_api_collector(pod_info)
                        elif pod_info.get("work_func_type") == TYPE.REMOTESERVER_TYPE:
                            print(1231513412515)
                            res, message = create_remote_server_collector(pod_info)
                        elif pod_info.get("work_func_type") == TYPE.CRAWLING_TYPE:
                            res, message = create_crawling_collector(pod_info)
                        elif pod_info.get("work_func_type") == TYPE.FB_DEPLOY_TYPE:
                            res, message = create_fb_deployment_collector(pod_info) 
                    elif pod_info.get("pod_type") == TYPE.ANALYZER_TYPE:
                        res, message = create_analyzer_pod(pod_info=pod_info)
                    if settings.LLM_USED:
                        if pod_info["pod_type"] == TYPE.FINE_TUNING_TYPE:
                            pod_info["cpu_allocate"] = instance["cpu_allocate"]*pod_info["instance_count"]
                            pod_info["ram_allocate"] = instance["ram_allocate"]*pod_info["instance_count"]
                            res, message = create_fine_tuning(pod_info=pod_info)
                    if res: # helm 성공 시
                        logging.info("helm ok")
                    else: # helm 실패 시 
                        logging.info(message)
                                                
                        if pod_info["pod_type"] == TYPE.DEPLOYMENT_TYPE:
                            workspace_id = pod_info.get('workspace_id') if pod_info.get('workspace_id') else pod_info.get("metadata_workspace_id")
                            if settings.LLM_USED and pod_info.get("is_llm"):
                                uninstall_deployment_llm(deployment_id=pod_info["deployment_id"], llm_type=pod_info["llm_type"], llm_id=pod_info["llm_id"])
                            else:
                                uninstall_pod_deployment(workspace_id=workspace_id, deployment_id=pod_info["deployment_id"], deployment_worker_id=pod_info["deployment_worker_id"],)
                        elif pod_info["pod_type"] == TYPE.PROJECT_TYPE:
                            if pod_info["work_func_type"] == TYPE.TRAINING_ITEM_B:
                                delete_helm_project(project_tool_type=TYPE.TOOL_TYPE[pod_info["tool_type"]], project_tool_id=pod_info["id"], workspace_id=workspace["id"])
                            elif pod_info["work_func_type"] in [TYPE.TRAINING_ITEM_A, TYPE.TRAINING_ITEM_C]:
                                delete_helm_project(project_tool_type=pod_info["work_func_type"], project_tool_id=pod_info["id"], workspace_id=workspace["id"])
                        elif pod_info["pod_type"] == TYPE.PREPROCESSING_TYPE:
                            if pod_info["work_func_type"] == TYPE.PREPROCESSING_ITEM_A:
                                delete_helm_preprocessing(preprocessing_tool_type=TYPE.TOOL_TYPE[pod_info["tool_type"]], preprocessing_tool_id=pod_info["id"] , workspace_id=workspace["id"])
                            elif pod_info["work_func_type"] == TYPE.PREPROCESSING_ITEM_B:
                                delete_helm_preprocessing(preprocessing_tool_type=pod_info["work_func_type"], preprocessing_tool_id=pod_info["id"] ,workspace_id=workspace["id"])
                        elif pod_info.get("pod_type") == TYPE.ANALYZER_TYPE:
                            delete_helm_analyzer(pod_info=pod_info)
                        if settings.LLM_USED:
                            if pod_info["pod_type"] == TYPE.FINE_TUNING_TYPE:
                                delete_helm_fine_tuning(model_id=pod_info["model_id"], workspace_id=workspace["id"])
                            # queue 앞으로 다시 입력
                        redis_queue.lput(json.dumps(pod_info))
        except Exception as e:
            consumer.unsubscribe()
            print(traceback.print_exc(), file=sys.stderr)
    # consumer.unsubscribe()