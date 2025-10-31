from utils import TYPE, PATH, settings, topic_key, redis_key, common
from utils.msa_db import db_project, db_workspace, db_deployment, db_node, db_instance
from utils.redis import get_redis_client, RedisQueue
from utils.TYPE import RESOURCE_TYPE_GPU, RESOURCE_TYPE_CPU, RESOURCE_TYPES

from scheduler.project_tool_run import create_hps_pod, create_training_pod, create_project_tool
from scheduler.helm_run import (install_deployment_pod, install_deployment_svc_ing, uninstall_pod_deployment,
                                delete_helm_resource)


from datetime import datetime
from typing import List
from collections import defaultdict
from functools import reduce

from confluent_kafka import Producer
from confluent_kafka import Consumer, KafkaError, KafkaException, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic
from kubernetes import config, client

import json, traceback, time, sys, threading
import random
import math, re

config.load_kube_config(config_file=settings.KUBER_CONFIG_PATH)
coreV1Api = client.CoreV1Api()


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

redis_client = get_redis_client(role="slave")


"""
{
    workspace_id : {
        instance_id: pod_info
    }

}

"""
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






def workspace_item_pod_check():

    def db_sync(pending_pod : dict, pod_info : dict, pending_flag : bool = False, project = None, deployment = None):
        if pod_info["pod_type"] == TYPE.TRAINING_ITEM_A:
            training_info = db_project.get_training(training_id=pod_info["id"])
            if training_info is None or training_info["end_datetime"]:
                if pending_flag:
                    del pending_pod[str(project["id"])] # 이미 삭제된 요청이라면 pending에서 삭제
                return False
        elif pod_info["pod_type"] == TYPE.TRAINING_ITEM_C:
            hps_info = db_project.get_hps(hps_id=pod_info["id"])
            if hps_info is None or hps_info["end_datetime"]:
                if pending_flag:
                    del pending_pod[str(project["id"])]
                return False
        elif pod_info["pod_type"] == TYPE.TRAINING_ITEM_B:
            tool_info =db_project.get_project_tool(project_tool_id=pod_info["id"])
            if tool_info is None or not tool_info['request_status']:
                if pending_flag:
                    del pending_pod[str(project["id"])]
                return False
        else: # 배포
            worker_info = db_deployment.get_deployment_worker(deployment_worker_id=pod_info["deployment_worker_id"])
            if worker_info is None or worker_info["end_datetime"]:
                if pending_flag:
                    del pending_pod[str(deployment["id"])]
                return False
        return True


    consumer = Consumer(conf)

    while True:
        try:
            time.sleep(0.5)
            workspace_list = db_workspace.get_workspace_list()

            for workspace in workspace_list:
                #======================================================================
                # workspace item queue
                #======================================================================
                workspace_item_pending_pod = redis_client.hget(redis_key.WORKSPACE_ITEM_PENDING_POD, workspace["id"])
                if not workspace_item_pending_pod:
                    workspace_item_pending_pod = {
                        "project" : {},
                        "deployment" : {}
                    }
                else:
                    workspace_item_pending_pod = json.loads(workspace_item_pending_pod)

                # instance queue
                # workspace_instance_queue = redis_client.hget(redis_key.WORKSPACE_INSTANCE_PENDING, workspace["id"])
                # if workspace_instance_queue:
                #     workspace_instance_queue = json.loads(workspace_instance_queue)
                # else:
                #     workspace_instance_queue = {}

                # workspace resource
                workspace_resource = db_workspace.get_workspace_resource(workspace_id=workspace["id"])
                # workspace pod status
                workspace_pod_status = redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, workspace["id"])
                if workspace_pod_status:
                    workspace_pod_status = json.loads(workspace_pod_status)
                else:
                    workspace_pod_status = {}
                projects_pod_status = workspace_pod_status.get(TYPE.PROJECT_TYPE, {})
                deployment_pod_status = workspace_pod_status.get(TYPE.DEPLOYMENT_TYPE, {})

                # project
                project_list = db_project.get_project_list(workspace_id=workspace["id"])
                project_pending_pod = workspace_item_pending_pod["project"]

                for project in project_list:
                    # TODO
                    # cpu ram 를 사용해 사용 가능한 pod 계산
                    project["gpu_allocate"] = project["gpu_allocate"] if project["gpu_allocate"] else 0
                    project_gpu_allocate = project["gpu_allocate"] * project["instance_allocate"]
                    project_cpu_allocate = project["cpu_allocate"] * project["instance_allocate"]
                    project_ram_allocate = project["ram_allocate"] * project["instance_allocate"]
                    used_gpu_allocate = 0
                    used_ram_allocate = 0
                    used_cpu_allocate = 0
                    pending_gpu_allocate = 0
                    pending_ram_allocate = 0
                    pending_cpu_allocate = 0


                    project_pod_status = projects_pod_status.get(str(project["id"]), {})
                    project_tool_pod = project_pod_status.get(TYPE.TRAINING_ITEM_B, {})
                    project_training_pod = project_pod_status.get(TYPE.TRAINING_ITEM_A, {})
                    # 동작 중인 pod
                    for tool_info in project_tool_pod.values():
                        used_gpu_allocate += tool_info["resource"].get("gpu", 0)
                        used_ram_allocate += tool_info["resource"].get("ram", 0)
                        used_cpu_allocate += tool_info["resource"].get("cpu", 0)
                    for training_info in project_training_pod.values():
                        used_gpu_allocate += training_info["resource"].get("gpu", 0)
                        used_ram_allocate += training_info["resource"]["cpu"]
                        used_cpu_allocate += training_info["resource"].get("ram", 0)



                    topic = topic_key.PROJECT_TOPIC.format(project["id"]) # TODO 포맷 변경
                    pending_flag = False

                    if str(project["id"]) in project_pending_pod:
                        pod_info = project_pending_pod[str(project["id"])]
                        pending_flag = True
                    else:
                        try:
                            consumer.subscribe([topic])
                            msg = consumer.poll(timeout=1)
                            if msg is None or msg.error():
                                continue
                            # pod_info = json.loads(msg.value())
                            pod_info = try_json_deserializer(msg.value())
                        except Exception as e :
                            #  토픽이 사라졌으므로 넘긴다 -> project가 사라졌을 경우, 아직 한번도 push를 안한경우
                            print("no topic",file=sys.stderr)
                            continue
                    if not db_sync(pending_pod=project_pending_pod, pod_info=pod_info, pending_flag=pending_flag):
                        continue

                    instance_key = redis_key.WORKSPACE_INSTANCE_QUEUE.format(workspace["id"], project["instance_id"]) # TODO 포맷 변경
                    redis_queue = RedisQueue(redis_client=redis_client, key=instance_key)

                    # new_instance_queue = workspace_instance_queue.get(str(project["instance_id"]), [])

                    # workspace로  대기중인 pod 확인
                    # instance queue 확인
                    instance_queue = redis_queue.fetch_queue_items()
                    for instance_queue_pod in instance_queue:
                        # instance_pod = {}
                        instance_queue_pod = json.loads(instance_queue_pod)
                        if instance_queue_pod.get("project_id", None) == project["id"]:
                            pending_gpu_allocate += instance_queue_pod["gpu_count"]
                            if instance_queue_pod.get("pod_type", None) == TYPE.TRAINING_ITEM_A:
                                pending_ram_allocate += workspace_resource["job_ram_limit"]
                                pending_cpu_allocate += workspace_resource["job_cpu_limit"]

                            elif instance_queue_pod.get("pod_type", None) == TYPE.TRAINING_ITEM_B:
                                pending_ram_allocate += workspace_resource["tool_ram_limit"]
                                pending_cpu_allocate += workspace_resource["tool_cpu_limit"]

                    available_gpu = project_gpu_allocate - used_gpu_allocate - pending_gpu_allocate
                    available_cpu = project_cpu_allocate - used_cpu_allocate - pending_cpu_allocate
                    available_ram = project_ram_allocate - used_ram_allocate - pending_ram_allocate
                    # CPU 및 RAM 자원량 확인
                    # job, tool 에 설정된 자원량보다 적으면 pending
                    pod_count = 1
                    if pod_info["gpu_cluster_auto"]:
                        pod_count = pod_info["gpu_auto_cluster_case"]["server"]
                    elif pod_info["gpu_count"] > 1:
                        pod_count = pod_info["gpu_count"]/pod_info["pod_per_gpu"] if pod_info["pod_per_gpu"] != 0 else pod_info["gpu_count"]

                    print("="*10, file=sys.stderr)
                    print(pod_info["resource_type"], file=sys.stderr)
                    print(available_gpu, available_cpu, available_ram , file=sys.stderr)
                    print(pod_count, file=sys.stderr)
                    print("="*10, file=sys.stderr)



                    if pod_info["pod_type"] == TYPE.TRAINING_ITEM_A:


                        if available_cpu < (workspace_resource["job_cpu_limit"]*pod_count) or available_ram < (workspace_resource["job_ram_limit"]*pod_count) or available_gpu < pod_info["gpu_count"]:
                            project_pending_pod[str(project["id"])] = pod_info
                            continue
                        else:
                            if str(project["id"]) in project_pending_pod:
                                del project_pending_pod[str(project["id"])]
                    elif pod_info["pod_type"] == TYPE.TRAINING_ITEM_B:
                        if available_cpu < (workspace_resource["tool_cpu_limit"]*pod_count) or available_ram < (workspace_resource["tool_ram_limit"]*pod_count) or available_gpu < pod_info["gpu_count"]:
                            project_pending_pod[str(project["id"])] = pod_info
                            continue
                        else:
                            if str(project["id"]) in project_pending_pod:
                                del project_pending_pod[str(project["id"])]

                    redis_queue.rput(json.dumps(pod_info))
                    # new_instance_queue.append(pod_info)
                    # workspace_instance_queue[str(project["instance_id"])] = new_instance_queue


                # deployment
                deployment_list = db_deployment.get_deployment_list_in_workspace(workspace_id=workspace["id"])
                deployment_pending_pod = workspace_item_pending_pod["deployment"]

                for deployment in deployment_list:
                    deployment["gpu_allocate"] = deployment["gpu_allocate"] if deployment["gpu_allocate"] else 0
                    deployment_gpu_allocate = deployment["gpu_allocate"] * deployment["instance_allocate"]
                    deployment_cpu_allocate = deployment["cpu_allocate"] * deployment["instance_allocate"]
                    deployment_ram_allocate = deployment["ram_allocate"] * deployment["instance_allocate"]
                    worker_pod_status = deployment_pod_status.get(str(deployment["id"]), {})
                    used_gpu_allocate = 0
                    used_ram_allocate = 0
                    used_cpu_allocate = 0
                    pending_gpu_allocate = 0
                    pending_ram_allocate = 0
                    pending_cpu_allocate = 0

                    # 동작 중인 worker
                    for worker_info in worker_pod_status.values():
                        used_gpu_allocate += worker_info["resource"].get("gpu", 0)
                        used_ram_allocate += worker_info["resource"].get("ram", 0)
                        used_cpu_allocate += worker_info["resource"].get("cpu", 0)

                    topic = topic_key.DEPLOYMENT_TOPIC.format(deployment["id"])
                    pending_flag = False
                    if str(deployment["id"]) in deployment_pending_pod:
                        pod_info = deployment_pending_pod[str(deployment["id"])]
                        pending_flag = True
                    else:

                        try:
                            consumer.subscribe([topic])
                            msg = consumer.poll(timeout=1)

                            if msg is None or msg.error():
                                continue
                            pod_info = json.loads(msg.value())

                        except Exception as e :
                            continue

                    if not db_sync(pending_pod=deployment_pending_pod, pod_info=pod_info, pending_flag=pending_flag):
                        continue

                    instance_key = redis_key.WORKSPACE_INSTANCE_QUEUE.format(workspace["id"], deployment["instance_id"])
                    redis_queue = RedisQueue(redis_client=redis_client, key=instance_key)
                    # new_instance_queue = workspace_instance_queue.get(str(project["instance_id"]), [])
                    # instance queue 확인 및 instance_pending 확인
                    instance_queue = redis_queue.fetch_queue_items()
                    for instance_queue_pod in instance_queue:
                        instance_queue_pod = json.loads(instance_queue_pod)
                        if instance_queue_pod.get("deployment_id") == deployment["id"]:
                            pending_gpu_allocate += instance_queue_pod["gpu_count"]
                            pending_ram_allocate += workspace_resource["deployment_ram_limit"]
                            pending_cpu_allocate += workspace_resource["deployment_cpu_limit"]

                    print(pending_gpu_allocate, pending_cpu_allocate, pending_ram_allocate , file=sys.stderr)

                    available_gpu = deployment_gpu_allocate - used_gpu_allocate - pending_gpu_allocate
                    available_cpu = deployment_cpu_allocate - used_cpu_allocate - pending_cpu_allocate
                    available_ram = deployment_ram_allocate - used_ram_allocate - pending_ram_allocate
                    # CPU 및 RAM 자원량 확인
                    # print("="*10, file=sys.stderr)
                    # # print(pod_info["resource_type"], file=sys.stderr)
                    # print(available_gpu, available_cpu, available_ram , file=sys.stderr)
                    # print("="*10, file=sys.stderr)
                    # print("배포 워커 추가 가능 여부", file=sys.stderr)
                    # print(available_cpu < workspace_resource["deployment_cpu_limit"] or available_ram < workspace_resource["deployment_ram_limit"] or available_gpu < pod_info["gpu_count"], file=sys.stderr)
                    # print("="*10, file=sys.stderr)

                    if available_cpu < workspace_resource["deployment_cpu_limit"] or available_ram < workspace_resource["deployment_ram_limit"] or available_gpu < pod_info["gpu_count"]:
                        deployment_pending_pod[str(deployment["id"])] = pod_info
                        continue
                    else:
                        if str(deployment["id"]) in deployment_pending_pod:
                            del deployment_pending_pod[str(deployment["id"])]

                    redis_queue.rput(json.dumps(pod_info))
                    # new_instance_queue.append(pod_info)
                    # workspace_instance_queue[str(project["instance_id"])] = new_instance_queue


                    print("*"*20, file=sys.stderr)
                redis_client.hset(redis_key.WORKSPACE_ITEM_PENDING_POD, workspace["id"], json.dumps(workspace_item_pending_pod))

        except Exception as e:
            traceback.print_exc(file=sys.stderr)

