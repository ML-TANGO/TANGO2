from prometheus_api_client import PrometheusConnect
from contextlib import contextmanager
from collections import defaultdict
from utils.settings import PROMETHEUS_DNS
import json
import traceback
from utils.resource import response
from utils import common
# import utils.db as db
import math
import requests
from utils.redis import get_redis_client
from utils.redis_key import GPU_INFO_RESOURCE, CPU_INFO_RESOURCE, MEM_INFO_RESOURCE, NODE_INFO, GPU_ALLOC_USAGE, WORKSPACE_RESOURCE_QUOTA, NODE_RESOURCE_USAGE, WORKSPACE_POD_RESOURCE_USAGE
from utils.msa_db import db_node
from utils.msa_db import db_instance
from utils.msa_db import db_workspace
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

# redis_client = get_redis_client()
def get_node_resource_info():
    try:
    
        result={
            'node_list' : [],
            'usage':{
                'gpu':{
                    'total':0,
                    'used':0,
                    'avail':0,
                    'alloc':0,
                    'detail':{}
                },
                'cpu':{
                    'total':0,
                    'used':0,
                    'avail':0,
                    'alloc':0,
                    'detail':{}
                },
                'mem':{
                    'total':0,
                    'used':0,
                    'avail':0,
                    'alloc':0,
                    'detail':{}
                },
                'instance':{},
                'workspace_instance_usage':{}
            }
        }
        redis_client = get_redis_client()
        print('node-info start')
        node_list = redis_client.hgetall(NODE_INFO)
        gpu_list = json.loads(redis_client.get(GPU_INFO_RESOURCE))
        cpu_list = redis_client.hgetall(CPU_INFO_RESOURCE)
        mem_list = redis_client.hgetall(MEM_INFO_RESOURCE)
        node_resource_usage_list = redis_client.hgetall(NODE_RESOURCE_USAGE)
        
        # print(node_resource_usage_list)
        # print(gpu_list)
        # id는 필요한데 RDB 조회시 속도문제??
        def get_node_id_list():
            db_node_info = db_node.get_node_list()
            return { item["name"] : {'id' : item["id"], 'role' : item['role']} for item in db_node_info}
        node_id_list = get_node_id_list()
        # node_id_list = db_node.get_node_list()

        def get_node_hardware_info():
            for hostname, info in node_list.items():
                try:
                    time3_1 = time.time()
                    
                    info=json.loads(info)
                    cpu=json.loads(cpu_list[hostname])
                    mem=json.loads(mem_list[hostname])

                    gpu=gpu_list.get(hostname,None)
                    memory_info_list=db_node.get_node_ram(node_id=node_id_list[hostname]['id'])
                    instance_list = db_node.get_node_instance_list(node_id_list[hostname]['id'])
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
                            if gpu_info_detail:
                                gpu[uuid]['cuda_cores'] = gpu_info_detail.get('cuda_core',None)
                                gpu[uuid]['architecture'] = gpu_info_detail['architecture']
                            else:
                                gpu[uuid]['cuda_cores'] = None
                                gpu[uuid]['architecture'] = None
                                
                            gpu[uuid]['nvlink'] = False
                            gpu[uuid]['mig_mode'] = False #TODO 수정필요
                            

                            if not result['usage']['gpu']['detail'].get(gpu_info['model_name']):
                                result['usage']['gpu']['detail'][gpu_info['model_name']]={
                                    'total':0,
                                    'used':0,
                                    'gpu_mem' : gpu_info['gpu_mem'],
                                    'cuda_core' :  gpu[uuid]['cuda_cores']
                            }
                            result['usage']['gpu']['detail'][gpu_info['model_name']]['total']+=1
                            result['usage']['gpu']['detail'][gpu_info['model_name']]['used']+=gpu_info['used']
                                    
                    
                    # cpu['cpu_used'] = resource_usage_info['usage']['cpu']
                    # mem['mem_used'] = int(resource_usage_info['usage']['mem'])
                    # mem['mem_usage']=round((mem['mem_used']/mem['mem_total'])*100,2)

                    result['usage']['cpu']['total']+=int(cpu['cpu_core'])
                    # result['usage']['cpu']['used']+=cpu['cpu_used']
                    result['usage']['mem']['total']+=int(mem['mem_total'])
                    # result['usage']['mem']['used']+=mem['mem_used']

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
                            'instance' : instance_list
                        }
                    )
                    time3_2 = time.time()
                    print("node-info time3_loop:", time3_2 - time3_1)
                except:
                    # traceback.print_exc()
                    print("="*50)
                    print(f"error hostname:{hostname}")
                    print("="*50)
                    continue
        
        def get_node_instance_allocate_info():
            #instance alloc check
            cpu_detail_temp={}
            mem_detail_temp={}
            gpu_detail_temp={}
            instance_list = db_node.get_node_instance_list()
            for instance in instance_list:
                cpu_alloc=0
                mem_alloc=0
                cpu=json.loads(cpu_list[instance['node_name']])
                mem=json.loads(mem_list[instance['node_name']])
                if result['usage']['instance'].get(instance['instance_name'],None):
                    result['usage']['instance'][instance['instance_name']]['instance_total_count'] += instance['instance_allocate']
                else:
                    result['usage']['instance'][instance['instance_name']]={
                        'allocate_workspace_list' : {},
                        'cpu_count' : instance['cpu_allocate'],
                        'gpu_count' : instance['gpu_allocate'],
                        'ram_count' : instance['ram_allocate'],
                        'instance_total_count': instance['instance_allocate'],
                        'gpu_name' : instance['gpu_name'] if instance['gpu_name'] else "No Resource Group",
                        'npu_count' : instance['npu_allocate']
                    }

                result['usage']['cpu']['alloc'] += instance['cpu_allocate']*instance['instance_allocate']
                result['usage']['mem']['alloc'] += instance['ram_allocate']*instance['instance_allocate']*1024*1024*1024
                result['usage']['gpu']['alloc'] += instance['gpu_allocate']*instance['instance_allocate']
                cpu_alloc += instance['cpu_allocate']*instance['instance_allocate']
                mem_alloc += instance['ram_allocate']*instance['instance_allocate']*1024*1024*1024

                if cpu_detail_temp.get(cpu['cpu_model'],None) is None:
                    cpu_detail_temp[cpu['cpu_model']]={
                        'cpu_core': int(cpu['cpu_core']),
                        'cpu_alloc' : cpu_alloc, 
                        'cpu_used' : 0,
                        'used_usage': 0,
                        'alloc_usage': 0
                    }
                else:
                    cpu_detail_temp[cpu['cpu_model']]['cpu_core'] += int(cpu['cpu_core'])
                    cpu_detail_temp[cpu['cpu_model']]['cpu_alloc'] += cpu_alloc
                cpu_detail_temp[cpu['cpu_model']]['alloc_usage']=round((cpu_detail_temp[cpu['cpu_model']]['cpu_alloc']/cpu_detail_temp[cpu['cpu_model']]['cpu_core'])*100,2)

                memory_info_list=db_node.get_node_ram(node_id=instance['node_id'])
                mem_type=None
                for memory_info in memory_info_list:
                    mem_type=memory_info['type']
                    if mem_type is not None:
                        break
                mem_detail_temp[instance['node_name']]={
                    'mem_total': int(mem['mem_total']),
                    'mem_alloc' : mem_alloc,
                    'mem_used': 0,
                    'type': mem_type,
                    'alloc_usage': 0,
                    'used_usage': 0
                }
                mem_detail_temp[instance['node_name']]['alloc_usage']=round((mem_detail_temp[instance['node_name']]['mem_alloc']/mem_detail_temp[instance['node_name']]['mem_total'])*100,2)
                # for cpu_name, cpu_usage_info in cpu_detail_temp.items():
                #     cpu_usage_info['name']=cpu_name
                #     cpu_usage_info['alloc_usage']=round((cpu_usage_info['cpu_alloc']/cpu_usage_info['cpu_core'])*100,2)
                #     # cpu_usage_info['cpu_usage'] = round((cpu_usage_info['cpu_used']/cpu_usage_info['cpu_core'])*100,2)
                #     result['usage']['cpu']['detail'][cpu_name]=cpu_usage_info
                result['usage']['mem']['detail']=mem_detail_temp
                result['usage']['cpu']['detail']=cpu_detail_temp


            gpu_alloc_usage_list = json.loads(redis_client.get(GPU_ALLOC_USAGE))
            for model, info in result['usage']['gpu']['detail'].items():
                result['usage']['gpu']['used'] +=info['used']
                alloc=gpu_alloc_usage_list.get(model,0)
                gpu_detail_temp[model]={
                    'total':info['total'],
                    'used':info['used'],
                    'alloc' : alloc,
                    'gpu_mem' : info['gpu_mem'],
                    'cuda_core' : info['cuda_core']
                }
                
            if result['usage']['gpu'] is not None:
                result['usage']['gpu']['detail'] = gpu_detail_temp
                result['usage']['gpu']['avail'] = result['usage']['gpu']['total'] - result['usage']['gpu']['alloc']
                # result['usage']['gpu']['detail']['workspace']={}
            for workspace_instance in db_instance.get_workspcae_instance_alloc_info():
                try:
                    result['usage']['instance'][workspace_instance['instance_name']]['allocate_workspace_list'][workspace_instance['workspace_name']]={'instance_count': workspace_instance['instance_allocate']}
                except:
                    continue
        # instance_info_list=db_instance.get_instance_total_info()
        # # print(instance_info_list)
        # if instance_info_list:
        #     for instance_info in instance_info_list:
        #         # print(instance_info)
        #         temp_dict={}
                # if result['usage']['instance'].get(instance_info['instance_name'],None) is None:
                #     result['usage']['instance'][instance_info['instance_name']]={
                #         'gpu_name':instance_info['resource_group_name'],
                #         'gpu_count': instance_info['gpu_allocate'],
                #         'cpu_count': instance_info['cpu_allocate'],s
                #         'ram_count': instance_info['ram_allocate'],
                #         'npu_count': instance_info['npu_allocate'],
                #         'instance_total_count': instance_info['instance_count'],
                #         'allocate_workspace_list': {}
                        
                #     }
                    
                    # result['usage']['gpu']['alloc']+=instance_info['gpu_allocate']*instance_info['instance_count']
                    # result['usage']['cpu']['alloc']+=instance_info['cpu_allocate']*instance_info['instance_count']
                    # result['usage']['mem']['alloc']+=instance_info['ram_allocate']*instance_info['instance_count']*1024*1024*1024 #GB to byte
                # if instance_info['workspace_name']!="":

                #     workspace_info=db_workspace.get_workspace(workspace_name=instance_info['workspace_name'])
                #     if result['usage']['instance'][instance_info['instance_name']]['allocate_workspace_list'].get(instance_info['workspace_name'],None):
                #         result['usage']['instance'][instance_info['instance_name']]['allocate_workspace_list'][instance_info['workspace_name']]['instance_count']+=instance_info['instance_allocate']
                #     else:
                #         result['usage']['instance'][instance_info['instance_name']]['allocate_workspace_list']={
                #             instance_info['workspace_name']:{
                #                 'instance_count':instance_info['instance_allocate']
                #             }
                            
                #         }

                #     cpu_model = json.loads(cpu_list[instance_info['node_name']])['cpu_model']
                #     if result['usage']['cpu']['detail'][cpu_model]['workspace'].get(instance_info['workspace_name'],None) is None:
                #         # result['usage']['cpu']['detail'][cpu_model]['cpu_alloc']= instance_info['cpu_allocate'] * instance_info['instance_allocate']
                #         result['usage']['cpu']['detail'][cpu_model]['workspace'][instance_info['workspace_name']]={
                #             'cpu_alloc' : instance_info['cpu_allocate']*instance_info['instance_allocate'],
                #             'manager' : workspace_info['manager_name'],
                #             'cpu_used' : 0,
                #             'used_usage': 0, 
                #             'alloc_usage' : 0
                #         }
                        
                #     else:
                #         # result['usage']['cpu']['detail'][cpu_model]['cpu_alloc'] += instance_info['cpu_allocate']*instance_info['instance_allocate']
                #         result['usage']['cpu']['detail'][cpu_model]['workspace'][instance_info['workspace_name']]['cpu_alloc']+=instance_info['cpu_allocate']*instance_info['instance_allocate']
                #     result['usage']['cpu']['detail'][cpu_model]['workspace'][instance_info['workspace_name']]['alloc_usage'] = round((result['usage']['cpu']['detail'][cpu_model]['workspace'][instance_info['workspace_name']]['cpu_alloc']
                #                                                                                                                       /result['usage']['cpu']['detail'][cpu_model]['cpu_core'])*100,2)
                #     # print(f"init {result['usage']['cpu']['detail'][cpu_model]['workspace'][instance_info['workspace_name']]}")
                #     if instance_info['resource_group_name'] != "No Resource Group":
                #         if result['usage']['gpu']['detail'][instance_info['resource_group_name']]['workspace'].get(instance_info['workspace_name'],None) is None:
                #             result['usage']['gpu']['detail'][instance_info['resource_group_name']]['alloc'] += instance_info['gpu_allocate']*instance_info['instance_allocate']
                #             result['usage']['gpu']['detail'][instance_info['resource_group_name']]['workspace'][instance_info['workspace_name']]={
                #                 'gpu_alloc' : instance_info['gpu_allocate']*instance_info['instance_allocate'],
                #                 'manager' : workspace_info['manager_name'],
                #                 'gpu_used' : 0,
                #                 'used_usage': 0, 
                #                 'alloc_usage' : 0
                #             }
                #         else:
                #             result['usage']['gpu']['detail'][instance_info['resource_group_name']]['alloc'] += instance_info['gpu_allocate']*instance_info['instance_allocate']
                #             result['usage']['gpu']['detail'][instance_info['resource_group_name']]['workspace'][instance_info['workspace_name']]['gpu_alloc']+=instance_info['gpu_allocate']*instance_info['instance_allocate']
                #         result['usage']['gpu']['detail'][instance_info['resource_group_name']]['workspace'][instance_info['workspace_name']]['alloc_usage'] = round((result['usage']['gpu']['detail'][instance_info['resource_group_name']]['workspace'][instance_info['workspace_name']]['gpu_alloc']
                #                                                                                                                       /result['usage']['gpu']['detail'][instance_info['resource_group_name']]['total'])*100,2)

                #     if result['usage']['mem']['detail'][instance_info['node_name']]['workspace'].get(instance_info['workspace_name'],None) is None:
                #         # result['usage']['mem']['detail'][instance_info['node_name']]['mem_alloc'] = instance_info['ram_allocate']*instance_info['instance_allocate']*1024*1024*1024
                #         result['usage']['mem']['detail'][instance_info['node_name']]['workspace'][instance_info['workspace_name']]={
                #             'mem_alloc' : instance_info['ram_allocate']*instance_info['instance_allocate']*1024*1024*1024,
                #             'manager' : workspace_info['manager_name'],
                #             'mem_used' : 0,
                #             'used_usage': 0, 
                #             'alloc_usage' : 0
                #         }
                #     else:
                #         # result['usage']['mem']['detail'][instance_info['node_name']]['mem_alloc'] += instance_info['ram_allocate']*instance_info['instance_allocate']*1024*1024*1024
                #         result['usage']['mem']['detail'][instance_info['node_name']]['workspace'][instance_info['workspace_name']]['mem_alloc']+=instance_info['ram_allocate']*instance_info['instance_allocate']*1024*1024*1024
                #     result['usage']['mem']['detail'][instance_info['node_name']]['workspace'][instance_info['workspace_name']]['alloc_usage'] = round((result['usage']['mem']['detail'][instance_info['node_name']]['workspace'][instance_info['workspace_name']]['mem_alloc']
                #                                                                                                                                         /result['usage']['mem']['detail'][instance_info['node_name']]['mem_total'])*100,2)
        def get_node_resource_usage():
            for hostname,_ in node_list.items():
                try:
                    node_resource_usage = json.loads(node_resource_usage_list[hostname])
                    cpu=json.loads(cpu_list[hostname])
                    result['usage']['cpu']['detail'][cpu['cpu_model']]['cpu_used'] += int(node_resource_usage['usage']['cpu'])
                    result['usage']['cpu']['used'] += int(node_resource_usage['usage']['cpu'])
                    result['usage']['cpu']['detail'][cpu['cpu_model']]['used_usage'] = round(result['usage']['cpu']['detail'][cpu['cpu_model']]['cpu_used']/result['usage']['cpu']['detail'][cpu['cpu_model']]['cpu_core']*100,2)

                    result['usage']['mem']['detail'][hostname]['mem_used'] += int(node_resource_usage['usage']['mem'])
                    result['usage']['mem']['used'] += int(node_resource_usage['usage']['mem'])
                    result['usage']['mem']['detail'][hostname]['used_usage'] = round(result['usage']['mem']['detail'][hostname]['mem_used']/result['usage']['mem']['detail'][hostname]['mem_total']*100,2)
                except:
                    continue
        get_node_hardware_info()
        get_node_instance_allocate_info()
        get_node_resource_usage()
        workspace_pod_resource_usage_list=redis_client.hgetall(WORKSPACE_POD_RESOURCE_USAGE)
        # print(workspace_pod_resource_usage_list)
        for workspace_id, pod_resource_used_info in workspace_pod_resource_usage_list.items():
            workspace_info = db_workspace.get_workspace(workspace_id=workspace_id)
            if workspace_info is None:
                redis_client.hdel(WORKSPACE_POD_RESOURCE_USAGE,workspace_id)
                continue
            if result['usage']['workspace_instance_usage'].get(workspace_info['name'],None) is None:
                resource_usage = redis_client.hget(WORKSPACE_RESOURCE_QUOTA, workspace_info['id'])
                if resource_usage:
                    resource_usage = json.loads(resource_usage)
                    if resource_usage['gpu']['hard'] != 0 :
                        resource_usage_total=((resource_usage['cpu']['used']/resource_usage['cpu']['hard'])*100)+((resource_usage['gpu']['used']/resource_usage['gpu']['hard'])*100)+((resource_usage['ram']['used']/resource_usage['ram']['hard'])*100)
                        resource_usage_percent=int((resource_usage_total/3))
                    else:
                        try: # 2025-02-04 wyatt 수정 (division by zero 발생으로 예외처리)
                            resource_usage_total=((resource_usage['cpu']['used']/resource_usage['cpu']['hard'])*100)+((resource_usage['ram']['used']/resource_usage['ram']['hard'])*100)
                            resource_usage_percent=int((resource_usage_total/2))
                        except ZeroDivisionError:
                            resource_usage_percent = 0
                    result['usage']['workspace_instance_usage'][workspace_info['name']]={
                        'usage': resource_usage_percent,
                        'cpu': resource_usage['cpu']['used'],
                        'gpu': resource_usage['gpu']['used'],
                        'mem': resource_usage['ram']['used']
                    }
            for pod_resource_used in json.loads(pod_resource_used_info):
                for _,resource_info in pod_resource_used.items():
                    try:
                        cpu_model = json.loads(cpu_list[resource_info['node']])['cpu_model']
                        # if result['usage']['cpu']['detail'][cpu_model]['workspace'][workspace_info['name']].get('cpu_used', None) is None:
                        #     print(11111111111111111111)
                        #     result['usage']['cpu']['detail'][cpu_model]['workspace'][workspace_info['name']]['cpu_used'] = resource_info['resource_usage']['cpu']
                        #     result['usage']['cpu']['detail'][cpu_model]['workspace'][workspace_info['name']]['manager'] = workspace_info['manager_name']
                        #     print(result['usage']['cpu']['detail'][cpu_model]['workspace'][workspace_info['name']])
                        # else:
                        result['usage']['cpu']['detail'][cpu_model]['workspace'][workspace_info['name']]['cpu_used'] += resource_info['resource_usage']['cpu']
                        
                        # if result['usage']['mem']['detail'][resource_info['node']]['workspace'][workspace_info['name']].get('mem_used', None) is None:
                        #     result['usage']['mem']['detail'][resource_info['node']]['workspace'][workspace_info['name']]['mem_used'] = int(resource_info['resource_usage']['mem'])
                        #     result['usage']['mem']['detail'][resource_info['node']]['workspace'][workspace_info['name']]['manager'] = workspace_info['manager_name']
                        # else:
                        result['usage']['mem']['detail'][resource_info['node']]['workspace'][workspace_info['name']]['mem_used'] += int(resource_info['resource_usage']['mem'])
                        
                        if resource_info['resource_usage'].get('gpu', None):
                            ws_usage_instance_list = db_node.get_node_instance_list(instance_id=resource_info['instance_id'])
                            for ws_usage_instance in ws_usage_instance_list:
                            #     if result['usage']['gpu']['detail'][ws_usage_instance['gpu_name']]['workspace'][workspace_info['name']].get('gpu_used',None) is None:
                            #         result['usage']['gpu']['detail'][ws_usage_instance['gpu_name']]['workspace'][workspace_info['name']]['gpu_used'] = resource_info['resource_usage']['gpu']
                            #         result['usage']['gpu']['detail'][ws_usage_instance['gpu_name']]['workspace'][workspace_info['name']]['manager'] = workspace_info['manager_name']
                            #     else:
                                result['usage']['gpu']['detail'][ws_usage_instance['gpu_name']]['workspace'][workspace_info['name']]['gpu_used']+=resource_info['resource_usage']['gpu']
                                result['usage']['gpu']['detail'][ws_usage_instance['gpu_name']]['workspace'][workspace_info['name']]['gpu_usage']=round((result['usage']['gpu']['detail'][ws_usage_instance['gpu_name']]['workspace'][workspace_info['name']]['gpu_used']/result['usage']['gpu']['detail'][ws_usage_instance['gpu_name']]['total'])*100,2)
                                result['usage']['gpu']['detail'][ws_usage_instance['gpu_name']]['workspace'][workspace_info['name']]['used_usage']=result['usage']['gpu']['detail'][ws_usage_instance['gpu_name']]['workspace'][workspace_info['name']]['gpu_usage']
                                result['usage']['gpu']['detail'][ws_usage_instance['gpu_name']]['used'] +=1
                                result['usage']['gpu']['used'] +=1
                                result['usage']['gpu']['gpu_usage'] = round((result['usage']['gpu']['used']/result['usage']['gpu']['total'])*100,2)
                                result['usage']['gpu']['avail'] = result['usage']['gpu']['total']-result['usage']['gpu']['alloc']
                            # gpu_ = gpu_list.get(hostname,None)
                            # if gpu_:
                            #     for _, gpu_info in gpu_.items():
                            #         print(1)
                            
                        # print(result['usage']['cpu']['detail'][cpu_model])
                        result['usage']['cpu']['detail'][cpu_model]['workspace'][workspace_info['name']]['used_usage'] = round((result['usage']['cpu']['detail'][cpu_model]['workspace'][workspace_info['name']]['cpu_used']/result['usage']['cpu']['detail'][cpu_model]['cpu_core'])*100,2)
                        result['usage']['cpu']['detail'][cpu_model]['cpu_used']+=resource_info['resource_usage']['cpu']
                        result['usage']['cpu']['detail'][cpu_model]['used_usage']=round((result['usage']['cpu']['detail'][cpu_model]['cpu_used']/result['usage']['cpu']['detail'][cpu_model]['cpu_core'])*100,2)
                        result['usage']['cpu']['used']+=resource_info['resource_usage']['cpu']

                        result['usage']['mem']['detail'][resource_info['node']]['workspace'][workspace_info['name']]['used_usage'] = round((result['usage']['mem']['detail'][resource_info['node']]['workspace'][workspace_info['name']]['mem_used']/result['usage']['mem']['detail'][resource_info['node']]['mem_total'])*100,2)
                        result['usage']['mem']['detail'][resource_info['node']]['mem_used']+=int(resource_info['resource_usage']['mem'])
                        result['usage']['mem']['detail'][resource_info['node']]['used_usage']=round(result['usage']['mem']['detail'][resource_info['node']]['mem_used']/result['usage']['mem']['detail'][resource_info['node']]['mem_total']*100,2)
                        result['usage']['mem']['used']+=resource_info['resource_usage']['mem']
                    except:
                        pass

                # result['usage']['cpu']=
            # 
            # json.loads(mem_list[pod_resource_used_info['node']])
            # :
            #     for pod_name ,pod_used in pod_resource_used.items():
            #         print(1)


            

        result['usage']['cpu']['avail'] = result['usage']['cpu']['total'] - result['usage']['cpu']['alloc']
        result['usage']['mem']['avail'] = result['usage']['mem']['total'] - result['usage']['mem']['alloc']

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