import subprocess
import os, sys, re
import traceback
from utils import settings, TYPE
import json
from scheduler.dto import *

from utils.msa_db import db_deployment, db_node, db_analyzing
from utils import common
from utils.helm_dto import YamlToValues

def create_project_tool_pod(project_tool_pod : ToolPodInfo):
    try:
        os.chdir("/app/helm_chart") # TODO 나중에 변수화 해야할 듯
        # helm install storage.tgz
        # namespace = NAMESPACE.format(settings.JF_SYSTEM_NAMESPACE, project_tool_pod.labels.workspace_id)
        
        labels_command=""
        for key, val in project_tool_pod.labels.model_dump().items():
            if val:
                labels_command += f" --set labels.{key}={val}"
        
        env_command=""
        for key, val in project_tool_pod.env.model_dump().items():
            if val:
                env_command += f" --set spec.containers.env.{key}={val}"
            
        resource_limit_command=""
        for key, val in project_tool_pod.resource.model_dump().items():
            resource_limit_command += f" --set spec.containers.resource.limits.{key}={val}"
        
        rdma_command = ""
        if settings.JF_RDMA_ENABLED:
            rdma_command += " --set rdma.enabled=true"
            
            if settings.JFB_MP_SEED_NUM and settings.JFB_MP_SEED_LIST:
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
        for index, node in enumerate(project_tool_pod.cluster):
            nodes_command += f" --set cluster[{index}].node_name={node.node_name}"
            nodes_command += f' --set cluster[{index}].device.type="{node.device.device_type}"'
            nodes_command += f' --set cluster[{index}].device.model="{node.device.model}"'
            nodes_command += f" --set cluster[{index}].device.count={node.device.count}"
            nodes_command += f' --set cluster[{index}].device.uuids="{node.device.uuids}"'
            nodes_command += f' --set cluster[{index}].device.ids="{node.device.ids}"'
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=project_tool_pod.labels.workspace_id)
        
        if settings.EXTERNAL_HOST_REDIRECT:
            domain = settings.EXTERNAL_HOST
        else:
            domain = f"{settings.EXTERNAL_HOST}:{settings.EXTERNAL_HOST_PORT}"
        
        
        command=f"""helm install {project_tool_pod.labels.helm_name} tools/ \
            -n {namespace} \
            --set namespace={namespace} \
            --set ingress_class_name={settings.INGRESS_CLASS_NAME} \
            --set owner_name={project_tool_pod.owner_name} \
            --set pod_name={project_tool_pod.pod_name} \
            --set service.svc_name={project_tool_pod.svc_name} \
            --set service.port={project_tool_pod.port} \
            --set spec.containers.image="{project_tool_pod.image}" \
            --set domain="{domain}" \
            --set tool_password="{project_tool_pod.tool_password}" \
            --set spec.restartPolicy={project_tool_pod.restartPolicy}\
            --set total_device_count={project_tool_pod.total_device_count} \
            --set spec.hostname={project_tool_pod.hostname} \
            --set dataset.access={project_tool_pod.dataset_access} \
            --set dataset.name={project_tool_pod.dataset_name} \
            --set privateRepo={settings.JONATHAN_PRIVATE_REPO_ENABLED} \
            --set privatePip={settings.JONATHAN_PRIVATE_PIP_ENABLED} \
            --set nexusPrefix={settings.JONATHAN_NEXUS_PREFIX} \
            --set offlineMode={settings.JF_OFFLINE_MODE} \
            --set nexus.hostname={settings.JONATHAN_NEXUS_HOST} \
            --set nexus.port={settings.JONATHAN_NEXUS_PORT} \
            {labels_command} {env_command} {resource_limit_command} \
            {rdma_command} {nodes_command} \
            """
        
            
        
        if project_tool_pod.cpu_instance_name:
            command += f"  --set spec.cpu_instance_name={project_tool_pod.cpu_instance_name}"
        
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


