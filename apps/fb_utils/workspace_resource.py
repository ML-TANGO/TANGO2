from utils.msa_db import db_prepro, db_project, db_deployment, db_workspace, db_instance

from utils.redis import get_redis_client_async
from utils import redis_key, TYPE
from collections import defaultdict
import json
import traceback
from utils import settings
if settings.LLM_USED:
    from utils.llm_db import db_model

async def get_workspace_usage_gpu_count_by_instance(instance_id : int, workspace_id : int):
    """
    해당 workspace 의 instance에서 사용중인 gpu 개수와 pending에 걸려있는 gpu 수 
    """
    
    
    workspace_instance_info = await db_workspace.get_workspace_instance(workspace_id=workspace_id, instance_id=instance_id)
    if workspace_instance_info is None:
        return None
    used_gpus = 0
    pending_gpus = 0
    total_gpus = workspace_instance_info["instance_allocate"] * workspace_instance_info["gpu_allocate"]
    
    deployments = await db_deployment.get_deployment_by_instance_id(workspace_id=workspace_id, instance_id=instance_id)
    
    for deployment in deployments:
        workers = await db_deployment.get_deployment_worker_request(deployment_id=deployment["id"])
        for worker in workers:
            if worker["start_datetime"]:
                used_gpus += deployment["gpu_per_worker"]
            else:
                pending_gpus += deployment["gpu_per_worker"]
    
    projects = await db_prepro.get_project_by_instance_id(workspace_id=workspace_id, instance_id=instance_id)
    
    for project in projects:
        tools = await db_project.get_project_tools_new(project_id=project["id"])
        for tool in tools:
            if tool["request_status"] == 1:
                if tool["start_datetime"] and tool["end_datetime"] is None:
                    used_gpus += tool["gpu_count"]
                elif tool["start_datetime"] is None and tool["end_datetime"] is None:
                    pending_gpus += tool["gpu_count"]
        
        
        trainings = await db_project.get_trainings_new(project_id=project["id"])
        for training in trainings:
            if training["start_datetime"] and training["end_datetime"] is None:
                used_gpus += training["gpu_count"]
            elif training["start_datetime"] is None and training["end_datetime"] is None:
                pending_gpus += training["gpu_count"]
    
    preprocessings = await db_prepro.get_user_preprocessing_list_by_instance_id(workspace_id=workspace_id, instance_id=instance_id)
    
    for preprocessing in preprocessings:
        tools = await db_prepro.get_preprocessing_tools(preprocessing_id=preprocessing["id"])
        for tool in tools:
            if tool["request_status"] == 1:
                if tool["start_datetime"] and tool["end_datetime"] is None:
                    used_gpus += tool["gpu_count"]
                elif tool["start_datetime"] is None and tool["end_datetime"] is None:
                    pending_gpus += tool["gpu_count"]
        jobs = await db_prepro.get_jobs_is_request(preprocessing_id=preprocessing["id"])
        for job in jobs:
            if job["start_datetime"] and job["end_datetime"] is None:
                used_gpus += job["gpu_count"]
            elif job["start_datetime"] is None and job["end_datetime"] is None:
                pending_gpus += job["gpu_count"]
        
    
    return {
        "usde_gpu_count" : used_gpus,
        "pending_gpu_count" : pending_gpus,
        "workspace_gpu_total" : total_gpus,
        "available_gpu_count" : total_gpus - used_gpus
    }



async def get_workspace_instance_used(instance_id : int, workspace_id : int) -> tuple:
    try:
        # print("workspace_resource")
        # print(instance_id, workspace_id)
        redis_client = await get_redis_client_async()
        # print()
        # print("redisclient", redis_client)
        workspace_pod_status = await redis_client.hget(redis_key.WORKSPACE_PODS_STATUS, workspace_id)
        if workspace_pod_status:
            workspace_pod_status = json.loads(workspace_pod_status)
        else:
            workspace_pod_status = {}
        
        # Resource summaries by instance and category
        resource_summary = defaultdict(lambda: {'cpu': 0, 'gpu': 0, 'ram': 0})
        instance_summary = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'cpu': 0, 'gpu': 0, 'ram': 0})))  # Tracks category, id, and resources for each instance

        def extract_resources(node, current_category=None, current_id=None, instance_key='instance_id', resource_key='resource'):
            if isinstance(node, dict):
                # Check if the current node contains resource information
                if instance_key in node and resource_key in node:
                    instance_id = node[instance_key]
                    resources = node[resource_key]

                    # Update instance-level resource summary
                    resource_summary[instance_id]['cpu'] += resources.get('cpu', 0)
                    resource_summary[instance_id]['gpu'] += resources.get('gpu', 0)
                    resource_summary[instance_id]['ram'] += resources.get('ram', 0)

                    # Ensure that the category and ID are initialized before updating the instance_summary
                    if current_category and current_id:
                        instance_summary[instance_id][current_category][current_id]['cpu'] += resources.get('cpu', 0)
                        instance_summary[instance_id][current_category][current_id]['gpu'] += resources.get('gpu', 0)
                        instance_summary[instance_id][current_category][current_id]['ram'] += resources.get('ram', 0)

                # Recursively process child nodes
                for key, value in node.items():
                    # Update category and ID based on the current key
                    new_category = current_category
                    new_id = current_id
                    if key in TYPE.INSTANCE_USED_TYPES:
                        new_category = key
                    elif new_category and new_id is None and key.isdigit():
                        new_id = key
                    extract_resources(value, new_category, new_id, instance_key, resource_key)

            elif isinstance(node, list):
                for item in node:
                    extract_resources(item, current_category, current_id, instance_key, resource_key)

        # Process the data
        extract_resources(workspace_pod_status)
        
        resource_used = resource_summary.get(str(instance_id), {'cpu': 0, 'gpu': 0, 'ram': 0})
        instance_used = instance_summary.get(str(instance_id), {})
        
        return dict(resource_used), dict(instance_used)
    except:
        traceback.print_exc()
        print("redisclient", redis_client)

        return None, None

