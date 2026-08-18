from utils.msa_db import db_node, db_workspace, db_prepro, db_dataset
# from utils.exception.exceptions import *
from utils.settings import *
# from utils.TYPE import *
from utils import PATH, TYPE, settings, common, TYPE_BUILT_IN

from scheduler.dto import *
from utils.kube import PodName

from datetime import datetime

import re, sys, subprocess, os


# 데이터 파이프라인 노드 스크립트 접두어. /built_in/dp_prep.py 처럼 실행되며,
# 이 접두어를 가진 잡만 /datasets(워크스페이스 data PVC 루트) RO 마운트를 받는다.
DATA_PIPELINE_SCRIPT_PREFIX = "dp_"
# 데이터 파이프라인 노드 빌트인 종류. TYPE_BUILT_IN 에 등록하는 것만으로는 부족하고
# 여기 분기에 걸려야 실행 명령이 만들어진다(안 걸리면 command="" 로 파드만 뜨고 끝).
DATA_PIPELINE_TFS = {TYPE_BUILT_IN.DP_PREP}


def get_job_parameter(run_parameter, unified_memory):
    parameter = run_parameter
    if unified_memory == 1:
        parameter += " --unified_memory 1 "
    
    return parameter


def job_run_command(run_code_type: str, run_code: str, parameter: str):
    run_command = ""
    if run_code_type == "py":
        run_command = f"python3 -u {run_code} {parameter}"
    elif run_code_type == "sh":
        run_command = f"bash {run_code} {parameter}"
    else:
        run_command = f"{run_code} {parameter}"
    return run_command

def create_preprocessing_job_pod(preprocessing_job_info : PreprocessingJobPodInfo):
    try:
        os.chdir("/app/helm_chart/") # TODO 나중에 변수화 해야할 듯
        job_command = f" --set spec.containers.command={common.helm_set_value(preprocessing_job_info.command)}"
        
        labels_command=""
        for key, val in preprocessing_job_info.labels.model_dump().items():
            if val:
                labels_command += f" --set labels.{key}={common.helm_set_value(val)}"
        
        env_command=""
        for key, val in preprocessing_job_info.env.model_dump().items():
            if val:
                env_command += f" --set spec.containers.env.{key}={common.helm_set_value(val)}"
            
        resource_limit_command=""
        for key, val in preprocessing_job_info.resource.model_dump().items():
            resource_limit_command += f" --set spec.containers.resource.limits.{key}={common.helm_set_value(val)}"
        nodes_command = ""
        for index, node in enumerate(preprocessing_job_info.cluster):
            nodes_command += f" --set cluster[{index}].node_name={common.helm_set_value(node.node_name)}"
            nodes_command += f" --set cluster[{index}].device.type={common.helm_set_value(node.device.device_type)}"
            nodes_command += f" --set cluster[{index}].device.model={common.helm_set_value(node.device.model)}"
            nodes_command += f" --set cluster[{index}].device.count={common.helm_set_value(node.device.count)}"
            nodes_command += f" --set cluster[{index}].device.uuids={common.helm_set_value(node.device.uuids)}"
            nodes_command += f" --set cluster[{index}].device.ids={common.helm_set_value(node.device.ids)}"        
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=preprocessing_job_info.labels.workspace_id)
        # 데이터 파이프라인 노드(dp_*.py)만 소스 데이터셋이 여러 개일 수 있어 워크스페이스
        # data PVC 루트를 /datasets 에 RO 로 추가 마운트한다. 기존 빌트인은 /dataset 단일
        # 마운트만 쓰므로 기본 off — 스크립트 이름으로 가른다(불리언 하나를 run_job 3계층에
        # 관통시키지 않기 위해. 판정을 바꾸려면 여기 한 곳만 보면 된다).
        datasets_root = f"/{DATA_PIPELINE_SCRIPT_PREFIX}" in str(preprocessing_job_info.command or "")
        command=f"""helm install {common.shell_arg(preprocessing_job_info.labels.helm_name)} prepro_job/ \
            --set datasetsRoot={str(bool(datasets_root)).lower()} \
            -n {common.shell_arg(namespace)} \
            --set system.namespace={settings.JF_SYSTEM_NAMESPACE} \
            --set namespace={common.shell_arg(namespace)} \
            --set owner_name={common.helm_set_value(preprocessing_job_info.owner_name)} \
            --set pod_name={common.helm_set_value(preprocessing_job_info.pod_name)} \
            --set spec.restartPolicy={preprocessing_job_info.restartPolicy} \
            --set spec.containers.image={common.helm_set_value(preprocessing_job_info.image)} \
            --set total_device_count={preprocessing_job_info.total_device_count} \
            --set spec.hostname={common.helm_set_value(preprocessing_job_info.hostname)} \
            --set dataset.access={common.helm_set_value(preprocessing_job_info.dataset_access)} \
            --set dataset.name={common.helm_set_value(preprocessing_job_info.dataset_name)} \
            --set privateRepo={settings.JONATHAN_PRIVATE_REPO_ENABLED} \
            --set privatePip={settings.JONATHAN_PRIVATE_PIP_ENABLED} \
            --set nexusPrefix={settings.JONATHAN_NEXUS_PREFIX} \
            --set offlineMode={settings.JF_OFFLINE_MODE} \
            --set nexus.hostname={settings.JONATHAN_NEXUS_HOST} \
            --set nexus.port={settings.JONATHAN_NEXUS_PORT} \
            {labels_command} {env_command} {resource_limit_command} {job_command} {nodes_command} \
            """
            
            
        if preprocessing_job_info.cpu_instance_name:
            command += f"  --set spec.cpu_instance_name={common.helm_set_value(preprocessing_job_info.cpu_instance_name)}"
            
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