def create_project_hps_pod(hps_pod : HPSPodInfo):
    try:
        os.chdir("/app/helm_chart/") # TODO 나중에 변수화 해야할 듯
        hps_command = f' --set spec.containers.command="{hps_pod.command}"'
        
        labels_command=""
        for key, val in hps_pod.labels.model_dump().items():
            if val:
                labels_command += f" --set labels.{key}={val}"
        
        env_command=""
        for key, val in hps_pod.env.model_dump().items():
            if val:
                env_command += f" --set spec.containers.env.{key}={val}"
            
        resource_limit_command=""
        for key, val in hps_pod.resource.model_dump().items():
            resource_limit_command += f" --set spec.containers.resource.limits.{key}={val}"
        
        nodes_command = ""
        for index, node in enumerate(hps_pod.cluster):
            nodes_command += f" --set cluster[{index}].node_name={node.node_name}"
            nodes_command += f' --set cluster[{index}].device.type="{node.device.device_type}"'
            nodes_command += f' --set cluster[{index}].device.model="{node.device.model}"'
            nodes_command += f" --set cluster[{index}].device.count={node.device.count}"
            nodes_command += f' --set cluster[{index}].device.uuids="{node.device.uuids}"'
            nodes_command += f' --set cluster[{index}].device.ids="{node.device.ids}"'
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=hps_pod.labels.workspace_id)
        command=f"""helm install {hps_pod.labels.helm_name} project_job/ \
            -n {namespace} \
            --set namespace={namespace} \
            --set owner_name={hps_pod.owner_name} \
            --set pod_name={hps_pod.pod_name} \
            --set spec.restartPolicy={hps_pod.restartPolicy} \
            --set spec.containers.image={hps_pod.image} \
            --set distributed_framework={hps_pod.distributed_framework} \
            --set distributed_config_path="{hps_pod.distributed_config_path}" \
            --set total_device_count={hps_pod.total_device_count} \
            --set spec.hostname={hps_pod.hostname} \
            --set dataset.access={hps_pod.dataset_access} \
            --set dataset.name={hps_pod.dataset_name} \
            --set privateRepo={settings.JONATHAN_PRIVATE_REPO_ENABLED} \
            --set privatePip={settings.JONATHAN_PRIVATE_PIP_ENABLED} \
            --set nexusPrefix={settings.JONATHAN_NEXUS_PREFIX} \
            --set offlineMode={settings.JF_OFFLINE_MODE} \
            --set nexus.hostname={settings.JONATHAN_NEXUS_HOST} \
            --set nexus.port={settings.JONATHAN_NEXUS_PORT} \
            {labels_command} {env_command} {resource_limit_command} {hps_command} {nodes_command} \
            """
            
            # --set dataset.access={project_tool_pod.dataset_access} \
            # --set dataset.name={project_tool_pod.dataset_name} \
        if hps_pod.cpu_instance_name:
            command += f"  --set spec.cpu_instance_name={hps_pod.cpu_instance_name}"
            
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

