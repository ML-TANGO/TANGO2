from pydantic import BaseModel, Field, validator, StrictStr
from typing import Optional, List
import utils.HELP as HELP
from utils.PATH import *
from utils import PATH_NEW
from utils.TYPE import TRAINING_ITEM_A, TRAINING_ITEM_B, TRAINING_ITEM_C, PROJECT_TYPE, DEPLOYMENT_TYPE, DEPLOYMENT_ITEM_A, PROJECT_POD_HOSTNAME
#===================================
#=============LABEL=================
#===================================


class Cluster(BaseModel):
    node_name : str = ""
    gpu_uuids : str = ""
    gpu_ids : str = "" # label에 길이 제한이 있기 때문에 추가
    gpu_count : int = 0

class Labels(BaseModel):
    role: str = "jfb-user-function"
    project_item_id : int = None
    workspace_name: str
    workspace_id: int
    project_name: str
    project_id: int = None
    work_func_type: str = TRAINING_ITEM_B # tool, job, hps, deployment
    work_type: str = PROJECT_TYPE# project, deploy
    owner_id: int = None
    pod_type: str = PROJECT_TYPE
    instance_id: int = 1
    pod_count: int = 1

class TrainingLabels(Labels):
    distributed_framework : str = ""
    training_name : str

class HPSLabels(Labels):
    create_user_id : int
    hps_group_id: int
    hps_group_index : int
    hps_group_name: str
    distributed_framework : str = ""

class ProjectToolLabels(Labels):
    project_tool_type: str
    # project_tool_id: int

class DeploymentLabels(Labels):
    deployment_id: int
    deployment_worker_id: int
    deployment_name: str
    deployment_type: str = DEPLOYMENT_TYPE
    executor_id: int
    executor_name: str
    user: str
    pod_name: str
    pod_base_name: str

#===================================
#==============ENV==================
#===================================
class ENV(BaseModel):
    JF_HOME: str = PATH_NEW.JF_PROJECT_BASE_HOME_POD_PATH
    JF_HOST: str
    JF_ITEM_ID: int
    JF_POD_NAME: str
    JF_TOTAL_GPU: int

class HpsENV(ENV):
    JF_HPS_ORIGINAL_RECORD_FILE_PATH: str
    JF_HPS_ORIGINAL_RECORD_N_ITER_FILE_PATH: str
    JF_HPS_ID: int
    JF_HPS_SAVE_FILE_BASE_PATH: str
    JF_HPS_SAVE_FILE_NAME: str
    JF_HPS_LOAD_FILE_NAME: str
    JF_GRAPH_LOG_FILE_PATH: str
    JF_GRAPH_LOG_BASE_PATH: str
    # JF_OMPI_HOSTS: str
    # JF_N_GPU: int


#===================================
#============RESOURCE===============
#===================================

class LimitResource(BaseModel):
    cpu: float = 0
    memory: str = "0Gi"
    # ephemeral_storage: str
    # gpu: int

#===================================
#============COMMAND================
#===================================
class HPSCommand(BaseModel):
    run_command: str
    hps_run_file : str
    search_option_command : str
    log_command : str
    # use_mpi: bool = False
    # use_gpu_acceleration: bool = False
    # run_code_type: StrictStr = Field(pattern="^(py|sh)$")


#===================================
#==============POD==================
#===================================

class PodBaseInfo(BaseModel):
    pod_type: str
    gpu_count: Optional[int]
    instance_id: int
    nodename : Optional[str] = None
    gpu_uuid : Optional[str] = None
    cpu_instance_name :  Optional[str] = None

class ToolPodInfo(BaseModel):
    restartPolicy: str = "Never"
    labels: Labels = None
    env: ENV = None
    resource: LimitResource = None
    image: str = None
    pod_name: str
    owner_name: str
    clusters : List[Cluster] = []
    cpu_instance_name :  Optional[str] = None
    total_gpu_count : int  = 0
    tool_password : str = None
    hostname: str = PROJECT_POD_HOSTNAME


class TrainingPodInfo(ToolPodInfo):
    helm_repo_name : str
    cpu_instance: str = None
    command: str = None
    distributed_framework : str = ""
    distributed_config_path : str = ""

class HPSPodInfo(TrainingPodInfo):
    command : HPSCommand
    distributed_framework : str = ""
    distributed_config_path : str = ""

class DeploymentResources(BaseModel):
    cpu_limits: Optional[int] = 0
    ram_limits: Optional[int] = 0

class DeploymentInfo(PodBaseInfo):
    pod_type: str = DEPLOYMENT_TYPE
    # -------------------------
    deployment_id: int
    deployment_name: str
    deployment_worker_id: int
    workspace_id: int
    workspace_name: str
    resource_group_id : int
    # resource_name: str
    executor_id: int
    executor_name: str
    # -------------------------
    project_name: str
    base_pod_name: str
    pod_base_name: str
    pod_name: str
    # -------------------------
    user: str
    pod_image: str
    run_code: Optional[str] = None
    # labels: dict
    env: Optional[list] = None
    # -------------------------
    work_type: str = DEPLOYMENT_TYPE
    work_func_type: str = DEPLOYMENT_TYPE
    deployment_type:str = DEPLOYMENT_TYPE
    # -------------------------
    clusters : List[Cluster] = []
    gpu_count: int
    instance_id: int
    gpu_cluster_auto: Optional[bool] = False
    gpu_select: Optional[list] = []
    resources: DeploymentResources
