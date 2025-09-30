


from utils.msa_db import db_project, db_node, db_workspace
# from utils.exceptions import *
from utils.settings import *
# from utils.TYPE import *
from utils import PATH_NEW, TYPE, settings

from scheduler.dto import *
from scheduler.helm_run import create_project_training_pod, create_project_tool_pod
from utils.kube import PodName

from datetime import datetime

import re, sys


# DEFAULT_TEMPORARY_STORAGE="10.0Gi"
def get_training_parameter(run_parameter, unified_memory):
    parameter = run_parameter
    if unified_memory == 1:
        parameter += " --unified_memory 1 "

    return parameter

def gen_built_in_run_code(built_in_model_info, total_gpu):
    run_code = built_in_model_info["training_py_command"]
    if built_in_model_info["checkpoint_save_path_parser"] is not None and built_in_model_info["checkpoint_save_path_parser"] != "":
        run_code += " --{} {} ".format(built_in_model_info["checkpoint_save_path_parser"], JF_TRAINING_CHECKPOINT_ITEM_POD_STATIC_PATH)

    if built_in_model_info["training_num_of_gpu_parser"] is not None and built_in_model_info["training_num_of_gpu_parser"] != "":
        run_code += " --{} {} ".format(built_in_model_info["training_num_of_gpu_parser"], total_gpu)

    return run_code

def get_run_code(run_code, built_in_model_info, total_gpu):
    run_code = run_code
    if built_in_model_info is not None:
        run_code = gen_built_in_run_code(built_in_model_info, total_gpu)
    return run_code



LOG_COMMAND = " > {log_base}/{item_id}.jflog 2>&1"
def training_run_command(run_code_type: str, run_code: str, parameter: str, log_command :str):
    run_coomand = ""
    if run_code_type == "py":

        # run_coomand = f"python3 -u {run_code} {parameter} {log_command}"
        run_coomand = f"python3 -u {run_code} {parameter}"
    elif run_code_type == "sh":
        # run_coomand = f"bash {run_code} {parameter} {log_command}"
        run_coomand = f"bash {run_code} {parameter}"
    else:
        # run_coomand = f"{run_code} {parameter} {log_command}"
        run_coomand = f"{run_code} {parameter}"
    return run_coomand

def hps_run_command(run_code_type: str, run_code: str, parameter: str):
    run_coomand = ""
    if run_code_type == "py":

        run_coomand = f"python3 -u {run_code} {parameter}"
    elif run_code_type == "sh":
        run_coomand = f"bash {run_code} {parameter}"
    else:
        run_coomand = f"{run_code} {parameter}"

    return run_coomand