def pod_start_new():
    def db_sync(pending_pod : dict, pod_info : dict, pending_flag : bool = False, project = None, deployment = None):
        if pod_info["pod_type"] == TYPE.TRAINING_ITEM_A:
            training_info = db_project.get_training(training_id=pod_info["id"])
            if training_info is None or training_info["end_datetime"]:
                if pending_flag:
                    del pending_pod[str(project["id"])] # 이미 삭제된 요청이라면 pending에서 삭제
                return False
        elif pod_info["pod_type"] == TYPE.TRAINING_ITEM_C:
            hps_info = db_project.get_hps(hps_id=pod_info["id"])
            if hps_info is None or hps_info["end_datetime"]:
                if pending_flag:
                    del pending_pod[str(project["id"])]
                return False
        elif pod_info["pod_type"] == TYPE.TRAINING_ITEM_B:
            tool_info =db_project.get_project_tool(project_tool_id=pod_info["id"])
            if tool_info is None or not tool_info['request_status']:
                if pending_flag:
                    del pending_pod[str(project["id"])]
                return False
        else: # 배포
            worker_info = db_deployment.get_deployment_worker(deployment_worker_id=pod_info["deployment_worker_id"])
            if worker_info is None or worker_info["end_datetime"]:
                if pending_flag:
                    del pending_pod[str(deployment["id"])]
                return False
        return True


    consumer = Consumer(conf)



    while True:
        try:
            time.sleep(0.1)

            workspace_list = db_workspace.get_workspace_list()

            for workspace in workspace_list:
                #======================================================================
                # workspace item queue
                #======================================================================
                workspace_item_pending_pod = redis_client.hget(redis_key.WORKSPACE_ITEM_PENDING_POD, workspace["id"])
                if not workspace_item_pending_pod:
                    workspace_item_pending_pod = {
                        "project" : {},
                        "deployment" : {}
                    }
                else:
                    workspace_item_pending_pod = json.loads(workspace_item_pending_pod)

                # workspace resource
                workspace_resource = db_workspace.get_workspace_resource(workspace_id=workspace["id"])
                # workspace pod status
                workspace_pod_status = redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, workspace["id"])
                if workspace_pod_status:
                    workspace_pod_status = json.loads(workspace_pod_status)
                else:
                    workspace_pod_status = {}
                projects_pod_status = workspace_pod_status.get(TYPE.PROJECT_TYPE, {})
                deployment_pod_status = workspace_pod_status.get(TYPE.DEPLOYMENT_TYPE, {})

                # project
                project_list = db_project.get_project_list(workspace_id=workspace["id"])
                project_pending_pod = workspace_item_pending_pod["project"]

                for project in project_list:
                    # TODO
                    # cpu ram 를 사용해 사용 가능한 pod 계산
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
                    for tool_info in tools:
                        used_gpu_allocate += tool_info["gpu_count"]
                        used_ram_allocate += workspace_resource["tool_ram_limit"]
                        used_cpu_allocate += workspace_resource["tool_cpu_limit"]
                    for training_info in trainings:
                        used_gpu_allocate += training_info["gpu_count"]
                        used_ram_allocate += workspace_resource["job_ram_limit"]
                        used_cpu_allocate += workspace_resource["job_cpu_limit"]


                    # project_pod_status = projects_pod_status.get(str(project["id"]), {})
                    # project_tool_pod = project_pod_status.get(TYPE.TRAINING_ITEM_B, {})
                    # project_training_pod = project_pod_status.get(TYPE.TRAINING_ITEM_A, {})
                    # 동작 중인 pod
                    # for tool_info in project_tool_pod.values():
                    #     used_gpu_allocate += tool_info["resource"].get("gpu", 0)
                    #     used_ram_allocate += tool_info["resource"].get("ram", 0)
                    #     used_cpu_allocate += tool_info["resource"].get("cpu", 0)
                    # for training_info in project_training_pod.values():
                    #     used_gpu_allocate += training_info["resource"].get("gpu", 0)
                    #     used_ram_allocate += training_info["resource"]["cpu"]
                    #     used_cpu_allocate += training_info["resource"].get("ram", 0)



                    topic = topic_key.PROJECT_TOPIC.format(project["id"]) # TODO 포맷 변경
                    pending_flag = False

                    if str(project["id"]) in project_pending_pod:
                        pod_info = project_pending_pod[str(project["id"])]
                        pending_flag = True
                    else:
                        try:
                            consumer.subscribe([topic])
                            msg = consumer.poll(timeout=1)
                            if msg is None or msg.error():
                                continue
                            # pod_info = json.loads(msg.value())
                            pod_info = try_json_deserializer(msg.value())
                        except Exception as e :
                            #  토픽이 사라졌으므로 넘긴다 -> project가 사라졌을 경우, 아직 한번도 push를 안한경우
                            print("no topic",file=sys.stderr)
                            continue
                    if not db_sync(pending_pod=project_pending_pod, pod_info=pod_info, pending_flag=pending_flag, project=project):
                        continue

                    instance_key = redis_key.WORKSPACE_INSTANCE_QUEUE.format(workspace["id"], project["instance_id"]) # TODO 포맷 변경
                    redis_queue = RedisQueue(redis_client=redis_client, key=instance_key)

                    # new_instance_queue = workspace_instance_queue.get(str(project["instance_id"]), [])

                    # workspace로  대기중인 pod 확인
                    # instance queue 확인
                    instance_queue = redis_queue.fetch_queue_items()
                    print(instance_queue)
                    for instance_queue_pod in instance_queue:
                        # instance_pod = {}
                        instance_queue_pod = json.loads(instance_queue_pod)
                        if instance_queue_pod.get("project_id", None) == project["id"]:
                            pending_gpu_allocate += instance_queue_pod["gpu_count"]
                            if instance_queue_pod.get("pod_type", None) == TYPE.TRAINING_ITEM_A:
                                pending_ram_allocate += workspace_resource["job_ram_limit"]
                                pending_cpu_allocate += workspace_resource["job_cpu_limit"]

                            elif instance_queue_pod.get("pod_type", None) == TYPE.TRAINING_ITEM_B:
                                pending_ram_allocate += workspace_resource["tool_ram_limit"]
                                pending_cpu_allocate += workspace_resource["tool_cpu_limit"]

                    available_gpu = project_gpu_allocate - used_gpu_allocate - pending_gpu_allocate
                    available_cpu = project_cpu_allocate - used_cpu_allocate - pending_cpu_allocate
                    available_ram = project_ram_allocate - used_ram_allocate - pending_ram_allocate
                    # CPU 및 RAM 자원량 확인
                    # job, tool 에 설정된 자원량보다 적으면 pending
                    pod_count = 1
                    if pod_info["gpu_cluster_auto"]:
                        pod_count = pod_info["gpu_auto_cluster_case"]["server"]
                    elif pod_info["gpu_count"] > 1:
                        pod_count = pod_info["gpu_count"]/pod_info["pod_per_gpu"] if pod_info["pod_per_gpu"] != 0 else pod_info["gpu_count"]

                    print("="*10, file=sys.stderr)
                    print(pod_info["resource_type"], file=sys.stderr)
                    print(available_gpu, available_cpu, available_ram , file=sys.stderr)
                    print(pod_count, file=sys.stderr)
                    print("="*10, file=sys.stderr)



                    if pod_info["pod_type"] == TYPE.TRAINING_ITEM_A:


                        if available_cpu < (workspace_resource["job_cpu_limit"]*pod_count) or available_ram < (workspace_resource["job_ram_limit"]*pod_count) or available_gpu < pod_info["gpu_count"]:
                            project_pending_pod[str(project["id"])] = pod_info
                            continue
                        else:
                            if str(project["id"]) in project_pending_pod:
                                del project_pending_pod[str(project["id"])]
                    elif pod_info["pod_type"] == TYPE.TRAINING_ITEM_B:
                        if available_cpu < (workspace_resource["tool_cpu_limit"]*pod_count) or available_ram < (workspace_resource["tool_ram_limit"]*pod_count) or available_gpu < pod_info["gpu_count"]:
                            project_pending_pod[str(project["id"])] = pod_info
                            continue
                        else:
                            if str(project["id"]) in project_pending_pod:
                                del project_pending_pod[str(project["id"])]

                    redis_queue.rput(json.dumps(pod_info))


                # deployment
                deployment_list = db_deployment.get_deployment_list_in_workspace(workspace_id=workspace["id"])
                deployment_pending_pod = workspace_item_pending_pod["deployment"]

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
                    deployments = db_deployment.get_deployment_worker_running(deployment_id=deployment["id"])
                    # 동작 중인 worker
                    for worker_info in deployments:
                        used_gpu_allocate += worker_info["gpu_per_worker"]
                        used_ram_allocate += workspace_resource["deployment_ram_limit"]
                        used_cpu_allocate += workspace_resource["deployment_cpu_limit"]

                    topic = topic_key.DEPLOYMENT_TOPIC.format(deployment["id"])
                    pending_flag = False
                    if str(deployment["id"]) in deployment_pending_pod:
                        pod_info = deployment_pending_pod[str(deployment["id"])]
                        pending_flag = True
                    else:

                        try:
                            consumer.subscribe([topic])
                            msg = consumer.poll(timeout=1)

                            if msg is None or msg.error():
                                continue
                            pod_info = json.loads(msg.value())

                        except Exception as e :
                            continue

                    if not db_sync(pending_pod=deployment_pending_pod, pod_info=pod_info, pending_flag=pending_flag, deployment=deployment):
                        continue

                    instance_key = redis_key.WORKSPACE_INSTANCE_QUEUE.format(workspace["id"], deployment["instance_id"])
                    redis_queue = RedisQueue(redis_client=redis_client, key=instance_key)
                    # new_instance_queue = workspace_instance_queue.get(str(project["instance_id"]), [])
                    # instance queue 확인 및 instance_pending 확인
                    instance_queue = redis_queue.fetch_queue_items()
                    for instance_queue_pod in instance_queue:
                        instance_queue_pod = json.loads(instance_queue_pod)
                        if instance_queue_pod.get("deployment_id") == deployment["id"]:
                            pending_gpu_allocate += instance_queue_pod["gpu_count"]
                            pending_ram_allocate += workspace_resource["deployment_ram_limit"]
                            pending_cpu_allocate += workspace_resource["deployment_cpu_limit"]

                    # print(pending_gpu_allocate, pending_cpu_allocate, pending_ram_allocate , file=sys.stderr)

                    available_gpu = deployment_gpu_allocate - used_gpu_allocate - pending_gpu_allocate
                    available_cpu = deployment_cpu_allocate - used_cpu_allocate - pending_cpu_allocate
                    available_ram = deployment_ram_allocate - used_ram_allocate - pending_ram_allocate
                    # CPU 및 RAM 자원량 확인
                    # print("="*10, file=sys.stderr)
                    # # print(pod_info["resource_type"], file=sys.stderr)
                    # print(available_gpu, available_cpu, available_ram , file=sys.stderr)
                    # print("="*10, file=sys.stderr)
                    # print("배포 워커 추가 가능 여부", file=sys.stderr)
                    # print(available_cpu < workspace_resource["deployment_cpu_limit"] or available_ram < workspace_resource["deployment_ram_limit"] or available_gpu < pod_info["gpu_count"], file=sys.stderr)
                    # print("="*10, file=sys.stderr)

                    if available_cpu < workspace_resource["deployment_cpu_limit"] or available_ram < workspace_resource["deployment_ram_limit"] or available_gpu < pod_info["gpu_count"]:
                        deployment_pending_pod[str(deployment["id"])] = pod_info
                        continue
                    else:
                        if str(deployment["id"]) in deployment_pending_pod:
                            del deployment_pending_pod[str(deployment["id"])]

                    redis_queue.rput(json.dumps(pod_info))
                    # new_instance_queue.append(pod_info)
                    # workspace_instance_queue[str(project["instance_id"])] = new_instance_queue


                    print("*"*20, file=sys.stderr)
                redis_client.hset(redis_key.WORKSPACE_ITEM_PENDING_POD, workspace["id"], json.dumps(workspace_item_pending_pod))



                #======================================================================
                # instance queue
                #======================================================================
                workspace_instances = db_workspace.get_workspace_instance_list(workspace_id=workspace["id"])


                for instance in workspace_instances:
                    # 맞줘야 하는 key
                    # gpu_count , pod_type

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
                        continue

                    # print(pod_info, file=sys.stderr)

                    # DB sync
                    if pod_info["pod_type"] == TYPE.TRAINING_ITEM_A:
                        training_info = db_project.get_training(training_id=pod_info["id"])
                        if training_info is None or training_info["end_status"] == TYPE.KUBE_POD_STATUS_STOP or training_info["instance_id"] is None:
                            continue
                    # elif pod_info["pod_type"] == TYPE.TRAINING_ITEM_C:
                    #     hps_info = db_project.get_hps(hps_id=pod_info["id"])
                    #     if hps_info is None or hps_info["end_datetime"]: # hps가 삭제 되었거나 중지되었을 떄
                    #         continue
                    elif pod_info["pod_type"] == TYPE.TRAINING_ITEM_B:
                        tool_info =db_project.get_project_tool(project_tool_id=pod_info["id"])
                        if tool_info is None or not tool_info['request_status'] or tool_info["gpu_count"] != pod_info["gpu_count"] \
                            or tool_info["image_real_name"] != pod_info["image_name"] or json.loads(tool_info["gpu_select"]) != pod_info["gpu_select"] or \
                                tool_info["instance_id"] is None: # tool이 삭제 되었거나 , 중지 , gpu 개수가 변경 되었을 경우, gpu 클러스터링이 변경 되었을 경우 삭제
                            continue
                    elif pod_info["pod_type"] == TYPE.DEPLOYMENT_TYPE:
                        worker_info = db_deployment.get_deployment_worker(deployment_worker_id=pod_info["deployment_worker_id"])
                        if worker_info is None or worker_info["end_datetime"] or worker_info["instance_id"] is None:
                            continue

                    if pod_info["gpu_count"] > 0: # GPU
                        # 워크스페이스에서 해당 instance로 할당된 gpu 개수
                        workspace_instance_gpu_count = instance["instance_allocate"] * instance["gpu_allocate"]
                        gpu_select = pod_info.get("gpu_select",[])
                        gpu_auto_cluster_case = pod_info["gpu_auto_cluster_case"]
                        gpu_cluster_auto = pod_info["gpu_cluster_auto"] # True -> 자동 , False -> 수동
                        # print("자동 클러스터링 : ", gpu_cluster_auto, file=sys.stderr)
                        # workspace에서 사용중인 instance pod 조회
                        used_workspace_instance_gpu_count = 0
                        workspace_selector = "workspace_id={},instance_id={}".format(workspace["id"],instance["instance_id"])
                        used_gpu_uuid = get_used_gpu_uuid(label_select=workspace_selector)


                        # 해당 인스턴스를 사용하는 모든 pod 조회
                        instance_selector = "instance_id={}".format(instance["instance_id"])
                        used_instance_gpu_uuid = get_used_gpu_uuid(label_select=instance_selector)


                        # 워크스페이스 인스턴스 할당량 확인
                        used_workspace_instance_gpu_count += len(used_gpu_uuid)
                        free_workspace_gpu_count = workspace_instance_gpu_count - used_workspace_instance_gpu_count

                        print("="*20, file=sys.stderr)
                        print("pod_info_gpu_count :", pod_info["gpu_count"], ", free_workspace_gpu_count :", free_workspace_gpu_count, file=sys.stderr)

                        if pod_info["gpu_count"] > free_workspace_gpu_count:
                            # if not pending_flag:
                                # workspace_instance_pending_pod[resource_type][str(instance['instance_id'])] = pod_info
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

                        print("="*20, file=sys.stderr)
                        print("실 사용 가능", real_available_gpus, file=sys.stderr)
                        print("실 사용 가능2", available_gpus, file=sys.stderr)
                        print("="*20, file=sys.stderr)

                        if not real_available_gpus:
                            # if not pending_flag:
                                # workspace_instance_pending_pod[resource_type][str(instance['instance_id'])] = pod_info
                            redis_queue.lput(json.dumps(pod_info))
                            continue


                        if pod_info["gpu_count"] == 1: # gpu가 하나일 경우

                            real_available_gpus = get_optimal_gpus(data=real_available_gpus, num_gpus=1)
                            # 클러스터링
                            real_available_gpus = gpu_auto_clustering(real_available_gpus, pod_per_gpu=1)

                        elif gpu_cluster_auto and pod_info["gpu_count"] > 1:  # 자동 클러스터링
                            # TODO
                            # real_available_gpus 를 가지고 gpu 선택 할 수 있도록 수정
                            print("="*20, file=sys.stderr)
                            print("자동 옵션 : pod 당 gpu 개수 :", gpu_auto_cluster_case["gpu_count"], ", pod 개수 : ", gpu_auto_cluster_case["server"], file=sys.stderr)
                            print("="*20, file=sys.stderr)
                            gpu_select = common.get_gpu_auto_select_new(gpu_count=gpu_auto_cluster_case["gpu_count"], pod_count=gpu_auto_cluster_case["server"], gpu_data=real_available_gpus)
                            print("자동 선택 : ", gpu_select, file=sys.stderr)
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


                        elif not gpu_cluster_auto and pod_info["gpu_count"] > 1:  # 수동 클러스터 구성일 경우 워크스페이스에서 해당 cluster를 사용중인지 확인

                            gpu_cluster_status = True
                            pod_per_gpu = pod_info["pod_per_gpu"]
                            for gpu in gpu_select:
                                select_gpu_uuid = gpu["gpu_uuid"]
                                if select_gpu_uuid in used_instance_gpu_uuid:
                                    gpu_cluster_status = False
                                    break

                            if not gpu_cluster_status:
                                # if not pending_flag:
                                    # workspace_instance_pending_pod[resource_type][str(instance['instance_id'])] = pod_info
                                redis_queue.lput(json.dumps(pod_info))
                                continue

                            real_available_gpus = gpu_auto_clustering(available_gpus=gpu_select, pod_per_gpu=pod_per_gpu)

                        pod_info["available_gpus"] = real_available_gpus
                    elif pod_info["gpu_count"] == 0 and  instance["instance_type"] == "GPU": # GPU 인스턴스인데 gpu 개수가 0개일 경우 해당 인스턴스 중 가중치가 높은 노드 지정 (가중치의 기준은 인스턴스의 개수)
                        node_list = db_node.get_node_instance_list(instance_id=instance["instance_id"])
                        nodes = [item['node_name'] for item in node_list]
                        weights = [item['instance_allocate'] for item in node_list]

                        pod_info["available_node"] = random.choices(nodes, weights=weights, k=1)[0]
                    # print(pod_info, file=sys.stderr)

                    # CPU 인스턴스일 경우
                    if instance["instance_type"] == "CPU":
                        pod_info["cpu_instance_name"] = instance["instance_name"]

                    # print(pod_info, file=sys.stderr)
                    # helm 실행
                    if pod_info["pod_type"] == TYPE.TRAINING_ITEM_A:
                        res, message = create_training_pod(pod_info=pod_info)
                    elif pod_info["pod_type"] == TYPE.TRAINING_ITEM_C:
                        res, message = create_hps_pod(pod_info=pod_info)
                    elif pod_info["pod_type"] == TYPE.TRAINING_ITEM_B:
                        res, message = create_project_tool(pod_info=pod_info)
                    elif pod_info["pod_type"] == TYPE.DEPLOYMENT_TYPE:
                        res1, message = install_deployment_pod(deployment_info=pod_info)
                        res2, message = install_deployment_svc_ing(deployment_info=pod_info)
                        res = True if res1 != False and res2 != False else False
                    print(res, file=sys.stderr, flush=True)
                    if res: # helm 성공 시
                        print("helm ok", file=sys.stderr)
                        print(message, file=sys.stderr, flush=True)
                        # if pending_flag:
                        #     del workspace_instance_pending_pod[resource_type][str(instance['instance_id'])]
                    else: # helm 실패 시
                        print(message, file=sys.stderr)

                        if pod_info["pod_type"] == TYPE.DEPLOYMENT_TYPE:
                            uninstall_pod_deployment(workspace_id=pod_info["workspace_id"], deployment_id=pod_info["deployment_id"], deployment_worker_id=pod_info["deployment_worker_id"],)
                        elif pod_info["pod_type"] == TYPE.TRAINING_ITEM_B:
                            delete_helm_resource(project_tool_type=TYPE.TOOL_TYPE[pod_info["tool_type"]], project_tool_id=pod_info["id"])
                        else:
                            delete_helm_resource(project_tool_type=pod_info["pod_type"], project_tool_id=pod_info["id"])
                        # queue 앞으로 다시 입력
                        redis_queue.lput(json.dumps(pod_info))

        except Exception as e:
            print(traceback.print_exc(), file=sys.stderr)