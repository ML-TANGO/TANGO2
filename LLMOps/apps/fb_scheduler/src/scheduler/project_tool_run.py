


from utils.msa_db import db_project, db_node, db_workspace, db_dataset
# from utils.exception.exceptions import *
from utils.settings import *
# from utils.TYPE import *
from utils import PATH, TYPE, settings, common, TYPE_BUILT_IN

from scheduler.dto import *
from scheduler.helm_run import create_project_training_pod, create_project_tool_pod, create_project_hps_pod
from utils.kube import PodName

from datetime import datetime

import re, sys, json


# DEFAULT_TEMPORARY_STORAGE="10.0Gi"
def get_training_parameter(run_parameter, unified_memory):
    parameter = run_parameter
    if unified_memory == 1:
        parameter += " --unified_memory 1 "
    
    return parameter

# def gen_built_in_run_code(built_in_model_info, total_gpu):
#     run_code = built_in_model_info["training_py_command"]
#     if built_in_model_info["checkpoint_save_path_parser"] is not None and built_in_model_info["checkpoint_save_path_parser"] != "":
#         run_code += " --{} {} ".format(built_in_model_info["checkpoint_save_path_parser"], JF_TRAINING_CHECKPOINT_ITEM_POD_STATIC_PATH)

#     if built_in_model_info["training_num_of_gpu_parser"] is not None and built_in_model_info["training_num_of_gpu_parser"] != "":
#         run_code += " --{} {} ".format(built_in_model_info["training_num_of_gpu_parser"], total_gpu)

#     return run_code

# def get_run_code(run_code, built_in_model_info, total_gpu):
#     run_code = run_code
#     if built_in_model_info is not None:
#         run_code = gen_built_in_run_code(built_in_model_info, total_gpu)
#     return run_code



LOG_COMMAND = " > {log_base}/{item_id}.jflog 2>&1"
def training_run_command(run_code_type: str, run_code: str, parameter: str):
    run_command = ""
    if run_code_type == "py":
        # base_path = "/root/project"
        # relative_path = os.path.relpath(run_code, base_path)
        run_command = f"python3 -u {run_code} {parameter}"
    elif run_code_type == "sh":
        run_command = f"bash {run_code} {parameter}"
    else:
        run_command = f"{run_code} {parameter}"
    return run_command

def hps_run_command(run_code_type: str, run_code: str):
    run_coomand = ""
    if run_code_type == "py":
        
        run_coomand = f"python3 -u {run_code}"
    elif run_code_type == "sh":
        run_coomand = f"bash {run_code}"
    else:
        run_coomand = f"{run_code}"
    
    return run_coomand



