from pydantic import BaseModel, Field, validator, StrictStr
from typing import Optional, List, Union
import utils.HELP as HELP
from utils import PATH
from utils.TYPE import TRAINING_ITEM_A, TRAINING_ITEM_B, TRAINING_ITEM_C, PROJECT_TYPE, DEPLOYMENT_TYPE, PROJECT_POD_HOSTNAME, PROJECT_TYPE_A, PROJECT_TYPE_B, PROJECT_TYPE_C, DEPLOYMENT_TYPE_CUSTOM
#===================================
#=============LABEL=================
#===================================


class Accelerator(BaseModel):
    device_type: Optional[str] = ""  # GPU, NPU, ...
    model: Optional[str] = ""
    uuids : Optional[str] = ""
    ids : Optional[str] = "" # label에 길이 제한이 있기 때문에 추가
    count : int = 0

class Node(BaseModel):
    node_name : str = ""
    device : Accelerator = None

class Labels(BaseModel):
    role: str = "jfb-user-function"
    workspace_name: str
    workspace_id: int
    work_func_type: str = TRAINING_ITEM_B # tool, job, hps, deployment
    work_type: str = PROJECT_TYPE # project, deploy
    owner_id: int = None
    pod_type: str = PROJECT_TYPE
    instance_id: int = 1
    pod_count: int = 1
    helm_name: str = ""
    dataset_id: int = None

class PreprocessingLabels(Labels):
    preprocessing_id: int = None
    preprocessing_name: Optional[str] = None
    preprocessing_item_id : int = None
    
    
class ProjectLable(Labels):
    project_name: Optional[str] = None
    project_id: int = None
    project_item_id : int = None

class PreprocessingToolLabels(PreprocessingLabels):
    tool_type: str

class PreprocessingJobLabels(PreprocessingLabels):
    preprocessing_type : str 
    job_name : str


class TrainingLabels(ProjectLable):
    work_func_type : str = TRAINING_ITEM_A
    project_type : str = PROJECT_TYPE_A
    distributed_framework : str = ""
    training_name : str

class HPSLabels(ProjectLable):
    project_type : str = PROJECT_TYPE_A
    work_func_type : str = TRAINING_ITEM_C
    hps_name : str 
    distributed_framework : str = ""
    
class ProjectToolLabels(ProjectLable):
    tool_type: str
    # project_tool_id: int
    
class DeploymentLabels(Labels):
    deployment_id: int
    deployment_worker_id: int
    deployment_name: str
    deployment_type: str = DEPLOYMENT_TYPE
    user: str
    pod_name: str

    
class FineTuningLabel(Labels):
    pod_name : str = ""
    model_name : str
    model_id: int
    commit_id: int
    role: str = "jfb-api"
    commit_name : str
    model_dataset_id : int
    class Config:
        protected_namespaces = ()
    
#===================================
#==============ENV==================
#===================================
class ENV(BaseModel):
    JF_HOME: str = PATH.JF_PROJECT_BASE_HOME_POD_PATH
    JF_HOST: str 
    JF_ITEM_ID: int
    JF_POD_NAME: str
    JF_TOTAL_GPU: int

class BUILT_IN_ENV(ENV):
    JF_MODEL_PATH : str = PATH.JF_BUILT_IN_MODEL_PATH
    JF_DATASET_PATH : str = PATH.JF_BUILT_IN_DATASET_PATH
    JF_BUILT_IN_CHECKPOINT_PATH : str 
    JF_HUGGINGFACE_TOKEN : str 
    JF_HUGGINGFACE_MODEL_ID : str
    
class HpsENV(ENV):
    JF_HPS_LOG_BASE_PATH : str = PATH.JF_PROJECT_HPS_LOG_DIR_POD_PATH
    JF_HPS_LOG_PATH : str

class BUILT_IN_HpsENV(HpsENV):
    JF_MODEL_PATH : str = PATH.JF_BUILT_IN_MODEL_PATH
    JF_DATASET_PATH : str = PATH.JF_BUILT_IN_DATASET_PATH
    JF_BUILT_IN_CHECKPOINT_PATH : str 
    JF_HUGGINGFACE_TOKEN : str 
    JF_HUGGINGFACE_MODEL_ID : str
    
class FineTuningENV(BaseModel):
    JF_HOME: str = PATH.JF_POD_MODEL_PATH 
    JF_ITEM_ID: int
    JF_POD_NAME: str
    JF_TOTAL_GPU: int
    HUGGING_FACE_HUB_TOKEN : str
    JF_DB_HOST : str
    JF_DB_PORT : int
    JF_DB_USER : str
    JF_DB_PWD : str
#===================================
#============RESOURCE===============
#===================================

