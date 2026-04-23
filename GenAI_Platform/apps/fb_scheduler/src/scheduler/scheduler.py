import json, traceback, time, sys, threading
import random
import logging
from collections import defaultdict
from functools import reduce
from typing import List
from enum import Enum

from confluent_kafka import Consumer
from confluent_kafka.admin import AdminClient, NewTopic
from kubernetes import config, client
from kubernetes.client.rest import ApiException

from utils import TYPE, PATH, settings, topic_key, redis_key, common
from utils.kube import get_node_request_budget
from utils.msa_db import (
    db_project, db_workspace, db_deployment, db_node,
    db_instance, db_prepro, db_analyzing, db_collect
)
from utils.redis import get_redis_client, RedisQueue
from scheduler.collect_run import (
    create_crawling_collector, create_fb_deployment_collector,
    create_public_api_collector, create_remote_server_collector
)
from scheduler.project_tool_run import create_hps_pod, create_training_pod, create_project_tool
from scheduler.preprocessing_tool_run import create_preprocessing_tool, create_preprocessing_job
if settings.LLM_USED:
    from utils.llm_db import db_model
    from scheduler.llm_run import create_fine_tuning
    from scheduler.helm_run import uninstall_deployment_llm

from scheduler.helm_run import (
    install_deployment_pod, install_deployment_svc_ing, uninstall_pod_deployment,
    delete_helm_project, delete_helm_fine_tuning, install_deployment_llm,
    delete_helm_preprocessing, create_analyzer_pod, delete_helm_analyzer
)
from scheduler.resource_usage import *

config.load_kube_config(config_file=settings.KUBER_CONFIG_PATH)
coreV1Api = client.CoreV1Api()

KAFKA_TIMEOUT = 0.5
last_print_time = 0  
PRINT_INTERVAL = 3  # seconds

DEBUG = False
class Status(Enum):
    SUCCESS = 0
    FAIL_RETRY = 1  # 실패 후 재실행 시도
    FAIL_PASS = 2   # 실패 후 패스

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

"""
 자원 부족:
   * pods "xxx" is forbidden: exceeded quota ...

 이미 실행중:
   Error: INSTALLATION FAILED: release: already exists
"""