def create_preprocessing_tool_pod(preprocessing_tool_pod : PreprocessingToolPodInfo):
    try:
        os.chdir("/app/helm_chart") # TODO 나중에 변수화 해야할 듯
        
        labels_command=""
        for key, val in preprocessing_tool_pod.labels.model_dump().items():
            if val:
                labels_command += f" --set labels.{key}={common.helm_set_value(val)}"
        
        env_command=""
        for key, val in preprocessing_tool_pod.env.model_dump().items():
            if val:
                env_command += f" --set spec.containers.env.{key}={common.helm_set_value(val)}"
            
        resource_limit_command=""
        for key, val in preprocessing_tool_pod.resource.model_dump().items():
            resource_limit_command += f" --set spec.containers.resource.limits.{key}={common.helm_set_value(val)}"
        
        nodes_command = ""
        for index, node in enumerate(preprocessing_tool_pod.cluster):
            nodes_command += f" --set cluster[{index}].node_name={common.helm_set_value(node.node_name)}"
            nodes_command += f" --set cluster[{index}].device.type={common.helm_set_value(node.device.device_type)}"
            nodes_command += f" --set cluster[{index}].device.model={common.helm_set_value(node.device.model)}"
            nodes_command += f" --set cluster[{index}].device.count={common.helm_set_value(node.device.count)}"
            nodes_command += f" --set cluster[{index}].device.uuids={common.helm_set_value(node.device.uuids)}"
            nodes_command += f" --set cluster[{index}].device.ids={common.helm_set_value(node.device.ids)}"
        namespace = TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=preprocessing_tool_pod.labels.workspace_id)
        
        if settings.EXTERNAL_HOST_REDIRECT:
            domain = settings.EXTERNAL_HOST
        else:
            domain = f"{settings.EXTERNAL_HOST}:{settings.EXTERNAL_HOST_PORT}"
        
        
        command=f"""helm install {common.shell_arg(preprocessing_tool_pod.labels.helm_name)} tools/ \
            -n {common.shell_arg(namespace)} \
            --set namespace={common.shell_arg(namespace)} \
            --set ingress_class_name={settings.INGRESS_CLASS_NAME} \
            --set owner_name={common.helm_set_value(preprocessing_tool_pod.owner_name)} \
            --set pod_name={common.helm_set_value(preprocessing_tool_pod.pod_name)} \
            --set service.svc_name={common.helm_set_value(preprocessing_tool_pod.svc_name)} \
            --set service.port={preprocessing_tool_pod.port} \
            --set spec.containers.image={common.helm_set_value(preprocessing_tool_pod.image)} \
            --set domain="{domain}" \
            --set tool_password={common.helm_set_value(preprocessing_tool_pod.tool_password)} \
            --set spec.restartPolicy={preprocessing_tool_pod.restartPolicy}\
            --set total_device_count={preprocessing_tool_pod.total_device_count} \
            --set spec.hostname={common.helm_set_value(preprocessing_tool_pod.hostname)} \
            --set dataset.access={common.helm_set_value(preprocessing_tool_pod.dataset_access)} \
            --set dataset.name={common.helm_set_value(preprocessing_tool_pod.dataset_name)} \
            --set privateRepo={settings.JONATHAN_PRIVATE_REPO_ENABLED} \
            --set privatePip={settings.JONATHAN_PRIVATE_PIP_ENABLED} \
            --set nexusPrefix={settings.JONATHAN_NEXUS_PREFIX} \
            --set offlineMode={settings.JF_OFFLINE_MODE} \
            --set nexus.hostname={settings.JONATHAN_NEXUS_HOST} \
            --set nexus.port={settings.JONATHAN_NEXUS_PORT} \
            {labels_command} {env_command} {resource_limit_command} {nodes_command} \
            """
        
            
        
        if preprocessing_tool_pod.cpu_instance_name:
            command += f"  --set spec.cpu_instance_name={common.helm_set_value(preprocessing_tool_pod.cpu_instance_name)}"
        
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


