from prometheus_api_client import PrometheusConnect, MetricSnapshotDataFrame, MetricRangeDataFrame
from kubernetes import client, config
from contextlib import contextmanager
from collections import defaultdict
from utils.settings import PROMETHEUS_DNS
import json
import traceback
from utils.resource import response
from utils.PATH import *
from utils import PATH_NEW, TYPE, common
import utils.msa_db.db_storage as storage_db
import utils.msa_db.db_workspace as ws_db
import utils.msa_db.db_node as node_db
import utils.msa_db.db_dataset as dataset_db
import utils.msa_db.db_project as project_db
import utils.msa_db.db_deployment as deployment_db
from helm_run import create_node_init_job, delete_helm
import math
import requests
import os
import sys
from utils import settings
import time
from utils import redis_key, notification_key
from utils.redis import get_redis_client
import subprocess
from utils.mongodb import insert_user_dashboard_timeline, get_user_dashboard_timeline, insert_admin_dashboard_timeline, NotificationWorkspace, insert_notification_history, get_resource_over_message
# from utils.mongodb_key import DASHBOARD_TIMELINE
import datetime
import requests

"""
prometheus promql query start

"""
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


GPU_USAGE_RATE ="DCGM_FI_DEV_GPU_UTIL * 100"
GPU_TEMPERATURE = "DCGM_FI_DEV_GPU_TEMP" # count를 사용해서 gpu 개수를 구해도 될것같음.
GPU_MEMORY_USAGE = "DCGM_FI_DEV_FB_USED"
GPU_MEMORY_CAPACITY = "DCGM_FI_DEV_FB_FREE{{Hostname='{HOST_NAME}',modelName='{GPU_MODEL}'}}"

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

DATASET_FILEBROWSER_STATUS_READY="kube_pod_container_status_ready{{pod='{POD_NAME}'}}"
DATASET_FILEBROWSER_POD_LIST="kube_pod_labels{{label_dataset_id='{DATASET_ID}'}}"
REDIS_WORKSPACE_POD_LITS="kube_pod_labels{{label_workspace_id='{workspace_id}'}}"
TRAINING_POD_LIST="kube_pod_labels{label_work_func_type='training'}"
HPS_POD_LIST="kube_pod_labels{label_work_func_type='hps'}"
TOOL_POD_DNS = "http://{SERVICE_NAME}.{NAMESPACE}.svc.cluster.local"
POD_STATUS="kube_pod_status_phase{{pod='{POD_NAME}'}}==1"
POD_STATUS_REASON="kube_pod_status_reason{{pod='{POD_NAME}'}}==1"
POD_START_TIME="kube_pod_start_time{{pod='{POD_NAME}'}}"
POD_END_TIME="kube_pod_completion_time{{pod='{POD_NAME}'}}"

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

MONITORING_DNS=os.environ.get('JF_MONITORING_URL')
url="http://{DNS}/prometheus".format(DNS=MONITORING_DNS)


CONTAINER_STATUS_READY_TRUE="kube_pod_container_status_ready{{pod='{POD_NAME}'}}==1"
CONTAINER_STATUS_READY_FALSE="kube_pod_container_status_ready{{pod='{POD_NAME}'}}==0"
CONTAINER_STATUS_RUNNING="kube_pod_container_status_running{{pod='{POD_NAME}'}}==1"
CONTAINER_STATUS_WAITING="kube_pod_container_status_waiting_reason{{pod='{POD_NAME}'}}==1"
CONTAINER_STATUS_TERMINATED="kube_pod_container_status_terminated_reason{{pod='{POD_NAME}'}}==1"
CONTAINER_RESTART_TOTAL="kube_pod_container_status_restarts_total{{pod='{POD_NAME}'}}"


DEPLOYMENT_POD_RESOURCE_LIMIT_CPU = "kube_pod_container_resource_limits{{pod='{POD_NAME}', resource='cpu'}}"
DEPLOYMENT_POD_RESOURCE_LIMIT_RAM = "kube_pod_container_resource_limits{{pod='{POD_NAME}', resource='memory'}}"

"""
prometheus promql query end

"""