# Consumer 설정
conf = {
    'bootstrap.servers': settings.JF_KAFKA_DNS,
    'group.id': 'mygroup',
    'auto.offset.reset': 'earliest',
    'max.poll.interval.ms': 10000,
    'session.timeout.ms': 10000,
    'enable.auto.commit': True,
    'auto.commit.interval.ms': 5000,
}
kafka_admin_conf = {
    'bootstrap.servers': settings.JF_KAFKA_DNS
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


def create_topic(topics: List[str] = []):
    if not topics:
        return
    conf = {'bootstrap.servers': settings.JF_KAFKA_DNS}
    a = AdminClient(conf)
    new_topics = [topic for topic in topics if topic not in a.list_topics().topics]
    if new_topics:
        fs = a.create_topics([NewTopic(topic=topic, num_partitions=3, replication_factor=1) for topic in new_topics])
        for topic, f in fs.items():
            try:
                f.result()
                logging.info(f"✅ Topic '{topic}' created successfully.")
            except Exception as e:
                logging.error(f"❌ Failed to create topic '{topic}': {e}")
    else:
        logging.info("✅ All topics are already created.")

def get_optimal_gpus(data: List[dict], num_gpus: int):
    """
    {
    "node-A": ["GPU1", "GPU2"],
    "node-B": ["GPU3"],
    ...
    } 형식으로 정리 후에 가용 GPU가 많은 노드부터 순서대로 할당

    """
    nodes = defaultdict(list)
    for item in data:
        nodes[item["node_name"]].append(item["gpu_uuid"])
    sorted_nodes = sorted(nodes.items(), key=lambda x: len(x[1]), reverse=True)

    result = []
    remaining_gpus = num_gpus

    for node, gpus in sorted_nodes:
        if remaining_gpus <= 0:
            break
        if len(gpus) >= remaining_gpus:
            result.extend([{"node_name": node, "gpu_uuid": gpu} for gpu in gpus[:remaining_gpus]])
            remaining_gpus = 0
        else:
            result.extend([{"node_name": node, "gpu_uuid": gpu} for gpu in gpus])
            remaining_gpus -= len(gpus)
    return result

# def get_optimal_gpus(available_gpus: List[dict], num_gpus: int):
#     """
#     가능한 한 적은 노드에서 많은 GPU를 할당하도록 개선한 로직.
#     동일 조건에서는 무작위로 노드를 선택함.
#     """
#     print("### avail:", available_gpus)
#     # 우선 gpu_count로 내림차순 정렬
#     sorted_nodes = sorted(available_gpus, key=lambda x: x["gpu_count"], reverse=True)

#     # 동일한 gpu_count를 가진 노드를 그룹핑하여 셔플
#     gpu_count_groups = {}
#     for node in sorted_nodes:
#         gpu_count = node["gpu_count"]
#         gpu_count_groups.setdefault(gpu_count, []).append(node)

#     # 각 그룹 내에서 노드를 무작위로 섞음
#     randomized_nodes = []
#     for gpu_count in sorted(gpu_count_groups.keys(), reverse=True):
#         nodes = gpu_count_groups[gpu_count]
#         random.shuffle(nodes)
#         randomized_nodes.extend(nodes)

#     # GPU 할당 수행
#     result = []
#     remaining_gpus = num_gpus

#     for node_info in randomized_nodes:
#         if remaining_gpus <= 0:
#             break

#         allocatable = min(node_info["gpu_count"], remaining_gpus)
#         result.append({
#             "node_name": node_info["node_name"],
#             "allocated_gpu_count": allocatable
#         })
#         remaining_gpus -= allocatable

#     if remaining_gpus > 0:
#         raise ValueError("요청한 GPU 개수보다 사용 가능한 GPU가 적습니다.")

#     return result

def gpu_auto_clustering(available_gpus: List[dict], pod_per_gpu: int = None):
    grouped_data = defaultdict(list)
    for item in available_gpus:
        grouped_data[item["node_name"]].append(item["gpu_uuid"])

    def gcd(a, b):
        while b:
            a, b = b, a % b
        return a

    def gcd_multiple(numbers):
        return reduce(gcd, numbers)

    node_counts = {node: len(uuids) for node, uuids in grouped_data.items()}
    counts = list(node_counts.values())

    if pod_per_gpu:
        max_gcd = pod_per_gpu
    else:
        max_gcd = gcd_multiple(counts)

    result = []
    for node, uuids in grouped_data.items():
        chunks = [uuids[i:i + max_gcd] for i in range(0, len(uuids), max_gcd)]
        for chunk in chunks:
            result.append({"node_name": node, "gpu_uuids": chunk})
    return result
# def gpu_auto_clustering(optimal_allocations: List[dict], pod_per_gpu: int = 1):
#     """
#     각 노드의 GPU 수를 기준으로 pod_per_gpu로 나누어 클러스터링.
#     """
#     clusters = []
#     for alloc in optimal_allocations:
#         node_name = alloc["node_name"]
#         gpu_count = alloc["allocated_gpu_count"]

#         full_clusters, remainder = divmod(gpu_count, pod_per_gpu)

#         # 풀 클러스터 배정
#         for _ in range(full_clusters):
#             clusters.append({
#                 "node_name": node_name,
#                 "gpu_count": pod_per_gpu
#             })

#         # 나머지 GPU가 있으면 별도 클러스터로 배정
#         if remainder:
#             clusters.append({
#                 "node_name": node_name,
#                 "gpu_count": remainder
#             })

#     return clusters

def get_used_gpu_uuid(label_select: str):
    used_gpu_uuid = []
    live_pods = coreV1Api.list_pod_for_all_namespaces(label_selector=label_select).items
    for live_pod in live_pods:
        pod_labels = live_pod.metadata.labels
        pod_status = live_pod.status.phase
        if pod_status not in ["Succeeded", "Failed"]:
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


# --------------------------------------------------------------------------------
# (A) Kafka 메시지 -> Pending Pod 큐에 저장
# --------------------------------------------------------------------------------
def run_kafka_consumer():
    """
    Kafka에서 pod_info 메시지를 수신하여,
    메시지에 포함된 workspace_id 기준으로 'WORKSPACE_ITEM_PENDING_POD2'에 저장.
    (실제 실행은 run_scheduler()에서 처리)
    """
    logging.info("Starting Kafka Consumer...")
    consumer = Consumer(conf)
    kafka_admin = AdminClient(kafka_admin_conf)
    
    type_id_map = {
                TYPE.PROJECT_TYPE: "project_id",
                TYPE.DEPLOYMENT_TYPE: "deployment_id",
                TYPE.PREPROCESSING_TYPE: "preprocessing_id",
                TYPE.ANALYZER_TYPE: "analyzer_id",
                TYPE.COLLECT_TYPE: "collect_id",
                TYPE.FINE_TUNING_TYPE: "model_id" if settings.LLM_USED else None
            }

    while True:
        try:
            time.sleep(0.3)

            # TODO: 추후 토픽 구조 변경
            pod_info = dict()
            kafka_topic_list = [topic for topic in kafka_admin.list_topics().topics]
            kafka_topic_list = [x for x in kafka_topic_list if x != '__consumer_offsets']
            if not kafka_topic_list:
                continue
            consumer.subscribe(kafka_topic_list)

            try:
                msgs = consumer.consume(num_messages=100, timeout=KAFKA_TIMEOUT)  # 신규 메시지 없을 시 None 반환
                if not msgs:
                    continue
            except Exception as e:
                logging.error("Exception occurred while fetching Kafka message", exc_info=True)
                continue
            
            redis_client = get_redis_client()
            for msg in msgs:
                pod_info = try_json_deserializer(msg.value())
                logging.info(f"[kafka polled msg] pod_info: {json.dumps(pod_info, ensure_ascii=False)}")
                # 메시지에서 workspace_id 추출
                ws_id = pod_info.get("workspace_id") or pod_info.get("metadata_workspace_id")
                if not ws_id:
                    logging.info("No workspace_id in pod_info, skipping.")
                    continue
                # {item_type}:{workspace_id}
                # Pending Pod 큐에 저장
                raw_pending = redis_client.hget(redis_key.WORKSPACE_ITEM_PENDING_POD2, ws_id)
                if not raw_pending:
                    workspace_item_pending_pod = {
                        TYPE.PROJECT_TYPE: {},
                        TYPE.DEPLOYMENT_TYPE: {},
                        TYPE.PREPROCESSING_TYPE: {},
                        TYPE.ANALYZER_TYPE: {},
                        TYPE.COLLECT_TYPE: {},
                        TYPE.FINE_TUNING_TYPE: {}
                    }
                else:
                    workspace_item_pending_pod = json.loads(raw_pending)

                # pod_type별로 분류
                ptype = pod_info["pod_type"]

                # pod_info에서 해당 타입별 ID 가져오기
                item_key = type_id_map.get(ptype)
                if item_key:
                    item_id = pod_info.get(item_key)
                    if item_id:
                        # 중복 처리 방지: 동일한 pod_info가 이미 있는지 확인
                        existing_items = workspace_item_pending_pod.setdefault(ptype, {}).setdefault(str(item_id), [])
                        # pod_info의 고유 식별자로 중복 체크 (id 기준)
                        if not any(existing['id'] == pod_info['id'] for existing in existing_items):
                            existing_items.append(pod_info)
                            logging.info(f"[NEW POD ADDED] {ptype} ID {item_id}: pod_info added to pending")
                        else:
                            logging.info(f"[DUPLICATE SKIPPED] {ptype} ID {item_id}: pod_info already exists in pending")
                logging.info(f"[workspace_item_pending_pod] : {json.dumps(workspace_item_pending_pod, ensure_ascii=False)}")
                # Redis에 다시 저장
                redis_client.hset(redis_key.WORKSPACE_ITEM_PENDING_POD2, ws_id, json.dumps(workspace_item_pending_pod))

        except Exception as e:
            consumer.unsubscribe()
            traceback.format_exc()
            time.sleep(1)
    # consumer.close() # 필요시

def kafka_consume_msgs(consumer, kafka_admin, redis_client, type_id_map):
    """
    Kafka에서 pod_info 메시지를 수신하여,
    메시지에 포함된 workspace_id 기준으로 'WORKSPACE_ITEM_PENDING_POD2'에 저장.
    """
    try:

        # TODO: 추후 토픽 구조 변경
        pod_info = dict()
        # kafka_topic_list = [topic for topic in kafka_admin.list_topics().topics if topic != '__consumer_offsets']
        # if not kafka_topic_list:
        #     return
        consumer.subscribe([str(topic_key.SCHEDULER_TOPIC)])

        try:
            msgs = consumer.consume(num_messages=100, timeout=KAFKA_TIMEOUT)  # 신규 메시지 없을 시 None 반환
            if not msgs:
                return True
        except Exception as e:
            logging.error("Exception occurred while fetching Kafka message", exc_info=True)
            return True
        
        for msg in msgs:
            pod_info = try_json_deserializer(msg.value())
            logging.info(f"[kafka polled msg] pod_info: {json.dumps(pod_info, ensure_ascii=False)}")
            # 메시지에서 workspace_id 추출
            ws_id = pod_info.get("workspace_id") or pod_info.get("metadata_workspace_id")
            if not ws_id:
                logging.info("No workspace_id in pod_info, skipping.")
                continue
            # {item_type}:{workspace_id}
            # Pending Pod 큐에 저장
            raw_pending = redis_client.hget(redis_key.WORKSPACE_ITEM_PENDING_POD2, ws_id)
            if not raw_pending:
                workspace_item_pending_pod = {
                    TYPE.PROJECT_TYPE: {
                        # "1" : []
                    },
                    TYPE.DEPLOYMENT_TYPE: {},
                    TYPE.PREPROCESSING_TYPE: {},
                    TYPE.ANALYZER_TYPE: {},
                    TYPE.COLLECT_TYPE: {},
                    TYPE.FINE_TUNING_TYPE: {}
                }
            else:
                workspace_item_pending_pod = json.loads(raw_pending)

            # pod_type별로 분류
            ptype = pod_info.get("pod_type", None)
            if not ptype:
                continue
            # pod_info에서 해당 타입별 ID 가져오기
            item_key = type_id_map.get(ptype)
            if item_key:
                item_id = pod_info.get(item_key)
                if item_id:
                    # 중복 처리 방지: 동일한 pod_info가 이미 있는지 확인
                    existing_items = workspace_item_pending_pod.setdefault(ptype, {}).setdefault(str(item_id), [])
                    # pod_info의 고유 식별자로 중복 체크 (id 기준)
                    if not any(existing['id'] == pod_info['id'] for existing in existing_items):
                        existing_items.append(pod_info)
                        logging.info(f"[NEW POD ADDED] {ptype} ID {item_id}: pod_info added to pending")
                    else:
                        logging.info(f"[DUPLICATE SKIPPED] {ptype} ID {item_id}: pod_info already exists in pending")
            logging.info(f"[workspace_item_pending_pod] : {json.dumps(workspace_item_pending_pod, ensure_ascii=False)}")
            # Redis에 다시 저장
            redis_client.hset(redis_key.WORKSPACE_ITEM_PENDING_POD2, ws_id, json.dumps(workspace_item_pending_pod))

        # 메시지 처리 완료 후 commit
        try:
            consumer.commit()
        except Exception as e:
            logging.error(f"Failed to commit offset: {e}")

    except Exception as e:
        traceback.print_exc()
        try:
            consumer.unsubscribe()
        except:
            pass
        try:
            consumer.close()
        except:
            pass
        logging.error("Kafka consumer error, will reinitialize", exc_info=True)
        return False  # 실패 처리


# --------------------------------------------------------------------------------
# (B) Workspace 스케줄러 (기존 pod_start_new() 로직)
# --------------------------------------------------------------------------------
def _fine_tuning_node_budget_guard(pod_info):
    """대상 노드(들)에 pod을 수용할 K8s request 예산이 남았는지 실측 검증.

    호출 시점: process_instance_queue_item 내부, GPU/node 선택 완료 후 deploy_pod_via_helm 직전.
    이 시점에 pod_info에는 반드시 available_gpus[*].node_name 또는 available_node 가 채워져 있음
    (fine-tuning 경로 기준).

    Returns:
        (ok: bool, reason: str) — ok=False면 호출자가 Status.FAIL_RETRY 반환.
    """
    pod_count = pod_info.get("pod_count") or 1
    try:
        pod_count = max(1, int(pod_count))
    except (TypeError, ValueError):
        pod_count = 1

    total_ram_gb = float(pod_info["resource"]["ram"])
    total_cpu_cores = float(pod_info["resource"]["cpu"])
    total_gpu = int(pod_info.get("gpu_count", 0) or 0)

    per_pod_mem_bytes = int((total_ram_gb / pod_count) * (10 ** 9))
    per_pod_cpu_mc = int((total_cpu_cores / pod_count) * 1000)
    per_pod_gpu = (total_gpu // pod_count) if pod_count > 0 else total_gpu

    # 노드별 수요 집계(한 노드가 여러 pod 호스트하는 경우 대비)
    node_demand = {}  # node_name -> [mem_bytes, cpu_mc, gpu]
    available_gpus = pod_info.get("available_gpus") or []
    available_node = pod_info.get("available_node")

    if available_gpus:
        for g in available_gpus:
            n = g.get("node_name")
            if not n:
                return False, f"available_gpus entry missing node_name: {g!r}"
            slot = node_demand.setdefault(n, [0, 0, 0])
            slot[0] += per_pod_mem_bytes
            slot[1] += per_pod_cpu_mc
            slot[2] += per_pod_gpu
    elif available_node:
        node_demand[available_node] = [
            int(total_ram_gb * 10 ** 9),
            int(total_cpu_cores * 1000),
            total_gpu,
        ]
    else:
        # NPU 경로 등 특정 노드 pinning이 없는 경우. 현 fine-tuning 범위에서는 예상되지 않음.
        # 게이트를 우회해 기존 동작 유지(워크스페이스 쿼터 체크는 이미 통과).
        return True, "no specific node binding; node budget guard skipped"

    for node_name, (need_mem, need_cpu_mc, need_gpu) in node_demand.items():
        try:
            budget = get_node_request_budget(node_name)
        except ApiException as e:
            return False, f"node={node_name} budget ApiException: status={e.status} reason={e.reason}"
        except Exception as e:
            return False, f"node={node_name} budget fetch error: {e!r}"

        if budget.memory_free_bytes < need_mem:
            return False, (
                f"node={node_name} memory insufficient: "
                f"free={budget.memory_free_bytes}B < need={need_mem}B "
                f"(allocatable={budget.memory_allocatable_bytes}B, used={budget.memory_used_bytes}B)"
            )
        if budget.cpu_free_millicores < need_cpu_mc:
            return False, (
                f"node={node_name} cpu insufficient: "
                f"free={budget.cpu_free_millicores}m < need={need_cpu_mc}m"
            )
        if budget.gpu_free < need_gpu:
            return False, f"node={node_name} gpu insufficient: free={budget.gpu_free} < need={need_gpu}"

    return True, "ok"


def run_scheduler():
    """
    1) 모든 workspace를 순회하며,
       - Pending Pod에서 자원 사용량 계산 후, 실행 가능하면 인스턴스 큐로 이동
       - 인스턴스 큐에서 pop -> Helm 배포 -> 실패 시 롤백/재대기
    2) 기존의 pod_start_new() 함수를 대체
    """

    def db_sync(pod_info: dict, project=None, deployment=None, preprocessing=None, analyzer=None, fine_tuning=None, collect=None):
        if pod_info["pod_type"] == TYPE.PROJECT_TYPE:
            if pod_info["work_func_type"] == TYPE.TRAINING_ITEM_A:
                training_info = db_project.get_training(training_id=pod_info["id"])
                if training_info is None or training_info["end_datetime"]:
                    return False
            elif pod_info["work_func_type"] == TYPE.TRAINING_ITEM_C:
                hps_info = db_project.get_hps(hps_id=pod_info["id"])
                if hps_info is None or hps_info["end_datetime"]:
                    return False
            elif pod_info["work_func_type"] == TYPE.TRAINING_ITEM_B:
                tool_info = db_project.get_project_tool(project_tool_id=pod_info["id"])
                if tool_info is None or not tool_info['request_status'] or tool_info["end_datetime"]:
                    return False
        elif pod_info["pod_type"] == TYPE.PREPROCESSING_TYPE:
            if pod_info["work_func_type"] == TYPE.PREPROCESSING_ITEM_A:
                tool_info = db_prepro.get_preprocessing_tool_sync(preprocessing_tool_id=pod_info["id"])
                if tool_info is None or not tool_info['request_status']:
                    return False
            elif pod_info["work_func_type"] == TYPE.PREPROCESSING_ITEM_B:
                job_info = db_prepro.get_job_simple(preprocessing_job_id=pod_info["id"])
                if job_info is None or job_info["end_datetime"]:
                    return False
        elif pod_info["pod_type"] == TYPE.ANALYZER_TYPE:
            analyzer_graph_info = db_analyzing.get_analyzer_graph_sync(id=pod_info.get("graph_id"))
            if analyzer_graph_info is None or analyzer_graph_info.get("end_datetime"):
                return False
        elif pod_info["pod_type"] == TYPE.DEPLOYMENT_TYPE: # 배포
            worker_info = db_deployment.get_deployment_worker(deployment_worker_id=pod_info["deployment_worker_id"])
            if worker_info is None or worker_info["end_datetime"]:
                return False
        elif pod_info["pod_type"] == TYPE.FINE_TUNING_TYPE:
            model_info = db_model.get_model_sync(model_id=pod_info["model_id"])
            if model_info is None or \
                model_info["latest_fine_tuning_status"] in \
                        [TYPE.KUBE_POD_STATUS_STOP, TYPE.KUBE_POD_STATUS_ERROR, TYPE.KUBE_POD_STATUS_RUNNING, TYPE.KUBE_POD_STATUS_DONE]:
                return False
        elif pod_info["pod_type"] == TYPE.COLLECT_TYPE:
            collect_info = db_collect.get_collect_info(collect_id=pod_info["collect_info"]["id"])
            if collect_info is None or collect_info["end_datetime"]:
                return False
        return True

    def workspace_db_sync(pod_info):
        pt = pod_info.get("pod_type")
        if pt == TYPE.PROJECT_TYPE:
            wft = pod_info.get("work_func_type")
            if wft == TYPE.TRAINING_ITEM_A:
                training_info = db_project.get_training(training_id=pod_info["id"])
                if (training_info is None or
                    training_info["end_status"] == TYPE.KUBE_POD_STATUS_STOP or
                    training_info["instance_id"] is None or
                    training_info["end_datetime"]):
                    return False
            elif wft == TYPE.TRAINING_ITEM_C:
                hps_info = db_project.get_hps(hps_id=pod_info["id"])
                if hps_info is None or hps_info["end_datetime"]:
                    return False
            elif wft == TYPE.TRAINING_ITEM_B:
                tool_info = db_project.get_project_tool(project_tool_id=pod_info["id"])
                if (tool_info is None or
                    not tool_info['request_status'] or
                    tool_info["gpu_count"] != pod_info["gpu_count"] or
                    tool_info["image_real_name"] != pod_info["image_name"] or
                    json.loads(tool_info["gpu_select"]) != pod_info["gpu_select"] or
                    tool_info["instance_id"] is None or
                    tool_info["end_datetime"]):
                    return False
        elif pt == TYPE.PREPROCESSING_TYPE:
            wft = pod_info.get("work_func_type")
            if wft == TYPE.PREPROCESSING_ITEM_A:
                tool_info = db_prepro.get_preprocessing_tool_sync(preprocessing_tool_id=pod_info["id"])
                if (tool_info is None or
                    not tool_info['request_status'] or
                    tool_info["gpu_count"] != pod_info["gpu_count"] or
                    tool_info["image_real_name"] != pod_info["image_name"] or
                    json.loads(tool_info["gpu_select"]) != pod_info["gpu_select"] or
                    tool_info["instance_id"] is None or
                    tool_info["end_datetime"]):
                    return False
            elif wft == TYPE.PREPROCESSING_ITEM_B:
                job_info = db_prepro.get_job_simple(preprocessing_job_id=pod_info["id"])
                if (job_info is None or job_info["end_datetime"] or job_info["instance_id"] is None):
                    return False
        elif pt == TYPE.ANALYZER_TYPE:
            analyzer_graph_info = db_analyzing.get_analyzer_graph_sync(id=pod_info.get("graph_id"))
            if (analyzer_graph_info is None or
                analyzer_graph_info.get("end_datetime") or
                analyzer_graph_info.get("instance_id") is None):
                return False
        elif pt == TYPE.DEPLOYMENT_TYPE:
            worker_info = db_deployment.get_deployment_worker(deployment_worker_id=pod_info["deployment_worker_id"])
            if (worker_info is None or
                worker_info["end_datetime"] or
                worker_info["instance_id"] is None):
                return False
        elif pt == TYPE.COLLECT_TYPE:
            collect_info = db_collect.get_collect_info(collect_id=pod_info["collect_info"]["id"])
            if (collect_info is None or
                collect_info["end_datetime"] or
                collect_info["instance_id"] is None):
                return False
        if settings.LLM_USED:
            if pt == TYPE.FINE_TUNING_TYPE:
                model_info = db_model.get_model_sync(model_id=pod_info["model_id"])
                if model_info is None or \
                    model_info["latest_fine_tuning_status"] in \
                        [TYPE.KUBE_POD_STATUS_STOP, TYPE.KUBE_POD_STATUS_ERROR, TYPE.KUBE_POD_STATUS_RUNNING, TYPE.KUBE_POD_STATUS_DONE]:
                    return False
        return True

    

    def calculate_pending_in_instance_queue(redis_queue, item, item_type):
        """
        인스턴스 큐에 들어있는 pod_info들 중,
        item_type/id가 동일한 것들을 모아서 pending cpu/ram/gpu를 합산
        """
        def is_same_item(qpod, item_type, item_id):
            """
            qpod 안에 있는 id(project_id, deployment_id 등)와
            현재 item['id']가 일치하는지 확인
            """
            if item_type == TYPE.PROJECT_TYPE:
                return qpod.get("project_id") == item_id
            elif item_type == TYPE.DEPLOYMENT_TYPE:
                return qpod.get("deployment_id") == item_id
            elif item_type == TYPE.PREPROCESSING_TYPE:
                return qpod.get("preprocessing_id") == item_id
            elif item_type == TYPE.ANALYZER_TYPE:
                return qpod.get("analyzer_id") == item_id
            elif item_type == TYPE.COLLECT_TYPE:
                return qpod.get("collect_id") == item_id
            return False
        
        USAGE_CALC_MAP = {
            TYPE.PROJECT_TYPE: usage_for_project,
            TYPE.DEPLOYMENT_TYPE: usage_for_deployment,
            TYPE.PREPROCESSING_TYPE: usage_for_preprocessing,
            TYPE.ANALYZER_TYPE: usage_for_analyzer,
            TYPE.COLLECT_TYPE: usage_for_collector,
            TYPE.FINE_TUNING_TYPE: usage_for_fine_tuning,
            # LLM 등 다른 항목이 필요하다면 추가
        }

        pending_cpu = 0
        pending_ram = 0
        pending_gpu = 0

        calc_fn = USAGE_CALC_MAP.get(item_type, None)
        if not calc_fn:
            # item_type에 대응하는 usage 함수가 없으면 바로 반환
            return 0, 0, 0

        instance_items = redis_queue.fetch_queue_items()
        for data in instance_items:
            qpod = json.loads(data)

            # 1) item_type/id 매칭 여부 확인
            if not is_same_item(qpod, item_type, item["id"]):
                # 항목이 달라서 스킵
                continue

            # 2) GPU 개수 및 pod_count 계산
            p_gpu = qpod["gpu_count"]
            pod_count = 1
            if qpod["gpu_cluster_auto"] and qpod["gpu_auto_cluster_case"]:
                pod_count = qpod["gpu_auto_cluster_case"]["server"]
            elif p_gpu > 1 and qpod["pod_per_gpu"]:
                pod_count = p_gpu / qpod["pod_per_gpu"]

            # 3) CPU, RAM 계산 (항목별 전담 함수 활용)
            cpu, ram = calc_fn(item, qpod, pod_count)

            # 4) pending 누적
            pending_cpu += cpu
            pending_ram += ram
            pending_gpu += p_gpu

        return pending_cpu, pending_ram, pending_gpu



    def process_item_type(
        ws_id,
        workspace_item_pending_pod,
        workspace_instance_used_resource,
        item_type,
        get_item_list_fn,
        calculate_usage_fn,
        get_limits_fn,
        db_sync_fn
    ):
        """
        1) DB에서 item_list를 가져옴
        2) 자원 사용량을 합산 → workspace_instance_used_resource
        3) pending_pod 확인 + db_sync
        4) 인스턴스 큐에서 이미 대기중인 pod들의 자원(pending) 계산
        5) available vs required 비교 → 인스턴스 큐로 rput or pending 유지
        """
        redis_client = get_redis_client()
        pending_dict = workspace_item_pending_pod.get(item_type, {})

        item_list = get_item_list_fn(workspace_id=ws_id)

        # 삭제된 item id 삭제 용으로 추가
        # 해당 로직이 없어도 기능상 문제는 없음(삭제해도 무방)
        #=========
        item_str_id_list = [str(item["id"]) for item in item_list]
        pending_str_id_list = list(pending_dict.keys())
        del_item_ids = set(pending_str_id_list) - set(item_str_id_list) 
        for del_item_id in list(del_item_ids):
            del pending_dict[del_item_id]
        #=========

        for item in item_list:
            # 1) 자원 사용량 계산
            used_cpu, used_ram, used_gpu = calculate_usage_fn(item)

            inst_id = item["instance_id"]
            # 인스턴스 큐
            inst_queue_key = redis_key.WORKSPACE_INSTANCE_QUEUE.format(ws_id, inst_id)
            redis_queue = RedisQueue(redis_client=redis_client, key=inst_queue_key)
            if inst_id not in workspace_instance_used_resource:
                workspace_instance_used_resource[inst_id] = {"cpu":0, "ram":0, "gpu":0}
            workspace_instance_used_resource[inst_id]["cpu"] += used_cpu
            workspace_instance_used_resource[inst_id]["ram"] += used_ram
            workspace_instance_used_resource[inst_id]["gpu"] += used_gpu
            # 2) Pending Pod 있는지 확인
            item_id_str = str(item["id"])
            if item_id_str in pending_dict and pending_dict[item_id_str] != []:
                pod_info = pending_dict[item_id_str].pop(0)
            else:
                # 만약 pod_info의 item_id가 item["id"]인지 체크
                # 없으면 continue
                continue

            # DB sync
            if not db_sync_fn(
                pod_info=pod_info,
                **{item_type: item}  # ex) project=project
            ):
                logging.info(f"[PENDING REMOVED] {pod_info['pod_type']} ID {item_id_str}: 사용자 중지, 삭제")
                continue

            pen_cpu, pen_ram, pen_gpu = calculate_pending_in_instance_queue(redis_queue, item, item_type)
            # pen_cpu, pen_ram, pen_gpu = 0, 0, 0

            # Fine-tuning 모델은 db_model.get_models_sync가 instance_allocate를 제공하지 않는다
            # (Task 1에서 잘못된 SQL alias 제거). 타 item_type은 자체 쿼리로 instance_allocate를
            # 공급하므로 폴백: instance_allocate → instance_count → 1.
            # 실제 노드 용량 검증은 process_instance_queue_item::_fine_tuning_node_budget_guard (Task 4)가 수행.
            _alloc_count = item.get("instance_allocate", item.get("instance_count", 1))
            total_cpu = item["cpu_allocate"] * _alloc_count
            total_ram = item["ram_allocate"] * _alloc_count
            total_gpu = item["gpu_allocate"] * _alloc_count


            available_cpu = total_cpu - used_cpu - pen_cpu
            available_ram = total_ram - used_ram - pen_ram
            available_gpu = total_gpu - used_gpu - pen_gpu

            # CPU/RAM Limit
            limit_cpu, limit_ram = get_limits_fn(item, pod_info)
            # GPU count
            gpu_count = pod_info["gpu_count"]

            # pod_count 계산 (gpu_cluster_auto 등, 원본 로직 그대로)
            pod_count = 1
            # print("pod_info:", pod_info)
            pod_per_gpu = pod_info["pod_per_gpu"] if pod_info.get("pod_per_gpu") else 1
            if pod_info["gpu_cluster_auto"] and pod_info["gpu_auto_cluster_case"]:
                pod_count = pod_info["gpu_auto_cluster_case"]["server"]
                pod_per_gpu = pod_info["gpu_auto_cluster_case"]["gpu_count"]
                pod_info["pod_per_gpu"] = pod_per_gpu
            elif gpu_count > 1 and pod_per_gpu:
                pod_count = gpu_count / pod_per_gpu
            pod_info["pod_count"] = pod_count


            # 자원 비교
            # TODO
            # 파인튜닝의 경우 get_limits_fn 여기서 이미 계산됨
            # 따라서, pod_count 를 곱하면 안됨
            if item_type == TYPE.FINE_TUNING_TYPE:
                need_cpu = limit_cpu
                need_ram = limit_ram
                need_gpu = gpu_count
                pod_info["resource"] = {"cpu": limit_cpu, "ram": limit_ram}
            else:
                need_cpu = limit_cpu * pod_count * (pod_per_gpu if pod_per_gpu > 1 else 1)
                need_ram = limit_ram * pod_count * (pod_per_gpu if pod_per_gpu > 1 else 1)
                need_gpu = gpu_count
                pod_info["resource"] = {"cpu": limit_cpu * (pod_per_gpu if pod_per_gpu > 1 else 1), "ram": limit_ram * (pod_per_gpu if pod_per_gpu > 1 else 1)}

            
            
            if (available_cpu < need_cpu) or (available_ram < need_ram) or (available_gpu < need_gpu):
                logging.info(
                    f"{pod_info['pod_type']} ID {item_id_str}: 자원 부족으로 인한 Pending - CPU/RAM/GPU Available: {available_cpu}/{available_ram}/{available_gpu} | Need: {need_cpu}/{need_ram}/{need_gpu}"
                )
                pending_dict[item_id_str].insert(0, pod_info)  # 자원이 부족하여 pending 상태로 유지
            else:
                # 자원 충분 → pending 제거, 인스턴스 큐
                if item_id_str in pending_dict:
                    # del pending_dict[item_id_str]
                    logging.info(f"[PENDING REMOVED] {pod_info['pod_type']} ID {item_id_str}: 자원 확보 완료 → 대기 해제")
                 
                try:
                    
                    redis_queue.rput(json.dumps(pod_info))                  
                    logging.info(
                        f"[QUEUE SUCCESS] {pod_info['pod_type']} ID {item_id_str}: 인스턴스 큐에 추가 완료 (CPU: {need_cpu}, RAM: {need_ram}, GPU: {need_gpu})"
                    )
                except Exception as e:
                    logging.error(f"[QUEUE ERROR] {pod_info['pod_type']} ID {item_id_str}: 큐 추가 실패 - {e}")

        if DEBUG:
            logging.info("[WORKSPACE ITEM USED RESOURCE] : [%s] : %s", item_type ,json.dumps(workspace_instance_used_resource, ensure_ascii=False))

    ITEM_PROCESSORS = {
    TYPE.PROJECT_TYPE: {
        "get_item_list_fn": db_project.get_project_list,        # (workspace_id=...)
        "calculate_usage_fn": calculate_project_usage,
        "get_limits_fn": get_project_limits,
        "db_sync_fn": db_sync,  # 원본 db_sync 함수
    },
    TYPE.DEPLOYMENT_TYPE: {
        "get_item_list_fn": db_deployment.get_deployment_list_in_workspace,
        "calculate_usage_fn": calculate_deployment_usage,
        "get_limits_fn": get_deployment_limits,
        "db_sync_fn": db_sync,
    },
    TYPE.PREPROCESSING_TYPE: {
        "get_item_list_fn": db_prepro.get_preprocessing_list_sync,
        "calculate_usage_fn": calculate_preprocessing_usage,
        "get_limits_fn": get_preprocessing_limits,
        "db_sync_fn": db_sync,
    },
    TYPE.ANALYZER_TYPE: {
        "get_item_list_fn": db_analyzing.get_analyzer_list,
        "calculate_usage_fn": calculate_analyzer_usage,
        "get_limits_fn": get_analyzer_limits,
        "db_sync_fn": db_sync,
    },
    TYPE.COLLECT_TYPE: {
        "get_item_list_fn": db_collect.get_collect_list,
        "calculate_usage_fn": calculate_collector_usage,
        "get_limits_fn": get_collector_limits,
        "db_sync_fn": db_sync,
    },
    TYPE.FINE_TUNING_TYPE: {
        "get_item_list_fn": db_model.get_models_sync,
        "calculate_usage_fn": calculate_fine_tuning_usage,
        "get_limits_fn": get_fine_tuning_limits,
        "db_sync_fn": db_sync,                               # TODO: Fine Tuning은 실제론 db_sync 함수를 사용하지 않아 문제 생길 여지 있으므로 확인 필요
    },
    }

    def process_all_item_types(ws_id, workspace_item_pending_pod, workspace_instance_used_resource):
        """
        Project / Deployment / Preprocessing / Analyzer / Collector 등
        모든 항목에 대해 process_item_type(...)를 한꺼번에 호출
        """
        for itype, cfg in ITEM_PROCESSORS.items():
            process_item_type(
                ws_id=ws_id,
                workspace_item_pending_pod=workspace_item_pending_pod,
                workspace_instance_used_resource=workspace_instance_used_resource,
                item_type=itype,
                get_item_list_fn=cfg["get_item_list_fn"],
                calculate_usage_fn=cfg["calculate_usage_fn"],
                get_limits_fn=cfg["get_limits_fn"],
                db_sync_fn=cfg["db_sync_fn"]
            )
            
    def deploy_pod_via_helm(pod_info):
        """
        헬름 실행을 한 곳에서 관리.
        pod_type 및 work_func_type 별로 기존 로직(create_* 등) 호출
        """
        res, message = None, None
        pt = pod_info.get("pod_type")
        if pt == TYPE.PROJECT_TYPE:
            wft = pod_info.get("work_func_type")
            if wft == TYPE.TRAINING_ITEM_A:
                res, message = create_training_pod(pod_info=pod_info)
            elif wft == TYPE.TRAINING_ITEM_B:
                res, message = create_project_tool(pod_info=pod_info)
            elif wft == TYPE.TRAINING_ITEM_C:
                res, message = create_hps_pod(pod_info=pod_info)

        elif pt == TYPE.DEPLOYMENT_TYPE:
            if settings.LLM_USED and pod_info.get("is_llm"):
                res, message = install_deployment_llm(pod_info=pod_info)
            else:
                res1, message = install_deployment_pod(deployment_info=pod_info)
                res2, message = install_deployment_svc_ing(deployment_info=pod_info)
                res = True if (res1 != False and res2 != False) else False

        elif pt == TYPE.PREPROCESSING_TYPE:
            wft = pod_info.get("work_func_type")
            if wft == TYPE.PREPROCESSING_ITEM_A:
                res, message = create_preprocessing_tool(pod_info=pod_info)
            elif wft == TYPE.PREPROCESSING_ITEM_B:
                res, message = create_preprocessing_job(pod_info=pod_info)

        elif pt == TYPE.COLLECT_TYPE:
            wft = pod_info.get("work_func_type")
            if wft == TYPE.PUBLICAPI_TYPE:
                res, message = create_public_api_collector(pod_info)
            elif wft == TYPE.REMOTESERVER_TYPE:
                print("RemoteServer Collector")
                res, message = create_remote_server_collector(pod_info)
            elif wft == TYPE.CRAWLING_TYPE:
                res, message = create_crawling_collector(pod_info)
            elif wft == TYPE.FB_DEPLOY_TYPE:
                res, message = create_fb_deployment_collector(pod_info)

        elif pt == TYPE.ANALYZER_TYPE:
            res, message = create_analyzer_pod(pod_info=pod_info)

        if settings.LLM_USED:
            if pt == TYPE.FINE_TUNING_TYPE:
                # LLM Fine Tuning
                # CPU, RAM은 아래에서 설정 가능
                res, message = create_fine_tuning(pod_info=pod_info)

        return res, message

    def revert_helm_on_failure(pod_info, workspace_id):
        """
        헬름 배포 실패 시 rollback (사용자 코드에서 하던 부분)
        """
        try:
            if pod_info["pod_type"] == TYPE.DEPLOYMENT_TYPE:
                if settings.LLM_USED and pod_info.get("is_llm"):
                    uninstall_deployment_llm(
                        deployment_id=pod_info["deployment_id"],
                        llm_type=pod_info["llm_type"],
                        llm_id=pod_info["llm_id"]
                    )
                else:
                    uninstall_pod_deployment(
                        workspace_id=workspace_id,
                        deployment_id=pod_info["deployment_id"],
                        deployment_worker_id=pod_info["deployment_worker_id"]
                    )
            elif pod_info["pod_type"] == TYPE.PROJECT_TYPE:
                if pod_info["work_func_type"] == TYPE.TRAINING_ITEM_B:
                    delete_helm_project(
                        project_tool_type=TYPE.TOOL_TYPE[pod_info["tool_type"]],
                        project_tool_id=pod_info["id"],
                        workspace_id=workspace_id
                    )
                elif pod_info["work_func_type"] in [TYPE.TRAINING_ITEM_A, TYPE.TRAINING_ITEM_C]:
                    delete_helm_project(
                        project_tool_type=pod_info["work_func_type"],
                        project_tool_id=pod_info["id"],
                        workspace_id=workspace_id
                    )
            elif pod_info["pod_type"] == TYPE.PREPROCESSING_TYPE:
                wft = pod_info["work_func_type"]
                delete_helm_preprocessing(
                    preprocessing_tool_type=wft,
                    preprocessing_tool_id=pod_info["id"],
                    workspace_id=workspace_id
                )
            elif pod_info.get("pod_type") == TYPE.ANALYZER_TYPE:
                delete_helm_analyzer(pod_info=pod_info)
            if settings.LLM_USED and pod_info["pod_type"] == TYPE.FINE_TUNING_TYPE:
                delete_helm_fine_tuning(
                    model_id=pod_info["model_id"],
                    workspace_id=workspace_id
                )
        except Exception as e:
            traceback.print_exc()
            pass

    def process_instance_queue_item(
    redis_client,
    pod_info,
    instance,
    ws_id,
    workspace_instance_used_resource
    ):
        """
        1) DB Sync
        2) 인스턴스 자원 체크(available vs needed)
        3) GPU/CPU/NPU 처리
        4) Helm 배포 (deploy_pod_via_helm)
        5) 실패시 revert
        """
        # 1) DB Sync
        if not workspace_db_sync(pod_info):
            return Status.FAIL_PASS, "사용자 중지, 삭제된 요청"

        # 2) 인스턴스 자원 계산
        total_cpu = instance["instance_allocate"] * instance["cpu_allocate"]
        total_ram = instance["instance_allocate"] * instance["ram_allocate"]
        total_gpu = instance["instance_allocate"] * instance["gpu_allocate"]

        used_res = workspace_instance_used_resource.get(instance["instance_id"], {"cpu":0,"ram":0,"gpu":0})
        available_cpu = total_cpu - used_res["cpu"]
        available_ram = total_ram - used_res["ram"]
        available_gpu = total_gpu - used_res["gpu"]
        need_cpu = pod_info["resource"]["cpu"] * pod_info["pod_count"]
        need_ram = pod_info["resource"]["ram"] * pod_info["pod_count"]
        need_gpu = pod_info.get("gpu_count", 0)

        if (available_cpu < need_cpu) or (available_ram < need_ram) or (available_gpu < need_gpu):
            return Status.FAIL_RETRY, f"자원 부족 - instance id : {instance["instance_id"]} | CPU/RAM/GPU Available: {available_cpu}/{available_ram}/{available_gpu} | Need: {need_cpu}/{need_ram}/{need_gpu}"

        # 3) GPU / CPU / NPU 처리
        if need_gpu > 0:
            # GPU 로직
            free_workspace_gpu_count = (instance["instance_allocate"] * instance["gpu_allocate"]) - used_res["gpu"]
            if need_gpu > free_workspace_gpu_count:
                return Status.FAIL_RETRY, "Workspace GPU 자원 부족"

            instance_selector = f"instance_id={instance['instance_id']}"
            used_instance_gpu_uuid = get_used_gpu_uuid(label_select=instance_selector)

            gpu_cluster_auto = pod_info["gpu_cluster_auto"]
            gpu_select = pod_info.get("gpu_select", [])
            if gpu_cluster_auto and need_gpu > 1:
                # 예: 자동 클러스터링
                gpu_auto_cluster_case = pod_info["gpu_auto_cluster_case"]
                gpu_model_status = json.loads(redis_client.get(redis_key.GPU_INFO_RESOURCE))
                available_gpus = get_available_gpus_by_model(
                    model_name=instance["resource_name"], 
                    data=gpu_model_status, 
                    instance_id=instance["instance_id"]
                )
                # filter out used
                real_available_gpus = []
                for g in available_gpus:
                    if g["gpu_uuid"] not in used_instance_gpu_uuid:
                        real_available_gpus.append(g)
                if not real_available_gpus:
                    return Status.FAIL_RETRY, "GPU 없음"

                # 예: common.get_gpu_auto_select_new(...)
                auto_select = get_gpu_auto_select(
                    gpu_count=gpu_auto_cluster_case["gpu_count"],
                    pod_count=gpu_auto_cluster_case["server"],
                    gpu_data=real_available_gpus
                )
                if not auto_select:
                    return Status.FAIL_RETRY, "GPU auto select 실패"
                # 클러스터링
                real_available_gpus = gpu_auto_clustering(
                    available_gpus=auto_select,
                    pod_per_gpu=gpu_auto_cluster_case["gpu_count"]
                )
                pod_info["available_gpus"] = real_available_gpus

            elif (not gpu_cluster_auto) and need_gpu > 1:
                # 수동 클러스터링
                gpu_cluster_status = True
                for g in gpu_select:
                    if g["gpu_uuid"] in used_instance_gpu_uuid:
                        gpu_cluster_status = False
                        break
                if not gpu_cluster_status:
                    return Status.FAIL_RETRY, "수동 클러스터링 충돌"
                # 클러스터링
                real_available_gpus = gpu_auto_clustering(
                    available_gpus=gpu_select,
                    pod_per_gpu=pod_info["pod_per_gpu"]
                )
                pod_info["available_gpus"] = real_available_gpus

            else:
                # need_gpu == 1 or other simple cases
                gpu_model_status = json.loads(redis_client.get(redis_key.GPU_INFO_RESOURCE))
                available_gpus = get_available_gpus_by_model(
                    model_name=instance["resource_name"],
                    data=gpu_model_status,
                    instance_id=instance["instance_id"]
                )
                # filter out used
                real_available_gpus = []
                for g in available_gpus:
                    if g["gpu_uuid"] not in used_instance_gpu_uuid:
                        real_available_gpus.append(g)
                if not real_available_gpus:
                    return Status.FAIL_RETRY, "GPU 없음"

                available_gpus = get_optimal_gpus(available_gpus, num_gpus=1)
                available_gpus = gpu_auto_clustering(available_gpus, pod_per_gpu=1)
                pod_info["available_gpus"] = available_gpus

        elif need_gpu == 0 and instance["instance_type"] == TYPE.INSTANCE_TYPE_GPU:
            # GPU 인스턴스지만 gpu_count=0
            node_list = db_node.get_node_instance_list(instance_id=instance["instance_id"])
            nodes = [n['node_name'] for n in node_list]
            weights = [n['instance_allocate'] for n in node_list]
            pod_info["available_node"] = random.choices(nodes, weights=weights, k=1)[0]

        # CPU 인스턴스
        elif instance["instance_type"] == TYPE.INSTANCE_TYPE_CPU:
            node_list = db_node.get_node_instance_list(instance_id=instance["instance_id"])
            nodes = [n['node_name'] for n in node_list]
            weights = [n['instance_allocate'] for n in node_list]
            pod_info["available_node"] = random.choices(nodes, weights=weights, k=1)[0]
            pod_info["cpu_instance_name"] = instance["instance_name"]

        # NPU 인스턴스
        elif instance["instance_type"] == TYPE.INSTANCE_TYPE_NPU:
            logging.info("NPU 사용")
            pod_info["used_npu"] = True

        # 3-b) FINE_TUNING 한정: 노드 실측 K8s request 예산 guard
        # workspace 쿼터(step 2)와 GPU/node 선택(step 3)은 통과했더라도,
        # 외부 워크로드(Redis/EFK 등) 때문에 해당 노드의 실측 request 예산이
        # 부족할 수 있다. 부족 시 FAIL_RETRY로 되돌려 다음 틱에 재평가.
        if pod_info.get("pod_type") == TYPE.FINE_TUNING_TYPE:
            ok, reason = _fine_tuning_node_budget_guard(pod_info)
            if not ok:
                return Status.FAIL_RETRY, f"노드 예산 부족/확인 실패로 재시도: {reason}"

        # 4) helm 배포
        res, message = deploy_pod_via_helm(pod_info)
        if not res:
            # rollback
            revert_helm_on_failure(pod_info, ws_id)
            return Status.FAIL_RETRY, message
        else:
            logging.info("helm ok")
            return Status.SUCCESS, "success"

    def print_pending_queue_pods(ws_id, workspace_item_pending_pod):
        """
        특정 워크스페이스의 pending pod 및 인스턴스 대기열을 정리하여 출력하는 함수.
        - workspace_id: 워크스페이스 ID
        - workspace_name: 워크스페이스 이름
        - workspace_item_pending_pod: Pending된 Pod 정보 딕셔너리
        - workspace_instances: 해당 워크스페이스의 인스턴스 리스트
        """        
        # workspace_id = workspace["id"]
        # workspace_name = workspace["name"]
        
        logging.info("=" * 50)
        logging.info(f"🟢 워크스페이스 #{ws_id} ") # [{workspace_name}]
        logging.info("=" * 50)

        has_pending = False  # Pending Pod이 하나라도 있는지 확인하는 플래그
        
        # 워크스페이스별 Pending Pod 개수 출력
        for pod_type, pending_dict in workspace_item_pending_pod.items():
            # print(pending_dict, file=sys.stderr)
            total_pending = sum(len(v) for v in pending_dict.values())
            if total_pending == 0:
                continue  # 해당 타입에 pending된 pod가 없으면 건너뜀
            
            has_pending = True

            logging.info(f"🔸 {pod_type} ({total_pending} pending)")
            for item_id, pod_infos in pending_dict.items():
                for pod_info in pod_infos:
                    instance_id = pod_info.get("instance_id", "N/A")
                    gpu_count = pod_info.get("gpu_count", 0)
                    cpu_limit = pod_info.get("resource", {}).get("cpu", "N/A")
                    ram_limit = pod_info.get("resource", {}).get("ram", "N/A")
                    logging.info(f"  - ID: {item_id} | Instance: {instance_id} | GPU: {gpu_count} | CPU: {cpu_limit} | RAM: {ram_limit}")

        if not has_pending:
            logging.info("✅ 현재 PENDING 상태인 Pod이 없습니다.")

    global last_print_time
    consumer = Consumer(conf)
    kafka_admin = AdminClient(kafka_admin_conf)
    
    type_id_map = {
                TYPE.PROJECT_TYPE: "project_id",
                TYPE.DEPLOYMENT_TYPE: "deployment_id",
                TYPE.PREPROCESSING_TYPE: "preprocessing_id",
                TYPE.ANALYZER_TYPE: "analyzer_id",
                TYPE.COLLECT_TYPE: "collect_id",
                TYPE.FINE_TUNING_TYPE: "model_id" if settings.LLM_USED else None
            }
    
    while True:
        try:
            time.sleep(0.1)
            redis_client = get_redis_client()
            # workspace_list = db_workspace.get_workspace_list()

            # Kafka Consume Messages
            success = kafka_consume_msgs(consumer, kafka_admin, redis_client, type_id_map)
            if not success:
                # 재생성
                consumer = Consumer(conf)
                kafka_admin = AdminClient(kafka_admin_conf)
                logging.info("Kafka consumer reinitialized.")
                time.sleep(3)
            
            # Pending Load
            workspace_pending_pod = redis_client.hgetall(redis_key.WORKSPACE_ITEM_PENDING_POD2)
            # print(workspace_pending_pod, file=sys.stderr)
            # for workspace in workspace_list:
            for ws_id, raw_pending in workspace_pending_pod.items():
                workspace_item_pending_pod = json.loads(raw_pending)
                #TODO
                # workspace instance queue에 값이 있거나 instance queue =에 값이 있을 경우에만 돌 수 있도록 수정
                
                # 준비: instance별 자원 사용량 dict
                workspace_instance_used_resource = {}

                # 1) Project / Deployment / Preprocessing / Analyzer / Collector 등 공통 처리
                process_all_item_types(
                    ws_id=ws_id,
                    workspace_item_pending_pod=workspace_item_pending_pod,
                    workspace_instance_used_resource=workspace_instance_used_resource
                )

                # pending 반영
                redis_client.hset(
                    redis_key.WORKSPACE_ITEM_PENDING_POD2,
                    ws_id,
                    json.dumps(workspace_item_pending_pod)
                )
                # Pending Pod Queue 상태 출력
                if DEBUG:
                    print_pending_queue_pods(ws_id, workspace_item_pending_pod)
                
                # 2) 인스턴스 큐에서 실제 helm 배포 시도
                # -----------------------------------------------------------------------
                workspace_instances = db_workspace.get_workspace_instance_list(workspace_id=ws_id)

                for instance in workspace_instances:
                    try:
                        instance_key = redis_key.WORKSPACE_INSTANCE_QUEUE.format(ws_id, instance["instance_id"])
                        redis_queue = RedisQueue(redis_client=redis_client, key=instance_key)
                        pod_info_queue = redis_queue.pop_nowait()
                        if not pod_info_queue:
                            continue
                        pod_info = json.loads(pod_info_queue)
                    except Exception as e:
                        logging.info("pod_info_queue 에러")
                        continue
                    logging.info("POD INFO QUEUE : %s", pod_info)
                    # 통합 함수 호출 → DB sync, 자원 체크, GPU 처리, helm 배포까지 수행
                    status, msg = process_instance_queue_item(
                        redis_client=redis_client,
                        pod_info=pod_info,
                        instance=instance,
                        ws_id=ws_id,
                        workspace_instance_used_resource=workspace_instance_used_resource
                    )
                    
                    # 자원 부족 등으로 실패 시 → 다시 큐에 넣어두기
                    if status == Status.FAIL_RETRY:
                        logging.info(f"Instance Queue failed scheduling (retry): {msg}")
                        redis_queue.lput(json.dumps(pod_info))
                    elif status == Status.FAIL_PASS:
                        logging.info(f"Instance Queue failed scheduling (pass): {msg}")
                    else:
                        logging.info("Instance Queue scheduling success")
            # Pending Pod Queue 상태 출력
            # current_time = time.time()
            # if current_time - last_print_time >= PRINT_INTERVAL:
            #     workspace_pending = redis_client.hgetall(redis_key.WORKSPACE_ITEM_PENDING_POD2)
            #     for workspace in workspace_list:
            #         raw_pending = workspace_pending.get(workspace["id"])
            #         if raw_pending:
            #             workspace_item_pending_pod = json.loads(raw_pending)
            #         else:
            #             workspace_item_pending_pod = {
            #                 TYPE.PROJECT_TYPE: {},
            #                 TYPE.DEPLOYMENT_TYPE: {},
            #                 TYPE.PREPROCESSING_TYPE: {},
            #                 TYPE.ANALYZER_TYPE: {},
            #                 TYPE.COLLECT_TYPE: {},
            #                 TYPE.FINE_TUNING_TYPE: {},
            #             }
            #         print(f"3 {workspace["id"]} ", workspace_item_pending_pod, file=sys.stderr)
            #         print_pending_queue_pods(workspace, workspace_item_pending_pod)
            #     last_print_time = current_time
                
        except Exception as e:
            print(traceback.format_exc(), file=sys.stderr)