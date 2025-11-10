from prometheus_api_client import PrometheusConnect, MetricSnapshotDataFrame, MetricRangeDataFrame
from confluent_kafka import Producer
from kubernetes import client, config
from contextlib import contextmanager
from collections import defaultdict, Counter
from utils.settings import PROMETHEUS_DNS
from utils import settings
import json
import traceback
import logging
# from utils.resource import response
from utils import PATH, TYPE, topic_key
import utils.msa_db.db_storage as storage_db
import utils.msa_db.db_workspace as ws_db
import utils.msa_db.db_node as node_db
import utils.msa_db.db_dataset as dataset_db
import utils.msa_db.db_project as project_db
import utils.msa_db.db_deployment as deployment_db
if settings.LLM_USED:
    import utils.llm_db.db_model as model_db
    import utils.llm_db.db_rag as rag_db
import utils.msa_db.db_instance as instance_db
import utils.msa_db.db_prepro as prepro_db
import utils.msa_db.db_collect as collect_db
from utils.common import calculate_elapsed_time
from helm_run import create_node_init_job, delete_helm
from utils.msa_db import db_cost_management as cost_db
import math
import requests
import os
import sys
import time
from utils.kafka_producer import KafkaProducer
from utils import redis_key, notification_key
from utils.redis import get_redis_client
import subprocess
from utils.mongodb import NotificationWorkspace, insert_notification_history, get_resource_over_message
# from utils.mongodb_key import DASHBOARD_TIMELINE
import datetime
import requests
import pandas as pd

def safe_redis_operation(operation_name, operation_func, *args, **kwargs):
    """Redis 작업을 안전하게 실행하는 wrapper 함수 (Kubernetes probe 기반)"""
    max_retries = 1  # Kubernetes probe에 의존하여 재시도 횟수 줄임
    for attempt in range(max_retries):
        try:
            return operation_func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Redis 작업 '{operation_name}' 실패 (시도 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)  # 간단한 재시도
                try:
                    # Redis 클라이언트 재연결 시도
                    get_redis_client(retry_attempts=1)
                except:
                    pass
            else:
                logging.warning(f"Redis 작업 '{operation_name}' 실패 - Kubernetes probe에서 pod 상태 관리")
                return None

def get_safe_redis_client():
    """안전한 Redis 클라이언트 획득"""
    try:
        return get_redis_client()
    except Exception as e:
        logging.error(f"Redis 클라이언트 획득 실패: {e}")
        return None

"""
prometheus promql query start    
    
"""
# KAFKA
conf = {
            'bootstrap.servers' : settings.JF_KAFKA_DNS
        }


MONITORING_DNS=os.environ.get('JF_MONITORING_URL')
url="http://{DNS}/prometheus".format(DNS=MONITORING_DNS)

NODE_LIST = "kube_node_info"
POD_LIST = "kube_pod_info"
CPU_MODEL_INFO="count(node_cpu_info{{instance=~'{NODE_IP}.*'}}) by(instance,model_name)"
NODE_CPU_INFO="machine_cpu_cores" # node:node_num_cpu:sum , machine_cpu_cores{{node='{node}'}}
NODE_CPU_USAGE_RATE="instance:node_cpu:rate:sum{{instance=~'{NODE_IP}.*'}}"
POD_CPU_USAGE_RATE="sum(node_namespace_pod_container:container_cpu_usage_seconds_total:sum_irate{{node='{NODE}'}})"
POD_ALLOCATE_CPU_CORE= "sum(kube_pod_container_resource_requests{{resource='cpu', node='{NODE}'}})"

NODE_MEM_TOTAL="node_memory_MemTotal_bytes{{instance=~'{NODE_IP}.*'}}"
NODE_MEM_AVAIL="node_memory_MemAvailable_bytes{{instance=~'{NODE_IP}.*'}}"
NODE_MEM_POD_REQUESTS= "sum(kube_pod_container_resource_requests{{resource='memory',node='{NODE}'}})"
NODE_MEM_POD_USAGE = "sum(container_memory_usage_bytes{{node='{NODE}'}})"
CLUSTER_MEM_TOTAL_INFO = "machine_memory_bytes"
NODE_MEM_USED="node_memory_Active_bytes{{instance=~'{NODE_IP}.*'}}"


GPU_USAGE_RATE ="DCGM_FI_DEV_GPU_UTIL"
GPU_TEMPERATURE = "DCGM_FI_DEV_GPU_TEMP" # count를 사용해서 gpu 개수를 구해도 될것같음.
GPU_MEMORY_USAGE = "DCGM_FI_DEV_FB_USED"
GPU_MEMORY_CAPACITY = "DCGM_FI_DEV_FB_FREE{{Hostname='{HOST_NAME}',modelName='{GPU_MODEL}'}}"
GPU_MEMORY_CAPACITY_ALL = "DCGM_FI_DEV_FB_FREE"

# kubelet/var/lib/kubelet/pod-resources 를 사용해서 어떤 GPU가 할당되었는지 확인가능
REDIS_NODE_STATUS = "kube_node_spec_unschedulable"
REDIS_NODE_INFO="kube_node_info"
NODE_ROLE_INFO="kube_node_role"
REDIS_GPU_INFO="DCGM_FI_DEV_FB_FREE"
REDIS_CPU_UAGE="instance:node_cpu:ratio"
REDIS_CPU_INFO="count(node_cpu_info) by(instance,model_name)"
REDIS_MEM_TOTAL="node_memory_MemTotal_bytes"
REDIS_MEM_AVAIL="node_memory_MemAvailable_bytes"
WORKSPACE_RESOURCE_USAGE="kube_resourcequota"
#TODO
RESOURCE_QUOTA="kube_resourcequota{resource=~'limits.cpu|limits.memory'}"
POD_RESOURCE_LIMIT="kube_pod_container_resource_limits{{pod='{POD_NAME}'}}"
POD_RESOURCE_LIMIT_LIST="kube_pod_container_resource_limits"
DATASET_FILEBROWSER_STATUS_READY="kube_pod_container_status_ready{{pod='{POD_NAME}'}}"
DATASET_FILEBROWSER_POD_LIST="kube_pod_labels{label_pod_type='filebrowser'}"
REDIS_WORKSPACE_POD_LIST="kube_pod_labels{{label_workspace_id='{workspace_id}', label_work_func_type!=''}}"
NAMESPACE_TOOL_LIST="kube_pod_labels{{label_work_func_type!='',namespace='{namespace}'}}"
WORKSPACE_POD_RESOURCE_USAGE="kube_pod_labels{label_work_func_type=~'tool|training|deployment'}"
WORKSPACE_NETWORK_OUTBOUND_USAGE="container_network_transmit_bytes_total" # return value Byte/s
WORKSPACE_NETWORK_INBOUND_USAGE="container_network_receive_bytes_total" # return value Byte/s
WORKSPACE_POD_INFO_JOIN_LABELS="kube_pod_info * on(pod) group_left(label_workspace_id, label_pod_type, label_helm_name, label_instance_id) kube_pod_labels{label_work_func_type=~'tool|training|deployment'}"
TRAINING_POD_LIST="kube_pod_labels{label_work_func_type='training'}"
HPS_POD_LIST="kube_pod_labels{label_work_func_type='hps'}"
TOOL_POD_DNS = "http://{SERVICE_NAME}.{NAMESPACE}.svc.cluster.local"
POD_STATUS="kube_pod_status_phase{{pod='{POD_NAME}'}}==1"
POD_STATUS_REASON="kube_pod_status_reason{{pod='{POD_NAME}'}}==1"
POD_START_TIME="kube_pod_start_time{{pod='{POD_NAME}'}}"
POD_END_TIME="kube_pod_completion_time{{pod='{POD_NAME}'}}"

RAG_USAGE_INFO = "rag_usage_bytes"
MODEL_USAGE_INFO = "model_usage_bytes"
DATASET_USAGE_INFO = "dataset_usage_bytes"
PROJECT_USAGE_INFO = "project_usage_bytes"
WORKSAPCE_USAGE_INFO="workspace_usage_bytes"
STORAGE_REQUESTS_BYTE="kube_persistentvolumeclaim_resource_requests_storage_bytes"
STORAGE_PERSISTENTVOLUME_LIST = "kube_persistentvolumeclaim_info{storageclass!=''}"
STORAGE_PVC_INFO="kube_persistentvolumeclaim_labels{label_workspace_name!=''}"

DEPLOYMENT_INFO="kube_pod_labels{label_deployment_id!=''}"


JUPYTER_PORT="8888"
VSCODE_PORT="8080"
SSH_PORT="7681"

COMPLETE_JOB="kube_job_complete{condition='true'}"

CEPH_STORAGE_INFO = "ceph_fs_metadata"
STORAGE_TOTAL_SIZE_BYTES = "ceph_pool_max_avail{{pool_id='{POOL_ID}'}}"
STORAGE_USED_SIZE_BYTES = "ceph_pool_stored{{pool_id='{POOL_ID}'}}"
FSTYPE='nfs4'

STORAGE_INFO = "kube_persistentvolumeclaim_info{{persistentvolumeclaim='jfb-{WORKSPACE_NAME}-ws-pvc',service='monitoring-kube-state-metrics'}}" # nfs-client storage class 를 사용한 persistentvolume만 출력
STORAGE_STATUS = "kube_persistentvolume_status_phase == 1" # persistent volume 의 현재 상태들을 출력
STORAGE_CAPACITY_BYTES = "kube_persistentvolume_capacity_bytes{{persistentvolume='{PERSISTENTVOLUME_NAME}', service='monitoring-kube-state-metrics'}}" # persistent volume name을 입력해서 출력해야함 사용중인 byte용량을 알 수 있으면 사용률도 알 수 있음
STORAGE_USED="kubelet_volume_stats_used_bytes{{persistentvolumeclaim='{PERSISTENTVOULUMECLAIM_NAME}'}}"
STORAGE_USAGE="100 * sum(kubelet_volume_stats_used_bytes{{persistentvolumeclaim='{PERSISTENTVOULUMECLAIM_NAME}'}}) by (persistentvolumeclaim)/sum(kubelet_volume_stats_capacity_bytes{{persistentvolumeclaim='{PERSISTENTVOULUMECLAIM_NAME}'}}) by (persistentvolumeclaim)"
WORKSPACE_LIST="kube_persistentvolumeclaim_labels{label_workspace_name=~'.+'}"
WORKSPACE_AVAILABLE = "kube_persistentvolumeclaim_resource_requests_storage_bytes{{persistentvolumeclaim='{PERSISTENTVOULUMECLAIM_NAME}'}}"
WORKSPACE_USED="kubelet_volume_stats_used_bytes{{persistentvolumeclaim='{PERSISTENTVOULUMECLAIM_NAME}'}}"

GET_PERSISTENTVOLUMECLAIME="kube_persistentvolumeclaim_labels{{label_workspace_name='{WORKSPACE_NAME}'}}"
GET_PERSISTENTVOLUME="kube_persistentvolumeclaim_info{{persistentvolumeclaim='{PERSISTENTVOLUMECLAIME}'}}"




CONTAINER_STATUS_READY_TRUE="kube_pod_container_status_ready{{pod='{POD_NAME}'}}==1"
CONTAINER_STATUS_READY_FALSE="kube_pod_container_status_ready{{pod='{POD_NAME}'}}==0"
CONTAINER_STATUS_RUNNING="kube_pod_container_status_running{{pod='{POD_NAME}'}}==1"
CONTAINER_STATUS_WAITING="kube_pod_container_status_waiting_reason{{pod='{POD_NAME}'}}==1"
CONTAINER_STATUS_TERMINATED="kube_pod_container_status_terminated_reason{{pod='{POD_NAME}'}}==1"
CONTAINER_RESTART_TOTAL="kube_pod_container_status_restarts_total{{pod='{POD_NAME}'}}"


DEPLOYMENT_POD_RESOURCE_LIMIT_CPU = "kube_pod_container_resource_limits{{pod='{POD_NAME}', resource='cpu'}}"
DEPLOYMENT_POD_RESOURCE_LIMIT_RAM = "kube_pod_container_resource_limits{{pod='{POD_NAME}', resource='memory'}}"

MODEL_COMMIT_POD_STATUS="kube_pod_labels{label_model_commit_type!=''}"


"""
prometheus promql query end

"""

# redis_client = get_redis_client()

@contextmanager
def prometheus_connection(url):
    prom = PrometheusConnect(url=url, disable_ssl=True)
    try:
        yield prom
    finally:
        del prom

def dataset_progress_clear():
    while(True):
        try:
            dataset_list = dataset_db.get_dataset_list()
            if dataset_list:
                redis_client=get_redis_client()
                for dataset in dataset_list:
                    progress_list = redis_client.hgetall(redis_key.DATASET_PROGRESS.format(dataset_id=dataset['id'])) # 2024 08 28 wyatt 수정
                    for name, progress in progress_list.items():
                        if int(float(progress)) == 100:
                            redis_client.hdel(redis_key.DATASET_PROGRESS.format(dataset_id=dataset['id']), name)
        except:
            traceback.print_exc()
# {
#             "used_gpu": 6,
#             "total_gpu": 10,
#             "usage_gpu": 60,
#             "date": "2024-06-28 01:50:00"
#         }
# {
#             "used_storage_data": 183,
#             "total_storage_data": 1000,
#             "usage_storage_data": 18,
#             "date": "2024-06-28 08:10:00"
#         }

def get_helm_list(namespace):
    try:
        result = subprocess.run(['helm', 'list', '-n' ,namespace, '--output', 'json'], capture_output=True, text=True)
        helm_releases = json.loads(result.stdout)
        return helm_releases
    except:
        return {} 


def get_gpu_uuid(dic):
    # pandas Series의 NaN 체크를 위해 isna() 사용
    if 'GPU_MIG_UUID' not in dic or pd.isna(dic['GPU_MIG_UUID']):
        return dic['UUID']
    else:
        # NaN이 아닌 경우에만 문자열 변환 시도
        try:
            gpu_mig_uuid = str(dic['GPU_MIG_UUID'])
            if "MIG" not in gpu_mig_uuid:
                return dic['UUID']
            return gpu_mig_uuid
        except:
            return dic['UUID']


def get_gpu_name(dic):
    if 'GPU_I_PROFILE' not in dic or pd.isna(dic['GPU_I_PROFILE']):
        return dic['modelName']
    else:
        try:
            gpu_profile = str(dic['GPU_I_PROFILE'])
            return f"{dic['modelName']} MIG {gpu_profile}"
        except:
            return dic['modelName']


def make_nested_dict():
    return defaultdict(make_nested_dict)