def create_training_pod(pod_info: dict):
    labels = TrainingLabels(
        project_item_id=pod_info["id"],
        workspace_id=pod_info["workspace_id"],
        workspace_name=pod_info["workspace_name"],
        project_id=pod_info["project_id"],
        project_name=pod_info["project_name"],
        owner_id=pod_info["owner_id"],
        training_name=pod_info["training_name"],
        work_func_type=pod_info["pod_type"],
        instance_id = pod_info["instance_id"]
    )

    cpu_instance_name=""
    nodes = []
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
            nodes.append(Cluster(
                node_name = gpu_info["node_name"],
                gpu_uuids =  escape_special_chars(",".join(gpu_uuids)),
                gpu_ids = ".".join(map(str, gpu_ids)),
                gpu_count = len(gpu_uuids)
            ))
    elif pod_info.get("available_node",None):
        nodes.append(Cluster(
                node_name = pod_info["available_node"],
                gpu_uuids =  "",
                gpu_count = 0
            ))
    elif pod_info.get("cpu_instance_name", None):
        nodes.append(Cluster()) # helm 에서 for문을 돌려야 하기 때문에
        cpu_instance_name=pod_info.get("cpu_instance_name")


    owner_name = pod_info["owner_name"]
    image = pod_info["image_name"]
    run_code = pod_info["run_code"]
    parameter = pod_info["parameter"]


    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=labels.workspace_id, item_name=labels.project_id, \
        item_type="training", sub_item_name=labels.project_item_id, sub_flag="{}-{}".format(1, labels.project_item_id)).get_all() # TODO training_index 값 임의로 1로 수정

    # TODO
    # 추후 Path 정리
    env = ENV(
            JF_HOST=pod_info["owner_name"],
            JF_ITEM_ID=pod_info["id"],
            JF_POD_NAME=unique_pod_name,
            JF_TOTAL_GPU=pod_info["gpu_count"]
        )

    # TODO
    # 자원 스케쥴링 추가되면 수정
    workspace_resource = db_workspace.get_workspace_resource(workspace_id=labels.workspace_id)

    resource = LimitResource(
            cpu=workspace_resource["job_cpu_limit"],
            memory="{}Gi".format(workspace_resource["job_ram_limit"])
        )


    parameter = get_training_parameter(run_parameter=parameter, unified_memory=pod_info.get("unified_memory", 0)) # unified_memory 를 어디서 얻는지 모르겠음


    _, run_code_type = os.path.splitext(run_code)
    # built-in model일 경우

    log_command = LOG_COMMAND.format(log_base=PATH_NEW.JF_PROJECT_TRAINING_LOG_DIR_POD_PATH, item_id=labels.project_item_id)
    run_command = training_run_command(run_code_type=run_code_type[1:], run_code=run_code, parameter=parameter, log_command=log_command)

    # 생성되는 pod 개수
    labels.pod_count = len(nodes)
    training_pod_info = TrainingPodInfo(
        helm_repo_name=TYPE.PROJECT_HELM_CHART_NAME.format(labels.project_item_id, "training"),
        clusters=nodes,
        cpu_instance_name=cpu_instance_name,
        command=run_command,
        labels=labels,
        env=env,
        resource=resource,
        image=image,
        pod_name=unique_pod_name,
        owner_name=owner_name,
        total_gpu_count=pod_info["gpu_count"],
        distributed_framework=pod_info["distributed_framework"],
        distributed_config_path=escape_special_chars(pod_info["distributed_config_path"])
    )

    result , message = create_project_training_pod(training_pod=training_pod_info)
    if result:
        db_project.update_project_training_datetime(training_type=labels.work_func_type ,training_id=labels.project_item_id, start_datetime=datetime.today().strftime("%Y-%m-%d %H:%M:%S"))
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
        search_option += " --save_data {0}/{1}  ".format(PATH_NEW.JF_PROJECT_HPS_SAVE_FILE_DIR_POD_STATIC_PATH, save_file_name)
    if load_file_name is not None:
        search_option += " --load_data {0}/{1} ".format(PATH_NEW.JF_PROJECT_HPS_SAVE_FILE_DIR_POD_STATIC_PATH, load_file_name)

    if int_parameter is not None and int_parameter != "":
        search_option += " --int_parameter {}".format(int_parameter)


    # search_option += "--save_data {0}/{1} --load_data {0}/{2}".format(JF_TRAINING_HPS_SAVE_FILE_DIR_POD_STATIC_PATH, save_file_name, load_file_name)

    return search_option

def get_hyperparamsearch_parameter(run_parameter, search_parameter):
    parameter = "{run_param} {search_param}".format(run_param=run_parameter, search_param=search_parameter)
    return parameter


def escape_special_chars(command):
    # 특수 기호 목록
    special_chars = ['(', ')', '"', '\'', '&', '|', ';', '<', '>', '$', '`', '\\', ","]

    # 특수 기호 앞에 \를 붙여주는 함수
    def escape_char(match):
        return '\\' + match.group(0)

    # 정규식을 사용하여 특수 기호를 찾아 이스케이프 처리
    escaped_command = re.sub(r'([{}])'.format(''.join(re.escape(c) for c in special_chars)), escape_char, command)
    return escaped_command

