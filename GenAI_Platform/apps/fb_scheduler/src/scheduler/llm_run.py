
from utils.msa_db import db_project, db_node
from utils.llm_db import db_model
# from utils.exception.exceptions import *
from utils.settings import *

from utils import PATH, TYPE, settings, common

from scheduler.dto import *
from utils.kube import PodName
from datetime import datetime

import re
import sys
import subprocess
import json

FINE_TUNING_SCRIPT_NAME = "/llm_model_fine_tuning.py"

def create_fine_tuning_pod(fine_tuning_pod : FineTuningPodInfo):
    try:
        os.chdir("/app/helm_chart")
        training_command = f' --set command="{fine_tuning_pod.command}"'
        labels_command=""
        for key, val in fine_tuning_pod.labels.model_dump().items():
            if val:
                labels_command += f" --set labels.{key}={val}"
        
        env_command=""
        for key, val in fine_tuning_pod.env.model_dump().items():
            if val:
                env_command += f" --set env.{key}={val}"
            
        resource_limit_command=""
        for key, val in fine_tuning_pod.resource.model_dump().items():
            resource_limit_command += f" --set resource.limits.{key}={val}"
            
        rdma_command = ""
        if settings.JF_RDMA_ENABLED:
            rdma_command += " --set rdma.enabled=true"
            
            if fine_tuning_pod.multipath_enable:  # 사용자 입력
                if settings.JFB_MP_SEED_NUM and settings.JFB_MP_SEED_LIST: # 시스템 설정
                    rdma_command += f" --set rdma.mp.enabled=true"
                    rdma_command += f" --set rdma.mp.seed_num={settings.JFB_MP_SEED_NUM}"
                    
                    seed_list = json.loads(settings.JFB_MP_SEED_LIST.strip())
                    rdma_command += f" --set-json 'rdma.mp.seed_list={json.dumps(seed_list)}'"
            if settings.JF_PERF_ENABLED:
                rdma_command += " --set rdma.perf.enabled=true"
                
            if settings.JF_P2P_LIST:
                p2p_list = json.loads(settings.JF_P2P_LIST.strip())
                rdma_command += f" --set-json 'rdma.p2p={json.dumps(p2p_list)}'"
        
        nodes_command = ""
        for index, node in enumerate(fine_tuning_pod.cluster):
            nodes_command += f" --set cluster[{index}].node_name={node.node_name}"
            nodes_command += f' --set cluster[{index}].device.type="{node.device.device_type}"'
            nodes_command += f' --set cluster[{index}].device.model="{node.device.model}"'
            nodes_command += f" --set cluster[{index}].device.count={node.device.count}"
            nodes_command += f' --set cluster[{index}].device.uuids="{node.device.uuids}"'
            nodes_command += f' --set cluster[{index}].device.ids="{node.device.ids}"'
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=fine_tuning_pod.labels.workspace_id)
        command=f"""helm install {fine_tuning_pod.helm_repo_name} {fine_tuning_pod.labels.work_func_type}/ \
                -n {namespace} \
                --set namespace={namespace} \
                --set pod_name={fine_tuning_pod.pod_name} \
                --set image={fine_tuning_pod.image} \
                --set total_device_count={fine_tuning_pod.total_device_count} \
                --set spec.hostname={fine_tuning_pod.hostname} \
                --set dataset.access={fine_tuning_pod.dataset_access} \
                --set dataset.name={fine_tuning_pod.dataset_name} \
                --set labels.helm_name={fine_tuning_pod.helm_repo_name} \
                {labels_command} {env_command} {resource_limit_command} {training_command} \
                {rdma_command} {nodes_command} \
                """
        if fine_tuning_pod.cpu_instance_name:
            command += f"  --set spec.cpu_instance_name={fine_tuning_pod.cpu_instance_name}"
        
        print(command, file=sys.stderr)
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip()
        if "cannot re-use a name that is still in use" in err_msg:
            return True, ""
        print(e.stdout)
        print(err_msg)
        print(command)
        return False ,err_msg


def fine_tuning_command(model_name : str, dataset_name : str, dataset_file_path: str,\
    fine_tuning_config : dict, used_dist : int = 0):
    
    script_path = PATH.JF_POD_MODEL_FINE_TUNING_SCRIPT_PATH + FINE_TUNING_SCRIPT_NAME
    config_path = None
    if fine_tuning_config["fine_tuning_type"] == TYPE.FINE_TUNING_ADVANCED:
        # config_path = PATH.JF_POD_MODEL_CONFIG_FILE_PATH.format(MODEL_NAME=model_name, FILE_NAME=fine_tuning_config["config_file_name"]) 
        config_path = fine_tuning_config["config_file_name"]
    dataset_path = PATH.JF_POD_MODEL_FINE_TUNING_DATASET_PATH.format(DATASET_NAME=dataset_name, FILE_PATH=dataset_file_path)
        
    fine_tuning_config = FineTuningParam(**fine_tuning_config)
    command = ""
    params = ""
    for key, value in fine_tuning_config.model_dump().items():
        params += f" --{key}={value}"
    
    if config_path is not None:
        params += f" --config_path={config_path}"
    # else:
    #     ds_config_path="/fine_tuning/ds_config.json"
    # if used_dist:
    #     command = f"deepspeed --hostfile /tmp_config/hostfile {script_path} --dataset_path={dataset_path} --deepspeed={ds_config_path} --used_dist={used_dist} {params}"
    # else:
    #     command = f"deepspeed {script_path} --dataset_path={dataset_path} --deepspeed={ds_config_path} --used_dist={used_dist} {params}"
    if used_dist:
        command = f"deepspeed --hostfile /tmp_config/hostfile {script_path} --dataset_path={dataset_path} --used_dist={used_dist} {params}"
    else:
        command = f"deepspeed {script_path} --dataset_path={dataset_path} --used_dist={used_dist} {params}"


    print(command, file=sys.stderr)
    return command


