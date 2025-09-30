from utils.resource import CustomResource, response, token_checker
# import utils.db as db
from utils.resource import response
from utils.PATH import JF_WS_DIR
from utils.TYPE import *
from prometheus_api_client import PrometheusConnect
from contextlib import contextmanager
import traceback
import requests
import utils.msa_db.db_storage as storage_db
from storage.helm_run import create_storage_check_job, create_storage_nfs_provisioner, create_storage_pvc, delete_helm, create_storage_exporter
from utils.redis import get_redis_client
from utils.redis_key import STORAGE_LIST_RESOURCE
import json
import time
CEPH_STORAGE_INFO = "ceph_fs_metadata"
STORAGE_TOTAL_SIZE_BYTES = "ceph_pool_max_avail{{pool_id='{POOL_ID}'}}"
STORAGE_USED_SIZE_BYTES = "ceph_pool_stored{{pool_id='{POOL_ID}'}}"
FSTYPE='nfs4'

STORAGE_INFO = "kube_persistentvolumeclaim_info{{persistentvolumeclaim='jfb-{WORKSPACE_NAME}-ws-pvc',service='monitoring-kube-state-metrics'}}" # nfs-client storage class 를 사용한 persistentvolume만 출력
STORAGE_STATUS = "kube_persistentvolume_status_phase == 1" # persistent volume 의 현재 상태들을 출력
STORAGE_CAPACITY_BYTES = "kube_persistentvolume_capacity_bytes{{persistentvolume='{PERSISTENTVOLUME_NAME}', service='monitoring-kube-state-metrics'}}" # persistent volume name을 입력해서 출력해야함 사용중인 byte용량을 알 수 있으면 사용률도 알 수 있음
STORAGE_USED="kubelet_volume_stats_used_bytes{{persistentvolumeclaim='{PERSISTENTVOULUMECLAIM_NAME}'}}"
STORAGE_USAGE="100 * sum(kubelet_volume_stats_used_bytes{{persistentvolumeclaim='{PERSISTENTVOULUMECLAIM_NAME}'}}) by (persistentvolumeclaim)/sum(kubelet_volume_stats_capacity_bytes{{persistentvolumeclaim='{PERSISTENTVOULUMECLAIM_NAME}'}}) by (persistentvolumeclaim)"



# ceph_pool_metadata 메트릭을 통해서 replica 갯수 확인 가능
monitoring_app="jfb-jfb-monitoring-svc.jfb.svc.cluster.local"
url="http://monitoring-kube-prometheus-prometheus.jfb.svc.cluster.local:9090/prometheus"
STORAGECLASS_NAME="storage-{NAME}"


def create_storage(ip, mountpoint, type, name):
    try:
        storageclass_name=STORAGECLASS_NAME.format(NAME=name)
        DATA_SC="storage-{NAME}-data-sc".format(NAME=name)
        MAIN_SC="storage-{NAME}-main-sc".format(NAME=name)

        storage_id = storage_db.insert_storage(ip=ip,name=storageclass_name, mountpoint=mountpoint, type=type, data_sc=DATA_SC, main_sc=MAIN_SC)
        # time.sleep(5)
        if storage_id:
            # res, message = create_storage_pvc(ip=ip, name=storageclass_name, mountpoint=mountpoint)
            # if not res:
            #     delete_helm(name=storageclass_name)
            #     raise Exception(message)
            job_name = "job-"+storageclass_name
            res, message = create_storage_check_job(name=name, helm_name=job_name)
            if not res:
                delete_helm(name=job_name)
                raise Exception(message)

            #위의 helm chart들이 정상적으로 실행되면 아래 helm chart들은 실패할 경우의 수가 존재하지 않음 따라서 res, message를 확인하지 않음
            create_storage_nfs_provisioner(ip=ip, name=DATA_SC, mountpoint=mountpoint+"/data")
            create_storage_nfs_provisioner(ip=ip, name=MAIN_SC, mountpoint=mountpoint+"/main")

            #start storage-exporter
            helm_name=name+"-storage-exporter"
            create_storage_exporter(helm_name=helm_name, name=name, server=ip, mountpoint=mountpoint, storage_id=storage_id)
            return response(status=1, message="success storage create")
    except Exception as e:
        storage_db.delete_storage(name=storageclass_name)
        traceback.print_exc()
        return response(status=0, message=e)

@contextmanager
def prometheus_connection(url):
    prom = PrometheusConnect(url=url, disable_ssl=True)
    try:
        yield prom
    finally:
        # 연결을 닫습니다.
        del prom