def create_hps_pod(pod_info: dict):


    labels = HPSLabels(
        project_item_id=pod_info["id"],
        workspace_name=pod_info["workspace_name"],
        workspace_id=pod_info["workspace_id"],
        project_name=pod_info["project_name"],
        project_id = pod_info["project_id"],
        work_func_type=pod_info["pod_type"],
        owner_id=pod_info["owner_id"],
        create_user_id=pod_info["create_user_id"] ,
        hps_group_id = pod_info["hps_group_id"],
        hps_group_name = pod_info["hps_group_name"],
        # hps_id = pod_info["hps_id"],
        hps_group_index=pod_info["hps_group_index"],
        instance_id = pod_info["instance_id"]
    )
    cpu_instance_name=""
    nodes = []
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
            nodes.append(Cluster(
                node_name = gpu_info["node_name"],
                gpu_uuids =  escape_special_chars(",".join(gpu_uuids)),
                gpu_ids = ".".join(map(str, gpu_ids)),
                gpu_count = len(gpu_uuids)
            ))
    elif pod_info.get("available_node",None):
        nodes.append(Cluster(
                node_name = pod_info["available_node"],
                gpu_uuids =  "",
                gpu_count = 0
            ))
    elif pod_info.get("cpu_instance_name", None):
        nodes.append(Cluster()) # helm 에서 for문을 돌려야 하기 때문에
        cpu_instance_name=pod_info.get("cpu_instance_name")

    owner_name = pod_info["owner_name"]

    image = pod_info["image_name"]
    run_code = pod_info["run_code"]
    run_parameter = pod_info["run_parameter"]
    search_parameter = pod_info["search_parameter"]
    int_parameter = pod_info["int_parameter"]

    search_method = pod_info["method"]
    search_count = pod_info["search_count"]
    search_interval = pod_info["search_interval"]
    init_points = pod_info["init_points"]
    save_file_name =  pod_info["save_file_name"]
    load_file_name = pod_info.get("load_file_name", None)



    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=labels.workspace_id, item_name=labels.project_id, item_type=TRAINING_ITEM_C, sub_item_name=labels.project_item_id, sub_flag="{}-{}".format(labels.hps_group_index, labels.project_item_id)).get_all()
    env = HpsENV(
            JF_HPS_ORIGINAL_RECORD_FILE_PATH=PATH_NEW.JF_PROJECT_HPS_LOG_ORIGINAL_RECORD_FILE_POD_PATH.format(hps_id=labels.project_item_id),
            JF_HPS_ORIGINAL_RECORD_N_ITER_FILE_PATH=PATH_NEW.JF_PROJECT_HPS_LOG_N_ITER_FILE_DIR_POD_PATH.format(hps_id=labels.project_item_id),
            JF_HPS_ID=labels.project_item_id,
            JF_ITEM_ID=labels.project_item_id,
            JF_POD_NAME=unique_pod_name,
            JF_TOTAL_GPU=pod_info["gpu_count"],
            JF_HPS_SAVE_FILE_BASE_PATH=PATH_NEW.JF_PROJECT_HPS_SAVE_FILE_DIR_POD_STATIC_PATH,
            JF_HPS_SAVE_FILE_NAME=save_file_name,
            JF_HPS_LOAD_FILE_NAME= load_file_name if load_file_name else "None" ,  # TODO 해당 변수는 어디에 쓰이는거?

            JF_HOST=pod_info["owner_name"],
            JF_GRAPH_LOG_FILE_PATH=PATH_NEW.JF_PROJECT_HPS_LOG_DIR_POD_PATH + "/{}.jflog_graph".format(pod_info["id"]),
            JF_GRAPH_LOG_BASE_PATH=PATH_NEW.JF_PROJECT_HPS_LOG_DIR_POD_PATH
        )
    workspace_resource = db_workspace.get_workspace_resource(workspace_id=labels.workspace_id)

    resource = LimitResource(
            cpu=workspace_resource["hps_cpu_limit"],
            memory="{}Gi".format(workspace_resource["hps_ram_limit"])
        )

    search_option_command = get_hyperparamsearch_search_option_command(search_method=search_method, init_points=init_points, search_count=search_count,
                                                            search_interval=search_interval, save_file_name=save_file_name, load_file_name=load_file_name,
                                                            int_parameter=int_parameter)

    search_parameter = escape_special_chars(search_parameter)

    parameter = get_hyperparamsearch_parameter(run_parameter=run_parameter, search_parameter=search_parameter)

    _, run_code_type = os.path.splitext(run_code)

    log_command = LOG_COMMAND.format(log_base=PATH_NEW.JF_PROJECT_HPS_LOG_DIR_POD_PATH, item_id=labels.project_item_id)

    run_command = hps_run_command(run_code_type=run_code_type[1:], run_code=run_code, parameter=parameter)

    # hps_run_command =  f"""{settings.HYPERPARAM_SEARCH_RUN_FILE} {search_option_command} --command \"{run_command}\" {log_command}"""

    hps_command = HPSCommand(
        run_command=run_command,
        hps_run_file=settings.HYPERPARAM_SEARCH_RUN_FILE,
        search_option_command=search_option_command,
        log_command=log_command
    )

    hps_pod_info = HPSPodInfo(
        helm_repo_name=TYPE.PROJECT_HELM_CHART_NAME.format(labels.project_item_id, TYPE.TOOL_TYPE[3]),
        clusters=nodes,
        cpu_instance_name=cpu_instance_name,
        command=hps_command,
        labels=labels,
        env=env,
        resource=resource,
        image=image,
        pod_name=unique_pod_name,
        owner_name=owner_name,
        total_gpu_count=pod_info["gpu_count"],
        distributed_framework=pod_info["distributed_framework"],
        distributed_config_path=escape_special_chars(pod_info["distributed_config_path"])
    )
    result , message = create_project_training_pod(training_pod=hps_pod_info)
    if result:
        db_project.update_project_training_datetime(training_type=labels.work_func_type ,training_id=labels.project_item_id, start_datetime=datetime.today().strftime("%Y-%m-%d %H:%M:%S"))

    return result , message