def create_preprocessing_job(pod_info: dict):
    labels = PreprocessingJobLabels(
        pod_type = TYPE.PREPROCESSING_TYPE,
        preprocessing_type = pod_info["preprocessing_type"],
        helm_name=TYPE.PREPROCESSING_HELM_CHART_NAME.format(pod_info["id"], pod_info["work_func_type"]),
        preprocessing_item_id=pod_info["id"],
        workspace_id=pod_info["workspace_id"],
        workspace_name=pod_info["workspace_name"],
        preprocessing_id=pod_info["preprocessing_id"],
        preprocessing_name=pod_info["preprocessing_name"],
        owner_id=pod_info["owner_id"],
        job_name=pod_info["job_name"],
        work_func_type=pod_info["work_func_type"],
        instance_id = pod_info["instance_id"],
        dataset_id = pod_info["dataset_id"]
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
                    uuids = ",".join(gpu_uuids),
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
    
    owner_name = pod_info["owner_name"]
    image = pod_info["image_name"]
    run_code = pod_info["run_code"]
    parameter = pod_info["parameter"]

    dataset_info = db_dataset.get_dataset(dataset_id=pod_info["dataset_id"])
    
    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=labels.workspace_id, item_name=labels.preprocessing_id, \
        item_type=labels.work_func_type, sub_item_name=labels.preprocessing_item_id, sub_flag="{}-{}".format(1, labels.preprocessing_item_id)).get_all() # TODO training_index 값 임의로 1로 수정 
    
    # TODO 
    # 추후 Path 정리
    env = ENV(
            JF_HOME=PATH.JF_PREPROCESSING_BASE_HOME_POD_PATH,
            JF_HOST=pod_info["owner_name"],
            JF_ITEM_ID=pod_info["id"],
            JF_POD_NAME=unique_pod_name,
            JF_TOTAL_GPU=pod_info["gpu_count"]
        )

    # TODO
    # 자원 스케쥴링 추가되면 수정
    # workspace_resource = db_workspace.get_workspace_resource(workspace_id=labels.workspace_id)
    preprocessing_info = db_prepro.get_preprocessing_simple_sync(preprocessing_id=labels.preprocessing_id)
    
    resource = LimitResource(
            cpu=preprocessing_info["job_cpu_limit"],
            memory="{}G".format(preprocessing_info["job_ram_limit"])
        )
    
    
    parameter = get_job_parameter(run_parameter=parameter, unified_memory=pod_info.get("unified_memory", 0)) # unified_memory 를 어디서 얻는지 모르겠음
    
    
    run_command = ""
    if labels.preprocessing_type == TYPE.PREPROCESSING_TYPE_A:
        _, run_code_type = os.path.splitext(run_code)
        run_command = job_run_command(run_code_type=run_code_type[1:], run_code=run_code, parameter=parameter)
    else:
        # built in model
        if pod_info["built_in_data_tf"] == TYPE_BUILT_IN.MARKER_ANALYSIS:
            dataset_data_path =PATH.JF_PREPROCESSING_DATA_PATH.format(DATA_PATH=pod_info["dataset_data_path"])  
            
            run_code = PATH.JF_PREPROCESSING_BUILT_IN_CODE_PATH.format(RUN_CODE=TYPE_BUILT_IN.PREPROCESSING_TFS_SCRIPT[pod_info["built_in_data_tf"]]) 
            _, run_code_type = os.path.splitext(run_code)
            parameter += f"--input_data={dataset_data_path}"
            run_command = job_run_command(run_code_type=run_code_type[1:], run_code=run_code, parameter=parameter)
        elif pod_info["built_in_data_tf"] == TYPE_BUILT_IN.IMAGE_AUGMENT:
            data_path = PATH.JF_PREPROCESSING_DATA_PATH.format(DATA_PATH=pod_info["dataset_data_path"])
            parameter += f" --data_path={data_path}"
            run_code = PATH.JF_PREPROCESSING_BUILT_IN_CODE_PATH.format(RUN_CODE=TYPE_BUILT_IN.PREPROCESSING_TFS_SCRIPT[pod_info["built_in_data_tf"]])
            _, run_code_type = os.path.splitext(run_code)
            run_command = job_run_command(run_code_type=run_code_type[1:], run_code=run_code, parameter=parameter)
        elif pod_info["built_in_data_tf"] in (TYPE_BUILT_IN.FORMAT_CONVERT, getattr(TYPE_BUILT_IN, "SDS_LLAVA_CONVERT", None)):
            # 포맷 변환(FORMAT_CONVERT) + SDS→LLaVA(SDS_LLAVA_CONVERT, Domain) — 둘 다
            # 입력 데이터셋 경로를 --input_data 로 주입(marker 동형). 출력은 원본 옆 파일(sidecar).
            dataset_data_path = PATH.JF_PREPROCESSING_DATA_PATH.format(DATA_PATH=pod_info["dataset_data_path"])
            parameter += f" --input_data={dataset_data_path}"
            run_code = PATH.JF_PREPROCESSING_BUILT_IN_CODE_PATH.format(RUN_CODE=TYPE_BUILT_IN.PREPROCESSING_TFS_SCRIPT[pod_info["built_in_data_tf"]])
            _, run_code_type = os.path.splitext(run_code)
            run_command = job_run_command(run_code_type=run_code_type[1:], run_code=run_code, parameter=parameter)
        elif pod_info["built_in_data_tf"] in DATA_PIPELINE_TFS:
            # 데이터 파이프라인 노드(dp_*.py). 다른 빌트인과 달리 스케줄러가 입력 경로를
            # 덧붙이지 않는다 — 노드 설정은 기능 목록·순서·파라미터가 중첩된 구조라
            # BE 가 작업 데이터셋에 params.json 을 써 두고 --params_path 하나만 보낸다.
            run_code = PATH.JF_PREPROCESSING_BUILT_IN_CODE_PATH.format(
                RUN_CODE=TYPE_BUILT_IN.PREPROCESSING_TFS_SCRIPT[pod_info["built_in_data_tf"]])
            _, run_code_type = os.path.splitext(run_code)
            run_command = job_run_command(run_code_type=run_code_type[1:], run_code=run_code, parameter=parameter)

    # 생성되는 pod 개수
    labels.pod_count = len(nodes)
    training_pod_info = PreprocessingJobPodInfo(
        cluster=nodes,
        cpu_instance_name=cpu_instance_name,
        command=run_command,
        labels=labels,
        env=env,
        resource=resource,
        image=image,
        pod_name=unique_pod_name,
        owner_name=owner_name,
        total_device_count=pod_info["gpu_count"],
        dataset_id=pod_info["dataset_id"],
        dataset_access=dataset_info["access"],
        dataset_name=dataset_info["name"]
    )

    result , message = create_preprocessing_job_pod(preprocessing_job_info=training_pod_info)
    if result:
        db_prepro.update_preprocessing_job_datetime(preprocessing_job_id=labels.preprocessing_item_id, start_datetime=datetime.today().strftime(TYPE.TIME_DATE_FORMAT), pod_count=labels.pod_count)
    else:
        if message:
            if "exceeded quota" in message:
                db_prepro.update_preprocessing_job_pending_reason(reason="Waiting for memory or cpu resource allocation.", preprocessing_job_id=labels.preprocessing_item_id)
    return result, message