def create_project_training_pod(training_pod : TrainingPodInfo):
    try:
        os.chdir("/app/helm_chart/") # TODO 나중에 변수화 해야할 듯

        training_command = f' --set spec.containers.command="{training_pod.command}"'
        
        labels_command=""
        for key, val in training_pod.labels.model_dump().items():
            if val:
                labels_command += f" --set labels.{key}={val}"
        
        env_command=""
        for key, val in training_pod.env.model_dump().items():
            if val:
                env_command += f" --set spec.containers.env.{key}={val}"
            
        resource_limit_command=""
        for key, val in training_pod.resource.model_dump().items():
            resource_limit_command += f" --set spec.containers.resource.limits.{key}={val}"
        
        nodes_command = ""
        for index, node in enumerate(training_pod.cluster):
            nodes_command += f" --set cluster[{index}].node_name={node.node_name}"
            nodes_command += f' --set cluster[{index}].device.type="{node.device.device_type}"'
            nodes_command += f' --set cluster[{index}].device.model="{node.device.model}"'
            nodes_command += f" --set cluster[{index}].device.count={node.device.count}"
            nodes_command += f' --set cluster[{index}].device.uuids="{node.device.uuids}"'
            nodes_command += f' --set cluster[{index}].device.ids="{node.device.ids}"'
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=training_pod.labels.workspace_id)
        command=f"""helm install {training_pod.labels.helm_name} project_job/ \
            -n {namespace} \
            --set namespace={namespace} \
            --set owner_name={training_pod.owner_name} \
            --set pod_name={training_pod.pod_name} \
            --set spec.restartPolicy={training_pod.restartPolicy} \
            --set spec.containers.image={training_pod.image} \
            --set distributed_framework={training_pod.distributed_framework} \
            --set distributed_config_path="{training_pod.distributed_config_path}" \
            --set total_device_count={training_pod.total_device_count} \
            --set spec.hostname={training_pod.hostname} \
            --set dataset.access={training_pod.dataset_access} \
            --set dataset.name={training_pod.dataset_name} \
            --set privateRepo={settings.JONATHAN_PRIVATE_REPO_ENABLED} \
            --set privatePip={settings.JONATHAN_PRIVATE_PIP_ENABLED} \
            --set nexusPrefix={settings.JONATHAN_NEXUS_PREFIX} \
            --set offlineMode={settings.JF_OFFLINE_MODE} \
            --set nexus.hostname={settings.JONATHAN_NEXUS_HOST} \
            --set nexus.port={settings.JONATHAN_NEXUS_PORT} \
            {labels_command} {env_command} {resource_limit_command} {training_command} {nodes_command} \
            """
            
            # --set dataset.access={project_tool_pod.dataset_access} \
            # --set dataset.name={project_tool_pod.dataset_name} \
        if training_pod.cpu_instance_name:
            command += f"  --set spec.cpu_instance_name={training_pod.cpu_instance_name}"
            
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