def storage_lock(workspace_info):
    namespace=settings.JF_SYSTEM_NAMESPACE+f"-{workspace_info['id']}"
    # helm_list = get_helm_list(namespace)
    with prometheus_connection(url) as prom:
        tool_list=prom.custom_query(query=NAMESPACE_TOOL_LIST.format(namespace=namespace))
        

    # print(namespace, tool_list)
    if workspace_info['data_storage_lock'] == 3:
        if tool_list:
            tool_list=MetricSnapshotDataFrame(tool_list)
            for _,pod_info in tool_list.iterrows(): 
                if pod_info.label_pod_type=="filebrowser": #delete dataset filebrowser
                    delete_helm(name=pod_info.label_helm_name, namespace=settings.JF_SYSTEM_NAMESPACE)
                    dataset_db.update_dataset(id=pod_info.lable_dataset_id,filebrowser=0)
                elif pod_info.label_pod_type==TYPE.DEPLOYMENT_TYPE: # delete deployment worker
                    print("delete helm", file=sys.stderr)
                    delete_helm(name=pod_info.label_helm_name, namespace=namespace)
                    deployment_db.update_end_datetime_deployment_worker(deployment_worker_id=pod_info.label_deployment_worker_id)
                elif pod_info.label_pod_type==TYPE.PROJECT_TYPE:
                    delete_helm(name=pod_info.label_helm_name, namespace=namespace)
                    end_datetime = datetime.datetime.now().strftime(TYPE.TIME_DATE_FORMAT)
                    if pod_info.label_work_func_type==TYPE.TRAINING_ITEM_A: # delete training job
                        project_db.update_project_item_datetime(item_id=pod_info.label_project_item_id, item_type="training", end_datetime=end_datetime, end_status="stop", error_reason="data storage over")
                    elif pod_info.label_work_func_type==TYPE.TRAINING_ITEM_B: # delete project tools
                        project_db.update_project_tool_request_status(request_status=0, project_tool_id=pod_info.label_project_item_id)
                        project_db.update_project_tool_datetime(project_tool_id=pod_info.label_project_item_id, end_datetime=end_datetime)
                    elif pod_info.label_work_func_type==TYPE.TRAINING_ITEM_C:
                        project_db.update_project_item_datetime(item_id=pod_info.label_project_item_id, item_type="project_hps", end_datetime=end_datetime, end_status="stop", error_reason="data storage over")
                elif pod_info.label_pod_type==TYPE.PREPROCESSING_TYPE:
                    delete_helm(name=pod_info.label_helm_name, namespace=namespace)
                    if pod_info.label_work_func_type==TYPE.PREPROCESSING_ITEM_A:
                        pass
                    elif pod_info.label_work_func_type==TYPE.PREPROCESSING_ITEM_B:
                        pass
                elif pod_info.label_pod_type==TYPE.ANALYZER_TYPE:
                    delete_helm(name=pod_info.label_helm_name, namespace=namespace)
                    pass
                elif pod_info.label_pod_type==TYPE.COLLECT_TYPE:
                    delete_helm(name=pod_info.label_helm_name, namespace=namespace)
                    pass
                elif pod_info.label_pod_type==TYPE.PIPELINE_TYPE:
                    delete_helm(name=pod_info.label_helm_name, namespace=namespace)
                    # TODO
                    # history 기록 해야 함
                    pass
                elif pod_info.label_pod_type==TYPE.FINE_TUNING_TYPE:
                    delete_helm(name=pod_info.label_helm_name, namespace=namespace)
                    if pod_info.label_work_func_type==TYPE.FINE_TUNING_TYPE:
                        # TODO
                        # DB 업데이트, 체크포인트 이동
                        pass
                    else: # COMMIT POD
                        # TODO
                        # DB 업데이트
                        pass
                    pass


    if workspace_info['main_storage_lock'] == 3:
        if tool_list:
            tool_list=MetricSnapshotDataFrame(tool_list)
            for _,pod_info in tool_list.iterrows(): 
                if pod_info.label_pod_type=="filebrowser": #delete dataset filebrowser
                    delete_helm(name=pod_info.label_helm_name, namespace=settings.JF_SYSTEM_NAMESPACE)
                    dataset_db.update_dataset(id=pod_info.lable_dataset_id,filebrowser=0)
                elif pod_info.label_pod_type==TYPE.DEPLOYMENT_TYPE: # delete deployment worker
                    print("delete helm", file=sys.stderr)
                    delete_helm(name=pod_info.label_helm_name, namespace=namespace)
                    deployment_db.update_end_datetime_deployment_worker(deployment_worker_id=pod_info.label_deployment_worker_id)
                elif pod_info.label_pod_type==TYPE.PROJECT_TYPE:
                    delete_helm(name=pod_info.label_helm_name, namespace=namespace)
                    end_datetime = datetime.datetime.now().strftime(TYPE.TIME_DATE_FORMAT)
                    if pod_info.label_work_func_type==TYPE.TRAINING_ITEM_A: # delete training job
                        project_db.update_project_item_datetime(item_id=pod_info.label_project_item_id, item_type="training", end_datetime=end_datetime, end_status="stop", error_reason="data storage over")
                    elif pod_info.label_work_func_type==TYPE.TRAINING_ITEM_B: # delete project tools
                        project_db.update_project_tool_request_status(request_status=0, project_tool_id=pod_info.label_project_item_id)
                        project_db.update_project_tool_datetime(project_tool_id=pod_info.label_project_item_id, end_datetime=end_datetime)
                    elif pod_info.label_work_func_type==TYPE.TRAINING_ITEM_C:
                        project_db.update_project_item_datetime(item_id=pod_info.label_project_item_id, item_type="project_hps", end_datetime=end_datetime, end_status="stop", error_reason="data storage over")
                elif pod_info.label_pod_type==TYPE.PREPROCESSING_TYPE:
                    delete_helm(name=pod_info.label_helm_name, namespace=namespace)
                    if pod_info.label_work_func_type==TYPE.PREPROCESSING_ITEM_A:
                        pass
                    elif pod_info.label_work_func_type==TYPE.PREPROCESSING_ITEM_B:
                        pass
                elif pod_info.label_pod_type==TYPE.ANALYZER_TYPE:
                    delete_helm(name=pod_info.label_helm_name, namespace=namespace)
                    pass
                elif pod_info.label_pod_type==TYPE.COLLECT_TYPE:
                    delete_helm(name=pod_info.label_helm_name, namespace=namespace)
                    pass
                elif pod_info.label_pod_type==TYPE.PIPELINE_TYPE:
                    delete_helm(name=pod_info.label_helm_name, namespace=namespace)
                    # TODO
                    # history 기록 해야 함
                    pass
                elif pod_info.label_pod_type==TYPE.FINE_TUNING_TYPE:
                    delete_helm(name=pod_info.label_helm_name, namespace=namespace)
                    if pod_info.label_work_func_type==TYPE.FINE_TUNING_TYPE:
                        # TODO
                        # DB 업데이트, 체크포인트 이동
                        pass
                    else: # COMMIT POD
                        # TODO
                        # DB 업데이트
                        pass
                    pass


def set_filebrowser_pod_list():
    while(True):
        try:
            redis_client=get_redis_client()
            
            with prometheus_connection(url) as prom:
                filebrowser_list=prom.custom_query(query=DATASET_FILEBROWSER_POD_LIST)
                
                # Redis에서 현재 저장된 모든 filebrowser 상태 조회
                current_filebrowser_statuses = redis_client.hgetall(redis_key.DATASET_FILEBROWSER_POD_STATUS)
                
                # 실제 pod들을 처리
                if filebrowser_list:
                    filebrowser_list_df = MetricSnapshotDataFrame(filebrowser_list)
                    
                    for _,filebrowser in filebrowser_list_df.iterrows():
                        try:
                            pod_name = filebrowser['pod']
                            dataset_id = filebrowser['label_dataset_id']
                            
                            ready_check = prom.custom_query(DATASET_FILEBROWSER_STATUS_READY.format(POD_NAME=pod_name))
                            metric=prom.custom_query(POD_STATUS.format(POD_NAME=pod_name))
                            
                            phase = None
                            if ready_check and len(ready_check) > 0:
                                if ready_check[0]['value'][1] == '1':
                                    phase = TYPE.KUBE_POD_STATUS_RUNNING
                                else:
                                    if metric and len(metric) > 0:
                                        phase=metric[0]['metric']['phase']
                                        if phase =="Failed":
                                            phase = TYPE.KUBE_POD_STATUS_ERROR
                                        elif phase =="Pending":
                                            phase = TYPE.KUBE_POD_STATUS_PENDING
                                        elif phase =="Running":
                                            phase = TYPE.KUBE_POD_STATUS_PENDING
                                        else:
                                            phase = None
                            elif metric and len(metric) > 0:
                                phase=metric[0]['metric']['phase']
                                if phase =="Failed":
                                    phase = TYPE.KUBE_POD_STATUS_ERROR
                                elif phase =="Pending":
                                    phase = TYPE.KUBE_POD_STATUS_PENDING
                                elif phase =="Running":
                                    phase = TYPE.KUBE_POD_STATUS_RUNNING
                                else:
                                    phase = None

                            if phase is not None:
                                pod_info={
                                    'url' : f"/{filebrowser.label_ingress_path}",
                                    'pod_status' : phase
                                }
                                redis_client.hset(redis_key.DATASET_FILEBROWSER_POD_STATUS, dataset_id, json.dumps(pod_info))
                                print(f"Updated filebrowser status for dataset {dataset_id}: {phase}")
                                
                        except Exception as pod_error:
                            print(f"Error processing filebrowser pod {filebrowser.get('pod', 'unknown')}: {pod_error}")
                
                # Redis에는 있지만 실제 pod이 없는 경우 처리 (삭제된 pod들)
                processed_dataset_ids = set()
                if filebrowser_list:
                    filebrowser_list_df = MetricSnapshotDataFrame(filebrowser_list)
                    processed_dataset_ids = set(filebrowser_list_df['label_dataset_id'])
                
                for dataset_id_bytes, status_json in current_filebrowser_statuses.items():
                    dataset_id = dataset_id_bytes.decode('utf-8') if isinstance(dataset_id_bytes, bytes) else dataset_id_bytes
                    
                    # pod이 삭제되었지만 Redis에 상태가 남아있는 경우
                    if dataset_id not in processed_dataset_ids:
                        try:
                            status_data = json.loads(status_json)
                            current_status = status_data.get('pod_status', '')
                            
                            # DB를 확인해서 적절히 처리
                            dataset_info = dataset_db.get_dataset(dataset_id)
                            if dataset_info and dataset_info.get('filebrowser') == 0:
                                # DB=0이면 사용자가 끈 것이므로 Redis에서 삭제
                                redis_client.hdel(redis_key.DATASET_FILEBROWSER_POD_STATUS, dataset_id)
                                print(f"Dataset {dataset_id} pod deleted and DB=0 - removed from Redis")
                            elif current_status == "pending":
                                # pending 상태에서 pod이 사라진 경우, 새로운 pod 생성을 기다림 (error로 바꾸지 않음)
                                print(f"Dataset {dataset_id} pod disappeared but status is pending - waiting for new pod")
                            elif current_status != "error":
                                # 다른 상태에서 갑자기 pod이 사라진 경우만 error로 설정
                                status_data['pod_status'] = "error"
                                redis_client.hset(redis_key.DATASET_FILEBROWSER_POD_STATUS, dataset_id, json.dumps(status_data))
                                print(f"Dataset {dataset_id} pod disappeared unexpectedly - set status to error")
                        except:
                            # JSON 파싱 실패시 삭제
                            redis_client.hdel(redis_key.DATASET_FILEBROWSER_POD_STATUS, dataset_id)
                
        except Exception as e:
            print(f"Error in set_filebrowser_pod_list: {e}")
            traceback.print_exc()
        
        time.sleep(0.5)

def get_pod_resource_usage_in_workspace():
    while(True):
        try:
            result=dict()
            
            with prometheus_connection(url) as prom:
                pod_list = prom.custom_query(query=WORKSPACE_POD_INFO_JOIN_LABELS)
                pod_resource_limit_list = prom.custom_query(query=POD_RESOURCE_LIMIT_LIST)
                if pod_resource_limit_list and pod_list:
                    pod_resource_limit_df=MetricSnapshotDataFrame(pod_resource_limit_list)
                    pod_list_df = MetricSnapshotDataFrame(pod_list)
                    # node_list = node_db.get_node_list()
                    # for node_info in node_list:
                    #     result[node_info['name']]={
                    #         'pod_info':[],
                    #         'usage':{
                    #             'cpu':0,
                    #             'gpu':0,
                    #             'mem':0
                    #         }
                    #     }
                    for _, pod_info in pod_list_df.iterrows():
                        pod_metadata=dict()
                        if result.get(pod_info['label_workspace_id'], None) is None:
                            result[pod_info['label_workspace_id']]=[]
                        pod_metadata[pod_info['pod']]={
                                    'instance_id' : pod_info.get('label_instance_id',None),
                                    'type' : pod_info['label_pod_type'],
                                    'namespace' : pod_info['namespace'],
                                    'helm_name': pod_info['label_helm_name'],
                                    'node': pod_info['node'],
                                    'resource_usage': {}
                        }
                        pod_resource_info_df = pod_resource_limit_df[pod_resource_limit_df['pod']==pod_info['pod']]
                        for _, pod_resource_info in pod_resource_info_df.iterrows():
                            if pod_resource_info['resource'] =="cpu":
                                pod_metadata[pod_info['pod']]['resource_usage']['cpu']=pod_resource_info['value']
                            elif pod_resource_info['resource'] =="memory":
                                pod_metadata[pod_info['pod']]['resource_usage']['mem']=pod_resource_info['value']
                            elif pod_resource_info['resource'] =="nvidia_com_gpu":
                                pod_metadata[pod_info['pod']]['resource_usage']['gpu']=pod_resource_info['value']
                            else:
                                continue
                        result[pod_info['label_workspace_id']].append(pod_metadata)

                    redis_client=get_redis_client()
                    for workspace_id, usage_info in result.items():
                        redis_client.hset(redis_key.WORKSPACE_POD_RESOURCE_USAGE, workspace_id, json.dumps(usage_info))
                    # print(redis_client.hgetall(redis_key.WORKSPACE_POD_RESOURCE_USAGE))
                    # for ws_info in ws_db.get_workspace_list():
                    #     ws_pod_list_df = pod_list_df[pod_list_df['label_workspace_id']==ws_info['id']]

        except:
            traceback.print_exc()
            pass

def insert_mongodb_admin_dashboard_timeline():
    while(True):
        try:
            result={
                "gpu" : {
                    "used_gpu" : 0,
                    "total_gpu" : 0,
                },
                "cpu" : {
                    "used_cpu" : 0,
                    "total_cpu" : 0,
                },
                "ram" : {
                    "used_ram" : 0,
                    "total_ram" : 0,
                },
                "storage_main" : {
                    "used_storage_main" : 0,
                    "total_storage_main" : 0,
                },
                "storage_data" : {
                    "used_storage_data" : 0,
                    "total_storage_data" : 0,
                },
                "network": {
                    "inbound" : 0,
                    "outbound" : 0
                }
            }
            redis_client=get_redis_client()
            cpu_info_list = redis_client.hgetall(redis_key.CPU_INFO_RESOURCE)
            ram_info_list = redis_client.hgetall(redis_key.MEM_INFO_RESOURCE)
            gpu_info_list = redis_client.get(redis_key.GPU_INFO_RESOURCE)
            storage_info = redis_client.get(redis_key.STORAGE_LIST_RESOURCE)
            workspace_resource_usage_list = redis_client.hgetall(redis_key.WORKSPACE_RESOURCE_QUOTA)
            
            # workspace_resource_usage_list = redis_client.hgetall(redis_key.WORKSPACE_POD_RESOURCE_USAGE)

             # id
            # create_time = datetime.datetime.now()
            # workspace_list = ws_db.get_workspace_list()
            # # print(create_time)
            # with prometheus_connection(url) as prom:
            #     for workspace in workspace_list:
            #         result={}
            #         namespace = f'{settings.JF_SYSTEM_NAMESPACE}-{workspace["id"]}'
            #         network_outbound=prom.custom_query(query=WORKSPACE_NETWORK_OUTBOUND_USAGE.format(namespace=namespace))
            #         network_inbound=prom.custom_query(query=WORKSPACE_NETWORK_INBOUND_USAGE.format(namespace=namespace))

            for _, cpu_info in cpu_info_list.items():
                cpu_info=json.loads(cpu_info)
                result['cpu']['total_cpu'] += int(cpu_info['cpu_core'])
                # result['cpu']['used_cpu'] += float(cpu_info['cpu_usage'])
            for _, ram_info in ram_info_list.items():
                ram_info=json.loads(ram_info)
                result['ram']['total_ram'] += int(ram_info['mem_total'])
                # result['ram']['used_ram'] += int(ram_info['mem_used'])
            if gpu_info_list is not None:
                gpu_info_list=json.loads(gpu_info_list)
                for _, gpu_info in gpu_info_list.items():
                    result['gpu']['total_gpu'] +=len(gpu_info)
                    for _, gpu in gpu_info.items():
                        result['gpu']['used_gpu'] += gpu['used']
            if storage_info is not None:
                storage_info=json.loads(storage_info)
                for _, storage in storage_info.items() :
                    result['storage_main']['used_storage_main'] += storage['data_alloc']
                    result['storage_data']['used_storage_data'] += storage['main_alloc']
                    result['storage_main']['total_storage_main'] += storage['total']
                    result['storage_data']['total_storage_data'] += storage['total']
            # with prometheus_connection(url) as prom:
            for workspace_id, ws_usage_info in workspace_resource_usage_list.items():
                try:
                    ws_usage_info=json.loads(ws_usage_info)
                    if ws_usage_info and isinstance(ws_usage_info, dict):
                        # network 정보 안전하게 처리
                        if 'network' in ws_usage_info:
                            result['network']['inbound'] += ws_usage_info['network'].get('inbound', 0)
                            result['network']['outbound'] += ws_usage_info['network'].get('outbound', 0)
                        
                        # CPU 사용량 안전하게 처리
                        if 'cpu' in ws_usage_info and 'used' in ws_usage_info['cpu']:
                            cpu_used = ws_usage_info['cpu']['used']
                            if cpu_used is not None:
                                try:
                                    result['cpu']['used_cpu'] += float(cpu_used)
                                except (ValueError, TypeError):
                                    print(f"Warning: Invalid CPU usage value for workspace {workspace_id}: {cpu_used}")
                        
                        # RAM 사용량 안전하게 처리
                        if 'ram' in ws_usage_info and 'used' in ws_usage_info['ram']:
                            ram_used = ws_usage_info['ram']['used']
                            if ram_used is not None:
                                try:
                                    result['ram']['used_ram'] += int(ram_used)
                                except (ValueError, TypeError):
                                    print(f"Warning: Invalid RAM usage value for workspace {workspace_id}: {ram_used}")
                except json.JSONDecodeError:
                    print(f"Warning: Invalid JSON for workspace {workspace_id} usage info")
                except Exception as e:
                    print(f"Warning: Error processing workspace {workspace_id} usage info: {e}")
            create_time = datetime.datetime.now()
            result["create_datetime"] = create_time.strftime("%Y:%m:%d %H:%M:%S")
            result["pricing"]=[]
            #EFK
            print(f"[resource/jonathan_usage] {json.dumps(result)}", file=sys.stdout)
            sys.stdout.flush()
            # sys.stderr.flush()
            #TODO delete 
            # result["create_datetime"] = create_time
            # res,msg=insert_admin_dashboard_timeline(result)
            # print(result)
            # if res:
            #     print(res, msg)
            
            # del result['_id']
            
        except:
            traceback.print_exc()
            pass
        finally:
            time.sleep(60)
            