class LimitResource(BaseModel):
    cpu: float = 0
    memory: str = "0G"
    # ephemeral_storage: str
    # gpu: int
    
#===================================
#============COMMAND================
#===================================
class HPSCommand(BaseModel):
    run_command: str  
    hps_run_code: str
    encode_params : Optional[str]
    encode_fixed_params : Optional[str]
    built_in_search_count : Optional[int]
    
    
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
    gpu_uuid : Optional[str] = None # TODO 사용하는지 여부 
    cpu_instance_name :  Optional[str] = None
    
class ToolPodInfo(BaseModel):
    restartPolicy: str = "Never"
    labels: Labels = None
    env: ENV = None
    resource: LimitResource = None
    cluster : List[Node] = []
    image: str = None
    pod_name: str
    svc_name: str = None
    port : int = None
    owner_name: str
    cpu_instance_name :  Optional[str] = None
    total_device_count : int  = 0 
    tool_password : str = None
    hostname: str = PROJECT_POD_HOSTNAME
    dataset_id : int 
    dataset_access : int
    dataset_name : str 

class PreprocessingToolPodInfo(BaseModel):
    restartPolicy: str = "Never"
    labels: Labels = None
    env: ENV = None
    resource: LimitResource = None
    cluster : List[Node] = []
    image: str = None
    pod_name: str
    svc_name: str = None
    port : int = None
    owner_name: str
    cpu_instance_name :  Optional[str] = None
    total_device_count : int  = 0 
    tool_password : str = None
    hostname: str = PROJECT_POD_HOSTNAME
    dataset_id : int 
    dataset_access : int
    dataset_name : str 

class PreprocessingJobPodInfo(PreprocessingToolPodInfo):
    command: str = None

    
class TrainingPodInfo(ToolPodInfo):
    command: str = None
    distributed_framework : str = ""
    distributed_config_path : str = ""
    
class HPSPodInfo(TrainingPodInfo):
    command : str

class DeploymentResourcesDetail(BaseModel):
    cpu: Optional[float] = 0.0
    memory: Optional[float] = 0.0
    gpu: Optional[int] = 0
    npu: Optional[int] = 0

class DeploymentResources(BaseModel):
    limits: Optional[DeploymentResourcesDetail] = None
    requests: Optional[DeploymentResourcesDetail] = None

class DeploymentInfo(PodBaseInfo):
    pod_type: str = DEPLOYMENT_TYPE
    work_type: str = DEPLOYMENT_TYPE
    work_func_type: str = DEPLOYMENT_TYPE
    deployment_type:str = DEPLOYMENT_TYPE
    # -------------------------
    workspace_id: int
    workspace_name: str
    user: str
    deployment_id: int
    deployment_name: str
    deployment_worker_id: int
    project_name: Optional[str] = None
    # -------------------------
    pod_name: str
    pod_base_name: str
    pod_image: str
    run_code: Optional[str] = None
    # -------------------------
    instance_id: int
    resource_group_id : Optional[int] = None
    gpu_count: int
    cluster : List[Node] = []
    gpu_cluster_auto: Optional[bool] = False
    gpu_auto_cluster_case: Optional[dict] = dict()
    gpu_select: Optional[list] = []
    resources: DeploymentResources
    # -------------------------
    model_type: str = DEPLOYMENT_TYPE_CUSTOM
    huggingface_model_id: Optional[str] = None
    huggingface_token: Optional[str] = None
    training_id: Optional[int] = None

    class Config:
        protected_namespaces = ()

class FineTuningPodInfo(BaseModel):
    restartPolicy: str = "Never"
    env: FineTuningENV 
    labels : FineTuningLabel
    resource: LimitResource
    image: str = None
    pod_name: str
    command : str
    cluster : List[Node] = []
    cpu_instance_name :  Optional[str] = None
    total_device_count : int  = 0 
    used_dist : bool
    helm_repo_name: str
    hostname: str = PROJECT_POD_HOSTNAME
    dataset_access: int
    dataset_name: str
    multipath_enable: Optional[bool] = False
    
#===============================
# fine tuning param
#===============================

class FineTuningParam(BaseModel):
    num_train_epochs : float = Field(default=3.0, description='Total number of training epochs to perform')
    gradient_accumulation_steps : Optional[int] = Field(default=1, description='Number of updates steps to accumulate before performing a backward/update pass.')
    cutoff_length : int = Field(default=1, description='')
    learning_rate : float = Field(default=5e-5, description='The initial learning rate for AdamW.')
    warmup_steps : int = Field(default=0, description='Linear warmup over warmup_steps.')
    load_in_8bit : int = Field(default=0, description='')
    used_lora : int = Field(default=0, description='used lora')




