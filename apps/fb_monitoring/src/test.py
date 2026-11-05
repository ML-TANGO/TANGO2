from utils.redis import get_redis_client
from utils import redis_key
from prometheus_api_client import PrometheusConnect, MetricSnapshotDataFrame, MetricRangeDataFrame
import json
import traceback
import utils.msa_db.db_storage as storage_db
import utils.msa_db.db_workspace as ws_db
import time
import utils.msa_db.db_node as node_db
import utils.msa_db.db_dataset as dataset_db
import utils.msa_db.db_project as project_db
import utils.msa_db.db_deployment as deployment_db
import os
from contextlib import contextmanager

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

DATASET_FILEBROWSER_STATUS_READY="kube_pod_container_status_ready{{pod='{POD_NAME}'}}"
DATASET_FILEBROWSER_POD_LIST="kube_pod_labels{{label_dataset_id='{DATASET_ID}'}}"
REDIS_WORKSPACE_POD_LITS="kube_pod_labels{{label_workspace_id='{workspace_id}'}}"
TRAINING_POD_LIST="kube_pod_labels{label_work_func_type='training'}"
HPS_POD_LIST="kube_pod_labels{label_work_func_type='hps'}"
TOOL_POD_DNS = "http://{SERVICE_NAME}.{NAMESPACE}.svc.cluster.local"
POD_STATUS="kube_pod_status_phase{{pod='{POD_NAME}'}}==1"
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


@contextmanager
def prometheus_connection(url):
    prom = PrometheusConnect(url=url, disable_ssl=True)
    try:
        yield prom
    finally:
        del prom
# redis=get_redis_client()
# print(redis.get(STORAGE_LIST_RESOURCE))

def set_storage_usage_info():
    try:
        time.sleep(1)
        result = {}
        storage_list = storage_db.get_storage()
        print("=")
        redis=get_redis_client()
        print(storage_list)
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
                                # print(data_storage_info)
                                workspace_name = data_storage_info.iloc[0]['label_workspace_name']
                                print(workspace_name)
                                workspace_usage = json.loads(redis.hget(redis_key.WORKSPACE_STORAGE_USAGE, workspace_name))
                                used_size = workspace_usage.get('data',0)
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
                                workspace_usage = json.loads(redis.hget(redis_key.WORKSPACE_STORAGE_USAGE, workspace_name))
                                used_size = workspace_usage.get('main',0)
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
                redis.set(redis_key.STORAGE_LIST_RESOURCE,json.dumps(result))
                print(redis.get(redis_key.STORAGE_LIST_RESOURCE))
    except:
        traceback.print_exc()
        pass
from utils import PATH
def get_storage_usage_info():
    # while(True):
    try:
        storage_info = storage_db.get_storage()
        storage_list = {}
        for storage in storage_info:
            storage_list[storage['id']]=storage['name']
        workspace_list = ws_db.get_workspace_list()
        # print(workspace_list)
        for workspace in workspace_list :
            main_storage_path = PATH.JF_MAIN_STORAGE_PATH.format(STORAGE_NAME=storage_list[workspace['main_storage_id']] , WORKSPACE_NAME=workspace['name'])
            data_storage_path = PATH.JF_DATA_STORAGE_PATH.format(STORAGE_NAME=storage_list[workspace['data_storage_id']] , WORKSPACE_NAME=workspace['name'])
            workspace_path = [main_storage_path, data_storage_path]
            storage_usage={}
            redis=get_redis_client()
            with prometheus_connection(url) as prom:
                ws_usage_list_df=MetricSnapshotDataFrame(prom.custom_query(query=WORKSAPCE_USAGE_INFO))
                # print(ws_usage_list_df)
                ws_usage_df = ws_usage_list_df[ws_usage_list_df['name']==workspace['name']]
                for _, ws_usage in ws_usage_df.iterrows():
                    # print(ws_usage)
                    storage_usage[ws_usage['type']]=int(ws_usage['value'])
                redis.hset(redis_key.WORKSPACE_STORAGE_USAGE, workspace['name'], json.dumps(storage_usage))
                print(redis.hget(redis_key.WORKSPACE_STORAGE_USAGE, workspace['name']))
            print(redis.hgetall(redis_key.WORKSPACE_STORAGE_USAGE))
    except:
        traceback.print_exc()
        pass

set_storage_usage_info()
get_storage_usage_info()