def workspace_basic_cost():
    #Network cost, workspace cost
    while(True):
        try:
            result={
                "network":{},
                "workspace":{}
            }
            workspace_list = ws_db.get_workspace_list()
            basic_cost_info = cost_db.get_basic_cost()
            basic_cost_info["out_bound_network"] = json.loads(basic_cost_info["out_bound_network"])
            # result["network"]["cost"].append(json.dumps(item) for item in json.loads(basic_cost_info['out_bound_network']))
            redis_client = get_redis_client()
            
            with prometheus_connection(url) as prom:
                network_outbound=prom.custom_query(query=WORKSPACE_NETWORK_OUTBOUND_USAGE)
                if network_outbound:
                    network_outbound_df=MetricSnapshotDataFrame(network_outbound)
                    last_network_usage_info = redis_client.hgetall(redis_key.WORKSPACE_NETWORK_USAGE)
                else:
                    network_outbound_df=None
                    last_network_usage_info= {}

            date_time = datetime.datetime.now()
            for workspace in workspace_list:
                # start_time = time.time()
                network_outbound_usage=0
                if network_outbound is not None :
                    network_outbound_dict={}
                    namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace['id'])
                    workspace_user_count = len(ws_db.get_workspace_users(workspace_id=workspace['id']))
                    last_usage = last_network_usage_info.get(workspace['id'], {})
                    workspace_network_outbound_pod_list = network_outbound_df[network_outbound_df['namespace']==namespace]
                    for _, info in workspace_network_outbound_pod_list.iterrows():
                        network_outbound_dict[info.pod]=int(info.value)
                    redis_client.hset(redis_key.WORKSPACE_NETWORK_USAGE, workspace['id'], json.dumps(network_outbound_dict))
                    network_outbound_usage_counter = Counter(network_outbound_dict)-Counter(last_usage)
                    network_outbound_usage = sum(value for _,value in  network_outbound_usage_counter.items())

                convert_cost_info=[]
                for item in basic_cost_info["out_bound_network"]:
                    temp={}
                    if item["start_unit"] =="KB":
                        temp['start']=item["start"]*1024
                    elif item["start_unit"] =="MB":
                        temp['start']=item["start"]*1024*1024
                    elif item["start_unit"] =="GB":
                        temp['start']=item["start"]*1024*1024*1024
                    
                    if item["end_unit"] =="KB":
                        temp['end']=item["end"]*1024
                    elif item["end_unit"] =="MB":
                        temp['end']=item["end"]*1024*1024
                    elif item["end_unit"] =="GB":
                        temp['end']=item["end"]*1024*1024*1024

                    temp['cost']=item['cost']
                    convert_cost_info.append(temp)

                result["workspace_id"] = workspace['id']
                result["datetime"] = date_time
                result["network"]["cost"] = convert_cost_info
                result["network"]["outbound"] = network_outbound_usage
                result["workspace"]["excess_user"] = workspace_user_count - basic_cost_info['members'] if workspace_user_count > basic_cost_info['members'] else 0
                result["workspace"]["excess_user_cost"] = basic_cost_info["add_member_cost"]
                result["workspace"]["time_unit"] = basic_cost_info["time_unit"]
                result["workspace"]["time_unit_cost"] = basic_cost_info["time_unit_cost"]
                print(f"[resource/workspace_cost] {json.dumps(result)}", file=sys.stdout)
                sys.stdout.flush()
                # end_time = time.time()
                # execution_time = end_time - start_time
                # print(f"{workspace['name']}실행 시간: {execution_time:.2f}초")
                time.sleep(1)

        except:
            traceback.print_exc()
            pass
            


#TODO 병렬 처리가 필요할 수 있음 1s안에 모든 workspace의 instanace 사용여부 및 요금을 위한 사용량 check가 필요한데
#     많은 instance를 사용하는 workspace의 경우 1초에 가깝게 소요됨
def workspace_instance_cost():
    while(True):
        try:
            result={
                "instance":{}
            }
            redis_client = get_redis_client()
            workspace_resource_usage_list = redis_client.hgetall(redis_key.WORKSPACE_POD_RESOURCE_USAGE)
            instance_cache = {str(instance["id"]): instance for instance in instance_db.get_all_instances()}
            date_time = datetime.datetime.now()
            for workspace in  ws_db.get_workspace_list():
                start_time = time.time()

                result["datetime"]=date_time
                result["workspace_id"]=workspace['id']

                instance_cost_info = cost_db.get_instance_cost_plan(id=4) # TODO workspace에 cost_plan을 넣었을때 대체해야함
                aggregated_usage ={}
                # aggregated_usage = defaultdict(lambda: {"usage" : {"cpu": 0.0, "mem": 0.0, "gpu": 0.0}, "cost":{}, "count":0})
                workspace_resource_usage=workspace_resource_usage_list.get(str(workspace['id']),None)

                if workspace_resource_usage is None:
                    print(f"[resource/workspace_instance_cost] {json.dumps(result)}", file=sys.stdout)
                    sys.stdout.flush()
                    continue

                for usage_info in json.loads(workspace_resource_usage):
                    value = next(iter(usage_info.values()))  # item.values()에서 첫 번째 값을 가져옴
                    instance_id = value["instance_id"]
                    resource_usage = value["resource_usage"]

                    if instance_id not in aggregated_usage:
                        aggregated_usage[instance_id] = {
                            "usage": {"cpu": 0.0, "mem": 0.0, "gpu": 0.0},
                            "cost": {
                                "time_unit": instance_cost_info["time_unit"],
                                "time_unit_cost": instance_cost_info["time_unit_cost"],
                                "type": instance_cost_info["type"],
                            },
                            "count": 0,
                        }

                    # 리소스 사용량 합산
                    aggregated_usage[instance_id]["usage"]["cpu"] += resource_usage.get("cpu", 0.0)
                    aggregated_usage[instance_id]["usage"]["mem"] += resource_usage.get("mem", 0.0)
                    aggregated_usage[instance_id]["usage"]["gpu"] += resource_usage.get("gpu", 0.0)

                    # if not aggregated_usage[instance_id]['cost']:
                    #     aggregated_usage[instance_id]['cost']['time_unit']=instance_cost_info['time_unit']
                    #     aggregated_usage[instance_id]['cost']['time_unit_cost']=instance_cost_info['time_unit_cost']
                    #     aggregated_usage[instance_id]['cost']['type']=instance_cost_info['type']

                    aggregated_usage[instance_id]['count']=math.ceil(aggregated_usage[instance_id]["usage"]["cpu"]/instance_cache[instance_id]['cpu_allocate'])

                result["instance"]=dict(aggregated_usage)
                print(f"[resource/workspace_instance_cost] {json.dumps(result)}", file=sys.stdout)
                sys.stdout.flush()

                end_time = time.time()
                execution_time = end_time - start_time
                print(f"{workspace['name']}실행 시간: {execution_time:.2f}초")
            time.sleep(1)
            
                # time.sleep(0.1)
                # if result["usage"].get(usage_info['instance_id'],None) is None:
                #    result["usage"][usage_info['instance_id']]={
                #        "cpu" : usage_info['resource_usage']['cpu'],
                #        "gpu" : usage_info['resource_usage']['gpu'],
                #        "mem" : usage_info['resource_usage']['mem']
                #    }
                # else:
                #     result["usage"][usage_info['instance_id']]["cpu"] += usage_info['resource_usage']['cpu']
                #     result["usage"][usage_info['instance_id']]["gpu"] += usage_info['resource_usage']['gpu']
                #     result["usage"][usage_info['instance_id']]["mem"] += usage_info['resource_usage']['mem']
        except:
            traceback.print_exc()
            pass

def workspace_storage_cost():
    while(True):
        try:
            result={}
            storage_cost_plan_id=1
            for workspace in ws_db.get_workspace_list():
                #TODO
                storage_cost_info = cost_db.get_storage_cost_plan(id=storage_cost_plan_id)
                if storage_cost_info:
                    result["workspace_id"] = workspace['id']
                    result["data_storage"] = {
                        "storage_id" : workspace['data_storage_id'],
                        "size" : workspace['data_storage_size'],
                        "cost" : storage_cost_info['cost'],
                        "source" : storage_cost_info['source']
                    }
                    result["main_storage"] = {
                        "storage_id" : workspace['main_storage_id'],
                        "size" : workspace['main_storage_size'],
                        "cost" : storage_cost_info['cost'],
                        "source" : storage_cost_info['source']
                    }
                    print(f"[resource/workspace_storage_cost] {json.dumps(result)}", file=sys.stdout)
                sys.stdout.flush()
        except:
            traceback.print_exc()
            pass


# def kafka_produce(producer, topic, message):
#     print(f"[kafka_produce] {message}", file=sys.stderr)
#     producer.produce(topic, message)
#     producer.flush()


def insert_mongodb_user_dashboard_timeline():
    producer = Producer(conf)

    while(True):
        try:
            
            workspace_list = ws_db.get_workspace_list()
            if workspace_list:
                redis_client=get_redis_client()
                storage_info = redis_client.get(redis_key.STORAGE_LIST_RESOURCE)
                if storage_info:
                    storage_info = json.loads(storage_info)
                    workspace_resource_usage_list = redis_client.hgetall(redis_key.WORKSPACE_RESOURCE_QUOTA) # id
                    create_time = datetime.datetime.now()
                    # print(create_time)
                    for workspace in workspace_list:
                        result={}
                        result["workspace_id"] = workspace["id"]
                        result["create_datetime"] = create_time.strftime("%Y:%m:%d %H:%M:%S")
                        main_storage_usage_list = storage_info[str(workspace["main_storage_id"])].get("workspaces", [])
                        for main_storage in main_storage_usage_list["main"]:
                            if main_storage["workspace_name"] == workspace["name"]:
                                result["storage_main"]={}
                                result["storage_main"]["total"]=main_storage["alloc_size"]
                                result["storage_main"]["used"]=main_storage["used_size"]
                        data_storage_usage_list = storage_info[str(workspace["data_storage_id"])].get("workspaces", [])
                        for data_storage in data_storage_usage_list["data"]:
                            if data_storage["workspace_name"] == workspace["name"]:
                                result["storage_data"]={}
                                result["storage_data"]["total"]=data_storage["alloc_size"]
                                result["storage_data"]["used"]=data_storage["used_size"]

                        resource_usage = json.loads(workspace_resource_usage_list.get(
                            str(workspace["id"]), 
                            json.dumps({"ram": {"hard":0, "used":0}, "cpu": {"hard":0, "used":0}, 
                                        "gpu": {"hard":0, "used":0},"network": {"inbound":0, "outbound":0}})
                        ))

                        
                        result["network"] = resource_usage["network"]
                        result["cpu"]=resource_usage["cpu"]
                        cpu_usage_percent = (result["cpu"]["used"] / result["cpu"]["hard"] ) * 100 if result["cpu"]["hard"] > 0 else 0
                        result["gpu"]=resource_usage["gpu"]
                        result["ram"]=resource_usage["ram"]
                        ram_usage_percent = (result["ram"]["used"] / result["ram"]["hard"]) * 100 if result["ram"]["hard"] > 0 else 0
                        if result.get("storage_main", None):
                            main_storage_percent = (result["storage_main"]["used"] / result["storage_main"]["total"]) * 100 if result["storage_main"]["total"] > 0 else 0
                        if result.get("storage_data", None):
                            data_storage_percent = (result["storage_data"]["used"] / result["storage_data"]["total"]) * 100 if result["storage_data"]["total"] > 0 else 0
                        
                        # basic_cost_info = cost_db.get_basic_cost()
                        # workspace_user_list = ws_db.get_workspace_users(workspace_id=workspace['id'])
                        # user_count = len(workspace_user_list)
                        # add_user_count = user_count-basic_cost_info['members'] if user_count > basic_cost_info['members'] else 0
                        #workspace_cost
                        #workspace_instance_cost
                        #workspace_storage_cost
                        #workspace_network_cost
                        manager_id = workspace["manager_id"]
                        result["pricing"]={}
                        if cpu_usage_percent > 80:
                            message=notification_key.WORKSPACE_INSTANCE_RESOURCE_CPU_OVER.format(workspace_name=workspace["name"])
                            if not get_resource_over_message(user_id=manager_id, workspace_id = workspace["id"], message=message):
                                
                                notification = NotificationWorkspace(
                                    user_id=manager_id,
                                    noti_type=notification_key.NOTIFICATION_TYPE_RESOURCE,
                                    user_type=notification_key.NOTIFICATION_USER_TYPE_WORKSPACE_MANAGER,
                                    message=message,
                                    workspace_id = workspace["id"],
                                    create_datetime=datetime.datetime.now()
                                )
                                KafkaProducer(conf).produce(topic=topic_key.ALERT_SYSTEM_TOPIC, value=notification.model_dump_json())
                                # kafka_produce(producer, topic_key.ALERT_SYSTEM_TOPIC, notification.model_dump_json())
                                # res, message = insert_notification_history(notification) 
                        if ram_usage_percent > 80:
                            message=notification_key.WORKSPACE_INSTANCE_RESOURCE_RAM_OVER.format(workspace_name=workspace["name"])
                            if not get_resource_over_message(user_id=manager_id, workspace_id = workspace["id"], message=message):
                                
                                notification = NotificationWorkspace(
                                    user_id=manager_id,
                                    noti_type=notification_key.NOTIFICATION_TYPE_RESOURCE,
                                    user_type=notification_key.NOTIFICATION_USER_TYPE_WORKSPACE_MANAGER,
                                    message=message,
                                    workspace_id = workspace["id"],
                                    create_datetime=datetime.datetime.now()
                                )
                                KafkaProducer(conf).produce(topic=topic_key.ALERT_SYSTEM_TOPIC, value=notification.model_dump_json())
                                # kafka_produce(producer, topic_key.ALERT_SYSTEM_TOPIC, notification.model_dump_json())
                                # res, message = insert_notification_history(notification)
                        if main_storage_percent < 80:
                            if workspace["main_storage_lock"] != 0:
                                ws_db.update_workspace_quota(workspace_id=workspace["id"], main_storage_lock=0)
                        elif main_storage_percent > 80 and main_storage_percent < 90:
                            message=notification_key.WORKSPACE_INSTANCE_RESOURCE_MAIN_STORAGE_OVER.format(workspace_name=workspace["name"])
                            
                            ws_db.update_workspace_quota(workspace_id=workspace["id"], main_storage_lock=1)
                            if not get_resource_over_message(user_id=manager_id, workspace_id = workspace["id"], message=message):
                                
                                notification = NotificationWorkspace(
                                    user_id=manager_id,
                                    noti_type=notification_key.NOTIFICATION_TYPE_RESOURCE,
                                    user_type=notification_key.NOTIFICATION_USER_TYPE_WORKSPACE_MANAGER,
                                    message=message,
                                    workspace_id = workspace["id"],
                                    create_datetime=datetime.datetime.now()
                                )
                                KafkaProducer(conf).produce(topic=topic_key.ALERT_SYSTEM_TOPIC, value=notification.model_dump_json())
                                # kafka_produce(producer, topic_key.ALERT_SYSTEM_TOPIC, notification.model_dump_json())
                                # res, message = insert_notification_history(notification) 
                        elif main_storage_percent > 90 and main_storage_percent < 100:
                            message=notification_key.WORKSPACE_INSTANCE_RESOURCE_MAIN_STORAGE_100_OVER.format(workspace_name=workspace["name"])
                            ws_db.update_workspace_quota(workspace_id=workspace["id"], main_storage_lock=2)
                            if not get_resource_over_message(user_id=manager_id, workspace_id = workspace["id"], message=message):
                                
                                notification = NotificationWorkspace(
                                    user_id=manager_id,
                                    noti_type=notification_key.NOTIFICATION_TYPE_RESOURCE,
                                    user_type=notification_key.NOTIFICATION_USER_TYPE_WORKSPACE_MANAGER,
                                    message=message,
                                    workspace_id = workspace["id"],
                                    create_datetime=datetime.datetime.now()
                                )
                                KafkaProducer(conf).produce(topic=topic_key.ALERT_SYSTEM_TOPIC, value=notification.model_dump_json())
                                # kafka_produce(producer, topic_key.ALERT_SYSTEM_TOPIC, notification.model_dump_json())
                                # res, message = insert_notification_history(notification) 
                        elif main_storage_percent >= 100:
                            ws_db.update_workspace_quota(workspace_id=workspace["id"], main_storage_lock=3)
                            storage_lock(workspace)

                        if data_storage_percent < 80:
                            if workspace["data_storage_lock"] != 0:
                                ws_db.update_workspace_quota(workspace_id=workspace["id"], data_storage_lock=0)
                        elif data_storage_percent > 80 and data_storage_percent < 90:
                            message=notification_key.WORKSPACE_INSTANCE_RESOURCE_DATA_STORAGE_OVER.format(workspace_name=workspace["name"])
                            ws_db.update_workspace_quota(workspace_id=workspace["id"], data_storage_lock=1)
                            if not get_resource_over_message(user_id=manager_id, workspace_id = workspace["id"], message=message):
                                
                                notification = NotificationWorkspace(
                                    user_id=manager_id,
                                    noti_type=notification_key.NOTIFICATION_TYPE_RESOURCE,
                                    user_type=notification_key.NOTIFICATION_USER_TYPE_WORKSPACE_MANAGER,
                                    message=message,
                                    workspace_id = workspace["id"],
                                    create_datetime=datetime.datetime.now()
                                )
                                KafkaProducer(conf).produce(topic=topic_key.ALERT_SYSTEM_TOPIC, value=notification.model_dump_json())
                                # kafka_produce(producer, topic_key.ALERT_SYSTEM_TOPIC, notification.model_dump_json())
                                # res, message = insert_notification_history(notification) 
                        elif data_storage_percent > 90 and data_storage_percent < 100:
                            message=notification_key.WORKSPACE_INSTANCE_RESOURCE_DATA_STORAGE_100_OVER.format(workspace_name=workspace["name"])
                            ws_db.update_workspace_quota(workspace_id=workspace["id"], data_storage_lock=2)
                            if not get_resource_over_message(user_id=manager_id, workspace_id = workspace["id"], message=message):
                                
                                notification = NotificationWorkspace(
                                    user_id=manager_id,
                                    noti_type=notification_key.NOTIFICATION_TYPE_RESOURCE,
                                    user_type=notification_key.NOTIFICATION_USER_TYPE_WORKSPACE_MANAGER,
                                    message=message,
                                    workspace_id = workspace["id"],
                                    create_datetime=datetime.datetime.now()
                                )
                                KafkaProducer(conf).produce(topic=topic_key.ALERT_SYSTEM_TOPIC, value=notification.model_dump_json())
                                # kafka_produce(producer, topic_key.ALERT_SYSTEM_TOPIC, notification.model_dump_json())
                                # res, message = insert_notification_history(notification) 
                        elif data_storage_percent >= 100:
                            ws_db.update_workspace_quota(workspace_id=workspace["id"], data_storage_lock=3)
                            storage_lock(workspace)
                        # storage_usage = storage_usage_list.get(workspace['name'] , {'main':0, 'data':0})
                        print(f"[resource/workspace_usage] {json.dumps(result)}", file=sys.stdout)
                        # sys.stderr.flush()
                        # result["create_datetime"] = create_time
                        # res,message = insert_user_dashboard_timeline(result)
                        sys.stdout.flush()
                        
            time.sleep(1)
        except:
            traceback.print_exc()


