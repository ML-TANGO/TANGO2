import subprocess
import os, sys, re
import traceback
from utils import settings, TYPE

from scheduler.dto import *

from utils.msa_db import db_deployment, db_node

def create_project_tool_pod(project_tool_pod : ToolPodInfo):
    try:
        helm_repo = TYPE.PROJECT_HELM_CHART_NAME.format(project_tool_pod.labels.project_item_id, project_tool_pod.labels.project_tool_type)
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

        nodes_command = ""
        for index, cluster in enumerate(project_tool_pod.clusters):
            nodes_command += f" --set cluster[{index}].node_name={cluster.node_name}"
            nodes_command += f' --set cluster[{index}].gpu_uuids="{cluster.gpu_uuids}"'
            nodes_command += f' --set cluster[{index}].gpu_ids="{cluster.gpu_ids}"'
            nodes_command += f" --set cluster[{index}].gpu_count={cluster.gpu_count}"

        command=f"""helm install {helm_repo} {project_tool_pod.labels.project_tool_type}/ \
            -n {settings.JF_SYSTEM_NAMESPACE} \
            --set system.namespace={settings.JF_SYSTEM_NAMESPACE} \
            --set ingress_class_name={settings.INGRESS_CLASS_NAME} \
            --set owner_name={project_tool_pod.owner_name} \
            --set pod_name={project_tool_pod.pod_name} \
            --set spec.containers.image="{project_tool_pod.image}" \
            --set domain="{settings.EXTERNAL_HOST}" \
            --set tool_password="{project_tool_pod.tool_password}" \
            --set spec.restartPolicy={project_tool_pod.restartPolicy}\
            --set total_gpu_count={project_tool_pod.total_gpu_count} \
            --set spec.hostname={project_tool_pod.hostname} \
            {labels_command} {env_command} {resource_limit_command} {nodes_command} \
            """
        if project_tool_pod.cpu_instance_name:
            command += f"  --set spec.cpu_instance={project_tool_pod.cpu_instance_name}"

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
        training_command=""
        if training_pod.labels.work_func_type == "hps":
            training_command = ""
            for key, val in training_pod.command.model_dump().items():
                if val:
                    training_command += f' --set spec.containers.command.{key}="{val}"'
        elif training_pod.labels.work_func_type == "training":
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
        for index, cluster in enumerate(training_pod.clusters):
            nodes_command += f' --set cluster[{index}].node_name="{cluster.node_name}"'
            nodes_command += f' --set cluster[{index}].gpu_uuids="{cluster.gpu_uuids}"'
            nodes_command += f' --set cluster[{index}].gpu_ids="{cluster.gpu_ids}"'
            nodes_command += f" --set cluster[{index}].gpu_count={cluster.gpu_count}"

        command=f"""helm install {training_pod.helm_repo_name} {training_pod.labels.work_func_type}/ \
            -n {settings.JF_SYSTEM_NAMESPACE} \
            --set system.namespace={settings.JF_SYSTEM_NAMESPACE} \
            --set owner_name={training_pod.owner_name} \
            --set pod_name={training_pod.pod_name} \
            --set spec.restartPolicy={training_pod.restartPolicy} \
            --set spec.containers.image={training_pod.image} \
            --set distributed_framework={training_pod.distributed_framework} \
            --set distributed_config_path="{training_pod.distributed_config_path}" \
            --set total_gpu_count={training_pod.total_gpu_count} \
            --set spec.hostname={training_pod.hostname} \
            {labels_command} {env_command} {resource_limit_command} {training_command} {nodes_command} \
            """
        if training_pod.cpu_instance_name:
            command += f"  --set spec.cpu_instance={training_pod.cpu_instance_name}"

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

    # svc, ing 는 배포 당 1개씩 만듬 (worker 마다 1개가 아니라)
    command=f"helm install deployment-svc-ing-{deployment_id} \
        -n {settings.JF_SYSTEM_NAMESPACE}-dp --create-namespace \
        --set metadata.deployment.id={str(deployment_id)} \
        --set metadata.workspace.id={str(workspace_id)} \
        --set metadata.workspace.name={workspace_name} \
        --set metadata.system.namespace={settings.JF_SYSTEM_NAMESPACE} \
        --set metadata.pod.podBaseName={pod_base_name} \
        --set ingress.ingressClassName={settings.INGRESS_CLASS_NAME} \
        {labels_command} \
        ./deployment_svc"

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
            return True, "use"
        print(e.stdout, file=sys.stderr)
        print(err_msg, file=sys.stderr)
        print(command, file=sys.stderr)
        return False, err_msg
    except Exception as e:
        print(traceback.print_exc(), file=sys.stderr)
        return False, ""