async def get_workspace_instance_total_info(instance_id : int, workspace_id : int,
                                            instance_allocate: int = 0, resource_limit: list = []
                                            ):
    """
    최종적으로 instane info 내려줄때 사용
    instance_allocate: 프로젝트에서 할당하는 개수 (db_instance는 )
    cpu,ram_limit은 db 학습, 배포에서 xxx_cpu_limit, xxx_ram_limit
    """
    result = {
        "instance_id" : instance_id,
        "instance_name" : None,
        "instance_type" : None,
        "instance_allocate" : None,
        "gpu_allocate" : None,
        "gpu_available" : None,
        "cpu_allocate" : None,
        "cpu_available" : None,
        "ram_allocate" : None,
        "ram_available" : None,
        "instance_used" : []
    }
    gpu_available = True
    cpu_available = True
    ram_available = True
    try:
        instance_info = db_instance.get_instance(instance_id=instance_id)
        workspace_instance_info = await db_workspace.get_workspace_instance(workspace_id=workspace_id, instance_id=instance_id)
        resource_used, instance_used = await get_workspace_instance_used(workspace_id=workspace_id, instance_id=instance_id)

        instance_name = instance_info.get("instance_name")
        instance_type = instance_info.get("instance_type")
        gpu_allocate = instance_info.get("gpu_allocate")
        cpu_allocate = instance_info.get("cpu_allocate")
        ram_allocate = instance_info.get("ram_allocate")

        # GPU
        if instance_type == TYPE.INSTANCE_TYPE_GPU:
            available_gpu_core = (gpu_allocate * workspace_instance_info["instance_allocate"]) - resource_used["gpu"]
            if available_gpu_core <= 0:
                gpu_available = False

        # CPU
        available_cpu_core = (cpu_allocate * workspace_instance_info["instance_allocate"]) - resource_used["cpu"]
        for limit in resource_limit:
            if available_cpu_core <= 0 or available_cpu_core < limit.get("cpu_limit", 0):
                cpu_available = False
                break  # 조건을 만족하지 않으면 루프를 종료

        # RAM
        available_ram = (ram_allocate * workspace_instance_info["instance_allocate"]) - resource_used["ram"]
        for limit in resource_limit:
            if available_ram <= 0 or available_ram < limit.get("ram_limit", 0):
                ram_available = False
                break  # 조건을 만족하지 않으면 루프를 종료

        # instance_used
        for key, value in instance_used.items():
            id_to_name = []
            if settings.LLM_USED:
                for item_id, resource in value.items():
                    if key == TYPE.FINE_TUNING_TYPE:
                        category_info = await db_model.get_model(int(item_id))
                        id_to_name.append({
                            "name": category_info["name"],
                            "resources": resource
                        })
                    else:
                        # try:
                        #     print("workspace_resource", item_id, key)
                        # except:
                        #     pass
                        category_info = await db_prepro.get_category_name(int(item_id), key)
                        id_to_name.append({
                            "name": category_info["name"],
                            "resources": resource
                        })
                instance_used[key] = id_to_name
            else:
                if key in TYPE.JONATHAN_FB_INSTANCE_USED_TYPES:
                    for item_id, resource in value.items():
                        category_info = await db_prepro.get_category_name(int(item_id), key)
                        id_to_name.append({
                            "name": category_info["name"],
                            "resources": resource
                        })
                    instance_used[key] = id_to_name
                
        result = {
            "instance_id" : instance_id,
            "instance_name" : instance_name,
            "instance_type" : instance_type,
            "instance_allocate" : instance_allocate,
            "gpu_allocate" : gpu_allocate,
            "gpu_available" : gpu_available,
            "cpu_allocate" : cpu_allocate,
            "cpu_available" : cpu_available,
            "ram_allocate" : ram_allocate,
            "ram_available" : ram_available,
            "instance_used" : instance_used,
            "instance_available" : all([cpu_available, ram_available, gpu_available])
        }
    except Exception as e:
        traceback.print_exc()
    return result