def set_project_storage_usage_info():
    while(True):
        try:
            project_list = project_db.get_project_list()
            if not project_list :
                continue
            redis_client=get_redis_client()   
            with prometheus_connection(url) as prom:
                project_usage_info = prom.custom_query(query=PROJECT_USAGE_INFO)
                if not project_usage_info:
                    continue
                else:
                    project_list_df=MetricSnapshotDataFrame(prom.custom_query(query=PROJECT_USAGE_INFO))
                    for project in project_list:
                        project_df = project_list_df[project_list_df['name']==project['name']]
                        for _, usage in project_df.iterrows():
                            redis_client.hset(redis_key.PROJECT_STORAGE_USAGE, project['id'], int(usage['value']))
            # print("project", redis_client.hgetall(redis_key.PROJECT_STORAGE_USAGE))
        except:
            traceback.print_exc()
            pass

def set_model_storage_usage_info():
    while(True):
        try:
            model_list = model_db.get_all_models_sync()
            if not model_list :
                continue
            redis_client=get_redis_client()
            with prometheus_connection(url) as prom:
                model_usage_info = prom.custom_query(query=MODEL_USAGE_INFO)
                if not model_usage_info :
                    continue
                else:
                    model_list_df=MetricSnapshotDataFrame(model_usage_info)
                    for model in model_list:
                        model_df = model_list_df[model_list_df['name']==model['name']]
                        for _, usage in model_df.iterrows():
                            if usage['workspace'] == model['workspace_name']:
                                redis_client.hset(redis_key.MODEL_STORAGE_USAGE, model['id'], int(usage['value']))
            # print("dataset", redis_client.hgetall(redis_key.DATASET_STORAGE_USAGE))
        except:
            traceback.print_exc()
            pass

def set_rag_storage_usage_info():
    while(True):
        try:
            rag_list = rag_db.get_rag_list_sync()
            if not rag_list :
                continue
            redis_client=get_redis_client()
            with prometheus_connection(url) as prom:
                rag_usage_info = prom.custom_query(query=RAG_USAGE_INFO)
                if not rag_usage_info :
                    continue
                else:
                    rag_list_df=MetricSnapshotDataFrame(rag_usage_info)
                    for rag in rag_list:
                        rag_df = rag_list_df[rag_list_df['name']==rag['name']]
                        for _, usage in rag_df.iterrows():
                            if usage['name'] == rag['name']:
                                redis_client.hset(redis_key.RAG_STORAGE_USAGE, rag['id'], int(usage['value']))
            # print("dataset", redis_client.hgetall(redis_key.DATASET_STORAGE_USAGE))
        except:
            traceback.print_exc()
            pass



def set_dataset_storage_usage_info():
    while(True):
        try:
            dataset_list = dataset_db.get_dataset_list()
            if not dataset_list :
                continue
            redis_client=get_redis_client()
            with prometheus_connection(url) as prom:
                dataset_usage_info = prom.custom_query(query=DATASET_USAGE_INFO)
                if not dataset_usage_info :
                    continue
                else:
                    dataset_list_df=MetricSnapshotDataFrame(dataset_usage_info)
                    for dataset in dataset_list:
                        dataset_df = dataset_list_df[dataset_list_df['name']==dataset['dataset_name']]
                        for _, usage in dataset_df.iterrows():
                            if usage['workspace'] == dataset['workspace_name']:
                                redis_client.hset(redis_key.DATASET_STORAGE_USAGE, dataset['id'], int(usage['value']))
            # print("dataset", redis_client.hgetall(redis_key.DATASET_STORAGE_USAGE))
        except:
            traceback.print_exc()
            pass

def get_storage_usage_info():
    while(True):
        try:
            storage_info = storage_db.get_storage()
            storage_list = {}
            if storage_info is None:
                continue
            for storage in storage_info:
                storage_list[storage['id']]=storage['name']
            workspace_list = ws_db.get_workspace_list()
            for workspace in workspace_list :
                main_storage_path = PATH.JF_MAIN_STORAGE_PATH.format(STORAGE_NAME=storage_list[workspace['main_storage_id']] , WORKSPACE_NAME=workspace['name'])
                data_storage_path = PATH.JF_DATA_STORAGE_PATH.format(STORAGE_NAME=storage_list[workspace['data_storage_id']] , WORKSPACE_NAME=workspace['name'])
                workspace_path = [main_storage_path, data_storage_path]
                storage_usage={}
                redis_client=get_redis_client()
                with prometheus_connection(url) as prom:
                    workspace_usage_info = prom.custom_query(query=WORKSAPCE_USAGE_INFO)
                    if workspace_usage_info :
                        ws_usage_list_df=MetricSnapshotDataFrame(workspace_usage_info)
                        ws_usage_df = ws_usage_list_df[ws_usage_list_df['name']==workspace['name']]
                        for _, ws_usage in ws_usage_df.iterrows():
                            storage_usage[ws_usage['type']]=int(ws_usage['value'])
                        redis_client.hset(redis_key.WORKSPACE_STORAGE_USAGE, workspace['name'], json.dumps(storage_usage))
        except:
            traceback.print_exc()
            pass

# def set_storage_info_to_redis():
#     while(True):
#         try:
#             time.sleep(1)
#             result={}
#             with prometheus_connection(url) as prom:
#                 node_list=prom.custom_query(query=REDIS_NODE_INFO)
#         except:
#             traceback.print_exc()
#             pass

def set_node_info_to_redis():
    while(True):
        try:
            time.sleep(1)
            redis_client = get_redis_client()
            with prometheus_connection(url) as prom:
                node_list=prom.custom_query(query=REDIS_NODE_INFO)
                if node_list:
                    node_status_df = MetricSnapshotDataFrame(prom.custom_query(query=REDIS_NODE_STATUS))
                    for node_info in node_list:
                        result={}
                        node_name = node_info['metric']['node']
                        node_status = node_status_df[node_status_df['node']==node_name]
                        for _, info in node_status.iterrows():
                            if int(info['value']) == 0:
                                status="Ready"
                            else:
                                status="Not Ready"
                        result={
                            'ip' : node_info['metric']['internal_ip'],
                            'kube_version' : node_info['metric']['kubelet_version'],
                            'container_runtime_version' : node_info['metric']['container_runtime_version'],
                            'os_version' : node_info['metric']['os_image'],
                            'status' : status
                        }
                        redis_client.hset(redis_key.NODE_INFO, node_name, json.dumps(result))
                # print(redis.hgetall(redis_key.NODE_INFO))
                # redis.delete(redis_key.NODE_INFO)
                # redis.set(redis_key.NODE_INFO,json.dumps(result))
        except:
            traceback.print_exc()
            pass


def init_node_info():
    try:
        with prometheus_connection(url) as prom:
            node_list=prom.custom_query(query=REDIS_NODE_INFO)
            if node_list :
                node_role_list_df=MetricSnapshotDataFrame(prom.custom_query(query=NODE_ROLE_INFO))
                node_gpu_info_df=MetricSnapshotDataFrame(prom.custom_query(query=REDIS_GPU_INFO))
                node_cpu_info_df=MetricSnapshotDataFrame(prom.custom_query(query=REDIS_CPU_INFO))
                for node in node_list:
                    if not node_db.get_node(node_name=node['metric']['node']):
                        node_role = node_role_list_df[node_role_list_df['node'] == node['metric']['node']]
                        # if node_role.empty:
                        #     role = "worker"
                        # else:
                        roles=[]
                        for _,node_role in node_role.iterrows():
                            roles.append(node_role.role)
                        # role= node_role.iloc[0]['role']

                        node_ip = node['metric']['internal_ip']
                        node_name = node['metric']['node']

                        node_id = node_db.insert_node(name=node_name,
                                                ip=node_ip,
                                                role=str(roles),
                                                status="Ready")
                        time.sleep(5)
                        gpu_info = node_gpu_info_df[node_gpu_info_df['Hostname'] == node_name]
                        if gpu_info is not None:
                            # Get CUDA cores
                            res,_ = create_node_init_job(node_id=node_id, node=node_name)
                            if not res :
                                print("{} get CUDA cores fail".format(node_name))

                        if not node_db.get_node_cpu(node_id=node_id) :
                            cpu_info = node_cpu_info_df[node_cpu_info_df['instance'] == node_ip+":"+settings.JF_NODE_EXPORTER_PORT]
                            for _, cpu in cpu_info.iterrows():
                                cpu_resource_group=node_db.get_resource_group(name=cpu['model_name'])
                                if cpu_resource_group is None:
                                    cpu_resource_group_id = node_db.insert_resource_group(name=cpu['model_name'])
                                else:
                                    cpu_resource_group_id = cpu_resource_group['id']
                                node_db.insert_node_cpu(node_id=node_id, resource_group_id=cpu_resource_group_id, core=int(cpu['value']))
                        print(gpu_info, file=sys.stderr)
                        for _, gpu in gpu_info.iterrows():
                            print(gpu, file=sys.stderr)
                            print("================================================",file=sys.stderr)
                            uuid = get_gpu_uuid(gpu)
                            print("================================================",file=sys.stderr)
                            print(uuid, file=sys.stderr)
                            print("================================================",file=sys.stderr)
                            model_name = get_gpu_name(gpu)
                            try:
                                if not node_db.get_node_gpu(gpu_uuid=uuid):       
                                    gpu_resource_group=node_db.get_resource_group(name=model_name)
                                    if gpu_resource_group is None:
                                        gpu_resource_group_id = node_db.insert_resource_group(name=model_name)
                                    else:
                                        gpu_resource_group_id = gpu_resource_group['id']
                                    
                                    # GPU 메모리 값이 nan인 경우 0으로 대체
                                    gpu_memory = gpu['value']
                                    if math.isnan(gpu_memory):
                                        gpu_memory = 0
                                        
                                    node_db.insert_node_gpu(node_id=node_id, resource_group_id=gpu_resource_group_id, gpu_memory=gpu_memory, gpu_uuid=uuid)
                            except:
                                traceback.print_exc()
        #                 if node_db.get_node_ram(node_id=node_id) is None:
        #                     node_ram_info_df=MetricSnapshotDataFrame(prom.custom_query(query=REDIS_MEM_TOTAL)) #instance ex) ip:settings.JF_NODE_EXPORTER_PORT
        #                     node_ram_info =node_ram_info_df[node_ram_info_df['instance'] == node['ip']+":"+settings.JF_NODE_EXPORTER_PORT]
        #                     for _, ram in node_ram_info.iterrows():
        #                         node_db.insert_node_ram(node_id=node['id'], size=ram['value'])
    except:
        traceback.print_exc()

def init_node_resource_info():
    try:
        node_list=node_db.get_node_list()
        if node_list is not None:
            with prometheus_connection(url) as prom:
                 
                node_gpu_info_df=MetricSnapshotDataFrame(prom.custom_query(query=REDIS_GPU_INFO)) # Hostname
                for node in node_list:
                    if node_db.get_node_cpu(node_id=node['id']) is None:
                        node_cpu_info_df=MetricSnapshotDataFrame(prom.custom_query(query=REDIS_CPU_INFO)) #instance ex) ip:settings.JF_NODE_EXPORTER_PORT
                        cpu_info = node_cpu_info_df[node_cpu_info_df['instance'] == node['ip']+":"+settings.JF_NODE_EXPORTER_PORT]
                        for _, cpu in cpu_info.iterrows():
                            cpu_resource_group=node_db.get_resource_group(name=cpu['model_name'])
                            if cpu_resource_group is None:
                                cpu_resource_group_id = node_db.insert_resource_group(name=cpu['model_name'])
                            else:
                                cpu_resource_group_id = cpu_resource_group['id']
                            
                            node_db.insert_node_cpu(node_id=node['id'], resource_group_id=cpu_resource_group_id, core=int(cpu['value']))
                    
                    gpu_info = node_gpu_info_df[node_gpu_info_df['Hostname'] == node['name']]
                    for _, gpu in gpu_info.iterrows():
                        uuid = get_gpu_uuid(gpu)
                        model_name = get_gpu_name(gpu)
                        if node_db.get_node_gpu(gpu_uuid=uuid) is None:
                            gpu_resource_group=node_db.get_resource_group(name=model_name)
                            if gpu_resource_group is None:
                                gpu_resource_group_id = node_db.insert_resource_group(name=model_name)
                            else:
                                gpu_resource_group_id = gpu_resource_group['id']
                            # print(gpu_resource_group_id)
                            node_db.insert_node_gpu(node_id=node['id'], resource_group_id=gpu_resource_group_id,gpu_memory=gpu['value'], gpu_uuid=uuid)
                    
                    if node_db.get_node_ram(node_id=node['id']) is None:
                        node_ram_info_df=MetricSnapshotDataFrame(prom.custom_query(query=REDIS_MEM_TOTAL)) #instance ex) ip:settings.JF_NODE_EXPORTER_PORT
                        node_ram_info =node_ram_info_df[node_ram_info_df['instance'] == node['ip']+":"+settings.JF_NODE_EXPORTER_PORT]
                        for _, ram in node_ram_info.iterrows():
                            node_db.insert_node_ram(node_id=node['id'], size=ram['value'])
                        # print(gpu.get('modelName'))
                    # if node_role.empty:
                    #     role = "worker"
                    # else:
                    #     role= node_role.iloc[0]['role']

                    # node_db.insert_node(name=node['node'],
                    #                         ip=node['internal_ip'],
                    #                         role=role,
                    #                         status="Ready")

        # =========================================================
        # node cpu, gpu, ram table 초기화 후 instance 초기화 -> 웹에서 초기화 세팅
        # try:
        #     print("Request Instance Init", file=sys.stderr)
        #     JFB_RESOURCE_APP_DNS=f"http://jfb-app-resource-svc"
        #     requests.post(JFB_RESOURCE_APP_DNS + "/api/nodes/instance")
        # except:
        #     print("Request Fail Instance Init")
        #     pass
    except:
        traceback.print_exc()