def get_workspace_stoarge_usage(workspace_name):
    prom = prometheus_connection(url)
    pv_list = prom.custom_query(query=STORAGE_INFO.format(WORKSPACE_NAME=workspace_name))
    storage_usage_info={}
    #TODO workspace 를 namespace 별로 구분한다면 {namespace=workspace_name} 을 이용해야함
    for pv in pv_list:
        capacity = int(prom.custom_query(query=STORAGE_CAPACITY_BYTES.format(NODE_IP=pv['metric']['persistentvolume']))[0]['value'][1])
        storage_usage_info[pv['metric']['persistentvolume']]={
            'capacity' : capacity,
            'workspace_name' : pv['metric']['namespace'],
            'used' : int(prom.custom_query(query=STORAGE_USED.format(PERSISTENTVOULUMECLAIM_NAME=pv['metric']['persistentvolumeclaim']))[0]['value'][1]), #AllPathInfo(JF_WORKSPACE_PATH.format(workspace_name=pv['metric']['namespace'])).get_disk_usage
            'usage' : (prom.custom_query(query=STORAGE_USAGE.format(PERSISTENTVOULUMECLAIM_NAME=pv['metric']['persistentvolumeclaim']))[0]['value'][1])
        }

redis =get_redis_client()

def get_storage_usage_info():
    global redis
    res =redis.get(STORAGE_LIST_RESOURCE)
    result_dict={'list' : [],
                 'total' : {
                    "total_size": 0,
                    "total_alloc": 0,
                    "total_pcent": ""
                 }}
    if res:
        res=json.loads(res)
        for id, storage in res.items():
            result_dict['list'].append(
                {
                    "id":id,
                    "name": storage['name'],
                    "fstype":storage['type'], #TODO REMOVE
                    "description": None,
                    "workspaces":storage['workspaces'],
                    "usage":{
                        "fstype": storage['type'],
                        "size": storage['total'],
                        "alloc": storage['total_alloc'],
                        "used" : storage['total_used'],
                        "data_used" : storage['data_alloc'],
                        "main_used" : storage['main_alloc'],
                        "avail": storage['avail'],
                        "pcent": str((storage['total_alloc']/storage['total'])*100)+"%"
                    }
                }
            )
            result_dict['total']['total_size'] += storage['total']
            result_dict['total']['total_alloc'] += storage['total_alloc']
        result_dict['total']['total_pcent'] = str((result_dict['total']['total_alloc']/result_dict['total']['total_size'])*100) +"%"
    else:
        storage_list = storage_db.get_storage()
        if storage_list is None:
            return result_dict
        else:
            for storage in storage_list:
                result_dict['list'].append(
                    {
                        "id":storage['id'],
                        "name": storage['name'],
                        "fstype":storage['type'], #TODO REMOVE
                        "description": None,
                        "workspaces":[],
                        "usage":{
                            "fstype": storage['type'],
                            "size": storage['size'],
                            "alloc": 0,
                            "used" : 0,
                            "data_used" : 0,
                            "main_used" : 0,
                            "avail": storage['size'],
                            "pcent": str(0)+"%"
                        }
                    }
                )
                result_dict['total']['total_size'] += storage['size']
            result_dict['total']['total_pcent'] = str(0)+"%"


    return result_dict

    # global url
    # result_dict={
    #     "id": 1,
    #     "physical_name": "/jfbcore",
    #     "logical_name": "MAIN_STORAGE",
    #     "fstype":FSTYPE,
    #     "description": None,
    #     "active": 0,
    #     "create_lock": 0,
    #     "share": 1,
    #     "create_datetime": "2024-04-11 02:17:08",


    # }
    # with prometheus_connection(url) as prom:
    #     storage_info = prom.custom_query(query=CEPH_STORAGE_INFO)[0]['metric']
    #     data_pool_id = storage_info['data_pools']
    #     fs_name = storage_info['name']
    #     total_size_bytes = int(prom.custom_query(query=STORAGE_TOTAL_SIZE_BYTES.format(POOL_ID=data_pool_id))[0]['value'][1])
    #     total_used_bytes = int(prom.custom_query(query=STORAGE_USED_SIZE_BYTES.format(POOL_ID=data_pool_id))[0]['value'][1])
    #     total_avail_bytes= total_size_bytes-total_used_bytes
    #     total_usage_avg = (total_used_bytes/total_size_bytes) * 100
    #     result_dict["usage"] = {
    #         "device": "ceph",
    #         "fstype": FSTYPE,
    #         "size": total_size_bytes,
    #         "used": total_used_bytes,
    #         "avail": total_avail_bytes,
    #         "pcent": str(total_usage_avg)+"%"
    #     }
    #     result_dict['workspaces']=[]

    #     return {
    #         'list' : [result_dict],
    #         "total": {
    #             "total_size": total_size_bytes,
    #             "total_used": total_used_bytes,
    #             "total_pcent": str(total_usage_avg)+"%"
    #         }
    #     }



        # storage_avail_size = prom.custom_query(query=STORAGE_AVAIL_SIZE_BYTES.format()[0]['value'][1])
        # storage_used_size = storage_total_size-storage_avail_size
