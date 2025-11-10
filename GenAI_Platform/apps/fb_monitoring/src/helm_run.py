import subprocess
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from utils import settings, TYPE
import traceback
from utils.redis_key import JOB_LIST
from utils.redis import get_redis_client
NODE_INIT_CHART_NAME="node-init"

redis = get_redis_client()

def create_node_init_job(node_id, node):
    try:
        helm_name=node+"-init"

        env={
            "NODE_ID" : node_id,
        }
        #TODO 네임스페이스를 어디로 지정?
        namespace = os.getenv("JF_SYSTEM_NAMESPACE")
        # namespace = "gpu-operator"
        registry_url = os.getenv("SYSTEM_DOCKER_REGISTRY_URL")
        env_command=""
        for key, val in env.items():
            if val:
                env_command += f" --set env.{key}={val}"
        command=f"""helm install {helm_name} /app/src/helm_chart/{NODE_INIT_CHART_NAME}/ \
            -n {namespace} \
            --set name="{helm_name}" \
            --set node="{node}" \
            --set namespace="{namespace}" \
            --set registry_url="{registry_url}" \
            {env_command} \
            """
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print(result.stdout )
        redis.hset(JOB_LIST,helm_name,namespace)
        return True, result.stdout 
    except subprocess.CalledProcessError as e:
        traceback.print_exc()
        return False, f"Error executing Helm command: {e.stderr}"
    except:
        traceback.print_exc()
        return False, result.stdout
    
def delete_helm(node, namespace):
    try:
        helm_name=node+"-init"
        # namespace = os.getenv("JF_SYSTEM_NAMESPACE")
        
        
        command=f"""helm uninstall {helm_name} -n {namespace} """

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

# def init_node_info():
#     try:
#         with prometheus_connection(url) as prom:
#             node_list=prom.custom_query(query=REDIS_NODE_INFO)
#             node_role_list_df=MetricSnapshotDataFrame(prom.custom_query(query=NODE_ROLE_INFO))
#             node_gpu_info_df=MetricSnapshotDataFrame(prom.custom_query(query=REDIS_GPU_INFO))
#             node_cpu_info_df=MetricSnapshotDataFrame(prom.custom_query(query=REDIS_CPU_INFO))
#             for node in node_list:
#                 if not node_db.get_node(node_name=node['metric']['node']):
#                     node_role = node_role_list_df[node_role_list_df['node'] == node['metric']['node']]
#                     if node_role.empty:
#                         role = "worker"
#                     else:
#                         role= node_role.iloc[0]['role']

#                     node_ip = node['metric']['internal_ip']
#                     node_name = node['metric']['node']

#                     node_id = node_db.insert_node(name=node_name,
#                                             ip=node_ip,
#                                             role=role,
#                                             status="Ready")

#                     res = create_node_init_job(node_id=node_id, node=node_name)

#                     if node_db.get_node_cpu(node_id=node_id) is None:
#                          #instance ex) ip:settings.JF_NODE_EXPORTER_PORT
#                         cpu_info = node_cpu_info_df[node_cpu_info_df['instance'] == node_ip+":"+settings.JF_NODE_EXPORTER_PORT]
#                         for _, cpu in cpu_info.iterrows():
#                             cpu_resource_group=node_db.get_resource_group(name=cpu['model_name'])
#                             if cpu_resource_group is None:
#                                 cpu_resource_group_id = node_db.insert_resource_group(name=cpu['model_name'])
#                                 print(cpu_resource_group_id)
#                             else:
#                                 cpu_resource_group_id = cpu_resource_group['id']
                            
#                             node_db.insert_node_cpu(node_id=node_id, resource_group_id=cpu_resource_group_id, core=int(cpu['value']))

#                     gpu_info = node_gpu_info_df[node_gpu_info_df['Hostname'] == node_name]
#                     for _, gpu in gpu_info.iterrows():
#                         if node_db.get_node_gpu(gpu_uuid=gpu['UUID']) is None:
#                             gpu_resource_group=node_db.get_resource_group(name=gpu['modelName'])
#                             if gpu_resource_group is None:
#                                 gpu_resource_group_id = node_db.insert_resource_group(name=gpu['modelName'])
#                             else:
#                                 gpu_resource_group_id = gpu_resource_group['id']
#                             print(gpu_resource_group_id)
#                             node_db.insert_node_gpu(node_id=node['id'], resource_group_id=gpu_resource_group_id,gpu_memory=gpu['value'], gpu_uuid=gpu['UUID'])

#     #                 if node_db.get_node_ram(node_id=node_id) is None:
#     #                     node_ram_info_df=MetricSnapshotDataFrame(prom.custom_query(query=REDIS_MEM_TOTAL)) #instance ex) ip:settings.JF_NODE_EXPORTER_PORT
#     #                     node_ram_info =node_ram_info_df[node_ram_info_df['instance'] == node['ip']+":"+settings.JF_NODE_EXPORTER_PORT]
#     #                     for _, ram in node_ram_info.iterrows():
#     #                         node_db.insert_node_ram(node_id=node['id'], size=ram['value'])
#     except:
#         traceback.print_exc()


# create_storage_nfs_provisioner(ip="192.168.1.14",name="jake-sc",mountpoint="/jf-storage-class")
# create_storage_check_job("192.168.1.14", "local", 'jake-sc', '/jf-storage-class')