def set_gpu_info_to_redis():
    try:
        result={}
        with prometheus_connection(url) as prom:
            gpu_list = prom.custom_query(query=REDIS_GPU_INFO)
            for gpu_info in gpu_list:
                hostname=gpu_info['metric']['Hostname']
                try:
                    gpu_uuid=get_gpu_uuid(gpu_info['metric'])
                except:
                    continue
                model_name=get_gpu_name(gpu_info['metric'])
                gpu_driver_version=gpu_info['metric']['DCGM_FI_DRIVER_VERSION']
                gpu_mem=int(gpu_info['value'][1])

                if hostname not in result:
                    result[hostname] = {}
                # if model_name not in result[hostname]:
                #     result[hostname][model_name] = []

                # result[hostname][model_name].append(
                #     {
                #         gpu_uuid : {
                #         "gpu_mem" : gpu_mem,
                #             "used" : 1 if  int(prom.custom_query(query=GPU_MEMORY_USAGE)[0]['value'][1]) > 0 else 0
                #         }
                #     }
                # )
                result[hostname][gpu_uuid]={
                    "model_name": model_name,
                    "gpu_mem" : gpu_mem,
                    "used" : 1 if  int(prom.custom_query(query=GPU_MEMORY_USAGE)[0]['value'][1]) > 0 else 0,
                    "gpu_driver" : gpu_driver_version,
                    "used_type" : None,
                    "used_info": {},
                    "mig" : gpu_info['metric'].get('GPU_I_PROFILE',False)
                }
        # print(result)
        redis_client=get_redis_client()
        redis_client.set(redis_key.GPU_INFO_RESOURCE, json.dumps(result))
        # print(redis.get(redis_key.GPU_INFO_RESOURCE))
        return 1234
    except:
        traceback.print_exc()
        pass

def set_cpu_info_to_redis():
    while(True):
        try:
            time.sleep(1)
            result={}
            redis_client = get_redis_client()
            with prometheus_connection(url) as prom:
                node_list = prom.custom_query(query=NODE_LIST)
                if node_list:
                    cpu_info_df = MetricSnapshotDataFrame(prom.custom_query(query=REDIS_CPU_INFO))
                    cpu_usage_df = MetricSnapshotDataFrame(prom.custom_query(query=REDIS_CPU_UAGE))
                    for node_info in node_list:
                        hostname=node_info['metric']['node']
                        node_exporter_instance=node_info['metric']['internal_ip']+":"+settings.JF_NODE_EXPORTER_PORT
                        cpu_info=cpu_info_df[cpu_info_df['instance']==node_exporter_instance]
                        if cpu_info.empty:
                            continue
                        model_name = cpu_info.iloc[0]['model_name']
                        cpu_core = cpu_info.iloc[0]['value']
                
                        cpu_usage_info = cpu_usage_df[cpu_usage_df['instance']==node_exporter_instance]
                        if cpu_usage_info.empty:
                            continue
                        cpu_usage = cpu_usage_info.iloc[0]['value']

                        cpu={
                            'cpu_model' : model_name,
                            'cpu_core' : int(cpu_core*settings.JF_COMPUTING_NODE_CPU_PERCENT),
                            'cpu_usage' : cpu_usage
                        }
                        # redis.delete(redis_key.CPU_INFO_RESOURCE)
                        redis_client.hset(redis_key.CPU_INFO_RESOURCE, hostname, json.dumps(cpu))
            # print(redis_client.hgetall(redis_key.CPU_INFO_RESOURCE))
                
        except:
            traceback.print_exc()
            pass

def set_mem_info_to_redis():
    while(True):
        try:
            time.sleep(1)
            result={}
            redis_client=get_redis_client()
            with prometheus_connection(url) as prom:
                node_list = prom.custom_query(query=NODE_LIST)
                if node_list:
                    mem_total_df = MetricSnapshotDataFrame(prom.custom_query(query=REDIS_MEM_TOTAL))
                    mem_avail_df = MetricSnapshotDataFrame(prom.custom_query(query=REDIS_MEM_AVAIL))
                    for node_info in node_list:
                        hostname=node_info['metric']['node']
                        node_exporter_instance=node_info['metric']['internal_ip']+":"+settings.JF_NODE_EXPORTER_PORT
                        mem_total = mem_total_df[mem_total_df['instance']==node_exporter_instance]
                        mem_avail = mem_avail_df[mem_avail_df['instance']==node_exporter_instance]
                        if mem_total.empty or mem_avail.empty:
                            continue
                        mem_total_byte=int(mem_total.iloc[0]['value'])
                        mem_avail_byte=int(mem_avail.iloc[0]['value'])
                        mem_used_byte=mem_total_byte-mem_avail_byte
                        mem_total_byte=mem_total_byte*settings.JF_COMPUTING_NODE_RAM_PERCENT
                        mem_info={
                            'mem_total' : mem_total_byte,
                            'mem_avail' : mem_total_byte-mem_used_byte,
                            'mem_used' : mem_used_byte
                        }
                        redis_client.hset(redis_key.MEM_INFO_RESOURCE, hostname, json.dumps(mem_info))
            # print(redis_client.hgetall(redis_key.MEM_INFO_RESOURCE))
        except:
            traceback.print_exc()
            pass

