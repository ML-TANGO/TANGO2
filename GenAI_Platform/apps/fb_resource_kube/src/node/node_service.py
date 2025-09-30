from prometheus_api_client import PrometheusConnect
from contextlib import contextmanager
from collections import defaultdict
from utils.settings import PROMETHEUS_DNS
import json
import traceback
from utils.resource import response
from utils.PATH import *
from utils import common
# import utils.db as db
import math
import requests
from utils.redis import get_redis_client
from utils.redis_key import GPU_INFO_RESOURCE, CPU_INFO_RESOURCE, MEM_INFO_RESOURCE, NODE_INFO, GPU_ALLOC_USAGE
from utils.msa_db import db_node
from node.helm_run import create_node_active_job, delete_helm
import time
import ast
"""
prometheus promql query start

"""
NODE_LIST = "kube_node_info"
CPU_MODEL_INFO="count(node_cpu_info{{instance=~'{NODE_IP}.*'}}) by(instance,model_name)"
NODE_CPU_INFO="machine_cpu_cores{job='kubelet'}" # node:node_num_cpu:sum , machine_cpu_cores{{node='{node}'}}
NODE_CPU_USAGE_RATE="instance:node_cpu:rate:sum{{instance=~'{NODE_IP}.*'}}"
POD_CPU_USAGE_RATE="sum(node_namespace_pod_container:container_cpu_usage_seconds_total:sum_irate{{node='{NODE}'}})"
POD_ALLOCATE_CPU_CORE= "sum(kube_pod_container_resource_requests{{resource='cpu', node='{NODE}'}})"

NODE_MEM_TOTAL="node_memory_MemTotal_bytes{{instance=~'{NODE_IP}.*'}}"
NODE_MEM_AVAIL="node_memory_MemAvailable_bytes{{instance=~'{NODE_IP}.*'}}"
NODE_MEM_POD_REQUESTS= "sum(kube_pod_container_resource_requests{{resource='memory',node='{NODE}'}})"
NODE_MEM_POD_USAGE = "sum(container_memory_usage_bytes{{node='{NODE}'}})"
CLUSTER_MEM_TOTAL_INFO = "machine_memory_bytes{job='kubelet'}"
NODE_MEM_USED="node_memory_Active_bytes{{instance=~'{NODE_IP}.*'}}"


GPU_USAGE_RATE ="DCGM_FI_DEV_GPU_UTIL * 100"
GPU_TEMPERATURE = "DCGM_FI_DEV_GPU_TEMP" # count를 사용해서 gpu 개수를 구해도 될것같음.
GPU_MEMORY_USAGE = "DCGM_FI_DEV_FB_USED"
GPU_MEMORY_CAPACITY = "DCGM_FI_DEV_FB_FREE{{Hostname='{HOST_NAME}',modelName='{GPU_MODEL}'}}"
# kubelet/var/lib/kubelet/pod-resources 를 사용해서 어떤 GPU가 할당되었는지 확인가능


monitoring_app="jfb-jfb-monitoring-svc.jfb.svc.cluster.local"

url="http://monitoring-kube-prometheus-prometheus.jfb.svc.cluster.local:9090/prometheus"
"""
prometheus promql query end

"""

@contextmanager
def prometheus_connection(url):
    prom = PrometheusConnect(url=url, disable_ssl=True)
    try:
        yield prom
    finally:
        del prom