def install_deployment_svc_ing(deployment_info: DeploymentInfo):
    # labels, workspace_name, workspace_id, deployment_id, base_pod_name, **kwargs):
    workspace_name = deployment_info.get("workspace_name")
    workspace_id =  deployment_info.get("workspace_id")
    deployment_id = deployment_info.get("deployment_id")
    pod_base_name = deployment_info.get("pod_base_name")
    
    labels = DeploymentLabels(**deployment_info).dict()
    labels_command=""
    for key,val in labels.items():
        labels_command += f"--set labels.{key}={val} "

    # =======================================================================================
    namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
    work_func_type = deployment_info.get("work_func_type")
    helm_path = "./deployment_svc" # JONATHAN

    # svc, ing 는 배포 당 1개씩 만듬 (worker 마다 1개가 아니라)
    namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)    
    command=f"helm install deployment-svc-ing-{deployment_id} \
        -n {namespace} --create-namespace \
        --set metadata.id.deploymentId={str(deployment_id)} \
        --set metadata.id.workspaceId={str(workspace_id)} \
        --set metadata.name.podBaseName={pod_base_name} \
        --set metadata.name.workspaceName={workspace_name} \
        --set metadata.namespace.systemNamespace={settings.JF_SYSTEM_NAMESPACE} \
        --set metadata.pod.podBaseName={pod_base_name} \
        --set ingress.ingressClassName={settings.INGRESS_CLASS_NAME} \
        {labels_command} {helm_path}"
        
    try:
        print(command, file=sys.stderr)
        os.chdir("/app/helm_chart/")
        result = subprocess.run(
            command, shell=True, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip()
        if "cannot re-use a name that is still in use" in err_msg:
            return True, ""
        
        err_msg = e.stderr.strip()
        print(e.stdout, file=sys.stderr)
        print(err_msg, file=sys.stderr)
        print(command, file=sys.stderr)
        return False, err_msg
    except Exception as e:
        print(traceback.print_exc(), file=sys.stderr)        
        return False, ""
        
def install_deployment_pod(deployment_info: dict):
    # 기본정보    
    deployment_name = deployment_info.get("deployment_name")    
    deployment_id = deployment_info.get("deployment_id")
    deployment_worker_id = deployment_info.get("deployment_worker_id")
    workspace_name =  deployment_info.get("workspace_name")
    workspace_id = deployment_info.get("workspace_id")
    project_name = deployment_info.get("project_name")
    pod_name = deployment_info.get("pod_name")
    pod_base_name = deployment_info.get("pod_base_name")
    pod_image = deployment_info.get("pod_image")
    run_code =deployment_info.get("run_code")
    model_type = deployment_info.get("model_type")
    huggingface_model_id = deployment_info.get("huggingface_model_id")
    huggingface_token = deployment_info.get("huggingface_token")
    training_id = deployment_info.get("training_id")

    # resource
    gpu_count = deployment_info.get("gpu_count")
    used_npu = deployment_info.get("used_npu", False)
    npu_count = 1 if deployment_info.get("used_npu", False) else 0
    
    # # cluster, nodes ======================================================================
    # node_name=""
    # gpu_uuids=""
    # cpu_instance_name=""
    # nodes = []
    # if deployment_info.get("available_gpus",None):
    #     for gpu_info in deployment_info["available_gpus"]:
    #         gpu_ids = []
    #         gpu_uuids = []
    #         for gpu_uuid in list(gpu_info["gpu_uuids"]):
    #             try:
    #                 # DB에 존재하는 gpu uuid인지 확인 
    #                 gpu_ids.append(db_node.get_node_gpu(gpu_uuid=gpu_uuid)["id"])
    #                 gpu_uuids.append(gpu_uuid)
    #             except:
    #                 # TODO
    #                 # 해당 gpu 제외 사켜야 하는지..
    #                 pass
    #         nodes.append(Cluster(
    #             node_name = gpu_info["node_name"],
    #             gpu_uuids =  escape_special_chars(",".join(gpu_uuids)),
    #             gpu_ids = ".".join(map(str, gpu_ids)),
    #             gpu_count = len(gpu_uuids)
    #         ))
    # elif deployment_info.get("available_node",None):
    #     nodes.append(Cluster(
    #             node_name = deployment_info["available_node"],
    #             gpu_uuids =  "",
    #             gpu_count = 0
    #         ))
    # elif deployment_info.get("cpu_instance_name", None):
    #     nodes.append(Node()) # helm 에서 for문을 돌려야 하기 때문에 
    #     cpu_instance_name=deployment_info.get("cpu_instance_name")
    # elif used_npu:
    #     nodes.append(Node())
    # cluster_command = ""
    # for index, cluster in enumerate(nodes):
    #     cluster_command += f" --set cluster[{index}].node_name={cluster.node_name}"
    #     cluster_command += f' --set cluster[{index}].gpu_uuids="{cluster.gpu_uuids}"'
    #     cluster_command += f' --set cluster[{index}].gpu_ids="{cluster.gpu_ids}"'
    #     cluster_command += f" --set cluster[{index}].gpu_count={cluster.gpu_count}"

    cluster_info = get_cluster_command(pod_info=deployment_info)
    cluster_command = cluster_info.get("cluster_command")
    cpu_instance_name = cluster_info.get("cpu_instance_name")
    used_npu = cluster_info.get("used_npu")
    node_name = cluster_info.get("node_name")

    # =======================================================================================
    labels_command=""
    labels = DeploymentLabels(**deployment_info).dict()
    if labels is not None:
        for key,val in labels.items():
            labels_command += f"--set labels.{key}={val} "

    env_command=""
    env = deployment_info.get("env")
    if env is not None:
        for item in env:
            env_command +=f"--set env.{item['name']}={item['value']} "

    annotation_command=""
    pod_annotation = deployment_info.get("pod_annotation")
    if pod_annotation is not None:
        for key,val in pod_annotation.items():
            annotation_command += f"--set annotations.{key}={val} "
            
    resources_command=""
    resources = deployment_info.get("resources")
    if resources is not None:
        for key,val in resources.items():
            if key == "limits":
                if val is not None:
                    for k, v in val.items():
                        resources_command += f"--set resources.limits.{k}={v}  " 
            else:
                if val is not None:
                    for k, v in val.items():
                        resources_command += f"--set resources.requests.{k}={v}  " 

    # LLM
    deployment_llm_command=""
    deployment_llm = deployment_info.get("deployment_llm")
    if deployment_llm is not None:
        json_deployment_llm = json.dumps(deployment_llm)
        deployment_llm_command = f" --set-json llm='{json_deployment_llm}' "
    
    deployment_llm_db_command=""
    deployment_llm_db = deployment_info.get("deployment_llm_db")
    if deployment_llm_db is not None:
        json_deployment_llm_db = json.dumps(deployment_llm_db)
        deployment_llm_db_command = f" --set-json llm.db='{json_deployment_llm_db}' "
 
    # =======================================================================================
    namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
    work_func_type = deployment_info.get("work_func_type")
    helm_path = "./deployment_pod" # JONATHAN

    command=f"helm install deployment-pod-{deployment_id}-{deployment_worker_id} \
        -n {namespace} --create-namespace \
        --set metadata.name.podName={pod_name} \
        --set metadata.name.podBaseName={pod_base_name} \
        --set metadata.name.hostname={pod_name} \
        --set metadata.name.workspaceName={workspace_name} \
        --set metadata.name.trainingName={project_name} \
        --set metadata.name.deploymentName={deployment_name} \
        --set metadata.namespace.systemNamespace={settings.JF_SYSTEM_NAMESPACE} \
        --set metadata.id.workspaceId={workspace_id} \
        --set pod.cpuInstance={cpu_instance_name} \
        --set pod.image={pod_image} \
        --set pod.imageRegistry={settings.DOCKER_REGISTRY_URL} \
        --set command.runCode=\'{run_code}\' \
        --set command.deploymentWorkerId={deployment_worker_id} \
        --set resources.limits.npu={npu_count} \
        --set resources.limits.gpu={gpu_count} \
        --set resources.requests.gpu={gpu_count} \
        --set ingress.ingressClassName={settings.INGRESS_CLASS_NAME} \
        --set deployment.model_type={model_type} \
        --set deployment.huggingface_model_id={huggingface_model_id} \
        --set deployment.huggingface_token={huggingface_token} \
        --set deployment.training_id={training_id} \
        --set privateRepo={settings.JONATHAN_PRIVATE_REPO_ENABLED} \
        --set privatePip={settings.JONATHAN_PRIVATE_PIP_ENABLED} \
        --set nexusPrefix={settings.JONATHAN_NEXUS_PREFIX} \
        --set offlineMode={settings.JF_OFFLINE_MODE} \
        --set nexus.hostname={settings.JONATHAN_NEXUS_HOST} \
        --set nexus.port={settings.JONATHAN_NEXUS_PORT} \
        {labels_command} {annotation_command} {env_command} {resources_command} {cluster_command} \
        --set labels.helm_name=deployment-pod-{deployment_id}-{deployment_worker_id} \
        {deployment_llm_command} {deployment_llm_db_command} {helm_path}"
    # =======================================================================================
    try:
        print("*" * 10, file=sys.stderr)
        print(command, file=sys.stderr)
        print("*" * 10, file=sys.stderr)

        os.chdir("/app/helm_chart/")
        subprocess.run(command, shell=True, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # start_datetime 입력
        db_deployment.update_start_datetime_deployment_worker(deployment_worker_id=deployment_worker_id)
        
        return True, ""
        # return result.stdout
    except subprocess.CalledProcessError as e:
        uninstall_pod_deployment(workspace_id, deployment_id, deployment_worker_id)
        err_msg = e.stderr.strip()
        print(e.stdout, file=sys.stderr)
        print(err_msg, file=sys.stderr)
        print(command, file=sys.stderr)
        return False, err_msg
    
def uninstall_pod_deployment(workspace_id, deployment_id, deployment_worker_id, **kwargs):
    helm_namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
    command=f"helm uninstall -n {helm_namespace} deployment-pod-{deployment_id}-{deployment_worker_id}"
    try:
        os.chdir("/app/helm_chart/")
        subprocess.run(
            command, shell=True, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return True, ""
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip()
        print(e.stdout)
        print(err_msg)
        print(command)
        return False, err_msg
    
def uninstall_all_deployment(workspace_id, deployment_id, **kwargs):
    helm_namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
    # deployment-pod-{deployment_id}- 끝에 '-' 없으면 안됨
    command_pod=f"helm list -n {helm_namespace} | grep deployment-pod-{deployment_id}- | \
        awk \'{{print $1}}\' | xargs helm uninstall -n {helm_namespace} "

    try:
        os.chdir("/app/helm_chart/")
        subprocess.run(
            command_pod, shell=True, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        print(e.stdout)
        print(e.stderr)
        print(command_pod)
    
    command_svc_ing=f"helm list -n {helm_namespace} | grep deployment-svc-ing-{deployment_id} | \
        awk \'{{print $1}}\' | xargs helm uninstall -n {helm_namespace} "

    try:
        os.chdir("/app/helm_chart/")
        subprocess.run(
            command_svc_ing, shell=True, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return True, ""
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip()
        print(e.stdout)
        print(err_msg)
        print(command_svc_ing)
        return False, err_msg

def delete_helm_preprocessing(preprocessing_tool_type : str, preprocessing_tool_id : int, workspace_id : int):
    try:
        os.chdir("/app/helm_chart/")
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
        command=f"helm uninstall {TYPE.PREPROCESSING_HELM_CHART_NAME.format(preprocessing_tool_id, preprocessing_tool_type)} -n {namespace}"
        
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

def delete_helm_project(project_tool_type : str, project_tool_id : int, workspace_id : int):
    try:
        os.chdir("/app/helm_chart/")
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
        command=f"helm uninstall {TYPE.PROJECT_HELM_CHART_NAME.format(project_tool_id, project_tool_type)} -n {namespace}"
        
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

def delete_helm_fine_tuning(model_id : int, workspace_id : int):
    try:
        os.chdir("/app/helm_chart/")
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=workspace_id)
        command=f"helm uninstall {TYPE.FINE_TUNING_REPO_NAME.format(model_id)} -n {namespace}"
        
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


def install_deployment_llm(pod_info):
    cluster_info = get_cluster_command(pod_info=pod_info)
    cluster_command = cluster_info.get("cluster_command")
    cpu_instance_name = cluster_info.get("cpu_instance_name")
    rdma_command = cluster_info.get("rdma_command")
    used_npu = cluster_info.get("used_npu")
    node_name = cluster_info.get("node_name")

    print("*" * 10, file=sys.stderr)
    print(pod_info, file=sys.stderr)
    print("*" * 10, file=sys.stderr)
    try:
        helm_name = pod_info.get("metadata_helm_name")
        set_values = YamlToValues(**pod_info, pod_cpu_instance=cpu_instance_name)
        command=f"helm install {helm_name} -n {pod_info.get("metadata_workspace_namespace")} \
            {set_values} {cluster_command} {rdma_command} ./deployment_llm"
    except Exception as e:
        traceback.print_exc()
        return False, str(e)

    # =======================================================================================
    try:
        os.chdir("/app/helm_chart/")
        subprocess.run(command, shell=True, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # start_datetime 입력
        db_deployment.update_start_datetime_deployment_worker(deployment_worker_id=pod_info.get("deployment_worker_id"))
        return True, ""
        # return result.stdout
    except subprocess.CalledProcessError as e:
        # uninstall_pod_deployment(workspace_id, deployment_id, deployment_worker_id)
        try:
            # embedding, reranker 연속 실행시 발생??
            err_msg = e.stderr.strip()
            if "cannot re-use a name that is still in use" in err_msg:
                print(err_msg, file=sys.stderr)
                uninstall_command = f"helm uninstall -n {pod_info.get('metadata_workspace_namespace')} {helm_name}"
                command = f"{uninstall_command} && {command}"
                subprocess.run(command, shell=True, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return True, ""
        except Exception as e:
            return False, err_msg

        err_msg = e.stderr.strip()
        print(e.stdout, file=sys.stderr)
        print(err_msg, file=sys.stderr)
        print(command, file=sys.stderr)
        return False, err_msg

def uninstall_deployment_llm(deployment_id, llm_type, llm_id):
    try:
        deployment_info = db_deployment.get_deployment(deployment_id=deployment_id)

        # llm 은 배포당 워커 1개이므로, deployment_id 로 worker end_datetime 업데이트
        db_deployment.update_end_datetime_deployment_worker(deployment_id=deployment_id)

        helm_namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=deployment_info.get("workspace_id"))
        llm_deployment_helm_name = TYPE.LLM_DEPLOYMENT_HELM_NAME.format(deployment_id=deployment_id, llm_type=llm_type, llm_id=llm_id)

        def uninstall_deployment_helm():
            command=f"helm uninstall -n {helm_namespace} {llm_deployment_helm_name} "
            try:
                subprocess.run(
                    command, shell=True, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
            except Exception as e:
                pass

        uninstall_deployment_helm()
        command = f"helm list -n {helm_namespace} | grep {llm_deployment_helm_name}"
        try:
            subprocess.run(command, shell=True, check=True, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            # 결과가 나오면 삭제 안된것이므로 한번더 삭제
            uninstall_deployment_helm(deployment_id, llm_type, llm_id)
        except Exception as e:
            pass
    except Exception as e:
        traceback.print_exc()
        raise e


def get_cluster_command(pod_info):
    try:
        node_name=""
        gpu_uuids=""
        cpu_instance_name=""
        nodes = []
        used_npu = pod_info.get("used_npu", False)

        resource_type = pod_info.get("resource_type")
        model = (pod_info.get("resource_name") or "").replace(" ", "_")
        if pod_info.get("available_gpus",None):
            # available_gpus가 있을 때 resource_type이 없으면 GPU로 설정
            if not resource_type:
                resource_type = "GPU"
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
                ))
            )
        elif pod_info.get("cpu_instance_name", None):
            nodes.append(Node(
                device=Accelerator(
                    device_type=resource_type,
                    model=model,
                    count=0
                )
        )) # helm 에서 for문을 돌려야 하기 때문에 
            cpu_instance_name=pod_info.get("cpu_instance_name")
        elif used_npu:
            nodes.append(Node(
                device=Accelerator(
                    device_type=resource_type,
                    model=model,
                    count=0
                )
        ))
        cluster_command = ""
        for index, node in enumerate(nodes):
            cluster_command += f" --set cluster[{index}].node_name={node.node_name}"
            cluster_command += f' --set cluster[{index}].device.type="{node.device.device_type}"'
            cluster_command += f' --set cluster[{index}].device.model="{node.device.model}"'
            cluster_command += f" --set cluster[{index}].device.count={node.device.count}"
            cluster_command += f' --set cluster[{index}].device.uuids="{node.device.uuids}"'
            cluster_command += f' --set cluster[{index}].device.ids="{node.device.ids}"'
        rdma_command = ""
        if settings.JF_RDMA_ENABLED:
            rdma_command += " --set rdma.enabled=true"
            if settings.JFB_MP_SEED_NUM and settings.JFB_MP_SEED_LIST:
                rdma_command += f" --set rdma.mp.enabled=true"
                rdma_command += f" --set rdma.mp.seed_num={settings.JFB_MP_SEED_NUM}"
                seed_list = json.loads(settings.JFB_MP_SEED_LIST.strip())
                rdma_command += f" --set-json 'rdma.mp.seed_list={json.dumps(seed_list)}'"
            if settings.JF_PERF_ENABLED:
                rdma_command += " --set rdma.perf.enabled=true"
            if settings.JF_P2P_LIST:
                p2p_list = json.loads(settings.JF_P2P_LIST.strip())
                rdma_command += f" --set-json 'rdma.p2p={json.dumps(p2p_list)}'"

        return {
            "cluster_command": cluster_command,
            "cpu_instance_name": cpu_instance_name,
            "used_npu": used_npu,
            "node_name" : node_name,
            "rdma_command" : rdma_command
        }
    except Exception as e:
        traceback.print_exc()
        raise e



def create_analyzer_pod(pod_info):
    from utils.helm_dto import YamlToSetValuesAnalyzer
    try:
        cluster_info = get_cluster_command(pod_info=pod_info)
        cluster_command = cluster_info.get("cluster_command")
        cpu_instance_name = cluster_info.get("cpu_instance_name")
        used_npu = cluster_info.get("used_npu")
        node_name = cluster_info.get("node_name")

        print("*" * 10, file=sys.stderr)
        print(pod_info, file=sys.stderr)
        print("*" * 10, file=sys.stderr)

        helm_name = pod_info.get("metadata_helm_name")
        helm_namespace = pod_info.get("metadata_workspace_namespace")
        set_values = YamlToSetValuesAnalyzer(**pod_info, pod_cpu_instance=cpu_instance_name)
        command=f"helm install {helm_name} -n {helm_namespace} {set_values} {cluster_command} ./analyzer"
        
        print(command)
        os.chdir("/app/helm_chart/")
        subprocess.run(command, shell=True, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # start_datetime 입력
        db_analyzing.update_start_datetime_analyzer_graph(graph_id=pod_info.get("graph_id"))
        return True, ""
    except subprocess.CalledProcessError as e:
        delete_helm_analyzer(pod_info=pod_info)
        try:
            err_msg = e.stderr.strip()
            if "cannot re-use a name that is still in use" in err_msg:
                print(err_msg, file=sys.stderr)
                uninstall_command = f"helm uninstall -n {helm_namespace} {helm_name}"
                command = f"{uninstall_command} && {command}"
                subprocess.run(command, shell=True, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return True, ""
        except Exception as e:
            return False, err_msg

        err_msg = e.stderr.strip()
        print(e.stdout, file=sys.stderr)
        print(err_msg, file=sys.stderr)
        print(command, file=sys.stderr)
        return False, err_msg

def delete_helm_analyzer(pod_info):
    try:
        # DB end datetime 기록
        db_analyzing.update_end_datetime_analyzer_graph(graph_id=pod_info.get("graph_id"))

        helm_namespace = pod_info.get("metadata_workspace_namespace")
        helm_name = pod_info.get("metadata_helm_name")

        def uninstall_deployment_helm():
            command=f"helm uninstall -n {helm_namespace} {helm_name} "
            try:
                subprocess.run(
                    command, shell=True, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
            except Exception as e:
                pass

        uninstall_deployment_helm()
        command = f"helm list -n {helm_namespace} | grep {helm_name}"
        try:
            subprocess.run(command, shell=True, check=True, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            # 결과가 나오면 삭제 안된것이므로 한번더 삭제
            uninstall_deployment_helm(pod_info)
        except Exception as e:
            pass
    except Exception as e:
        traceback.print_exc()
        raise e