# workspace pod status
def set_workspace_pod_status():
    from utils.msa_db import db_project, db_workspace
    from utils.TYPE import PROJECT_HELM_CHART_NAME, PREPROCESSING_HELM_CHART_NAME
    
    def gpu_reset():
        result={}
        with prometheus_connection(url) as prom:
            gpu_list = prom.custom_query(query=REDIS_GPU_INFO)
            for gpu_info in gpu_list:
                hostname=gpu_info['metric']['Hostname']
                gpu_uuid=get_gpu_uuid(gpu_info['metric'])
                model_name=get_gpu_name(gpu_info['metric'])
                gpu_driver_version=gpu_info['metric']['DCGM_FI_DRIVER_VERSION']
                gpu_mem=int(gpu_info['value'][1])

                if hostname not in result:
                    result[hostname] = {}
                result[hostname][gpu_uuid]={
                    "model_name": model_name,
                    "gpu_mem" : gpu_mem,
                    "used" : 0,
                    "gpu_driver" : gpu_driver_version,
                    "used_type" : None,
                    "used_info": {}
                }
        return result
    
    def delete_helm_resource(helm_name : str, workspace_id : int):
        try:
            # os.chdir("/app/helm_chart/")
            namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
            command=f"helm uninstall {helm_name} -n {namespace}"
            
            # print(command)
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return 1, result.stdout
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.strip()
            if "cannot re-use a name that is still in use" in err_msg:
                return True, ""
            # print(e.stdout)
            # print(err_msg)
            # print(command)
            return False ,err_msg
    
    
    def clear_gpu_usage(gpu_uuid):
        """Clear the GPU usage information."""
        gpu_uuid["used"] = 0
        gpu_uuid["used_type"] = None
        gpu_uuid["used_info"] = {}
    
    def update_resources_from_query(data):
        
        resources = {"cpu": 0, "gpu": 0, "ram": 0}
        for item in data:
            metric = item.get("metric", {})
            resource_type = metric.get("resource")
            value = item.get("value", [])[1]

            if resource_type == "cpu":
                resources["cpu"] = float(value)  # CPU 코어 수
            # elif resource_type == "nvidia_com_gpu":
            #     resources["gpu"] = int(value)  # GPU 개수
            elif resource_type == "memory":
                resources["ram"] = int(value) / (1000 ** 3)  # RAM 기가바이트(GB)로 변환

        return resources
    
    def insert_gpu_usage(pod_info, gpu_uuids, gpu_status):
        item_type = pod_info["label_pod_type"] # if pod_info["label_pod_type"] in [TYPE.DEPLOYMENT_TYPE, TYPE.FINE_TUNING_TYPE] else TYPE.PROJECT_TYPE
        if item_type == TYPE.PROJECT_TYPE:
            project_id = pod_info["label_project_id"]
            project_item_id = pod_info["label_project_item_id"]
            project_item_type = pod_info["label_work_func_type"]
            for gpu_uuid in gpu_uuids:
                gpu_status[node_name][gpu_uuid]["used"] = 1
                gpu_status[node_name][gpu_uuid]["used_type"] = item_type
                gpu_status[node_name][gpu_uuid]["used_info"] = {
                    "used_workspace" : workspace_id,
                    "used_project" : project_id,
                    "used_instance" : instance_id,
                    "used_project_item": project_item_id,
                    "used_project_item_type" : project_item_type
                }
        elif item_type == TYPE.FINE_TUNING_TYPE:
            model_id = pod_info["label_model_id"]
            for gpu_uuid in gpu_uuids:
                gpu_status[node_name][gpu_uuid]["used"] = 1
                gpu_status[node_name][gpu_uuid]["used_type"] = item_type
                gpu_status[node_name][gpu_uuid]["used_info"] = {
                    "used_workspace" : workspace_id,
                    "used_model" : model_id,
                    "used_instance" : instance_id
                }
        elif item_type == TYPE.PREPROCESSING_TYPE:
            preprocessing_id = pod_info["label_preprocessing_id"]
            preprocessing_item_id = pod_info["label_preprocessing_item_id"]
            preprocessing_item_type = pod_info["label_work_func_type"]
            for gpu_uuid in gpu_uuids:
                gpu_status[node_name][gpu_uuid]["used"] = 1
                gpu_status[node_name][gpu_uuid]["used_type"] = item_type
                gpu_status[node_name][gpu_uuid]["used_info"] = {
                    "used_workspace" : workspace_id,
                    "used_preprocessing" : preprocessing_id,
                    "used_instance" : instance_id,
                    "used_preprocessing_item": preprocessing_item_id,
                    "used_preprocessing_item_type" : preprocessing_item_type
                }
        elif item_type == TYPE.DEPLOYMENT_TYPE:
            deployment_id = pod_info["label_deployment_id"]
            deployment_worker_id = pod_info["label_deployment_worker_id"]
            for gpu_uuid in gpu_uuids:
                gpu_status[node_name][gpu_uuid]["used"] = 1
                gpu_status[node_name][gpu_uuid]["used_type"] = item_type
                gpu_status[node_name][gpu_uuid]["used_info"] = {
                    "used_workspace" : workspace_id,
                    "used_deployment" : deployment_id,
                    "used_instance" : instance_id,
                    "used_deployment_worker": deployment_worker_id
                }

    def update_pod_gpu_usage_from_labels(pod_labels: dict) -> int:
        """
        pod의 label 정보에서 GPU 사용량을 추출함
        - device_type == "GPU"일 경우에만 의미 있음
        - device_count가 명시되어 있으면 그것을 사용
        - 없으면 device_ids를 split하여 count 추정
        """
        if pod_labels.get("label_device_type") != "GPU":
            return 0

        if "label_device_count" in pod_labels:
            try:
                return int(pod_labels["label_device_count"])
            except ValueError:
                pass

        # fallback: device_ids로 계산
        device_ids = pod_labels.get("label_device_ids")
        if device_ids:
            return len([i for i in device_ids.split(".") if i.strip()])

        return 0

    
    while(True):
        try:
            time.sleep(0.1)
            workspace_list = db_workspace.get_workspace_list()
            redis_client = get_redis_client()
            # prometheus pod search
            with prometheus_connection(url) as prom:
                gpu_status = gpu_reset()
                # redis_con.set(redis_key.GPU_INFO_RESOURCE, json.dumps(gpu_status))
                for workspace in workspace_list:
            
                    workspace_pod_list = prom.custom_query(query=REDIS_WORKSPACE_POD_LIST.format(workspace_id=workspace["id"]))
                    # tool_status = redis_con.hget(redis_key.TOOL_PODS_STATUS_WORKSPACE.format(workspace_id=workspace["id"]), "tools")
                    # gpu_status = json.loads(redis_con.get(redis_key.GPU_INFO_RESOURCE))
                    
                    
                    workspace_pods = make_nested_dict()
                    for pod_info in workspace_pod_list:
                        # TODO
                        # DB sync 로직 추가 

                        pod_info=pod_info['metric']
                        workspace_id = pod_info["label_workspace_id"]
                        instance_id = pod_info.get("label_instance_id",None)
                        # workspace_instances[instance_id] += 1
                        node_name = pod_info.get("label_node_name", None)
                        gpu_ids = pod_info["label_device_ids"].split(".") if pod_info.get("label_device_ids", None) else []
                        gpu_uuids = []
                        for gpu_id in gpu_ids:
                            if gpu_id:
                                # print(gpu_id, file=sys.stderr)
                                gpu_uuid = node_db.get_node_gpu(gpu_id=gpu_id)["gpu_uuid"]
                                gpu_uuids.append(gpu_uuid)
                        
                        pod_status = prom.custom_query(query=POD_STATUS.format(POD_NAME=pod_info['pod']))

                        tmp_pod_status_reason = prom.custom_query(query=POD_STATUS_REASON.format(POD_NAME=pod_info['pod']))
                        pod_status_reason = tmp_pod_status_reason[0]['metric']["reason"] if tmp_pod_status_reason and tmp_pod_status_reason[0] is not None else None
                        
                        # print(pod_status)
                        # POD_RESOURCE_LIMIT
                        tmp_resources = prom.custom_query(query=POD_RESOURCE_LIMIT.format(POD_NAME=pod_info['pod']))
                        pod_resource = update_resources_from_query(tmp_resources)
                        # 현재 GPU 사용량은 label에서 별도 수집
                        pod_resource["gpu"] = update_pod_gpu_usage_from_labels(pod_info)

                        tmp_waiting = prom.custom_query(query=CONTAINER_STATUS_WAITING.format(POD_NAME=pod_info['pod']))
                        pod_waiting = tmp_waiting[0]['metric']['reason'] if tmp_waiting and tmp_waiting[0] is not None else None

                        tmp_terminated = prom.custom_query(query=CONTAINER_STATUS_TERMINATED.format(POD_NAME=pod_info['pod']))
                        pod_terminated = tmp_terminated[0]['metric']['reason'] if tmp_terminated and tmp_terminated[0] is not None else None

                        tmp_running = prom.custom_query(query=CONTAINER_STATUS_RUNNING.format(POD_NAME=pod_info['pod']))
                        pod_running = True if tmp_running and tmp_running[0] is not None else False

                        tmp_ready_true = prom.custom_query(query=CONTAINER_STATUS_READY_TRUE.format(POD_NAME=pod_info['pod']))
                        pod_ready_true = True if tmp_ready_true and tmp_ready_true[0] is not None else False

                        tmp_ready_false = prom.custom_query(query=CONTAINER_STATUS_READY_FALSE.format(POD_NAME=pod_info['pod']))
                        pod_ready_false = True if tmp_ready_false and tmp_ready_false[0] is not None else False
                        
                        tmp_restart_count = prom.custom_query(query=CONTAINER_RESTART_TOTAL.format(POD_NAME=pod_info['pod']))
                        pod_container_restart_count = tmp_restart_count[0]['value'][1] if tmp_restart_count else 0
                         # TODO label_work_func_type 가 없는 pod 존재 
                        pod_info["label_work_func_type"] = pod_info.get("label_work_func_type", None) 
                        status, reason, resolution = None, None, None
                        if pod_ready_true:
                            status = TYPE.KUBE_POD_STATUS_RUNNING
                            if gpu_uuids:
                                insert_gpu_usage(pod_info=pod_info, gpu_uuids=gpu_uuids, gpu_status=gpu_status)
                            
                        elif pod_ready_false:
                            if pod_waiting is not None:
                                
                                if pod_waiting == "ContainerCreating":
                                    status = TYPE.KUBE_POD_STATUS_INSTALLING
                                    if gpu_uuids:
                                        insert_gpu_usage(pod_info=pod_info, gpu_uuids=gpu_uuids, gpu_status=gpu_status)
                                else:
                                    status = TYPE.KUBE_POD_STATUS_ERROR
                                    container_waiting_reason = {
                                        'CrashLoopBackOff' : 'This error can be caused by a variery of issues',
                                        'ErrImagePull' : 'Wrong image name, Check the image or tag exist',
                                        'OutOfnvidia.com/gpu' : 'nvidia driver setting error',
                                        'ImagePullBackOff' : 'Wrong image name, Check the image or tag exist',
                                        'InvalidImageName' : 'Wrong image name, Check the image or tag exist',
                                        'CreateContainerConfigError' : 'ConfigMap or Secret is missing. Identify the missing ConfigMap or Secret',
                                        'CreateContainerError' : 'Container experienced an error when starting. Modify image specification to resolve it or Add a valid command to start the container',
                                        'RunContainerError': "Run Container Error. Check  Driver, package version or status. ",
                                        # 'others' : "This error can be caused by a variery of issues"
                                        'others' : "Invalid image."
                                    }
                                    reason = pod_waiting
                                    # print(pod_waiting, file=sys.stderr)
                                    resolution = container_waiting_reason[pod_waiting] if pod_waiting in container_waiting_reason.keys() else container_waiting_reason["others"]
                                    
                                    if pod_info["label_work_func_type"] in [TYPE.TRAINING_ITEM_C, TYPE.TRAINING_ITEM_A] and pod_info["label_pod_type"] == TYPE.PROJECT_TYPE:
                                        if pod_end_time:
                                            parse_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(pod_end_time)))
                                        else:
                                            parse_time = time.strftime('%Y-%m-%d %H:%M:%S')
                                        project_item_id = pod_info["label_project_item_id"]
                                        project_item_type = pod_info["label_work_func_type"]
                                        db_project.update_project_item_datetime(item_id=project_item_id, item_type=project_item_type, end_datetime=parse_time, end_status=status, error_reason=resolution)
                                        delete_helm_resource(helm_name=pod_info["label_helm_name"], workspace_id=workspace_id)
                                        try:
                                            project_id = pod_info["label_project_id"]
                                            project_info = db_project.get_project_new(project_id=project_id)
                                            if project_item_type == TYPE.TRAINING_ITEM_A:
                                                project_item_info = db_project.get_training(training_id=project_item_id)
                                                start_datetime = project_item_info["start_datetime"]
                                                elapsed_time = calculate_elapsed_time(start_time=start_datetime, end_time=parse_time)

                                                pod_count = int(pod_info.get("label_pod_count", 1))
                                                training_name = pod_info["label_training_name"]
                                                workspace_name = pod_info["label_workspace_name"]
                                                project_name = pod_info["label_project_name"]
                                                total_gpu_count = len(gpu_uuids) * pod_count
                                                instance_id = int(pod_info.get("label_instance_id", 0))
                                                instance_info = instance_db.get_instance(instance_id=instance_id)
                                                instance_name = instance_info["instance_name"]
                                                gpu_name = instance_info.get("gpu_name", None)
                                                instance_type = "GPU" if gpu_name  else "CPU"
                                                gpu_allocate = instance_info.get("gpu_allocate", 0)
                                                cpu_allocate = instance_info.get("cpu_allocate", 0)
                                                ram_allocate = instance_info.get("ram_allocate", 0)
                                                total_used_cpu = project_info.get("job_cpu_limit", 0) * project_item_info["pod_count"]
                                                total_used_ram = project_info.get("job_ram_limit", 0) * project_item_info["pod_count"]
                                                allocation_info = {
                                                            "workspace_name": workspace_name,
                                                            "start_datetime": start_datetime,
                                                            "item_name": training_name,
                                                            "item_type": project_item_type,
                                                            "project_name": project_name,
                                                            "end_datetime": parse_time,
                                                            "period": elapsed_time,
                                                            "type": project_item_type,
                                                            "type_detail": project_name,
                                                            "total_gpu_count": total_gpu_count,
                                                            "total_used_cpu": total_used_cpu,
                                                            "total_used_ram": total_used_ram,
                                                            "instance_info": {
                                                                "instance_name": instance_name,
                                                                "gpu_name": gpu_name,
                                                                "instance_type": instance_type,
                                                                "gpu_allocate": gpu_allocate,
                                                                "cpu_allocate": cpu_allocate,
                                                                "ram_allocate": ram_allocate
                                                            }
                                                        }
                                                log = {
                                                        "log_type": "allocation",
                                                        "allocation_info": json.dumps(allocation_info, separators=(',', ':'))
                                                    }
                                                print("[JFB/USAGE]", json.dumps(log, separators=(',', ':')))
                                        except Exception as e:
                                            traceback.print_exc()
                                            pass
                                    elif pod_info["label_pod_type"] == TYPE.FINE_TUNING_TYPE and pod_info["label_work_func_type"] == TYPE.FINE_TUNING_TYPE:
                                        model_id = pod_info["label_model_id"]
                                        model_db.update_model_fine_tuning_status_sync(status=TYPE.KUBE_POD_STATUS_ERROR, model_id=model_id)
                                        delete_helm_resource(workspace_id=workspace_id, helm_name=pod_info["label_helm_name"])
                                    elif pod_info["label_work_func_type"] in [TYPE.PREPROCESSING_ITEM_B, TYPE.PREPROCESSING_ITEM_A] and pod_info["label_pod_type"] == TYPE.PREPROCESSING_TYPE:
                                        preprocessing_item_id = pod_info["label_preprocessing_item_id"]
                                        preprocessing_item_type = pod_info["label_work_func_type"]
                                        if preprocessing_item_type == TYPE.PREPROCESSING_ITEM_B:
                                            prepro_db.update_preprocessing_job_datetime(preprocessing_job_id=preprocessing_item_id, end_datetime=parse_time, end_status=status, error_reason=reason)
                                        elif preprocessing_item_type == TYPE.PREPROCESSING_ITEM_A: 
                                            prepro_db.update_preprocessing_tool_datetime(preprocessing_tool_id=preprocessing_item_id, end_datetime=parse_time, error_reason=reason)
                                        delete_helm_resource(helm_name=pod_info["label_helm_name"], workspace_id=workspace_id)
                                    elif pod_info["label_pod_type"] == TYPE.COLLECT_TYPE:
                                        # collect_id = pod_info["label_collect_id"]
                                        kwargs={'end_datetime':datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                                        try:
                                            collect_db.update_collect(id=pod_info['label_collect_id'], **kwargs) # TODO 함수 없음
                                        except:
                                            pass
                                        delete_helm_resource(workspace_id=workspace_id, helm_name=pod_info["label_helm_name"])
                                    
                                        
                            elif pod_terminated is not None:
                                if pod_status[0]['metric']['phase'] != "Failed" and pod_terminated == "Completed":
                                    status = TYPE.KUBE_POD_STATUS_DONE
                                else:
                                    status = TYPE.KUBE_POD_STATUS_ERROR
                                if pod_info["label_work_func_type"] in [TYPE.TRAINING_ITEM_C, TYPE.TRAINING_ITEM_A, TYPE.TRAINING_ITEM_C] and pod_info["label_pod_type"] == TYPE.PROJECT_TYPE:
                                    """
                                    pod_terminated 종류 
                                    OOMKilled: 컨테이너가 메모리 부족(OOM, Out Of Memory)으로 인해 종료된 경우.
                                    Error: 컨테이너가 오류로 인해 종료된 경우.
                                    Completed: 컨테이너가 정상적으로 작업을 완료하고 종료된 경우.
                                    ContainerCannotRun: 컨테이너가 시작되지 못한 경우(예: 이미지 문제 또는 권한 문제).
                                    DeadlineExceeded: 컨테이너가 정해진 시간 내에 완료되지 않아 종료된 경우.
                                    Evicted: 컨테이너가 자원 부족 등으로 인해 노드에서 퇴출된 경우.
                                    Terminated: 사용자의 명령이나 다른 이유로 인해 컨테이너가 종료된 경우.
                                    CrashLoopBackOff: 컨테이너가 반복적으로 충돌하며 재시작되는 경우.
                                    """
                                    reason = pod_terminated
                                    resolution = None
                                    # project_id = pod_info["label_project_id"]
                                    # workspace_id = pod_info["label_workspace_id"]
                                    project_item_id = pod_info["label_project_item_id"]
                                    project_item_type = pod_info["label_work_func_type"]
                                    pod_end_time = prom.custom_query(query=POD_END_TIME.format(POD_NAME=pod_info["pod"]))[0]["value"][1]
                                    if pod_end_time:
                                        parse_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(pod_end_time)))
                                    else:
                                        parse_time = time.strftime('%Y-%m-%d %H:%M:%S')
                                    if pod_info["label_work_func_type"] in [TYPE.TRAINING_ITEM_B, TYPE.TRAINING_ITEM_A]:
                                        db_project.update_project_item_datetime(item_id=project_item_id, item_type=project_item_type, end_datetime=parse_time, end_status=status, error_reason=reason)
                                    elif pod_info["label_work_func_type"] == TYPE.TRAINING_ITEM_C:
                                        db_project.update_project_hps_datetime(hps_id=project_item_id, end_datetime=parse_time, end_status=status, error_reason=reason)
                                    delete_helm_resource(helm_name=pod_info["label_helm_name"], workspace_id=workspace_id)
                                    try:
                                        project_id = pod_info["label_project_id"]
                                        project_info = db_project.get_project_new(project_id=project_id)
                                        if project_item_type == TYPE.TRAINING_ITEM_A:
                                            project_item_info = db_project.get_training(training_id=project_item_id)
                                            start_datetime = project_item_info["start_datetime"]
                                            elapsed_time = calculate_elapsed_time(start_time=start_datetime, end_time=parse_time)

                                            pod_count = int(pod_info.get("label_pod_count", 1))
                                            training_name = pod_info["label_training_name"]
                                            workspace_name = pod_info["label_workspace_name"]
                                            project_name = pod_info["label_project_name"]
                                            total_gpu_count = len(gpu_uuids) * pod_count
                                            instance_id = int(pod_info.get("label_instance_id", 0))
                                            instance_info = instance_db.get_instance(instance_id=instance_id)
                                            instance_name = instance_info["instance_name"]
                                            gpu_name = instance_info.get("gpu_name", None)
                                            instance_type = "GPU" if gpu_name  else "CPU"
                                            gpu_allocate = instance_info.get("gpu_allocate", 0)
                                            cpu_allocate = instance_info.get("cpu_allocate", 0)
                                            ram_allocate = instance_info.get("ram_allocate", 0)
                                            total_used_cpu = project_info.get("job_cpu_limit", 0) * project_item_info["pod_count"]
                                            total_used_ram = project_info.get("job_ram_limit", 0) * project_item_info["pod_count"]
                                            allocation_info = {
                                                        "workspace_name": workspace_name,
                                                        "start_datetime": start_datetime,
                                                        "item_name": training_name,
                                                        "item_type": project_item_type,
                                                        "project_name": project_name,
                                                        "end_datetime": parse_time,
                                                        "period": elapsed_time,
                                                        "type": project_item_type,
                                                        "type_detail": project_name,
                                                        "total_gpu_count": total_gpu_count, 
                                                        "total_used_cpu": total_used_cpu,
                                                        "total_used_ram": total_used_ram,
                                                        "instance_info": {
                                                            "instance_name": instance_name,
                                                            "gpu_name": gpu_name,
                                                            "instance_type": instance_type,
                                                            "gpu_allocate": gpu_allocate,
                                                            "cpu_allocate": cpu_allocate,
                                                            "ram_allocate": ram_allocate
                                                        }
                                                    }
                                            log = {
                                                    "log_type": "allocation",
                                                    "allocation_info": json.dumps(allocation_info, separators=(',', ':'))
                                                }
                                            print("[JFB/USAGE]", json.dumps(log, separators=(',', ':')))
                                    except Exception as e:
                                        traceback.print_exc()
                                        pass
                                elif pod_info["label_work_func_type"] in [TYPE.PREPROCESSING_ITEM_B, TYPE.PREPROCESSING_ITEM_A] and pod_info["label_pod_type"] == TYPE.PREPROCESSING_TYPE:
                                    preprocessing_item_id = pod_info["label_preprocessing_item_id"]
                                    preprocessing_item_type = pod_info["label_work_func_type"]
                                    # print(prom.custom_query(query=POD_END_TIME.format(POD_NAME=pod_info["pod"])))
                                    # pod_end_time = prom.custom_query(query=POD_END_TIME.format(POD_NAME=pod_info["pod"]))[0]["value"][1]
                                    parse_time = time.strftime('%Y-%m-%d %H:%M:%S')
                                    # if pod_end_time:
                                    #     parse_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(pod_end_time)))
                                    # else:
                                    #     parse_time = time.strftime('%Y-%m-%d %H:%M:%S')
                                    if preprocessing_item_type == TYPE.PREPROCESSING_ITEM_B:
                                        prepro_db.update_preprocessing_job_datetime(preprocessing_job_id=preprocessing_item_id, end_datetime=parse_time, end_status=status, error_reason=reason)
                                    elif preprocessing_item_type == TYPE.PREPROCESSING_ITEM_A: 
                                        prepro_db.update_preprocessing_tool_datetime(preprocessing_tool_id=preprocessing_item_id, end_datetime=parse_time, error_reason=reason)
                                    delete_helm_resource(helm_name=pod_info["label_helm_name"], workspace_id=workspace_id)
                                    
                                    
                                elif pod_info["label_work_func_type"] == TYPE.FINE_TUNING_TYPE and pod_info["label_pod_type"] == TYPE.FINE_TUNING_TYPE:
                                    model_id = pod_info["label_model_id"]
                                    model_db.update_model_fine_tuning_status_sync(status=status, model_id=model_id)
                                    delete_helm_resource(workspace_id=workspace_id, helm_name=pod_info["label_helm_name"])
                                        
                                else: # TODO 사용자가 삭제하기 전까지 해당 pod에 대한 gpu 사용을 유지해야 하는가?
                                    status = TYPE.KUBE_POD_STATUS_ERROR
                                    reason = pod_terminated
                                    resolution = "This error can be caused by a variery of issues"
                                
                            elif pod_running is True:
                                status = TYPE.KUBE_POD_STATUS_INSTALLING
                                if gpu_uuids:
                                    insert_gpu_usage(pod_info=pod_info, gpu_uuids=gpu_uuids, gpu_status=gpu_status)
                        else:
                            phase = pod_status[0]['metric']["phase"] if pod_status and pod_status[0] is not None else None
                            if phase == 'Failed':
                                status = "error"
                                reason = pod_status_reason    
                        
                       
                        
                        if pod_info["label_pod_type"] == TYPE.DEPLOYMENT_TYPE:
                            if pod_info.get("label_pod_count",None):
                                    if int(pod_info["label_pod_count"]) >1:
                                        pod_resource = {
                                            "gpu" : pod_resource["gpu"] * int(pod_info["label_pod_count"]),
                                            "cpu" : pod_resource["cpu"] * int(pod_info["label_pod_count"]),
                                            "ram" : pod_resource["ram"] * int(pod_info["label_pod_count"])
                                        }
                            workspace_pods[TYPE.DEPLOYMENT_TYPE][pod_info["label_deployment_id"]][pod_info["label_deployment_worker_id"]] = {
                                    'status' : status,
                                    'instance_id' : instance_id,
                                    'reason' : reason,
                                    'resolution' : resolution,
                                    'restart_count' : pod_container_restart_count,
                                    'phase' : pod_status[0]['metric']['phase'] if pod_status else "Unknown",
                                    'resource' : pod_resource
                                }
                        elif pod_info["label_pod_type"] == TYPE.FINE_TUNING_TYPE and pod_info["label_work_func_type"] == TYPE.FINE_TUNING_TYPE:
                            if pod_info.get("label_pod_count",None):
                                if int(pod_info["label_pod_count"]) >1:
                                    pod_resource = {
                                        "gpu" : pod_resource["gpu"] * int(pod_info["label_pod_count"]),
                                        "cpu" : pod_resource["cpu"] * int(pod_info["label_pod_count"]),
                                        "ram" : pod_resource["ram"] * int(pod_info["label_pod_count"])
                                    }
                                workspace_pods[TYPE.FINE_TUNING_TYPE][pod_info["label_model_id"]] ={
                                    'status' : status if status else TYPE.KUBE_POD_STATUS_PENDING,
                                    'reason' : reason,
                                    'instance_id' : instance_id,
                                    'resolution' : resolution,
                                    'restart_count' : pod_container_restart_count,
                                    'phase' : pod_status[0]['metric']['phase'] if pod_status else "Unknown",
                                    'resource' : pod_resource
                                }
                        elif pod_info["label_pod_type"] == TYPE.PROJECT_TYPE:
                            if pod_info["label_work_func_type"] in workspace_pods and \
                                pod_info["label_project_item_id"] in workspace_pods[pod_info["label_work_func_type"]] and \
                                workspace_pods[pod_info["label_work_func_type"]][pod_info["label_project_item_id"]]["status"] != TYPE.KUBE_POD_STATUS_RUNNING:
                                pass # 분산학습 시 특정 node의 pod만 실행이 안될경우를 대비해 추가 
                            else:
                                if pod_info.get("label_pod_count",None):
                                    if int(pod_info["label_pod_count"]) >1:
                                        pod_resource = {
                                            "gpu" : pod_resource["gpu"] * int(pod_info["label_pod_count"]),
                                            "cpu" : pod_resource["cpu"] * int(pod_info["label_pod_count"]),
                                            "ram" : pod_resource["ram"] * int(pod_info["label_pod_count"])
                                        }
                                    workspace_pods[TYPE.PROJECT_TYPE][pod_info["label_project_id"]][pod_info["label_work_func_type"]][pod_info["label_project_item_id"]] = {
                                            'status' : status if status else TYPE.KUBE_POD_STATUS_PENDING,
                                            'reason' : reason,
                                            'instance_id' : instance_id,
                                            'resolution' : resolution,
                                            'restart_count' : pod_container_restart_count,
                                            'phase' : pod_status[0]['metric']['phase'] if pod_status else "Unknown",
                                            'resource' : pod_resource
                                        }
                        elif pod_info["label_pod_type"] == TYPE.PREPROCESSING_TYPE:
                            
                            if pod_info["label_work_func_type"] in workspace_pods and \
                                pod_info["label_preprocessing_item_id"] in workspace_pods[pod_info["label_work_func_type"]] and \
                                workspace_pods[pod_info["label_work_func_type"]][pod_info["label_preprocessing_item_id"]]["status"] != TYPE.KUBE_POD_STATUS_RUNNING:
                                pass
                            else:
                                pod_resource = {
                                    "gpu" : pod_resource.get("gpu", 0) * int(pod_info["label_pod_count"]),
                                    "cpu" : pod_resource["cpu"] * int(pod_info["label_pod_count"]),
                                    "ram" : pod_resource["ram"] * int(pod_info["label_pod_count"])
                                }
                                workspace_pods[TYPE.PREPROCESSING_TYPE][pod_info["label_preprocessing_id"]][pod_info["label_work_func_type"]][pod_info["label_preprocessing_item_id"]] = {
                                        'status' : status if status else TYPE.KUBE_POD_STATUS_PENDING,
                                        'reason' : reason,
                                        'instance_id' : instance_id,
                                        'resolution' : resolution,
                                        'restart_count' : pod_container_restart_count,
                                        'phase' : pod_status[0]['metric']['phase'] if pod_status else "Unknown",
                                        'resource' : pod_resource
                                    }
                        elif pod_info["label_pod_type"] == TYPE.COLLECT_TYPE:
                            
                                pod_resource = {
                                    "gpu" : pod_resource.get("gpu", 0),
                                    "cpu" : pod_resource["cpu"],
                                    "ram" : pod_resource["ram"],
                                }
                                workspace_pods[TYPE.COLLECT_TYPE][pod_info["label_collect_id"]] = {
                                        'status' : status if status else TYPE.KUBE_POD_STATUS_PENDING,
                                        'reason' : reason,
                                        'instance_id' : instance_id,
                                        'resolution' : resolution,
                                        'restart_count' : pod_container_restart_count,
                                        'phase' : pod_status[0]['metric']['phase'] if pod_status else "Unknown",
                                        'resource' : pod_resource
                                    }
                    redis_client.hset(redis_key.WORKSPACE_PODS_STATUS, workspace["id"], json.dumps(workspace_pods))    
                    # redis_client.hset(redis_key.WORKSPACE_INSTANCE_USED, workspace["id"], json.dumps(workspace_instances))
                redis_client.set(redis_key.GPU_INFO_RESOURCE, json.dumps(gpu_status))
        except:
            traceback.print_exc()
            pass