redis_client = get_redis_client()

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
                # redis=get_redis_client()
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
def set_filebrowser_pod_list():
    while(True):
        try:
            # redis=get_redis_client()
            # redis.delete(redis_key.DATASET_FILEBROWSER_POD_STATUS)
            # print(redis.hgetall(redis_key.DATASET_FILEBROWSER_POD_STATUS))
            dataset_list=dataset_db.get_dataset_list()
            for dataset_info in dataset_list:
                with prometheus_connection(url) as prom:
                    filebrowser_list=prom.custom_query(query=DATASET_FILEBROWSER_POD_LIST.format(DATASET_ID=dataset_info['id']))
                    if not filebrowser_list :
                        if dataset_info['filebrowser']==0:
                            redis_client.hdel(redis_key.DATASET_FILEBROWSER_POD_STATUS, dataset_info['id'])
                            continue
                    else:
                        # redis.hdel(redis_key.DATASET_FILEBROWSER_POD_STATUS,'2')
                        # pod_info_list=[]
                        filebrowser_list_df = MetricSnapshotDataFrame(filebrowser_list)
                        for _, filebrowser_info in filebrowser_list_df.iterrows():
                            ready_check = prom.custom_query(DATASET_FILEBROWSER_STATUS_READY.format(POD_NAME=filebrowser_info.pod))
                            metric=prom.custom_query(POD_STATUS.format(POD_NAME=filebrowser_info.pod))
                            if ready_check:
                                if dataset_info['filebrowser']==0:
                                    if metric:
                                       phase = TYPE.KUBE_POD_STATUS_PENDING
                                    # else:
                                    #     redis.hdel(redis_key.DATASET_FILEBROWSER_POD_STATUS, filebrowser_info.label_dataset_id)
                                    #     continue
                                else:
                                    if ready_check[0]['value'][1] == '1':
                                            # phase=TYPE.KUBE_POD_STATUS_PENDING
                                        response = requests.get("http://"+settings.EXTERNAL_HOST+'/'+filebrowser_info.label_ingress_path, timeout=5)
                                        if response.status_code == 200:
                                            phase = TYPE.KUBE_POD_STATUS_RUNNING
                                        else:
                                            phase = TYPE.KUBE_POD_STATUS_PENDING
                                        # print(phase)
                                    else:
                                        if metric:
                                            phase=metric[0]['metric']['phase']
                                            if phase =="Failed":
                                                phase = TYPE.KUBE_POD_STATUS_ERROR
                                            elif phase =="Pending":
                                                phase = TYPE.KUBE_POD_STATUS_PENDING
                                            else:
                                                phase = None
                            # else:
                            #     redis.hdel(redis_key.DATASET_FILEBROWSER_POD_STATUS, filebrowser_info.label_dataset_id)
                            #     continue
                                # phase = None
                            if phase is not None:
                                pod_info={
                                    'url' : f"/{filebrowser_info.label_ingress_path}",
                                    'pod_status' : phase
                                }
                                # print(pod_info)
                                redis_client.hset(redis_key.DATASET_FILEBROWSER_POD_STATUS, filebrowser_info.label_dataset_id, json.dumps(pod_info))
                # print(redis.hgetall(redis_key.DATASET_FILEBROWSER_POD_STATUS))
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
                }
            }
            # redis=get_redis_client()
            cpu_info_list = redis_client.hgetall(redis_key.CPU_INFO_RESOURCE)
            ram_info_list = redis_client.hgetall(redis_key.MEM_INFO_RESOURCE)
            gpu_info_list = redis_client.get(redis_key.GPU_INFO_RESOURCE)
            storage_info = redis_client.get(redis_key.STORAGE_LIST_RESOURCE)




            for _, cpu_info in cpu_info_list.items():
                cpu_info=json.loads(cpu_info)
                result['cpu']['total_cpu'] += int(cpu_info['cpu_core'])
                result['cpu']['used_cpu'] += float(cpu_info['cpu_usage'])
            for _, ram_info in ram_info_list.items():
                ram_info=json.loads(ram_info)
                result['ram']['total_ram'] += int(ram_info['mem_total'])
                result['ram']['used_ram'] += int(ram_info['mem_used'])
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
            create_time = datetime.datetime.now()
            result['create_datetime'] = create_time
            result['pricing']=[]
            # print(result)
            res,message = insert_admin_dashboard_timeline(result)
            time.sleep(60)
        except:
            traceback.print_exc()
            pass