def create_project_tool(pod_info : dict):
    labels = ProjectToolLabels(
                        project_item_id=pod_info["id"],
                        project_id=pod_info["project_id"],
                        project_name=pod_info["project_name"],
                        # project_tool_id=pod_info["id"],
                        project_tool_type=TYPE.TOOL_TYPE[pod_info["tool_type"]],
                        workspace_id=pod_info["workspace_id"],
                        workspace_name=pod_info["workspace_name"],
                        owner_id=pod_info["owner_id"],
                        instance_id = pod_info["instance_id"]
                    )
    cpu_instance_name=""
    nodes = []
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
            nodes.append(Cluster(
                node_name = gpu_info["node_name"],
                gpu_uuids =  escape_special_chars(",".join(gpu_uuids)),
                gpu_ids = ".".join(map(str, gpu_ids)),
                gpu_count = len(gpu_uuids)
            ))

    elif pod_info.get("available_node",None):
        nodes.append(Cluster(
                node_name = pod_info["available_node"],
                gpu_uuids =  "",
                gpu_count = 0
            ))
    elif pod_info.get("cpu_instance_name", None):
        nodes.append(Cluster()) # helm 에서 for문을 돌려야 하기 때문에
        cpu_instance_name=pod_info.get("cpu_instance_name")


    start_datetime = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    base_pod_name, unique_pod_name, container_name = PodName(workspace_name=labels.workspace_name, start_datetime=start_datetime, item_name=labels.project_name,
                                                                    item_type=labels.project_tool_type).get_all()
    tool_password = pod_info["tool_password"]
    env = ENV(
            JF_HOST=pod_info["owner_name"],
            JF_ITEM_ID=pod_info["id"],
            JF_POD_NAME=unique_pod_name,
            JF_TOTAL_GPU=pod_info["gpu_count"]
        )

    workspace_resource = db_workspace.get_workspace_resource(workspace_id=labels.workspace_id)

    resource = LimitResource(
            cpu=workspace_resource["tool_cpu_limit"],
            memory="{}Gi".format(workspace_resource["tool_ram_limit"])
        )

    # postStart_command = None
    print(nodes, file=sys.stderr)

    labels.pod_count = len(nodes)

    project_tool_pod = ToolPodInfo(
        clusters=nodes,
        cpu_instance_name=cpu_instance_name,
        labels=labels,
        env=env,
        tool_password=escape_special_chars(tool_password),
        resource=resource,
        image=pod_info["image_name"],
        pod_name=unique_pod_name,
        owner_name=pod_info["owner_name"],
        total_gpu_count=pod_info["gpu_count"]
    )

    res, message = create_project_tool_pod(project_tool_pod=project_tool_pod)
    if res:
        db_project.update_project_tool_datetime(project_tool_id=pod_info["id"], start_datetime=start_datetime)
    else:
        if message:
            if "exceeded quota" in message:
                db_project.update_project_tool_pending_reason(reason="Waiting for memory or cpu resource allocation.", project_tool_id=pod_info["id"])

    return res, message