# def set_workspace_pod_status2():
#     from utils.msa_db import db_workspace
#     from utils import kube
#     import json
#     import logging

#     # TODO
#     # kafka 이벤트 처리 방식으로 변경 시 삭제 가능 
#     from utils.msa_db.db_base import get_db as j_db
#     from utils.llm_db.db_base import get_db as l_db
#     ITEM_JOB_DB_UPDATE = {
#         TYPE.TRAINING_ITEM_A : {
#             "db_table" : "training" , # project_job 으로 추후 변경
#             "db_con" : j_db,
#             "status_column" : "end_status"
#         },
#         TYPE.TRAINING_ITEM_C : {
#             "db_table" : "project_hps" ,
#             "db_con" : j_db,
#             "status_column" : "end_status"
#         },
#         TYPE.PREPROCESSING_ITEM_B: {
#             "db_table" : "preprocessing_job" ,
#             "db_con" : j_db,
#             "status_column" : "end_status"
#         },
#         TYPE.FINE_TUNING_TYPE: {
#             "db_table" : "model" ,
#             "db_con" : l_db,
#             "status_column" : "latest_fine_tuning_status" # end_status 로 추후 변경
#         }
#     }
#     def update_job_status(db_con , db_table : str, status_column : str, item_id : int, end_datetime : str , error_reason : str, end_status : str):
#         try:
#             with db_con() as conn:
#                 cur = conn.cursor()
#                 sql = f"""
#                     UPDATE {db_table} SET
#                 """
#                 if end_datetime:
#                     sql += f" end_datetime = '{end_datetime}'"
#                 if end_status:
#                     sql += f", {status_column} = '{end_status}'"
#                 if error_reason:
#                     sql += f", error_reason = '{error_reason}'"
#                 sql += f" WHERE id = {item_id}"
#                 cur.execute(sql)
#                 conn.commit()
#             return True
#         except:
#             traceback.print_exc()
#             return False
#     def insert_gpu_usage(labels, gpu_uuids, gpu_status):
#         item_type = labels.get("pod_type")
#         instance_id = labels.get("instance_id")
#         type_mappings = {
#             TYPE.PROJECT_TYPE: {
#                 "used_project": labels.get("project_id"),
#                 "used_project_item": labels.get("project_item_id"),
#                 "used_project_item_type": labels.get("work_func_type")
#             },
#             TYPE.FINE_TUNING_TYPE: {
#                 "used_model": labels.get("model_id")
#             },
#             TYPE.PREPROCESSING_TYPE: {
#                 "used_preprocessing": labels.get("preprocessing_id"),
#                 "used_preprocessing_item": labels.get("preprocessing_item_id"),
#                 "used_preprocessing_item_type": labels.get("work_func_type")
#             },
#             TYPE.DEPLOYMENT_TYPE: {
#                 "used_deployment": labels.get("deployment_id"),
#                 "used_deployment_worker": labels.get("deployment_worker_id")
#             }
#         }
        
#         used_info = {"used_workspace": workspace_id, "used_instance": instance_id}
#         used_info.update(type_mappings.get(item_type, {}))
        
#         for gpu_uuid in gpu_uuids:
#             gpu_status[gpu_uuid["node_name"]][gpu_uuid["gpu_uuid"]].update({
#                 "used": 1,
#                 "used_type": item_type,
#                 "used_info": used_info
#             })

#     def gpu_reset():
#         result={}
#         node_list = node_db.get_node_list()
#         for node in node_list:
#             node_gpus = node_db.get_node_gpu_list(node_id=node["id"])
#             for gpu in node_gpus:
#                 result.setdefault(node["name"],{})[gpu["gpu_uuid"]] = {
#                     "model_name": gpu["resource_name"],
#                     "gpu_mem" : gpu["gpu_memory"],
#                     "used" : 0,
#                     "gpu_driver" : None,
#                     "used_type" : None,
#                     "used_info": {}
#                 }
#         return result

#     def delete_helm_resource(helm_name : str, workspace_id : int):
#         try:
#             namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
#             command=f"helm uninstall {helm_name} -n {namespace}"
#             result = subprocess.run(
#                 command,
#                 shell=True,
#                 check=True,
#                 stdout=subprocess.PIPE,
#                 stderr=subprocess.PIPE,
#                 text=True,
#             )
#             return 1, result.stdout
#         except subprocess.CalledProcessError as e:
#             err_msg = e.stderr.strip()
#             if "cannot re-use a name that is still in use" in err_msg:
#                 return True, ""
#             return False ,err_msg

#     while True:
#         time.sleep(0.1)
#         workspace_list = db_workspace.get_workspace_list()
#         gpu_status = gpu_reset()

#         for workspace in workspace_list:

#             workspace_id = workspace['id']
#             namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
#             redis_client = get_redis_client()
#             label_selector = f"workspace_id={workspace_id}"

#             try:
#                 pod_list = kube.get_all_pods(namespace=namespace, label_selector=label_selector)
#             except Exception as e:
#                 logging.error(f"Failed to list pods in namespace '{namespace}': {e}")
#                 return

#             workspace_pod_status = {}

#             for pod in pod_list.items:
#                 labels = pod.metadata.labels or {}
#                 pod_name = pod.metadata.name 
#                 pod_type = labels.get("pod_type", "unknown")
#                 primary_id = labels.get("project_id") or labels.get("deployment_id") or labels.get("preprocessing_id") \
#                     or labels.get("collect_id") or labels.get("model_id", "unknown")
#                 work_func_type = labels.get("work_func_type", "default")
#                 secondary_id = labels.get("project_item_id") or labels.get("deployment_worker_id") or labels.get("preprocessing_item_id") or "default"
#                 helm_name = labels.get("helm_name", "")
#                 gpu_ids = labels.get("gpu_ids", "").split(".")
#                 gpu_uuids = []
#                 for gpu_id in gpu_ids:
#                     if gpu_id:
#                         gpu_info = node_db.get_node_gpu(gpu_id=gpu_id)
#                         gpu_uuids.append({
#                             "node_name" : gpu_info["node_name"],
#                             "gpu_uuid" : gpu_info["gpu_uuid"]
#                         })

#                 status, reason, resolution, latest_finished_at = kube.analyze_pod_error(pod)
#                 if status in (TYPE.KUBE_POD_STATUS_DONE , TYPE.KUBE_POD_STATUS_ERROR):
#                     # job 이 끝났을 때 helm resource 삭제
#                     if work_func_type in (TYPE.TRAINING_ITEM_A, TYPE.TRAINING_ITEM_C, TYPE.PREPROCESSING_ITEM_B, TYPE.FINE_TUNING_TYPE):
#                         db_con = ITEM_JOB_DB_UPDATE[work_func_type]["db_con"]
#                         db_table = ITEM_JOB_DB_UPDATE[work_func_type]["db_table"]
#                         status_column = ITEM_JOB_DB_UPDATE[work_func_type]["status_column"]
#                         item_id = secondary_id if secondary_id != "default" else primary_id
#                         # TODO
#                         # 추후 kafka 이벤트 처리로 수정 가능
#                         # update_job_status(db_con=db_con, db_table=db_table, status_column=status_column, end_status=status, end_datetime=latest_finished_at, item_id=item_id)
#                         # delete_helm_resource(helm_name=helm_name, workspace_id=workspace_id)
#                         continue


#                 restart_count = sum(cs.restart_count for cs in pod.status.container_statuses or [])
#                 total_limits = {
#                     'cpu': float(sum(kube.parse_quantity(c.resources.limits.get('cpu', '0')) for c in pod.spec.containers)),
#                     'ram': float(sum(kube.parse_quantity(c.resources.limits.get('memory', '0Gi')) for c in pod.spec.containers) / (1024**3)),
#                     # 'gpu': int(sum(kube.parse_quantity(c.resources.limits.get('nvidia.com/gpu', 0)) for c in pod.spec.containers)),
#                     'gpu' : int(len(gpu_ids)),
#                 }

#                 # workspace_pod_status\
#                 #     .setdefault(pod_type, {})\
#                 #     .setdefault(primary_id, {})\
#                 #     .setdefault(pod_name, {
#                 #         'status': status,
#                 #         'item_id' : secondary_id,
#                 #         'work_func_type' : work_func_type,
#                 #         'reason': reason,
#                 #         'instance_id': labels.get("instance_id"),
#                 #         'resolution': resolution,
#                 #         'restart_count': restart_count,
#                 #         'phase': pod.status.phase,
#                 #         'resource': total_limits
#                 #     })
#                 current_entry = workspace_pod_status\
#                         .setdefault(pod_type, {})\
#                         .setdefault(primary_id, {})\
#                         .setdefault(secondary_id, {
#                             'status': status,
#                             # 'pod_name' : pod_name,
#                             # 'item_id' : secondary_id,
#                             'work_func_type' : work_func_type,
#                             'reason': reason,
#                             'instance_id': labels.get("instance_id"),
#                             'resolution': resolution,
#                             'restart_count': restart_count,
#                             'phase': pod.status.phase,
#                             'resource': {'cpu': 0, 'ram': 0, 'gpu': 0}
#                         })

#                 # 리소스는 항상 합산
#                 current_entry['resource']['cpu'] += total_limits['cpu']
#                 current_entry['resource']['ram'] += total_limits['ram']
#                 current_entry['resource']['gpu'] += total_limits['gpu']

#                 if current_entry['resource']['gpu'] > 0:
#                     insert_gpu_usage(labels=labels, gpu_uuids=gpu_uuids, gpu_status=gpu_status)

#                 # 상태 우선순위 처리 (error > installing > running > complete)
#                 status_priority = {'error': 4, 'installing': 3, 'running': 2, 'complete': 1}
#                 if status_priority.get(status, 0) > status_priority.get(current_entry['status'], 0):
#                     current_entry['status'] = status
#                     current_entry['reason'] = reason
#                     current_entry['resolution'] = resolution
#                     current_entry['phase'] = pod.status.phase
#                 # restart_count는 최대값 저장
#                 current_entry['restart_count'] = max(current_entry['restart_count'], restart_count)
#             redis_client.hset(redis_key.WORKSPACE_PODS_STATUS2, workspace_id, json.dumps(workspace_pod_status))
#         redis_client.set(redis_key.GPU_INFO_RESOURCE2, json.dumps(gpu_status))


def set_storage_usage_info():
    while(True):
        try:
            time.sleep(1)
            result = {}
            storage_list = storage_db.get_storage()
            redis_client=get_redis_client()
            if len(storage_list) > 0:
                with prometheus_connection(url) as prom:
                    pvc_requests_df = MetricSnapshotDataFrame(prom.custom_query(query=STORAGE_REQUESTS_BYTE))
                    pvc_list_df = MetricSnapshotDataFrame(prom.custom_query(query=STORAGE_PERSISTENTVOLUME_LIST))
                    # print(pvc_list_df)
                    try:
                        pvc_info_df = MetricSnapshotDataFrame(prom.custom_query(query=STORAGE_PVC_INFO))
                    except:
                        pvc_info_df = []
                    for storage in storage_list:
                        if storage['size'] is None :
                            continue
                        workspaces={'data':[], 'main':[]}
                        requests_total=0
                        used_total=0
                        data_requests_total=0
                        data_used_total=0
                        main_requests_total=0
                        main_used_total=0
                        if len(pvc_info_df) > 0 :
                            if len(ws_db.get_workspace_list())>0:
                                data_df=pvc_list_df[(pvc_list_df['storageclass']==storage['data_sc'])]
                                for pvc in data_df['persistentvolumeclaim']:
                                    data_storage_request=pvc_requests_df[pvc_requests_df['persistentvolumeclaim']==pvc].value.item()
                                    data_storage_info=pvc_info_df[pvc_info_df['persistentvolumeclaim']==pvc]
                                    if not data_storage_info.empty:
                                        data_requests_total += data_storage_request
                                        workspace_name = data_storage_info.iloc[0]['label_workspace_name']
                                        try:
                                            workspace_usage = json.loads(redis_client.hget(redis_key.WORKSPACE_STORAGE_USAGE, workspace_name))
                                            used_size = workspace_usage.get('data',0)
                                        except:
                                            used_size = 0
                                        # workspace_usage = json.loads(redis_client.hget(redis_key.WORKSPACE_STORAGE_USAGE, workspace_name))
                                        # used_size = workspace_usage.get('data',0)
                                        data_used_total += used_size
                                        workspaces['data'].append(
                                            {
                                                'workspace_name' : workspace_name,
                                                'alloc_size' : int(data_storage_request),
                                                'used_size' : used_size
                                            }
                                        )
                                main_df=pvc_list_df[(pvc_list_df['storageclass']==storage['main_sc'])]
                                for pvc in main_df['persistentvolumeclaim']:
                                    main_storage_request=pvc_requests_df[pvc_requests_df['persistentvolumeclaim']==pvc].value.item()
                                    main_storage_info=pvc_info_df[pvc_info_df['persistentvolumeclaim']==pvc]
                                    if not main_storage_info.empty :
                                        main_requests_total += main_storage_request
                                        workspace_name = main_storage_info.iloc[0]['label_workspace_name']
                                        try:
                                            workspace_usage = json.loads(redis_client.hget(redis_key.WORKSPACE_STORAGE_USAGE, workspace_name))
                                            used_size = workspace_usage.get('main',0)
                                        except:
                                            traceback.print_exc()
                                            used_size = 0
                                        # workspace_usage = json.loads(redis_client.hget(redis_key.WORKSPACE_STORAGE_USAGE, workspace_name))
                                        # used_size = workspace_usage.get('main',0)
                                        main_used_total += used_size
                                        workspaces['main'].append(
                                            {
                                                'workspace_name' : workspace_name,
                                                'alloc_size' : int(main_storage_request),
                                                'used_size' : used_size
                                            }
                                        )
                                workspaces['data'] = sorted(workspaces['data'], key=lambda x: x['workspace_name'])
                                workspaces['main'] = sorted(workspaces['main'], key=lambda x: x['workspace_name'])
                        requests_total=data_requests_total+main_requests_total
                        used_total = data_used_total + main_used_total
                        result[storage['id']]={
                            'type' : storage['type'],
                            'name' : storage['name'],
                            'total' : int(storage['size']),
                            'total_alloc' : int(requests_total),
                            'total_used' : int(used_total),
                            'avail' : int(storage['size'])-int(requests_total),
                            'data_alloc' : int(data_requests_total),
                            'main_alloc' : int(main_requests_total),
                            'workspaces' : workspaces
                        }
                    redis_client.set(redis_key.STORAGE_LIST_RESOURCE, json.dumps(result))
        except:
            traceback.print_exc()
            pass


def delete_complete_job():
    # global redis_client
    while(True):
        time.sleep(10)
        try:
            redis_client=get_redis_client()
            with prometheus_connection(url) as prom:
                job_df = MetricSnapshotDataFrame(prom.custom_query(query=COMPLETE_JOB))
                job_list=redis_client.hgetall(redis_key.JOB_LIST)
                if job_list is not None:
                    for name, namespace in job_list.items():
                        is_present = ((job_df['job_name'] == name) & (job_df['namespace'] == namespace)).any()
                        if is_present:
                            delete_helm(name,namespace)
                            redis_client.hdel(redis_key.JOB_LIST, name)
        except: 
            traceback.print_exc()
            pass