def create_preprocessing_tool(pod_info : dict):
    labels = PreprocessingToolLabels(
                        work_type=TYPE.PREPROCESSING_TYPE,
                        pod_type=pod_info["pod_type"],
                        work_func_type=pod_info["work_func_type"],
                        preprocessing_item_id=pod_info["id"],
                        preprocessing_id=pod_info["preprocessing_id"],
                        preprocessing_name=pod_info["preprocessing_name"],
                        preprocessing_tool_id=pod_info["id"],
                        tool_type=TYPE.TOOL_TYPE[pod_info["tool_type"]],
                        workspace_id=pod_info["workspace_id"],
                        workspace_name=pod_info["workspace_name"],
                        owner_id=pod_info["owner_id"],
                        instance_id = pod_info["instance_id"],
                        helm_name = TYPE.PREPROCESSING_HELM_CHART_NAME.format(pod_info["id"], TYPE.TOOL_TYPE[pod_info["tool_type"]]),
                        dataset_id = pod_info["dataset_id"]
                    )
    print(labels, file=sys.stderr)
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
                    uuids = ",".join(gpu_uuids),
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
        nodes.append(Node(Node(
            device=Accelerator(
                device_type=resource_type,
                model=model,
                count=0
            )
        ))) # helm 에서 for문을 돌려야 하기 때문에 
        cpu_instance_name=pod_info.get("cpu_instance_name")
    
    dataset_info = db_dataset.get_dataset(dataset_id=pod_info["dataset_id"])
    
    start_datetime = datetime.today().strftime(TYPE.TIME_DATE_FORMAT)
    print(f"[DEBUG] Creating preprocessing pod with preprocessing_item_id: {labels.preprocessing_item_id}", file=sys.stderr)
    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=labels.workspace_name, start_datetime=start_datetime, item_name=labels.preprocessing_name, 
                                                                    item_type=labels.tool_type, sub_flag=str(labels.preprocessing_item_id)).get_all()
    print(f"[DEBUG] Generated preprocessing pod names: base={base_pod_name}, unique={unique_pod_name}, container={container_name}", file=sys.stderr)
    
    svc_name = TYPE.PREPROCESSING_POD_SVC_NAME.format(POD_NAME=unique_pod_name, TOOL_TYPE=labels.tool_type)
    tool_password = pod_info["tool_password"]
    env = ENV(
            JF_HOME=PATH.JF_PREPROCESSING_BASE_HOME_POD_PATH,
            JF_HOST=pod_info["owner_name"],
            JF_ITEM_ID=pod_info["id"],
            JF_POD_NAME=unique_pod_name,
            JF_TOTAL_GPU=pod_info["gpu_count"]
        )


    
    resource = LimitResource(
            cpu=pod_info["resource"]["cpu"],
            memory="{}G".format(pod_info["resource"]["ram"])
        )
    
    labels.pod_count = len(nodes)
    
    preprocessing_tool_pod = PreprocessingToolPodInfo(
        cluster=nodes,
        cpu_instance_name=cpu_instance_name,
        labels=labels,
        env=env,
        port=TYPE.TOOL_PORT[pod_info["tool_type"]],
        svc_name=svc_name,
        tool_password=tool_password,
        resource=resource,
        image=pod_info["image_name"],
        pod_name=unique_pod_name,
        owner_name=pod_info["owner_name"],
        total_device_count=pod_info["gpu_count"],
        dataset_id=pod_info["dataset_id"],
        dataset_access=dataset_info["access"],
        dataset_name=dataset_info["name"]
    )
    
    res, message = create_preprocessing_tool_pod(preprocessing_tool_pod=preprocessing_tool_pod)
    if res:
        db_prepro.update_preprocessing_tool_datetime(preprocessing_tool_id=pod_info["id"], start_datetime=start_datetime, pod_count=labels.pod_count)
    else:
        if message:
            if "exceeded quota" in message:
                db_prepro.update_preprocessing_tool_pending_reason(reason="Waiting for memory or cpu resource allocation.", preprocessing_tool_id=pod_info["id"])

    return res, message