redis_client = get_redis_client()
def get_node_resource_info():
    try:
        result={
            'node_list' : [],
            'usage':{
                'gpu':{
                    'total':0,
                    'used':0,
                    'avail':0,
                    'detail':{}
                },
                'cpu':{
                    'total':0,
                    'used':0,
                    'avail':0
                },
                'mem':{
                    'total':0,
                    'used':0,
                    'avail':0
                }
            }
        }
        # redis_client = get_redis_client()
        print('node-info start')
        node_list = redis_client.hgetall(NODE_INFO)
        gpu_list = json.loads(redis_client.get(GPU_INFO_RESOURCE))
        cpu_list = redis_client.hgetall(CPU_INFO_RESOURCE)
        mem_list = redis_client.hgetall(MEM_INFO_RESOURCE)

        # print(gpu_list)
        # id는 필요한데 RDB 조회시 속도문제??
        def get_node_id_list():
            db_node_info = db_node.get_node_list()
            return { item["name"] : {'id' : item["id"], 'role' : item['role']} for item in db_node_info}
        node_id_list = get_node_id_list()
        # node_id_list = db_node.get_node_list()

        for hostname, info in node_list.items():

            try:
                time3_1 = time.time()

                info=json.loads(info)
                cpu=json.loads(cpu_list[hostname])
                mem=json.loads(mem_list[hostname])
                gpu=gpu_list.get(hostname,None)
                instance = db_node.get_node_instance_list(node_id_list[hostname]['id'])
                memory_info_list=db_node.get_node_ram(node_id=node_id_list[hostname]['id'])
                # print(memory_info)

                mem['device']=[]
                for memory_info in memory_info_list:
                    mem['type']=memory_info['type']
                    mem['device'].append({
                        'type' : memory_info['type'],
                        'speed' : memory_info['speed'],
                        'model' : memory_info['model'],
                        'manufacturer' : memory_info['manufacturer'],
                        'size' : str(int(common.byte_to_gigabyte(memory_info['size'])))+"GB",
                        'count' : memory_info['count']
                    })
                # print(gpu)
                if gpu is not None:
                    result['usage']['gpu']['total'] += len(gpu)
                    for uuid, gpu_info in gpu.items():
                        # print(gpu_info)
                        # print("="*50)
                        # print(uuid)
                        # print(gpu_info)
                        gpu_info_detail = db_node.get_gpu_cuda_info(model=gpu_info['model_name'])
                        # print(gpu_info_detail)
                        gpu[uuid]['cuda_cores'] = gpu_info_detail['cuda_core']
                        gpu[uuid]['architecture'] = gpu_info_detail['architecture']
                        gpu[uuid]['nvlink'] = False
                        gpu[uuid]['mig_mode'] = False #TODO 수정필요


                        if not result['usage']['gpu']['detail'].get(gpu_info['model_name']):
                            result['usage']['gpu']['detail'][gpu_info['model_name']]={
                                'total':0,
                                'used':0,
                                'gpu_mem' : gpu_info['gpu_mem'],
                                'cuda_core' : gpu_info_detail['cuda_core']
                        }
                        result['usage']['gpu']['detail'][gpu_info['model_name']]['total']+=1
                        result['usage']['gpu']['detail'][gpu_info['model_name']]['used']+=gpu_info['used']

                # usage percent
                cpu['used'] = math.ceil(cpu['cpu_core']*cpu['cpu_usage'])
                cpu['cpu_usage']=round(cpu['cpu_usage']*100,2)
                mem['mem_usage']=round((mem['mem_used']/mem['mem_total'])*100,2)
                # gpu_info['gpu_driver']
                result['usage']['cpu']['total']+=int(cpu['cpu_core'])
                result['usage']['cpu']['used']+=cpu['used']
                result['usage']['mem']['total']+=mem['mem_total']
                result['usage']['mem']['used']+=mem['mem_used']

                role_list = ast.literal_eval(node_id_list[hostname]['role'])
                node_types=[]
                if "control-plane" in role_list:
                    node_types.append("manage")
                if "compute" in role_list:
                    if gpu is None:
                        node_types.append("cpu")
                    else:
                        node_types.append("gpu")
                if "manage" in role_list and 'manage' not in node_types:
                    node_types.append("manage")
                result['node_list'].append(
                    {
                        'id' : node_id_list[hostname]['id'],
                        'hostname' : hostname,
                        'ip': info['ip'],
                        'role' :  role_list, #True if node_id_list[hostname]['role'] =="control-plane" else False,
                        'status' : info['status'],
                        'type' : node_types, # "gpu", #TODO 변경해야함
                        'os_version' : info['os_version'],
                        'nvidia_driver': gpu_info['gpu_driver'] if gpu else None,
                        'sw_version' : {
                            'kubernets' : info['kube_version'],
                            'container_rumtime': info['container_runtime_version']
                        },
                        'gpu_info' : gpu,
                        'cpu_info' : cpu,
                        'mem_info' : mem,
                        'instance' : instance
                    }
                )
                time3_2 = time.time()
                print("node-info time3_loop:", time3_2 - time3_1)
            except:
                traceback.print_exc()
                print(f"hostname:{hostname}")
                print("="*50)
                continue

        result['usage']['cpu']['avail'] = result['usage']['cpu']['total'] - result['usage']['cpu']['used']
        result['usage']['mem']['avail'] = result['usage']['mem']['total'] - result['usage']['mem']['used']
        detail_temp=[]
        gpu_alloc_usage_list = json.loads(redis_client.get(GPU_ALLOC_USAGE))
        for model, info in result['usage']['gpu']['detail'].items():
            result['usage']['gpu']['used'] +=gpu_alloc_usage_list.get(model,0)
            used=gpu_alloc_usage_list.get(model,0)
            detail_temp.append(
                {
                    'name':model,
                    'total':info['total'],
                    'used':used,
                    'usage': round((used/info['total'])*100,2),
                    'gpu_mem' : info['gpu_mem'],
                    'cuda_core' : info['cuda_core']
                }
            )
        if result['usage']['gpu'] is not None:
            result['usage']['gpu']['avail'] = result['usage']['gpu']['total']-result['usage']['gpu']['used']
            result['usage']['gpu']['detail'] = detail_temp

        print('node-info end')
        # redis_client.close()
        return response(status=1, result=result)
    except:
        traceback.print_exc()
        return response(status=0, result=None)



def set_node_active(node_id, active: bool):
    try:
        node_info = db_node.get_node(node_id=node_id)
        res,std= create_node_active_job(node = node_info['name'], active=active)
        if res:
            if active:
                status = "Ready"
            else:
                status= "Not Ready"
            return response(status=1, message="{} is {}".format(node_info['name'], status))
        else:
            response(status=0, message=std)
    except:
        traceback.print_exc()
        return response(status=0, message="node active change fail")