def get_workspace_gpu_usage_map(gpu_data: dict) -> dict:
        """
        GPU 사용 정보를 순회하면서 workspace_id별 GPU 사용 개수 딕셔너리 생성
        """
        usage_map = {}
        for node_name, gpus in gpu_data.items():
            for gpu_uuid, gpu_info in gpus.items():
                used_info = gpu_info.get("used_info", {})
                workspace_id = used_info.get("used_workspace")
                if workspace_id:
                    usage_map[workspace_id] = usage_map.get(workspace_id, 0) + 1
        return usage_map

def workspace_resource_usage():
    while(True):
        try:
            time.sleep(1)
            # redis_client.delete(redis_key.WORKSPACE_RESOURCE_QUOTA)
            redis_client=get_redis_client()
            workspace_list = ws_db.get_workspace_list()
            jonathan_namespace = os.getenv("JF_SYSTEM_NAMESPACE")
            NAMESPACE="{namespace}-{id}"

            # GPU 사용 현황은 Redis의 GPU_INFO_RESOURCE에서 가져옴
            gpu_resource_raw = redis_client.get(redis_key.GPU_INFO_RESOURCE)
            gpu_resource_info = json.loads(gpu_resource_raw) if gpu_resource_raw else {}
            
            workspace_gpu_usage_map = get_workspace_gpu_usage_map(gpu_resource_info)

            with prometheus_connection(url) as prom:
                try:
                    ws_df = MetricSnapshotDataFrame(prom.custom_query(query=WORKSPACE_RESOURCE_USAGE))
                    for ws in workspace_list:
                        ws_id = ws['id']
                        result = {}
                        try:
                            ws_quota_df=ws_df[(ws_df['namespace']==NAMESPACE.format(namespace=jonathan_namespace, id=ws_id))]
                            for _, quota in ws_quota_df.iterrows():
                                if quota['resource'] == "limits.cpu":
                                    resource = "cpu"
                                elif quota['resource'] == "limits.memory":
                                    resource = "ram"
                                elif quota['resource'] == "requests.nvidia.com/gpu":
                                    resource = "gpu"
                                else:
                                    continue

                                if not result.get(resource):
                                    result[resource]= {} 
                                result[resource][quota['type']]=int(quota['value'])
                            
                            # GPU 사용 현황만 별도 업데이트
                            if result.get('gpu', None):
                                result['gpu']["used"] = workspace_gpu_usage_map.get(str(ws_id), 0)

                        except:
                            traceback.print_exc()
                            pass

                        result['network'] = {
                            "outbound" : 0,
                            "inbound" : 0
                        }
                        network_outbound=prom.custom_query(query=WORKSPACE_NETWORK_OUTBOUND_USAGE.format(namespace=NAMESPACE.format(namespace=jonathan_namespace, id=ws_id)))
                        network_inbound=prom.custom_query(query=WORKSPACE_NETWORK_INBOUND_USAGE.format(namespace=NAMESPACE.format(namespace=jonathan_namespace, id=ws_id)))
                        result["network"]["outbound"] = float(network_outbound[0]['value'][1]) if network_outbound else 0
                        result["network"]["inbound"] = float(network_inbound[0]['value'][1]) if network_inbound else 0
                        redis_client.hset(redis_key.WORKSPACE_RESOURCE_QUOTA, ws_id, json.dumps(result))
                    # print(redis_client.hgetall(redis_key.WORKSPACE_RESOURCE_QUOTA))
                except:
                    continue
            
        except:
            traceback.print_exc()
            pass
def gpu_alloc_usage():
    try:
        instance_list = ws_db.get_instance_list()
        result={}
        for instance in instance_list:
            gpu_alloc_count=0
            if instance['gpu_allocate'] != 0 and instance['instance_allocate'] != 0:
                gpu_name = node_db.get_resource_group(id=instance['gpu_resource_group_id'])['name']
                if not result.get(gpu_name):
                    result[gpu_name] = 0
                instance_gpu_allocate = instance['gpu_allocate'] if instance['gpu_allocate'] is not None else 0 
                result[gpu_name] += instance_gpu_allocate * int(instance['instance_allocate'])
        redis_client=get_redis_client()
        # print(result)
        redis_client.set(redis_key.GPU_ALLOC_USAGE, json.dumps(result))
    except:
        traceback.print_exc()
        pass

def delete_helm(name, namespace):
    try:
        command=f"""helm uninstall {name} -n {namespace} """

        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout 
    except subprocess.CalledProcessError as e:
        traceback.print_exc()
        return f"Error executing Helm command: {e.stderr}"
    except:
        traceback.print_exc()
        return False


def get_workspace_path(workspace_name):

    kube_config_path=os.getenv('KUBER_CONFIG_PATH')
    # Load kube config (default location or specified path)
    config.load_kube_config(config_file=kube_config_path)  # or config.load_kube_config(config_file="/path/to/your/kubeconfig")

    # Create a client
    kube = client.CoreV1Api()
    import time
    time.sleep(5)
    # Define the name of the PV you want to get
    with prometheus_connection(url) as prom:
        pvc_name = prom.custom_query(query=GET_PERSISTENTVOLUMECLAIME.format(WORKSPACE_NAME=workspace_name))[0]['metric']['persistentvolumeclaim']
        # print(pvc_name)
        pv_name = prom.custom_query(query=GET_PERSISTENTVOLUME.format(PERSISTENTVOLUMECLAIME=pvc_name))[0]['metric']['volumename']
        # print(pv_name)

    # Get the specific Persistent Volume
    pv = kube.read_persistent_volume(pv_name)

    # extract VolumeAttributes subvolumePath
    pv_info=pv.to_dict()
    return pv_info['spec']['csi']['volume_attributes']['subvolumePath']
   
   
# ===========================================================================================================================
# Deployment
# ===========================================================================================================================

def set_deployment_pod_resouce_limit():
    while(True):
        try:
            time.sleep(1)
            result={}
            redis_client=get_redis_client()
            worker_list = deployment_db.get_deployment_worker_list(running=True)

            for worker in worker_list:
                pod_name = f"{worker.get('api_path')}-{worker.get('deployment_worker_id')}-0"
                DEPLOYMENT_POD_RESOURCE_LIMIT_CPU = "kube_pod_container_resource_limits{{pod='{POD_NAME}', resource='cpu'}}"
                DEPLOYMENT_POD_RESOURCE_LIMIT_RAM = "kube_pod_container_resource_limits{{pod='{POD_NAME}', resource='memory'}}"

                with prometheus_connection(url) as prom:
                    cpu = prom.custom_query(query=DEPLOYMENT_POD_RESOURCE_LIMIT_CPU.format(POD_NAME=pod_name))
                    ram = prom.custom_query(query=DEPLOYMENT_POD_RESOURCE_LIMIT_RAM.format(POD_NAME=pod_name))
                    if len(cpu) > 0 and len(ram) > 0:
                        result[str(worker.get('deployment_worker_id'))] = {'limit' : {"cpu" : cpu[0]['value'][1], "memory" : ram[0]['value'][1]}}
                    else:
                        result[str(worker.get('deployment_worker_id'))] = {'limit' : {"cpu" : None, "memory" : None}}
                        
            redis_client.set(redis_key.DEPLOYMENT_WORKER_RESOURCE_LIMIT, json.dumps(result))
        except:
            traceback.print_exc()
            pass

def get_deployment_worker_resource():
    from utils.TYPE import MEM_USAGE_KEY, MEM_LIMIT_KEY, MEM_USAGE_PER_KEY, CPU_USAGE_ON_POD_KEY
    while(True):
        try:
            time.sleep(1)
            result={}
            redis_client=get_redis_client()
            worker_list = deployment_db.get_deployment_worker_list(running=True)
            
            end_time = datetime.datetime.now()  # 현재 시간
            start_time = end_time - datetime.timedelta(minutes=5)  # 1시간 전부터

            for worker in worker_list:
                pod_name = f"{worker.get('api_path')}-{worker.get('deployment_worker_id')}-0"
                
                CPU_USAGE_QUERY = "sum(rate(container_cpu_usage_seconds_total{{pod='{POD_NAME}'}}[5m])) by (pod)" # query 누적값, 5분 일때 안정적인 결과 측정
                RAM_USAGE_QUERY = "sum(container_memory_usage_bytes{{pod='{POD_NAME}'}}) by (pod)"
                
                CPU_LIMIT_QUERY = "kube_pod_container_resource_limits{{pod='{POD_NAME}', resource='cpu'}}"
                RAM_LIMIT_QUERY = "kube_pod_container_resource_limits{{pod='{POD_NAME}', resource='memory'}}"
                GPU_LIMIT_QUERY = "kube_pod_container_resource_limits{{pod='{POD_NAME}', resource='nvidia_com_gpu'}}"
                
                with prometheus_connection(url) as prom:
                    # prometheus query ================================================================================
                    tmp_cpu_usage = prom.custom_query(query=CPU_USAGE_QUERY.format(POD_NAME=pod_name))
                    cpu_usage = tmp_cpu_usage[0]['value'][1] if len(tmp_cpu_usage) > 0 else 0
                    tmp_ram_usage = prom.custom_query(query=RAM_USAGE_QUERY.format(POD_NAME=pod_name))
                    ram_usage = tmp_ram_usage[0]['value'][1] if len(tmp_ram_usage) > 0 else 0
                    
                    tmp_cpu_limit = prom.custom_query(query=CPU_LIMIT_QUERY.format(POD_NAME=pod_name))
                    cpu_limit = tmp_cpu_limit[0]['value'][1] if len(tmp_cpu_limit) > 0 else 0
                    tmp_ram_limit = prom.custom_query(query=RAM_LIMIT_QUERY.format(POD_NAME=pod_name))
                    ram_limit = tmp_ram_limit[0]['value'][1] if len(tmp_ram_limit) > 0 else 0
                    tmp_gpu_limit = prom.custom_query(query=GPU_LIMIT_QUERY.format(POD_NAME=pod_name))
                    gpu_limit = tmp_gpu_limit[0]['value'][1] if len(tmp_gpu_limit) > 0 else 0
                    
                    tmp_cpu_range = prom.custom_query_range(query=CPU_USAGE_QUERY.format(POD_NAME=pod_name), start_time=start_time, end_time=end_time, step='10s')
                    cpu_range = tmp_cpu_range[0]['values'] if len(tmp_cpu_range) else []
                    
                    tmp_ram_range = prom.custom_query_range(query=RAM_USAGE_QUERY.format(POD_NAME=pod_name), start_time=start_time, end_time=end_time, step='10s')
                    ram_range = tmp_ram_range[0]['values'] if len(tmp_ram_range) else []

                    # 계산 ================================================================================
                    cpu_percentage = format((float(cpu_usage) / float(cpu_limit)) * 100, ".3f") if cpu_limit != 0 else 0
                    ram_percentage = format((float(ram_usage) / float(ram_limit)) * 100, ".3f") if ram_limit != 0 else 0
                    cpu_history = []
                    for x, value in enumerate(cpu_range):
                        if len(value) >= 2:
                            cpu_history.append({
                                'x' : x * 10,
                                CPU_USAGE_ON_POD_KEY : format((float(value[1]) / float(cpu_limit)) * 100, ".3f") if ram_limit != 0 else 0,
                            })
                    mem_history = []
                    for x, value in enumerate(ram_range):
                        if len(value) >= 2:
                            mem_history.append({
                                'x' : x * 10,
                                MEM_USAGE_KEY : value[1],
                                MEM_USAGE_PER_KEY : format((float(value[1]) / float(ram_limit)) * 100, ".3f") if ram_limit != 0 else 0
                            })
                    # result ================================================================================
                    result = {
                        "deployment_worker_id": worker.get('deployment_worker_id'), 
                        'cpu_cores' : {'total' : cpu_limit, 'usage' : cpu_usage, 'percentage' : cpu_percentage},
                        'ram' : {'total' : ram_limit, 'usage' : ram_usage, 'percentage' : ram_percentage},
                        'gpus' : gpu_limit,
                        'cpu_history' : cpu_history, 'mem_history' : mem_history, "gpu_history" : []
                    }
                    
                print(f'[resource/deployment_worker] {result}', file=sys.stderr)
                sys.stderr.flush()
                redis_client.hset(redis_key.DEPLOYMENT_WORKER_RESOURCE, str(worker.get('deployment_worker_id')), json.dumps(result))
            # redis_client.set(redis_key.DEPLOYMENT_WORKER_RESOURCE, json.dumps(result))
        except:
            traceback.print_exc()
            pass

def get_gpu_resource_utilization():
    while(True):
        try:
            time.sleep(1)
            result={}
            redis_client= get_redis_client()
            
            with prometheus_connection(url) as prom:
                gpu_list = prom.custom_query(query=REDIS_GPU_INFO)
                gpu_core_list = prom.custom_query(query=GPU_USAGE_RATE)
                gpu_mem_used_list = prom.custom_query(query=GPU_MEMORY_USAGE)
                gpu_mem_free_list = prom.custom_query(query=GPU_MEMORY_CAPACITY_ALL)
                
                # UUID 매핑 생성
                uuid_gpu_core_list = {}
                uuid_gpu_free_list = {}
                uuid_gpu_used_list = {}
                
                # 기본 GPU UUID로 매핑
                for item in gpu_core_list:
                    uuid = get_gpu_uuid(item['metric'])
                    uuid_gpu_core_list[uuid] = item
                
                for item in gpu_mem_free_list:
                    uuid = get_gpu_uuid(item['metric'])
                    uuid_gpu_free_list[uuid] = item
                
                for item in gpu_mem_used_list:
                    uuid = get_gpu_uuid(item['metric'])
                    uuid_gpu_used_list[uuid] = item

                for item in gpu_list:
                    gpu_uuid = get_gpu_uuid(item['metric'])
                    
                    # GPU 정보가 없는 경우 건너뛰기
                    if gpu_uuid not in uuid_gpu_core_list or gpu_uuid not in uuid_gpu_free_list or gpu_uuid not in uuid_gpu_used_list:
                        continue
                        
                    try:
                        mem_used = float(uuid_gpu_used_list[gpu_uuid]['value'][1])
                        mem_free = float(uuid_gpu_free_list[gpu_uuid]['value'][1])
                        mem_total = mem_used + mem_free
                        
                        result = {
                            "gpu_uuid" : gpu_uuid,
                            "gpu_core" : float(uuid_gpu_core_list[gpu_uuid]['value'][1]) if float(uuid_gpu_core_list[gpu_uuid]['value'][1]) > 0 else 0,
                            "gpu_mem" : {
                                'percentage' : (mem_used / mem_total) * 100 if mem_total != 0 else 0,
                                'used' : mem_used,
                                'free' : mem_free,
                                'total' : mem_total
                            }
                        }
                        
                        print(f'[resource/gpu_usage] {json.dumps(result)}', file=sys.stderr)
                        sys.stderr.flush()
                        redis_client.hset(redis_key.GPU_RESOUCE_UTILIZATION, gpu_uuid, json.dumps(result))
                    except (KeyError, ValueError, TypeError) as e:
                        print(f"Error processing GPU {gpu_uuid}: {str(e)}", file=sys.stderr)
                        continue
                        
        except:
            traceback.print_exc()
            pass

# ===========================================================================================================================
# LLMops
# ===========================================================================================================================

def get_model_commit_pod():
    
    def delete_helm_model_commit(model_id : int, workspace_id : int):
        try:
            # os.chdir("/app/helm_chart/")
            namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
            command=f"helm uninstall {TYPE.MODEL_COMMIT_JOB_HELM_NAME.format(MODEL_ID=model_id)} -n {namespace}"
            
            # print(command, file=sys.stderr)
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return 1, result.stdout
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.strip()
            if "cannot re-use a name that is still in use" in err_msg:
                return True, ""
            # print(e.stdout)
            # print(err_msg)
            # print(command)
            return False ,err_msg
    
    while True:
        try:
            time.sleep(1.5)  # API 호출 주기(1초)와 다르게 설정하여 Race condition 최소화
            with prometheus_connection(url) as prom:
                model_commit_pods = prom.custom_query(query=MODEL_COMMIT_POD_STATUS)
                

                for pod in model_commit_pods:
                    pod_info=pod['metric']
                    workspace_id = pod_info["label_workspace_id"]
                    model_id = pod_info["label_model_id"]
                    tmp_terminated = prom.custom_query(query=CONTAINER_STATUS_TERMINATED.format(POD_NAME=pod_info['pod']))
                    pod_terminated = tmp_terminated[0]['metric']['reason'] if tmp_terminated and tmp_terminated[0] is not None else None
                    if pod_terminated is not None:
                        if pod_terminated == "Completed":
                            status = TYPE.KUBE_POD_STATUS_DONE
                            if model_db.update_model_commit_status_sync(commit_status=status, model_id=model_id):
                                delete_helm_model_commit(workspace_id=workspace_id, model_id=model_id)
                        else:
                            print("="*20)
                            print("commit model kill reason")
                            print(pod_terminated)
                            print("="*20)
                            status = TYPE.KUBE_POD_STATUS_ERROR
                            if model_db.update_model_commit_status_sync(commit_status=status, model_id=model_id):
                                delete_helm_model_commit(workspace_id=workspace_id, model_id=model_id)
        except:
            traceback.print_exc()