def create_training_pod(pod_info: dict):
    labels = TrainingLabels(
        project_type=pod_info["project_type"],
        helm_name=TYPE.PROJECT_HELM_CHART_NAME.format(pod_info["id"], TYPE.TRAINING_ITEM_A),
        project_item_id=pod_info["id"],
        workspace_id=pod_info["workspace_id"],
        workspace_name=pod_info["workspace_name"],
        project_id=pod_info["project_id"],
        project_name=pod_info["project_name"],
        owner_id=pod_info["owner_id"],
        training_name=pod_info["training_name"],
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
    
    owner_name = pod_info["owner_name"]
    image = pod_info["image_name"]
    run_code = pod_info["run_code"]
    parameter = pod_info["parameter"]

    dataset_info = db_dataset.get_dataset(dataset_id=pod_info["dataset_id"])
    
    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=labels.workspace_id, item_name=labels.project_id, \
        item_type="training", sub_item_name=labels.project_item_id, sub_flag="{}-{}".format(1, labels.project_item_id)).get_all() # TODO training_index 값 임의로 1로 수정 
    parameter = get_training_parameter(run_parameter=parameter, unified_memory=pod_info.get("unified_memory", 0)) # unified_memory 를 어디서 얻는지 모르겠음
    # TODO 
    # built in일 경우 checkpoint 경로 및 data 경로 추가
    if pod_info["project_type"] == TYPE.PROJECT_TYPE_A:
        env = ENV(
                JF_HOST=pod_info["owner_name"],
                JF_ITEM_ID=pod_info["id"],
                JF_POD_NAME=unique_pod_name,
                JF_TOTAL_GPU=pod_info["gpu_count"]
            )
        
        _, run_code_type = os.path.splitext(run_code)
        # built-in model일 경우
        
        run_command = training_run_command(run_code_type=run_code_type[1:], run_code=run_code, parameter=parameter)
    else:
        env = BUILT_IN_ENV(
                JF_HOST=pod_info["owner_name"],
                JF_ITEM_ID=pod_info["id"],
                JF_POD_NAME=unique_pod_name,
                JF_TOTAL_GPU=pod_info["gpu_count"],
                JF_MODEL_PATH=PATH.JF_BUILT_IN_MODEL_PATH ,
                JF_DATASET_PATH = PATH.JF_BUILT_IN_DATASET_PATH,
                JF_BUILT_IN_CHECKPOINT_PATH = PATH.JF_BUILT_IN_CHECKPOINT_PATH,
                JF_HUGGINGFACE_TOKEN = settings.HUGGINGFACE_TOKEN,  # pod_info["huggingface_token"], # TODO 추후 수정
                JF_HUGGINGFACE_MODEL_ID = "Acryl-aLLM/BurnDepthAnalysisIntelligence", # pod_info["huggingface_model_id"] # TODO 추후 수정
            )
        # TODO
        # 추후 모델 추가되면 함수로 따로 뺴기 
        run_command = ""
        if pod_info["project_type"] == TYPE.PROJECT_TYPE_C:
            if pod_info["category"] == TYPE_BUILT_IN.MEDICAL:
                if pod_info["built_in_model"] == "화상 심도 탐지":
                    print(pod_info, file=sys.stderr)
                    # data_path = os.path.join(PATH.JF_BUILT_IN_DATASET_PATH, pod_info["dataset_data_path"]) 
                    data_path = os.path.join(PATH.JF_BUILT_IN_DATASET_PATH, pod_info["dataset_data_path"]) 
                    print(data_path, file=sys.stderr)
                    data_path_dir = os.path.dirname(data_path)
                    print(data_path_dir, file=sys.stderr)
                    checkpoint_file = PATH.JF_BUILT_IN_CHECKPOINT_FILE_PATH.format(JOB_ID=pod_info["id"])
                    run_command = f"python3 -u {PATH.JF_BUILT_IN_TRAIN_SCRIPT_PATH} {parameter} --dataset_csv_file={data_path} --image_dir={data_path_dir}/images --final_checkpoint_file={checkpoint_file}"
        elif pod_info["project_type"] == TYPE.PROJECT_TYPE_B:
            # TODO
            # 추후 수정
            data_path = os.path.join(PATH.JF_BUILT_IN_DATASET_PATH, pod_info["dataset_data_path"]) 
            print(data_path, file=sys.stderr)
            data_path_dir = os.path.dirname(data_path)
            print(data_path_dir, file=sys.stderr)
            checkpoint_file = PATH.JF_BUILT_IN_CHECKPOINT_FILE_PATH.format(JOB_ID=pod_info["id"])
            run_command = f"python3 -u {PATH.JF_BUILT_IN_TRAIN_SCRIPT_PATH} {parameter} --dataset_csv_file={data_path} --image_dir={data_path_dir}/images --final_checkpoint_file={checkpoint_file}"
            pass
    resource = LimitResource(
            cpu=pod_info["resource"]["cpu"],
            memory="{}G".format(pod_info["resource"]["ram"])
        )
    
    # 생성되는 pod 개수
    labels.pod_count = len(nodes)
    training_pod_info = TrainingPodInfo(
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
        distributed_framework=pod_info["distributed_framework"],
        distributed_config_path=common.escape_special_chars(pod_info["distributed_config_path"]),
        dataset_id=pod_info["dataset_id"],
        dataset_access=dataset_info["access"],
        dataset_name=dataset_info["name"]
    )

    result , message = create_project_training_pod(training_pod=training_pod_info)
    if result:
        db_project.update_project_training_datetime(training_type=labels.work_func_type ,training_id=labels.project_item_id, start_datetime=datetime.today().strftime(TYPE.TIME_DATE_FORMAT), pod_count=labels.pod_count)
    else:
        if message:
            if "exceeded quota" in message:
                db_project.update_project_training_pending_reason(reason="Waiting for memory or cpu resource allocation.", training_id=labels.project_item_id)
    return result, message