def insert_mongodb_user_dashboard_timeline():
    import sys
    while(True):
        try:
            workspace_list = ws_db.get_workspace_list()
            if workspace_list:
                # redis=get_redis_client()
                storage_info = json.loads(redis_client.get(redis_key.STORAGE_LIST_RESOURCE))
                workspace_resource_usage_list = redis_client.hgetall(redis_key.WORKSPACE_RESOURCE_QUOTA) # id
                create_time = datetime.datetime.now()
                # print(create_time)
                for workspace in workspace_list:
                    # print(workspace)
                    result={}
                    result['workspace_id'] = workspace['id']
                    result['create_datetime'] = create_time
                    main_storage_usage_list = storage_info[str(workspace['main_storage_id'])].get('workspaces', [])
                # print(main_storage_usage_list)
                    for main_storage in main_storage_usage_list['main']:
                        if main_storage['workspace_name'] == workspace['name']:
                            result['storage_main']={}
                            result['storage_main']['total']=main_storage['alloc_size']
                            result['storage_main']['used']=main_storage['used_size']
                            data_storage_usage_list = storage_info[str(workspace['data_storage_id'])].get('workspaces', [])
                    for data_storage in data_storage_usage_list['data']:
                        if data_storage['workspace_name'] == workspace['name']:
                            result['storage_data']={}
                            result['storage_data']['total']=data_storage['alloc_size']
                            result['storage_data']['used']=data_storage['used_size']
                    resource_usage = json.loads(workspace_resource_usage_list.get(str(workspace['id']) , {'ram': {'hard':0, 'used':0}, 'cpu': {'hard':0, 'used':0}, 'gpu': {'hard':0, 'used':0}}))
                    result['cpu']=resource_usage['cpu']
                    cpu_usage_percent = (result['cpu']['used'] / result['cpu']['hard'] ) * 100 if result['cpu']['hard'] > 0 else 0
                    result['gpu']=resource_usage['gpu']
                    result['ram']=resource_usage['ram']
                    ram_usage_percent = (result['ram']['used'] / result['ram']['hard']) * 100 if result['cpu']['hard'] > 0 else 0
                    main_storage_percent = (result['storage_main']['used'] / result['storage_main']['total']) * 100 if result['storage_main']['total'] > 0 else 0
                    data_storage_percent = (result['storage_data']['used'] / result['storage_data']['total']) * 100 if result['storage_data']['total'] > 0 else 0

                    result['pricing']={}
                    if cpu_usage_percent > 80:
                        message=notification_key.WORKSPACE_INSTANCE_RESOURCE_CPU_OVER.format(workspace_name=workspace["name"])
                        manager_id = workspace["manager_id"]
                        # print("resource over : ", get_resource_over_message(user_id=manager_id,workspace_id = workspace['id']), file=sys.stderr)
                        if not get_resource_over_message(user_id=manager_id, workspace_id = workspace['id'], message=message):

                            notification = NotificationWorkspace(
                                user_id=manager_id,
                                noti_type=notification_key.NOTIFICATION_TYPE_RESOURCE,
                                user_type=notification_key.NOTIFICATION_USER_TYPE_WORKSPACE_MANAGER,
                                message=message,
                                workspace_id = workspace['id'],
                                create_datetime=datetime.datetime.now()
                            )
                            res, message = insert_notification_history(notification)
                    if ram_usage_percent > 80:
                        message=notification_key.WORKSPACE_INSTANCE_RESOURCE_RAM_OVER.format(workspace_name=workspace["name"])
                        manager_id = workspace["manager_id"]
                        # print("resource over : ", get_resource_over_message(user_id=manager_id,workspace_id = workspace['id']), file=sys.stderr)
                        if not get_resource_over_message(user_id=manager_id, workspace_id = workspace['id'], message=message):

                            notification = NotificationWorkspace(
                                user_id=manager_id,
                                noti_type=notification_key.NOTIFICATION_TYPE_RESOURCE,
                                user_type=notification_key.NOTIFICATION_USER_TYPE_WORKSPACE_MANAGER,
                                message=message,
                                workspace_id = workspace['id'],
                                create_datetime=datetime.datetime.now()
                            )
                            res, message = insert_notification_history(notification)
                    if main_storage_percent > 80 and main_storage_percent < 100:
                        message=notification_key.WORKSPACE_INSTANCE_RESOURCE_MAIN_STORAGE_OVER.format(workspace_name=workspace["name"])
                        manager_id = workspace["manager_id"]
                        # print("resource over : ", get_resource_over_message(user_id=manager_id,workspace_id = workspace['id']), file=sys.stderr)
                        if not get_resource_over_message(user_id=manager_id, workspace_id = workspace['id'], message=message):

                            notification = NotificationWorkspace(
                                user_id=manager_id,
                                noti_type=notification_key.NOTIFICATION_TYPE_RESOURCE,
                                user_type=notification_key.NOTIFICATION_USER_TYPE_WORKSPACE_MANAGER,
                                message=message,
                                workspace_id = workspace['id'],
                                create_datetime=datetime.datetime.now()
                            )
                            res, message = insert_notification_history(notification)
                    elif main_storage_percent > 100:
                        message=notification_key.WORKSPACE_INSTANCE_RESOURCE_MAIN_STORAGE_100_OVER.format(workspace_name=workspace["name"])
                        manager_id = workspace["manager_id"]
                        # print("resource over : ", get_resource_over_message(user_id=manager_id,workspace_id = workspace['id']), file=sys.stderr)
                        if not get_resource_over_message(user_id=manager_id, workspace_id = workspace['id'], message=message):

                            notification = NotificationWorkspace(
                                user_id=manager_id,
                                noti_type=notification_key.NOTIFICATION_TYPE_RESOURCE,
                                user_type=notification_key.NOTIFICATION_USER_TYPE_WORKSPACE_MANAGER,
                                message=message,
                                workspace_id = workspace['id'],
                                create_datetime=datetime.datetime.now()
                            )
                            res, message = insert_notification_history(notification)
                    if data_storage_percent > 80 and data_storage_percent < 100:
                        message=notification_key.WORKSPACE_INSTANCE_RESOURCE_DATA_STORAGE_OVER.format(workspace_name=workspace["name"])
                        manager_id = workspace["manager_id"]
                        # print("resource over : ", get_resource_over_message(user_id=manager_id,workspace_id = workspace['id']), file=sys.stderr)
                        if not get_resource_over_message(user_id=manager_id, workspace_id = workspace['id'], message=message):

                            notification = NotificationWorkspace(
                                user_id=manager_id,
                                noti_type=notification_key.NOTIFICATION_TYPE_RESOURCE,
                                user_type=notification_key.NOTIFICATION_USER_TYPE_WORKSPACE_MANAGER,
                                message=message,
                                workspace_id = workspace['id'],
                                create_datetime=datetime.datetime.now()
                            )
                            res, message = insert_notification_history(notification)
                    elif main_storage_percent > 100:
                        message=notification_key.WORKSPACE_INSTANCE_RESOURCE_DATA_STORAGE_100_OVER.format(workspace_name=workspace["name"])
                        manager_id = workspace["manager_id"]
                        # print("resource over : ", get_resource_over_message(user_id=manager_id,workspace_id = workspace['id']), file=sys.stderr)
                        if not get_resource_over_message(user_id=manager_id, workspace_id = workspace['id'], message=message):

                            notification = NotificationWorkspace(
                                user_id=manager_id,
                                noti_type=notification_key.NOTIFICATION_TYPE_RESOURCE,
                                user_type=notification_key.NOTIFICATION_USER_TYPE_WORKSPACE_MANAGER,
                                message=message,
                                workspace_id = workspace['id'],
                                create_datetime=datetime.datetime.now()
                            )
                            res, message = insert_notification_history(notification)
                    # storage_usage = storage_usage_list.get(workspace['name'] , {'main':0, 'data':0})
                    res,message = insert_user_dashboard_timeline(result)
                    # if res :
            time.sleep(60)
        except:
            traceback.print_exc()