def install_deployment_pod(deployment_info: dict):
    from scheduler.project_tool_run import escape_special_chars # circular import

    workspace_name =  deployment_info.get("workspace_name")
    deployment_name = deployment_info.get("deployment_name")
    project_name = deployment_info.get("project_name")
    pod_name = deployment_info.get("pod_name")
    workspace_id = deployment_info.get("workspace_id")
    deployment_id = deployment_info.get("deployment_id")
    deployment_worker_id = deployment_info.get("deployment_worker_id")
    pod_image = deployment_info.get("pod_image")
    resource_name = deployment_info.get("resource_name")
    run_code =deployment_info.get("run_code")
    node_name = deployment_info.get("node_name")
    node_name = deployment_info.get("node_name")
    pod_annotation = deployment_info.get("pod_annotation")
    no_delete = deployment_info.get("no_delete")
    env = deployment_info.get("env")
    # pod_resource_limit = deployment_info.get("pod_resource_limit")
    gpu_count = deployment_info.get("gpu_count")
    resources = deployment_info.get("resources")
    cpu_limits = resources.get("cpu_limits")
    ram_limits = resources.get("ram_limits")

    labels = DeploymentLabels(**deployment_info).dict()

    node_name=""
    gpu_uuids=""
    cpu_instance_name=""

    nodes = []
    if deployment_info.get("available_gpus",None):
        for gpu_info in deployment_info["available_gpus"]:
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
            nodes.append(Cluster(
                node_name = gpu_info["node_name"],
                gpu_uuids =  escape_special_chars(",".join(gpu_uuids)),
                gpu_ids = ".".join(map(str, gpu_ids)),
                gpu_count = len(gpu_uuids)
            ))
    elif deployment_info.get("available_node",None):
        nodes.append(Cluster(
                node_name = deployment_info["available_node"],
                gpu_uuids =  "",
                gpu_count = 0
            ))
    elif deployment_info.get("cpu_instance_name", None):
        nodes.append(Cluster()) # helm 에서 for문을 돌려야 하기 때문에
        cpu_instance_name=deployment_info.get("cpu_instance_name")

    cluster_command = ""
    for index, cluster in enumerate(nodes):
        cluster_command += f" --set cluster[{index}].node_name={cluster.node_name}"
        cluster_command += f' --set cluster[{index}].gpu_uuids="{cluster.gpu_uuids}"'
        cluster_command += f' --set cluster[{index}].gpu_ids="{cluster.gpu_ids}"'
        cluster_command += f" --set cluster[{index}].gpu_count={cluster.gpu_count}"

    labels_command=""

    for key,val in labels.items():
        labels_command += f"--set labels.{key}={val} "

    env_command=""
    for item in env:
        # env format: [{'name': 'JF_HOME', 'value': '/jf-training-home'}, {}, ...]
        env_command +=f"--set env.{item['name']}={item['value']} "

    annotation_command=""
    if pod_annotation is not None:
        for key,val in pod_annotation.items():
            annotation_command += f"--set pod.metadata.annotations.{key}={val} "

    # limits_command="" # 현재 임시값 고정 사용
    # if pod_resource_limit is not None:
    #     for key,val in pod_resource_limit.items():
    #         if key == "nvidia.com/gpu":
    #             key = "gpu"
    #         limits_command += f"--set pod.resources.limits.{key}={val} "

    command=f"helm install deployment-pod-{deployment_id}-{deployment_worker_id} \
        -n {settings.JF_SYSTEM_NAMESPACE}-dp --create-namespace \
        --set pod.metadata.name={pod_name} \
        --set pod.spec.hostname={pod_name} \
        --set pod.spec.nodeName={node_name} \
        --set pod.spec.nodeSelector.cpuInstance={cpu_instance_name} \
        --set pod.spec.container.image={pod_image} \
        --set pod.spec.container.name={pod_name} \
        --set pod.spec.container.command.runCode=\'{run_code}\' \
        --set pod.spec.container.command.deploymentWorkerId={deployment_worker_id} \
        --set resources.limits.gpu={gpu_count} \
        --set resources.requests.gpu={gpu_count} \
        --set resources.limits.cpu={cpu_limits} \
        --set resources.limits.ram={ram_limits} \
        --set metadata.name.trainingName={project_name} \
        --set metadata.name.deploymentName={deployment_name} \
        --set metadata.name.workspaceName={workspace_name} \
        --set metadata.namespace.systemNamespace={settings.JF_SYSTEM_NAMESPACE} \
        --set metadata.namespace.workspaceId={workspace_id} \
        {labels_command} {annotation_command} {env_command} {cluster_command} \
        ./deployment_pod"
    # {limits_command}

    try:
        print(command, file=sys.stderr)

        os.chdir("/app/helm_chart/")
        subprocess.run(
            command, shell=True, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

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
    command=f"helm uninstall -n {settings.JF_SYSTEM_NAMESPACE}-dp deployment-pod-{deployment_id}-{deployment_worker_id}"
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
    # deployment-pod-{deployment_id}- 끝에 '-' 없으면 안됨
    command_pod=f"helm list -n {settings.JF_SYSTEM_NAMESPACE}-dp | grep deployment-pod-{deployment_id}- | \
        awk \'{{print $1}}\' | xargs helm uninstall -n {settings.JF_SYSTEM_NAMESPACE} "

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

    command_svc_ing=f"helm list -n {settings.JF_SYSTEM_NAMESPACE}-dp | grep deployment-svc-ing-{deployment_id} | \
        awk \'{{print $1}}\' | xargs helm uninstall -n {settings.JF_SYSTEM_NAMESPACE} "

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

def delete_helm_resource(project_tool_type : str, project_tool_id : int):
    try:
        os.chdir("/app/helm_chart/")
        command=f"helm uninstall {TYPE.PROJECT_HELM_CHART_NAME.format(project_tool_id, project_tool_type)} -n {settings.JF_SYSTEM_NAMESPACE}"

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