def get_hyperparamsearch_search_option_command(search_method, init_points, search_count, search_interval, save_file_name, load_file_name, int_parameter):
    search_option = "--method {} ".format(search_method)
    if init_points is not None:
        search_option += " --init_points {} ".format(init_points)
    if search_count is not None:
        search_option += " --n_iter {} ".format(search_count)
    if search_interval is not None:
        search_option += " --interval {} ".format(search_interval)
    
    if save_file_name is not None:
        search_option += " --save_data {0}/{1}  ".format(PATH.JF_PROJECT_HPS_SAVE_FILE_DIR_POD_STATIC_PATH, save_file_name)
    if load_file_name is not None:
        search_option += " --load_data {0}/{1} ".format(PATH.JF_PROJECT_HPS_SAVE_FILE_DIR_POD_STATIC_PATH, load_file_name)

    if int_parameter is not None and int_parameter != "":
        search_option += " --int_parameter {}".format(int_parameter)


    # search_option += "--save_data {0}/{1} --load_data {0}/{2}".format(JF_TRAINING_HPS_SAVE_FILE_DIR_POD_STATIC_PATH, save_file_name, load_file_name)
    
    return search_option

def get_hyperparamsearch_parameter(run_parameter, search_parameter):
    parameter = "{run_param} {search_param}".format(run_param=run_parameter, search_param=search_parameter)
    return parameter



EXAMPLE_FIXED_PARAM = [
    {
        "param_name": "epochs",
        "value": 1,
        "type": "int"
    },
    # {
    #     "param_name": "weights",
    #     "value": "yolov5s.pt",
    #     "type": "str"
    # }
]