def set_project_storage_usage_info():
    while(True):
        try:
            project_list = project_db.get_project_list()
            if not project_list :
                continue
            with prometheus_connection(url) as prom:
                project_list_df=MetricSnapshotDataFrame(prom.custom_query(query=PROJECT_USAGE_INFO))
                if project_list_df.empty:
                    continue
                # redis=get_redis_client()

                for project in project_list:
                    # workspace_info = ws_db.get_workspace(workspace_id=project['workspace_id'])
                    # storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
                    # project_path = PATH_NEW.JF_MAIN_PROJECT_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'] , PROJECT_NAME= project['name'])
                    project_df = project_list_df[project_list_df['name']==project['name']]
                    for _, usage in project_df.iterrows():
                        redis_client.hset(redis_key.PROJECT_STORAGE_USAGE, project['id'], int(usage['value']))
        except:
            traceback.print_exc()
            pass


def set_dataset_storage_usage_info():
    while(True):
        try:
            dataset_list = dataset_db.get_dataset_list()
            if not dataset_list :
                continue
            with prometheus_connection(url) as prom:
                dataset_list_df=MetricSnapshotDataFrame(prom.custom_query(query=DATASET_USAGE_INFO))
                if dataset_list_df.empty:
                    continue
                # redis=get_redis_client()

                for dataset in dataset_list:
                    # workspace_info = ws_db.get_workspace(workspace_id=dataset['workspace_id'])
                    # storage_info = storage_db.get_storage(storage_id=workspace_info['data_storage_id'])
                    # dataset_path = PATH_NEW.JF_DATA_DATASET_PATH.format(STORAGE_NAME=storage_info['name'], WORKSPACE_NAME=workspace_info['name'] ,ACCESS=dataset['access'], DATASET_NAME= dataset['dataset_name'])
                    dataset_df = dataset_list_df[dataset_list_df['name']==dataset['dataset_name']]
                    for _, usage in dataset_df.iterrows():
                        redis_client.hset(redis_key.DATASET_STORAGE_USAGE, dataset['dataset_name'], int(usage['value']))
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
                main_storage_path = PATH_NEW.JF_MAIN_STORAGE_PATH.format(STORAGE_NAME=storage_list[workspace['main_storage_id']] , WORKSPACE_NAME=workspace['name'])
                data_storage_path = PATH_NEW.JF_DATA_STORAGE_PATH.format(STORAGE_NAME=storage_list[workspace['data_storage_id']] , WORKSPACE_NAME=workspace['name'])
                workspace_path = [main_storage_path, data_storage_path]
                storage_usage={}
                # redis=get_redis_client()
                with prometheus_connection(url) as prom:
                    ws_usage_list_df=MetricSnapshotDataFrame(prom.custom_query(query=WORKSAPCE_USAGE_INFO))
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
            with prometheus_connection(url) as prom:
                node_list=prom.custom_query(query=REDIS_NODE_INFO)
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