def create_fine_tuning(pod_info: dict):
    labels = FineTuningLabel(
        pod_type=TYPE.FINE_TUNING_TYPE,
        model_id=pod_info["model_id"],
        model_name=pod_info["model_name"],
        commit_id=pod_info["commit_id"],
        commit_name=pod_info["commit_name"],
        model_dataset_id=pod_info["model_dataset_id"],
        workspace_id=pod_info["workspace_id"],
        workspace_name=pod_info["workspace_name"],
        owner_id=pod_info["owner_id"],
        work_func_type=pod_info["pod_type"],
        work_type=pod_info["pod_type"],
        instance_id = pod_info["instance_id"],
    )
    
    cpu_instance_name=""
    nodes = []

    resource_type = pod_info.get("resource_type")
    model = (pod_info.get("resource_name") or "").replace(" ", "_")
    if pod_info.get("available_gpus",None):
        for gpu_info in pod_info["available_gpus"]:
            gpu_ids = []
            gpu_uuids = []
            for gpu_uuid in list(gpu_info["gpu_uuids"]):
                try:
                    # DB에 존재하는 gpu uuid인지 확인 
                    gpu_ids.append(db_node.get_node_gpu(gpu_uuid=gpu_uuid)["id"])
                    gpu_uuids.append(gpu_uuid)
                except:
                    # TODO
                    # 해당 gpu 제외 사켜야 하는지..
                    pass
            nodes.append(Node(
                node_name=gpu_info["node_name"],
                device=Accelerator(
                    device_type=resource_type,
                    model=model,
                    uuids = common.escape_special_chars(",".join(gpu_uuids)),
                    ids = ".".join(map(str, gpu_ids)),
                    count = len(gpu_uuids)
                )
            ))
    elif pod_info.get("available_node",None):
        nodes.append(Node(
            node_name=pod_info["available_node"],
            device=Accelerator(
                device_type=resource_type,
                model=model,
                count=0
            )
        ))
    elif pod_info.get("cpu_instance_name", None):
        nodes.append(Node(
            device=Accelerator(
                device_type=resource_type,
                model=model,
                count=0
            )
        )) # helm 에서 for문을 돌려야 하기 때문에 
        cpu_instance_name=pod_info.get("cpu_instance_name")
    
    # 생성되는 pod 개수
    labels.pod_count = len(nodes)
    
    image = pod_info["image_name"]
    fine_tuning_config = pod_info["fine_tuning_config"]
    
    # 사용자 Accel 희망 && 시스템적으로 다중경로 허용시
    jonathan_accel = True if fine_tuning_config.get("used_jonathan_accelerator") and settings.JF_MP_ENABLED else False
    model_dataset_info = db_model.get_model_dataset_sync(model_dataset_id=labels.model_dataset_id)
    
    used_dist = 1 if pod_info["gpu_count"] > 1 else 0
    
    command = fine_tuning_command(model_name=labels.model_name, fine_tuning_config=fine_tuning_config, dataset_name=model_dataset_info["dataset_name"],\
        dataset_file_path=model_dataset_info["training_data_path"], used_dist=used_dist)
    start_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=labels.workspace_id, item_name=labels.model_id, \
        item_type=TYPE.FINE_TUNING_TYPE, start_datetime=start_datetime).get_all() # TODO training_index 값 임의로 1로 수정 
    labels.pod_name = unique_pod_name
    # TODO 
    # 추후 Path 정리
    env = FineTuningENV(
            JF_HOME="/tmp_config",
            JF_ITEM_ID=labels.model_id,
            JF_POD_NAME=unique_pod_name,
            JF_TOTAL_GPU=pod_info["gpu_count"],
            HUGGING_FACE_HUB_TOKEN=settings.HUGGINGFACE_TOKEN,
            JF_DB_HOST=settings.JF_DB_HOST,
            JF_DB_PORT=settings.JF_DB_PORT,
            JF_DB_USER=settings.JF_DB_USER,
            JF_DB_PWD=settings.JF_DB_PW,   
        )
    
    resource = LimitResource(
            cpu=pod_info["resource"]["cpu"]/labels.pod_count,
            memory="{}G".format(pod_info["resource"]["ram"]/labels.pod_count)
        )
    
    fine_tuning_pod = FineTuningPodInfo(
        pod_type=TYPE.FINE_TUNING_TYPE,
        helm_repo_name=TYPE.FINE_TUNING_REPO_NAME.format(labels.model_id),
        cluster=nodes,
        cpu_instance_name=cpu_instance_name,
        command=command,
        labels=labels,
        env=env,
        resource=resource,
        image=image,
        pod_name=unique_pod_name,
        total_device_count=pod_info["gpu_count"],
        used_dist=used_dist,
        dataset_access=model_dataset_info["access"],
        dataset_name=model_dataset_info["dataset_name"],
        multipath_enable=jonathan_accel
    )

    result , message = create_fine_tuning_pod(fine_tuning_pod=fine_tuning_pod)
    if result:
        db_model.update_model_fine_tuning_status_sync(status=TYPE.KUBE_POD_STATUS_INSTALLING, model_id=labels.model_id, start_datetime=start_datetime, pod_count=labels.pod_count)
    else:
        if message:
            if "exceeded quota" in message:
                pass
    return result, message