def create_hps_pod(pod_info: dict):
    
    
    labels = HPSLabels(
        project_type=pod_info["project_type"],
        helm_name=TYPE.PROJECT_HELM_CHART_NAME.format(pod_info["id"], TYPE.TRAINING_ITEM_C),
        project_item_id=pod_info["id"],
        workspace_name=pod_info["workspace_name"],
        workspace_id=pod_info["workspace_id"],
        project_name=pod_info["project_name"],
        project_id = pod_info["project_id"],
        work_func_type=pod_info["work_func_type"],
        owner_id=pod_info["owner_id"],
        hps_name=pod_info["hps_name"],
        instance_id = pod_info["instance_id"]
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

    dataset_info = db_dataset.get_dataset(dataset_id=pod_info["dataset_id"])
    
    image = pod_info["image_name"]
    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=labels.workspace_id, item_name=labels.project_id, \
        item_type=labels.work_func_type, sub_item_name=labels.project_item_id, sub_flag="{}-{}".format(1, labels.project_item_id)).get_all()
    if pod_info["project_type"] == TYPE.PROJECT_TYPE_A:
        run_code = pod_info["run_code"]
        _, run_code_type = os.path.splitext(run_code)
        parameter = json.loads(pod_info["parameter"])
        search_count = 1
        for i in parameter:
            search_count *= i["step"]
        target_metric = pod_info["target_metric"]
        encode_params = common.helm_parameter_encoding(pod_info["parameter"])
        encode_fixed_params = common.helm_parameter_encoding(pod_info["fixed_parameter"])
        run_command = hps_run_command(run_code_type=run_code_type[1:], run_code=run_code)
        command = f"{settings.HYPERPARAM_SEARCH_CUSTOM_RUN_FILE} --runcode='{run_command}' --fixed_params={encode_fixed_params} --param_config={encode_params} --search_count={search_count} --target_metric={target_metric}"
        env = HpsENV(
            JF_HOST=pod_info["owner_name"],
            JF_HPS_LOG_PATH=PATH.JF_PROJECT_HPS_LOG_ORIGINAL_RECORD_FILE_POD_PATH.format(hps_id=labels.project_item_id),
            JF_ITEM_ID=pod_info["id"],
            JF_POD_NAME=unique_pod_name,
            JF_TOTAL_GPU=pod_info["gpu_count"]
        )
    else:
        # TODO 
        # BUILT IN 추가 되면 시작
        env = BUILT_IN_HpsENV(
            JF_HOST=pod_info["owner_name"],
            JF_HPS_LOG_PATH=PATH.JF_PROJECT_HPS_LOG_ORIGINAL_RECORD_FILE_POD_PATH.format(hps_id=labels.project_item_id),
            JF_ITEM_ID=pod_info["id"],
            JF_POD_NAME=unique_pod_name,
            JF_TOTAL_GPU=pod_info["gpu_count"],
            JF_MODEL_PATH=PATH.JF_BUILT_IN_MODEL_PATH ,
            JF_DATASET_PATH = PATH.JF_BUILT_IN_DATASET_PATH,
            JF_BUILT_IN_CHECKPOINT_PATH = PATH.JF_BUILT_IN_CHECKPOINT_PATH,
            JF_HUGGINGFACE_TOKEN = pod_info["huggingface_token"],
            JF_HUGGINGFACE_MODEL_ID = pod_info["huggingface_model_id"]
        )
        command = ""
        run_command = ""
        if pod_info["project_type"] == TYPE.PROJECT_TYPE_C:
            if pod_info["category"] == TYPE_BUILT_IN.MEDICAL:
                if pod_info["built_in_model"] == "화상 심도 탐지":
                    data_path = os.path.join(PATH.JF_BUILT_IN_DATASET_PATH, pod_info["dataset_data_path"]) 
                    data_path_dir = os.path.dirname(data_path)
                    fixed_parameter = [
                        {
                            "name": "dataset_csv_file",
                            "value": f"{data_path}"
                        },
                        {
                            "name": "image_dir",
                            "value": f"{data_path_dir}/images"
                        },
                        {
                            "name" : "max_epoch",
                            "value" : 4
                        },
                    ]

                    parameter = [
                        {
                            "name": "batch",
                            "min": 12,
                            "max": 34,
                            "step": 10,
                            "type" : "int"
                        },
                        {
                            "name": "num_workers",
                            "min": 5,
                            "max": 16,
                            "step": 10,
                            "type" : "int"
                        },
                        {
                            "name": "lr",
                            "min": 1e-6,
                            "max": 1e-5,
                            "step": 10,
                            "type" : "float"
                        }
                    ]

                    
                    encode_params = common.helm_parameter_encoding(json.dumps(parameter))
                    encode_fixed_params = common.helm_parameter_encoding(json.dumps(fixed_parameter))
                    run_command = f"python3 -u {PATH.JF_BUILT_IN_TRAIN_SCRIPT_PATH}"
                    search_count = pod_info["built_in_search_count"]
                    command = f"{settings.HYPERPARAM_SEARCH_CUSTOM_RUN_FILE} --target_metric 'val_loss' --runcode='{run_command}' --fixed_params={encode_fixed_params} --param_config={encode_params} --search_count={search_count}"
        
        elif pod_info["project_type"] == TYPE.PROJECT_TYPE_B:
            # TODO
            # 추후 수정
            data_path = os.path.join(PATH.JF_BUILT_IN_DATASET_PATH, pod_info["dataset_data_path"]) 
            data_path_dir = os.path.dirname(data_path)
            fixed_parameter = [
                {
                    "name": "dataset_csv_file",
                    "value": f"{data_path}"
                },
                {
                    "name": "image_dir",
                    "value": f"{data_path_dir}/images"
                },
                {
                    "name" : "max_epoch",
                    "value" : 4
                },
            ]

            parameter = [
                {
                    "name": "batch",
                    "min": 12,
                    "max": 34,
                    "step": 10,
                    "type" : "int"
                },
                {
                    "name": "num_workers",
                    "min": 5,
                    "max": 16,
                    "step": 10,
                    "type" : "int"
                },
                {
                    "name": "lr",
                    "min": 1e-6,
                    "max": 1e-5,
                    "step": 10,
                    "type" : "float"
                }
            ]

            
            encode_params = common.helm_parameter_encoding(json.dumps(parameter))
            encode_fixed_params = common.helm_parameter_encoding(json.dumps(fixed_parameter))
            run_command = f"python3 -u {PATH.JF_BUILT_IN_TRAIN_SCRIPT_PATH}"
            search_count = pod_info["built_in_search_count"]
            command = f"{settings.HYPERPARAM_SEARCH_CUSTOM_RUN_FILE} --target_metric 'val_loss' --runcode='{run_command}' --fixed_params={encode_fixed_params} --param_config={encode_params} --search_count={search_count}"
    
    
    
    resource = LimitResource(
            cpu=pod_info["resource"]["cpu"],
            memory="{}G".format(pod_info["resource"]["ram"])
        )
    
    labels.pod_count = len(nodes)
    
    hps_pod_info = HPSPodInfo(
        cluster=nodes,
        cpu_instance_name=cpu_instance_name,
        command=command,
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
    result , message = create_project_hps_pod(hps_pod=hps_pod_info)
    if result:
        db_project.update_project_hps_datetime(hps_id=labels.project_item_id, start_datetime=datetime.today().strftime(TYPE.TIME_DATE_FORMAT), pod_count=labels.pod_count)
    else:
        if message:
            if "exceeded quota" in message:
                db_project.update_project_hps_pending_reason(reason="Waiting for memory or cpu resource allocation.", hps_id=labels.project_item_id)
    return result, message


def create_project_tool(pod_info : dict):
    labels = ProjectToolLabels(
        project_type=pod_info["project_type"],
        project_item_id=pod_info["id"],
        project_id=pod_info["project_id"],
        project_name=pod_info["project_name"],
        project_tool_id=pod_info["id"],
        work_func_type=pod_info["work_func_type"],
        tool_type=TYPE.TOOL_TYPE[pod_info["tool_type"]],
        workspace_id=pod_info["workspace_id"],
        workspace_name=pod_info["workspace_name"],
        owner_id=pod_info["owner_id"],
        instance_id = pod_info["instance_id"],
        helm_name = TYPE.PROJECT_HELM_CHART_NAME.format(pod_info["id"], TYPE.TOOL_TYPE[pod_info["tool_type"]]),
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
    
    dataset_info = db_dataset.get_dataset(dataset_id=pod_info["dataset_id"])
    
    start_datetime = datetime.today().strftime(TYPE.TIME_DATE_FORMAT)
    print(f"[DEBUG] Creating pod with project_item_id: {labels.project_item_id}", file=sys.stderr)
    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=labels.workspace_name, start_datetime=start_datetime, item_name=labels.project_name, 
                                                                    item_type=labels.tool_type, sub_flag=str(labels.project_item_id)).get_all()
    print(f"[DEBUG] Generated pod names: base={base_pod_name}, unique={unique_pod_name}, container={container_name}", file=sys.stderr)
    
    svc_name = TYPE.PROJECT_POD_SVC_NAME.format(POD_NAME=unique_pod_name, TOOL_TYPE=labels.tool_type)
    tool_password = pod_info["tool_password"]
    env = ENV(
            JF_HOST=pod_info["owner_name"],
            JF_ITEM_ID=pod_info["id"],
            JF_POD_NAME=unique_pod_name,
            JF_TOTAL_GPU=pod_info["gpu_count"]
        )
    
    resource = LimitResource(
            cpu=pod_info["resource"]["cpu"],
            memory="{}G".format(pod_info["resource"]["ram"])
        )

    # postStart_command = None
    print("Nodes:", nodes, file=sys.stderr)
    
    labels.pod_count = len(nodes)
    
    project_tool_pod = ToolPodInfo(
        cluster=nodes,
        cpu_instance_name=cpu_instance_name,
        labels=labels,
        env=env,
        port=TYPE.TOOL_PORT[pod_info["tool_type"]],
        svc_name=svc_name,
        tool_password=common.escape_special_chars(tool_password),
        resource=resource,
        image=pod_info["image_name"],
        pod_name=unique_pod_name,
        owner_name=pod_info["owner_name"],
        total_device_count=pod_info["gpu_count"],
        dataset_id=pod_info["dataset_id"],
        dataset_access=dataset_info["access"],
        dataset_name=dataset_info["name"]
    )
    
    res, message = create_project_tool_pod(project_tool_pod=project_tool_pod)
    if res:
        db_project.update_project_tool_datetime(project_tool_id=pod_info["id"], start_datetime=start_datetime, pod_count=labels.pod_count)
    else:
        if message:
            if "exceeded quota" in message:
                db_project.update_project_tool_pending_reason(reason="Waiting for memory or cpu resource allocation.", project_tool_id=pod_info["id"])

    return res, message