def test():
    try:
        # node_info = node_db.get_node(node_id=node_id)
        # res, output =create_node_init_job(node_id=node_id, node=node_info['name'])
        # print(res)
        # print(output)

        # print(get_user_dashboard_timeline(now_date=datetime.datetime.now(), workspace_id=2))
        return True
    except:
        traceback.print_exc()
        return False

def init_node_info():
    try:
        with prometheus_connection(url) as prom:
            node_list=prom.custom_query(query=REDIS_NODE_INFO)
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

                    for _, gpu in gpu_info.iterrows():
                        if not node_db.get_node_gpu(gpu_uuid=gpu['UUID']):
                            gpu_resource_group=node_db.get_resource_group(name=gpu['modelName'])
                            if gpu_resource_group is None:
                                gpu_resource_group_id = node_db.insert_resource_group(name=gpu['modelName'])
                            else:
                                gpu_resource_group_id = gpu_resource_group['id']
                            node_db.insert_node_gpu(node_id=node_id, resource_group_id=gpu_resource_group_id,gpu_memory=gpu['value'], gpu_uuid=gpu['UUID'])
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
                        if node_db.get_node_gpu(gpu_uuid=gpu['UUID']) is None:
                            gpu_resource_group=node_db.get_resource_group(name=gpu['modelName'])
                            if gpu_resource_group is None:
                                gpu_resource_group_id = node_db.insert_resource_group(name=gpu['modelName'])
                            else:
                                gpu_resource_group_id = gpu_resource_group['id']
                            # print(gpu_resource_group_id)
                            node_db.insert_node_gpu(node_id=node['id'], resource_group_id=gpu_resource_group_id,gpu_memory=gpu['value'], gpu_uuid=gpu['UUID'])

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
                gpu_uuid=gpu_info['metric']['UUID']
                model_name=gpu_info['metric']['modelName']
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
                    "used_info": {}
                }
        # print(result)
        # redis=get_redis_client()
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
            with prometheus_connection(url) as prom:
                node_list = prom.custom_query(query=NODE_LIST)
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
                        'cpu_core' : cpu_core,
                        'cpu_usage' : cpu_usage
                    }
                    # redis.delete(redis_key.CPU_INFO_RESOURCE)
                    redis_client.hset(redis_key.CPU_INFO_RESOURCE, hostname, json.dumps(cpu))

        except:
            traceback.print_exc()
            pass

def set_mem_info_to_redis():
    while(True):
        try:
            time.sleep(1)
            result={}
            redis=get_redis_client()
            with prometheus_connection(url) as prom:
                node_list = prom.custom_query(query=NODE_LIST)
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
                    mem_info={
                        'mem_total' : mem_total_byte,
                        'mem_avail' : mem_avail_byte,
                        'mem_used' : mem_total_byte-mem_avail_byte
                    }
                    redis.hset(redis_key.MEM_INFO_RESOURCE, hostname, json.dumps(mem_info))
            redis.close()
        except:
            traceback.print_exc()
            pass

def set_workspace_pod_status():
    import sys
    from utils.msa_db import db_project, db_workspace
    from utils.TYPE import PROJECT_HELM_CHART_NAME

    def gpu_reset():
        result={}
        with prometheus_connection(url) as prom:
            gpu_list = prom.custom_query(query=REDIS_GPU_INFO)
            for gpu_info in gpu_list:
                hostname=gpu_info['metric']['Hostname']
                gpu_uuid=gpu_info['metric']['UUID']
                model_name=gpu_info['metric']['modelName']
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

    def delete_helm_resource(project_item_type : str, project_item_id : int):
        try:
            # os.chdir("/app/helm_chart/")
            command=f"helm uninstall {PROJECT_HELM_CHART_NAME.format(project_item_id, project_item_type)} -n {settings.JF_SYSTEM_NAMESPACE}"

            print(command)
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
            print(e.stdout)
            print(err_msg)
            print(command)
            return False ,err_msg

    def clear_gpu_usage(gpu_uuid):
        """Clear the GPU usage information."""
        gpu_uuid["used"] = 0
        gpu_uuid["used_type"] = None
        gpu_uuid["used_info"] = {}

    def extract_resources(data):
        resources = {"cpu": None, "gpu": None, "ram": None}

        for item in data:
            metric = item.get("metric", {})
            resource_type = metric.get("resource")
            value = item.get("value", [])[1]

            if resource_type == "cpu":
                resources["cpu"] = float(value)  # CPU 코어 수
            elif resource_type == "nvidia_com_gpu":
                resources["gpu"] = int(value)  # GPU 개수
            elif resource_type == "memory":
                resources["ram"] = int(value) / (1024 ** 3)  # RAM 기가바이트로 변환

        return resources

    def insert_gpu_usage(pod_info, gpu_uuids, gpu_status):
        item_type = pod_info["label_work_func_type"] if pod_info["label_work_func_type"] == "deployment" else "project"
        if item_type == "project":
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
        else:
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

    # consumer = Consumer(conf)
    while(True):
        try:
            time.sleep(0.1)
            workspace_list = db_workspace.get_workspace_list()

            # prometheus pod search
            with prometheus_connection(url) as prom:
                gpu_status = gpu_reset()
                # redis_con.set(redis_key.GPU_INFO_RESOURCE, json.dumps(gpu_status))
                for workspace in workspace_list:

                    workspace_pod_list = prom.custom_query(query=REDIS_WORKSPACE_POD_LITS.format(workspace_id=workspace["id"]))
                    # tool_status = redis_con.hget(redis_key.TOOL_PODS_STATUS_WORKSPACE.format(workspace_id=workspace["id"]), "tools")
                    # gpu_status = json.loads(redis_con.get(redis_key.GPU_INFO_RESOURCE))


                    workspace_pods = common.make_nested_dict()
                    for pod_info in workspace_pod_list:
                        # TODO
                        # DB sync 로직 추가

                        pod_info=pod_info['metric']
                        workspace_id = pod_info["label_workspace_id"]
                        instance_id = pod_info["label_instance_id"]
                        # workspace_instances[instance_id] += 1
                        node_name = pod_info.get("label_node_name", None)
                        gpu_ids = pod_info["label_gpu_ids"].split(".") if pod_info.get("label_gpu_ids", None) else []
                        gpu_uuids = []
                        for gpu_id in gpu_ids:
                            if gpu_id:
                                # print(gpu_id)
                                gpu_uuid = node_db.get_node_gpu(gpu_id=gpu_id)["gpu_uuid"]
                                gpu_uuids.append(gpu_uuid)

                        pod_status = prom.custom_query(query=POD_STATUS.format(POD_NAME=pod_info['pod']))

                        tmp_pod_status_reason = prom.custom_query(query=POD_STATUS_REASON.format(POD_NAME=pod_info['pod']))
                        pod_status_reason = tmp_pod_status_reason[0]['metric']["reason"] if tmp_pod_status_reason and tmp_pod_status_reason[0] is not None else None

                        # print(pod_status)
                        # POD_RESOURCE_LIMIT
                        tmp_resources = prom.custom_query(query=POD_RESOURCE_LIMIT.format(POD_NAME=pod_info['pod']))
                        pod_resource = extract_resources(tmp_resources)

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
                                    print(pod_waiting, file=sys.stderr)
                                    resolution = container_waiting_reason[pod_waiting] if pod_waiting in container_waiting_reason.keys() else container_waiting_reason["others"]

                                    if pod_info["label_work_func_type"] in ["training", "hps"]:
                                        if pod_end_time:
                                            parse_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(pod_end_time)))
                                        else:
                                            parse_time = time.strftime('%Y-%m-%d %H:%M:%S')
                                        project_item_id = pod_info["label_project_item_id"]
                                        project_item_type = pod_info["label_work_func_type"]
                                        db_project.update_project_item_datetime(item_id=project_item_id, item_type=project_item_type, end_datetime=parse_time, end_status=status, error_reason=resolution)
                                        delete_helm_resource(project_item_id=project_item_id, project_item_type=project_item_type)

                            elif pod_terminated is not None:
                                if pod_info["label_work_func_type"] in ["training", "hps"]:
                                    status = TYPE.KUBE_POD_STATUS_DONE if pod_status[0]['metric']['phase'] != "Failed" else TYPE.KUBE_POD_STATUS_ERROR
                                    reason = pod_terminated
                                    resolution = None
                                    project_id = pod_info["label_project_id"]
                                    project_item_id = pod_info["label_project_item_id"]
                                    project_item_type = pod_info["label_work_func_type"]
                                    pod_end_time = prom.custom_query(query=POD_END_TIME.format(POD_NAME=pod_info["pod"]))[0]["value"][1]
                                    if pod_end_time:
                                        parse_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(pod_end_time)))
                                    else:
                                        parse_time = time.strftime('%Y-%m-%d %H:%M:%S')
                                    db_project.update_project_item_datetime(item_id=project_item_id, item_type=project_item_type, end_datetime=parse_time, end_status=status)
                                    delete_helm_resource(project_item_id=project_item_id, project_item_type=project_item_type)


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

                        if pod_info["label_work_func_type"] == "deployment":

                            workspace_pods[pod_info["label_work_func_type"]][pod_info["label_deployment_id"]][pod_info["label_deployment_worker_id"]] = {
                                    'status' : status,
                                    'instance_id' : instance_id,
                                    'reason' : reason,
                                    'resolution' : resolution,
                                    'restart_count' : pod_container_restart_count,
                                    'phase' : pod_status[0]['metric']['phase'] if pod_status else "Unknown",
                                    'resource' : pod_resource
                                }
                        else:
                            if pod_info["label_work_func_type"] in workspace_pods and \
                                pod_info["label_project_item_id"] in workspace_pods[pod_info["label_work_func_type"]] and \
                                workspace_pods[pod_info["label_work_func_type"]][pod_info["label_project_item_id"]]["status"] != TYPE.KUBE_POD_STATUS_RUNNING:
                                pass # 분산학습 시 특정 node의 pod만 실행이 안될경우를 대비해 추가
                            else:
                                # workspace_pods[pod_info["label_work_func_type"]][pod_info["label_project_item_id"]] = {
                                #         'status' : status if status else TYPE.KUBE_POD_STATUS_ERROR,
                                #         'reason' : reason,
                                #         'resolution' : resolution,
                                #         'restart_count' : pod_container_restart_count,
                                #         'phase' : pod_status[0]['metric']['phase'] if pod_status else "Unknown",
                                #     }
                                if int(pod_info["label_pod_count"]) >1:
                                    pod_resource = {
                                        "gpu" : pod_resource["gpu"] * int(pod_info["label_pod_count"]),
                                        "cpu" : pod_resource["cpu"] * int(pod_info["label_pod_count"]),
                                        "ram" : pod_resource["ram"] * int(pod_info["label_pod_count"])
                                    }
                                workspace_pods[TYPE.PROJECT_TYPE][pod_info["label_project_id"]][pod_info["label_work_func_type"]][pod_info["label_project_item_id"]] = {
                                        'status' : status if status else TYPE.KUBE_POD_STATUS_ERROR,
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


# def set_workspace_instance_used():
#     while True:
#         try:
#             redis_con = get_redis_client()
#             workspace_list = ws_db.get_basic_workspace_list()
#             with prometheus_connection(url) as prom:
#                 for workspace in workspace_list:
#                     instance_list = ws_db.get_workspace_instance_list(workspace_id=workspace["id"])
#                     for instance in instance_list:
#                         workspace_pod_list = prom.custom_query(query=REDIS_WORKSPACE_POD_LITS.format(workspace_id=workspace["id"]))


#                         pass

#             pass


def set_storage_usage_info():
    while(True):
        try:
            time.sleep(1)
            result = {}
            storage_list = storage_db.get_storage()
            # redis=get_redis_client()
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
                                    if data_storage_info.empty :
                                        continue
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
                                    if main_storage_info.empty :
                                        continue
                                    main_requests_total += main_storage_request
                                    workspace_name = main_storage_info.iloc[0]['label_workspace_name']
                                    try:
                                        workspace_usage = json.loads(redis_client.hget(redis_key.WORKSPACE_STORAGE_USAGE, workspace_name))
                                        used_size = workspace_usage.get('main',0)
                                    except:
                                        used_size = 0
                                    # workspace_usage = json.loads(redis_client.hget(redis_key.WORKSPACE_STORAGE_USAGE, workspace_name))
                                    # used_size = workspace_usage.get('main',0)
                                    used_size  = 0
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
            # redis=get_redis_client()
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

def workspace_resource_usage():
    while(True):
        try:
            time.sleep(1)
            # redis_client.delete(redis_key.WORKSPACE_RESOURCE_QUOTA)
            # redis=get_redis_client()
            workspace_list = ws_db.get_workspace_list()
            NAMESPACE='jonathan-system-{id}'
            with prometheus_connection(url) as prom:
                try:
                    ws_df = MetricSnapshotDataFrame(prom.custom_query(query=WORKSPACE_RESOURCE_USAGE))
                    for ws in workspace_list:
                        result = {}

                        ws_quota_df=ws_df[(ws_df['namespace']==NAMESPACE.format(id=ws['id']))]
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
                        # print(result)

                        redis_client.hset(redis_key.WORKSPACE_RESOURCE_QUOTA, ws['id'], json.dumps(result))
                    # print(redis_client.hgetall(redis_key.WORKSPACE_RESOURCE_QUOTA))
                except:
                    continue

            # redis.close()
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
        # redis=get_redis_client()
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


def get_workspace_usage():
    global url
    workspace_info=[]
    with prometheus_connection(url) as prom:
        workspace_lists = prom.custom_query(query=WORKSPACE_LIST)
        for workspace in workspace_lists:
            try:
                pvc_name=workspace['metric']['persistentvolumeclaim']
                workspace_avail= int(prom.custom_query(query=WORKSPACE_AVAILABLE.format(PERSISTENTVOULUMECLAIM_NAME=pvc_name))[0]['value'][1])
                workspace_used=int(prom.custom_query(query=WORKSPACE_USED.format(PERSISTENTVOULUMECLAIM_NAME=pvc_name))[0]['value'][1])
                recent_sync_time="2024-05-10 04:19:05"
                workspace_info.append(
                    {
                        "workspace_name": workspace['metric']['label_workspace_name'],
                        "workspace_used": str(workspace_used),
                        "workspace_avail": workspace_avail,
                        "workspace_pcent": str(int((workspace_used/workspace_avail)*100))+"%",
                        "recent_sync_time": recent_sync_time

                    }
                )
            except:
                pass
    return workspace_info

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


def set_deployment_pod_resouce_limit():
    while(True):
        try:
            time.sleep(1)
            result={}
            # redis=get_redis_client()
            worker_list = deployment_db.get_deployment_worker_list(running=True)

            for worker in worker_list:
                pod_name = f"{worker.get('api_path')}-{worker.get('deploymet_worker_id')}-0"
                DEPLOYMENT_POD_RESOURCE_LIMIT_CPU = "kube_pod_container_resource_limits{{pod='{POD_NAME}', resource='cpu'}}"
                DEPLOYMENT_POD_RESOURCE_LIMIT_RAM = "kube_pod_container_resource_limits{{pod='{POD_NAME}', resource='memory'}}"

                with prometheus_connection(url) as prom:
                    cpu = prom.custom_query(query=DEPLOYMENT_POD_RESOURCE_LIMIT_CPU.format(POD_NAME=pod_name))
                    ram = prom.custom_query(query=DEPLOYMENT_POD_RESOURCE_LIMIT_RAM.format(POD_NAME=pod_name))
                    if len(cpu) > 0 and len(ram) > 0:
                        result[str(worker.get('deploymet_worker_id'))] = {'limit' : {"cpu" : cpu[0]['value'][1], "memory" : ram[0]['value'][1]}}
                    else:
                        result[str(worker.get('deploymet_worker_id'))] = {'limit' : {"cpu" : None, "memory" : None}}

            redis_client.set(redis_key.DEPLOYMENT_WORKER_RESOURCE_LIMIT, json.dumps(result))
        except:
            traceback.print_exc()
            pass
