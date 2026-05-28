import utils.settings
from enum import Enum

#PLATFORM
PLATFORM_FLIGHTBASE = "flightbase"
PLATFORM_A_LLM = "a-llm" 
### 
STORAGE_TYPE_LOCAL = "local"
STORAGE_TYPE_S3 = "s3"
STORAGE_TYPE_NFS = "nfs"
STORAGE_TYPE_GCP = "gcp"
STORAGE_TYPE_AZURE = "azure"
STORAGE_TYPE_MINIO = "minio"
STORAGE_TYPE_HDFS = "hdfs"
STORAGE_TYPE_CEPH = "ceph"
STORAGE_TYPE_GLUSTERFS = "glusterfs"

STORAGE_TYPES = [STORAGE_TYPE_LOCAL, STORAGE_TYPE_S3, STORAGE_TYPE_NFS, STORAGE_TYPE_GCP, STORAGE_TYPE_AZURE, STORAGE_TYPE_MINIO, STORAGE_TYPE_HDFS, STORAGE_TYPE_CEPH, STORAGE_TYPE_GLUSTERFS]

STORAGE_ACCESS_MODE_READ_WRITE = "ReadWriteOnce"
STORAGE_ACCESS_MODE_READ_WRITE_MANY = "ReadWriteMany"

STORAGE_ACCESS_MODES = [STORAGE_ACCESS_MODE_READ_WRITE, STORAGE_ACCESS_MODE_READ_WRITE_MANY]

#######

TIME_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_DATE_FORMAT_SQL = "%Y-%m-%d %H:%i:%S"


PROJECT_TYPE = "project" # gpu usage type 중 하나
PROJECT_TYPE_A = "advanced" # training GPU
PROJECT_TYPE_B = "huggingface" # Huggingface Model
PROJECT_TYPE_C = "built-in" # Built-in Model 

TRAINING_ITEM_A = "training"
TRAINING_ITEM_B = "tool"
TRAINING_ITEM_C = "hps"

PROJECT_TYPES = [PROJECT_TYPE_A, PROJECT_TYPE_C, PROJECT_TYPE_B]

# Deployment
DEPLOYMENT_TYPE = "deployment"
DEPLOYMENT_TYPE_CUSTOM="custom"
DEPLOYMENT_TYPE_JI ="built-in"
DEPLOYMENT_TYPE_HUGGINGFACE="huggingface"

# ================================================================
# kubernetes
# ================================================================
 
# KUBE_POD_STATUS_ACTIVE =        "active"
KUBE_POD_STATUS_RUNNING =       "running" # deployment, training
KUBE_POD_STATUS_INSTALLING =    "installing" # deployment
KUBE_POD_STATUS_ERROR =         "error" # deployment
KUBE_POD_STATUS_STOP =          "stop" # deployment, training
KUBE_POD_STATUS_DONE =          "done" # == stop # training
KUBE_POD_STATUS_PENDING =       "pending" # training, deployment
KUBE_POD_STATUS_SCHEDULING =    "scheduling"

KUBER_NOT_RUNNING_STATUS = [KUBE_POD_STATUS_STOP, KUBE_POD_STATUS_PENDING, KUBE_POD_STATUS_DONE, KUBE_POD_STATUS_SCHEDULING, "expired", "reserved"]
KUBER_RUNNING_STATUS = [KUBE_POD_STATUS_RUNNING, KUBE_POD_STATUS_INSTALLING, KUBE_POD_STATUS_ERROR]
# running, installing, error

KUBE_ENV_JF_HOME_KEY="JF_HOME" # JF HOME DIR PATH KEY
KUBE_ENV_JF_HOME_KEY_ENV="$JF_HOME"

KUBE_ENV_JF_ITEM_OWNER_KEY="JF_HOST" # JF OWNER NAME KEY
KUBE_ENV_JF_ITEM_OWNER_KEY_ENV="$JF_HOST"

KUBE_ENV_JF_ITEM_ID_KEY="JF_ITEM_ID" # JF ITEM ID KEY (ex training_tool_id)
KUBE_ENV_JF_ITEM_ID_KEY_ENV="$JF_ITEM_ID"

KUBE_ENV_JF_ETC_DIR_KEY="JF_ETC"
KUBE_ENV_JF_ETC_DIR_KEY_ENV="$JF_ETC"

KUBE_ENV_JF_DEPLOYMENT_PWD_KEY="JF_DEPLOYMENT_PWD"
KUBE_ENV_JF_DEPLOYMENT_PWD_KEY_ENV="$JF_DEPLOYMENT_PWD"

# ================================================================
# TRAINING TOOL
# ================================================================

TOOL_JUPYTER_ID = 1
TOOL_JUPYTER_KEY = "jupyter"
TOOL_TRAINING_ID = 2
TOOL_TRAINING_KEY = "training"
TOOL_HPS_ID = 3
TOOL_HPS_KEY = "hps"
TOOL_SHELL_ID = 4
TOOL_SHELL_KEY = "shell"
TOOL_VSCODE_ID = 7
TOOL_VSCODE_KEY = "vscode"

DEFAULT_SHELL_PORT = 7681
DEFAULT_JUPYTER_PORT = 8888
DEFAULT_VSCODE_PORT = 8080

TOOL_TYPE = {
    TOOL_JUPYTER_ID: TOOL_JUPYTER_KEY,
    TOOL_TRAINING_ID: TOOL_TRAINING_KEY,
    TOOL_HPS_ID: TOOL_HPS_KEY,
    TOOL_SHELL_ID: TOOL_SHELL_KEY,
    TOOL_VSCODE_ID: TOOL_VSCODE_KEY
}

TOOL_PORT = {
    TOOL_JUPYTER_ID : DEFAULT_JUPYTER_PORT,
    TOOL_SHELL_ID : DEFAULT_SHELL_PORT,
    TOOL_VSCODE_ID : DEFAULT_VSCODE_PORT
}

TOOL_TYPE_ID = {
    TOOL_JUPYTER_KEY: TOOL_JUPYTER_ID,
    TOOL_TRAINING_KEY: TOOL_TRAINING_ID,
    TOOL_HPS_KEY: TOOL_HPS_ID,
    TOOL_SHELL_KEY: TOOL_SHELL_ID,
    TOOL_VSCODE_KEY : TOOL_VSCODE_ID
}
# Tool이 무슨 기능이 베이스인지 정보 제공용
TOOL_BASE_JUPYTER = "jupyter"
TOOL_BASE_UI = "ui"
TOOL_BASE_SHELL = "shell"
TOOL_BASE_VSCODE = "vscode"

TOOL_BASE = {
    TOOL_JUPYTER_ID: TOOL_BASE_JUPYTER,
    TOOL_TRAINING_ID: TOOL_BASE_UI,
    TOOL_HPS_ID: TOOL_BASE_UI,
    TOOL_SHELL_ID: TOOL_BASE_SHELL,
    TOOL_VSCODE_ID: TOOL_BASE_VSCODE
}
TOOL_BASE_LIST = [TOOL_JUPYTER_ID, TOOL_VSCODE_ID, TOOL_SHELL_ID]
# TOOL이 가지고 있는 기본 기능-Front와 연동용 (ssh, jupyter 버튼)
# TODO TOOL_BASE 와 TOOL_BUTTON 의 변수 분리 예정 (2022-09-29 Yeobie)
TOOL_BUTTON_LINK = "link"
TOOL_DEFAULT_FUNCTION_LIST = {
    TOOL_JUPYTER_KEY : [ TOOL_BASE_JUPYTER, TOOL_BUTTON_LINK], # TODO TOOL_BASE_JUPYTER 는 삭제 예정 (2022-09-29 Yeobie)
    TOOL_TRAINING_KEY : [TOOL_BASE_UI],
    TOOL_HPS_KEY : [TOOL_BASE_UI],
    TOOL_SHELL_KEY : [TOOL_BASE_SHELL,  TOOL_BUTTON_LINK],
    TOOL_VSCODE_KEY: [ TOOL_BASE_VSCODE, TOOL_BUTTON_LINK]
}

# ON/OFF로 동작하는 Tool 여부
TOOL_ON_OFF_POSSIBLE_LIST = [
    TOOL_JUPYTER_ID,
    TOOL_SHELL_ID,
    TOOL_VSCODE_ID
]

CHECKPOINT_EXTENSION = [".hdf5", ".pth", ".h5", ".pt", ".json", ".ckpt"]

# KUBE-DEFAULT-SVC
DEPLOYMENT_API_PORT_NAME="deployment-api"


TRAINING_ITEM_DELETED_INFO = {
    1: "training",
    2: TRAINING_ITEM_A,
    3: TRAINING_ITEM_C
}

# BUILT_IN_MODEL
INFO_JSON_EXTENSION='builtinjson'

# INGRESS
INGRESS_PATH_ANNOTAION="(/|$)(.*)"
INGRESS_REWRITE_DEFAULT="/$2"

# PORT FORWARDING 
# https://kubernetes.io/docs/concepts/services-networking/service/#protocol-support
# HTTP = LoadBalancer Only
# SCTP = > 1.20v  
PORT_PROTOCOL_LIST = ["TCP", "UDP"] # 

# POD RESOURCE KEY # TODO 하드코딩 되어 있는 부분 아래 변수로 통일 필요 (2022-09-20)
#==================================================================
# IMAGE
#==================================================================
IMAGE_UPLOAD_TYPE_TO_INT = {
  "built-in" : 0 ,"pull" : 1, "tar" : 2, "build" : 3, "tag" : 4, "ngc" : 5, "commit" : 6, "copy" : 7
}
IMAGE_UPLOAD_INT_TO_TYPE = {
    0 : "built-in", 1 : "pull", 2 : "tar", 3 : "build", 4 : "tag", 5 : "ngc", 6 : "commit", 7 : "copy",
}
IMAGE_LIBRATY_HELM = "image-library-{}"

IMAGE_TYPE_HELM = "{}-{}"

#==================================================================
# Filebrowser
#==================================================================
# Filebrowser Ingress 사용여부
FILEBROWSER_INGRESS_USE = False

# Filebrowser image 
FILEBROWSER_IMAGE = "jf_training_tool_filebrowser:latest"

#==================================================================
#NEW
#==================================================================
TOOL_URI_POD_NAME = "{}-0"

RESOURCE_TYPE_GPU = "GPU"
RESOURCE_TYPE_CPU = "CPU"
RESOURCE_TYPE_MIG = "MIG"
RESOURCE_TYPE_NPU = "NPU"
RESOURCE_TYPES = [RESOURCE_TYPE_GPU, RESOURCE_TYPE_CPU]

INSTANCE_TYPE_GPU = "GPU"
INSTANCE_TYPE_CPU = "CPU"
INSTANCE_TYPE_NPU = "NPU"


PROJECT_POD_HOSTNAME = "jonathan"

IMAGE_STATUS_PENDING = 0
IMAGE_STATUS_INSTALLING = 1
IMAGE_STATUS_READY = 2
IMAGE_STATUS_FAILED = 3

TRAINING_TOOL_VSCODE_URL = "/vscode/{}/?folder={}"
TRAINING_TOOL_SSH_URL = "/{}/{}"

DISTRIBUTED_FRAMEWORKS = ["NCCL", "MPI"]

#permission check levle
PERMISSION_ADMIN_LEVEL          = 1
PERMISSION_MANAGER_LEVEL        = 2
PERMISSION_CREATOR_LEVEL        = 3
PERMISSION_GENERAL_USER_LEVEL   = 4
PERMISSION_NOT_ACCESS_LEVEL     = 5

## HELM NAME 
PROJECT_HELM_CHART_NAME = "project-{}-{}"

NODE_ROLE_MANAGE = "manage"
NODE_ROLE_COMPUTING = "compute"

# PROJECT
PROJECT_POD_SVC_NAME = "{POD_NAME}-{TOOL_TYPE}"
PROJECT_POD_USER_INGRESS_NAME = "{SVC_NAME}-additional"

# WORKSPACE
WORKSPACE_NAMESPACE = "jonathan-system-{WORKSPACE_ID}"



# analyzer
ANALYZER_TYPE="analyzer"
ANALYZER_GRAPH_TYPE_LINE=0
ANALYZER_GRAPH_TYPE_BAR=1
ANALYZER_GRAPH_TYPE_PIE=2

ANALYZER_GRAPH_TYPE_INT_TO_STR = {
    0 : "line",
    1 : "bar",
    2 : "pie"
}
ANALYZER_HELM_NAME = "analyzer-{analyzer_id}-{graph_id}"


#==================================================================
# LLM
#==================================================================

FINE_TUNING_REPO_NAME = "fine-tuning-{}"

MODEL_COMMIT_NAMESPACE="jonathan-llm-model-commit"
MODEL_COMMIT_JOB_HELM_NAME="job-model-create-{MODEL_ID}"

FINE_TUNING_LOG_TAGS = ["train/loss", "train/grad_norm", "train/learning_rate", "eval/loss"]

MODEL_DATA_EXTENSIONS = [".csv", ".txt", ".json", ".jsonl", ".parquet", ".feather", ".pickle", ".pkl", ".pth", ".pt", ".h5", ".hdf5", ".hdf", ".hdf4", ".hdf3", ".hdf2", ".hdf1", ".hdf0", ".hdf-0", ".hdf-1", ".hdf-2", ".hdf-3", ".hdf-4", ".hdf-5", ".hdf-6", ".hdf-7", ".hdf-8", ".hdf-9", ".hdf-10"]

HUGGINGFACE_MODEL_GIT="https://huggingface.co/{MODEL_ID}"

MODEL_HUGGINGFACE_TYPE="huggingface"
MODEL_COMMIT_TYPE="commit"
MODEL_TYPES = [MODEL_HUGGINGFACE_TYPE, MODEL_COMMIT_TYPE]


MODEL_FIRST_COMMIT_NAME = "source_model"

FINE_TUNING_BASIC = "basic"
FINE_TUNING_ADVANCED = "advanced"

FINE_TUNING_TYPES = [FINE_TUNING_BASIC, FINE_TUNING_ADVANCED]

FINE_TUNING_TYPE = "fine_tuning"

COMMIT_TYPE_COMMIT = "commit"
COMMIT_TYPE_DOWNLOAD = "download"
COMMIT_TYPE_STOP = "stop"
COMMIT_TYPE_LOAD = "load"

# llm deployment
PLAYGROUND_MODEL = "playground-model"
PLAYGROUND_RAG_EMBEDDING = "playground-rag-embedding"
PLAYGROUND_RAG_RERANKER = "playground-rag-reranker"
RAG_RETRIEVAL_EMBEDDING = "rag-retrieval-embedding"
RAG_RETRIEVAL_RERANKER = "rag-retrieval-reranker"
RAG_TEST_EMBEDDING = "rag-test-embedding"
RAG_TEST_RERANKER = "rag-test-reranker"

LLM_RAG_TYPE_LIST = [PLAYGROUND_RAG_EMBEDDING, PLAYGROUND_RAG_RERANKER, RAG_RETRIEVAL_EMBEDDING, RAG_RETRIEVAL_RERANKER, RAG_TEST_EMBEDDING, RAG_TEST_RERANKER]
LLM_RAG_TYPE_INT_LIST = [2, 3, 4, 5, 6, 7]

LLM_RAG_EMBEDDING_LIST = [PLAYGROUND_RAG_EMBEDDING, RAG_RETRIEVAL_EMBEDDING, RAG_TEST_EMBEDDING]
LLM_RAG_RERANKER_LIST = [PLAYGROUND_RAG_RERANKER, RAG_RETRIEVAL_EMBEDDING, RAG_TEST_RERANKER]

LLM_DEPLOYMENT_TYPE_TO_INT = {
    PLAYGROUND_MODEL : 1,
    PLAYGROUND_RAG_EMBEDDING : 2,
    PLAYGROUND_RAG_RERANKER : 3,
    RAG_RETRIEVAL_EMBEDDING : 4,
    RAG_RETRIEVAL_RERANKER : 5,
    RAG_TEST_EMBEDDING : 6,
    RAG_TEST_RERANKER : 7,
}

LLM_DEPLOYMENT_INT_TO_TYPE = {
    1: PLAYGROUND_MODEL,
    2: PLAYGROUND_RAG_EMBEDDING,
    3: PLAYGROUND_RAG_RERANKER,
    4: RAG_RETRIEVAL_EMBEDDING,
    5: RAG_RETRIEVAL_RERANKER,
    6: RAG_TEST_EMBEDDING,
    7: RAG_TEST_RERANKER
}

LLM_DEPLOYMENT_HELM_NAME = "llm-deployment-{deployment_id}-{llm_type}-{llm_id}"

#==================================================================
# scheduler
#==================================================================
# SCHEDULING_TYPES = [TRAINING_ITEM_A, TRAINING_ITEM_B, TRAINING_ITEM_C, DEPLOYMENT_TYPE, FINE_TUNING_TYPE]


#==================================================================
# PREPROCESSING
#==================================================================

PREPROCESSING_TYPE = "preprocessing"
PREPROCESSING_ITEM_A = "tool"
PREPROCESSING_ITEM_B = "job"

PREPROCESSING_TYPE_A = "advanced" # training GPU
PREPROCESSING_TYPE_B = "built-in" # Built-in Model 
PREPROCESSING_TYPES = [PREPROCESSING_TYPE_A, PREPROCESSING_TYPE_B]

# BUILT IN
PREPROCESSING_BUILT_IN_TEXT_TYPE = "Text"
PREPROCESSING_BUILT_IN_IMAGE_TYPE = "Image"
PREPROCESSING_BUILT_IN_TABULAR_TYPE = "Tabular"
PREPROCESSING_BUILT_IN_VIDEO_TYPE = "Video"
PREPROCESSING_BUILT_IN_AUDIO_TYPE = "Audio"

## HELM NAME 
PREPROCESSING_HELM_CHART_NAME = "preprocessing-{}-{}"


PREPROCESSING_POD_SVC_NAME = "{POD_NAME}-{TOOL_TYPE}"

## PREPROCESSING BIILT IN DATA TYPE 
PREPROCESSING_BUILT_IN_DATA_TYPES = [
    PREPROCESSING_BUILT_IN_TEXT_TYPE,
    PREPROCESSING_BUILT_IN_IMAGE_TYPE,
    PREPROCESSING_BUILT_IN_TABULAR_TYPE,
    PREPROCESSING_BUILT_IN_VIDEO_TYPE,
    PREPROCESSING_BUILT_IN_AUDIO_TYPE
] 

# ================================================================
# COLLECT 
# ================================================================
COLLECT_TYPE = "collect"
PUBLICAPI_TYPE = "public-api"
REMOTESERVER_TYPE  = "remote-server"
CRAWLING_TYPE = "crawling"
FB_DEPLOY_TYPE = "flightbase"

#==================================================================
# PIPELINE
#==================================================================

PIPELINE_HELM_NAME = "pipeline-{}"
PIPELINE_TYPE = "pipeline"
PIPELINE_TYPE_A = "advanced"
PIPELINE_TYPE_B = "built-in"

DEPLOYMENT_TASK = "deployment_task"
PROJECT_TASK = "project_task"
PREPROCESSING_TASK = "preprocessing_task"

RETRAINING_DATA_TYPE = "data"
RETRAINING_TIME_TYPE = "time"

class PipelineRetrainingType(str, Enum):
    RETRAINING_DATA_TYPE = RETRAINING_DATA_TYPE
    RETRAINING_TIME_TYPE = RETRAINING_TIME_TYPE

RETRAINING_DATA_UNITS = ["TB","GB", "MB", "KB"]
RETRAINING_TIME_UNITS = ["hours", "minutes"]


TASK_TYPES = {
    DEPLOYMENT_TYPE: DEPLOYMENT_TASK,
    PROJECT_TYPE: PROJECT_TASK,
    PREPROCESSING_TYPE: PREPROCESSING_TASK
}

class PipelineTask(str, Enum):
    PREPROCESSING_TYPE = PREPROCESSING_TYPE
    PROJECT_TYPE = PROJECT_TYPE
    DEPLOYMENT_TYPE = DEPLOYMENT_TYPE

#==================================================================
# Huggingface tasks 
#==================================================================

MODEL_TASK_LIST = [
    "audio-classification",
    "audio-to-audio",
    "automatic-speech-recognition",
    "audio-text-to-text",
    "depth-estimation",
    "document-question-answering",
    "feature-extraction",
    "fill-mask",
    "graph-ml",
    "image-classification",
    "image-feature-extraction",
    "image-segmentation",
    "image-text-to-text",
    "image-to-image",
    "image-to-text",
    "image-to-video",
    "keypoint-detection",
    "video-classification",
    "mask-generation",
    "multiple-choice",
    "object-detection",
    "other",
    "question-answering",
    "robotics",
    "reinforcement-learning",
    "sentence-similarity",
    "summarization",
    "table-question-answering",
    "table-to-text",
    "tabular-classification",
    "tabular-regression",
    "tabular-to-text",
    "text-classification",
    "text-generation",
    "text-retrieval",
    "text-to-image",
    "text-to-speech",
    "text-to-audio",
    "text-to-video",
    "text2text-generation",
    "time-series-forecasting",
    "token-classification",
    "translation",
    "unconditional-image-generation",
    "video-text-to-text",
    "visual-question-answering",
    "voice-activity-detection",
    "zero-shot-classification",
    "zero-shot-image-classification",
    "zero-shot-object-detection",
    "text-to-3d",
    "image-to-3d",
    "any-to-any"
]


#==================================================================
# JONATHAN INSTANCE USED TYPE

INSTANCE_USED_TYPES = [
    PROJECT_TYPE, DEPLOYMENT_TYPE, PREPROCESSING_TYPE, FINE_TUNING_TYPE, ANALYZER_TYPE, COLLECT_TYPE
]

JONATHAN_FB_INSTANCE_USED_TYPES = [
        PROJECT_TYPE, DEPLOYMENT_TYPE, PREPROCESSING_TYPE, ANALYZER_TYPE, COLLECT_TYPE
]



















# ================================================================================================================================
# ================================================================================================================================
# ================================================================================================================================
# ================================================================================================================================
# ================================================================================================================================
# ================================================================================================================================
# ================================================================================================================================
# 사용안함

# DEPLOYMENT_TYPE_KEY = "deployment_type" # TEMP
# DEPLOYMENT_TYPE = "deployment" # gpu usage type 중 하나
# DEPLOYMENT_TYPE_A = "built-in" # TEMP
# DEPLOYMENT_TYPE_B = "custom" # TEMP
# DEPLOYMENT_TYPE_C = "example" # TEMP
# DEPLOYMENT_TYPE_E = "built-in-ji"

# DEPLOYMENT_TYPES = [DEPLOYMENT_TYPE_A, DEPLOYMENT_TYPE_B, DEPLOYMENT_TYPE_E]
# CREATE_KUBER_TYPE = [TRAINING_ITEM_A, TRAINING_ITEM_B, TRAINING_ITEM_C]


GPU_ALL_MODE = "all"
GPU_GENERAL_MODE = "general"
GPU_MIG_MODE = "mig"

# DEFAULT LABEL
KUBE_NODE_NAME_LABEL_KEY = "kubernetes.io/hostname"

# GPU-FEATURE-DISCOVERY LABEL
GFD_GPU_MODEL_LABEL_KEY = "nvidia.com/gpu.product"
GFD_GPU_MEMORY_LABEL_KEY = "nvidia.com/gpu.memory" # MSA 변경 "jfb/gpu-memory"??

# JF LABEL (KUBE LABEL)
CPU_WORKER_NODE_LABEL_KEY = "jfb/cpu-worker-node"
GPU_WORKER_NODE_LABEL_KEY = "jfb/gpu-worker-node"
GPU_MODEL_LABEL_KEY = "jfb/gpu-model"
GPU_MEMORY_LABEL_KEY = "jfb/gpu-memory"
GPU_CUDA_LABEL_KEY = "jfb/gpu-cuda-cores"
GPU_COMPUTER_CAPABILITY_LABEL_KEY = "jfb/gpu-computer-capability"
GPU_ARCHITECTURE_LABEL_KEY = "jfb/architecture"
CPU_MODEL_LABEL_KEY = "jfb/cpu-model"
CPU_MODEL_ENCODED_LABEL_KEY = "jfb/cpu-model-encoded"

NODE_NAME_LABEL_KEY = "kubernetes.io/hostname"

POD_NETWORK_INTERFACE_LABEL_KEY = "network_interface"
DEPLOYMENT_API_MODE_LABEL_KEY = "api_mode"
PARENT_DEPLOYMENT_WORKER_ID_LABEL_KEY = "parent_deployment_worker_id"

DEPLOYMENT_SERVICE_TYPE_LABEL_KEY = "service_type"
DEPLOYMENT_SERVICE_USER_NODE_PORT_VALUE = "user-nodeport"
DEPLOYMENT_SERVICE_USER_CLUSTER_IP_VALUE = "user-clusterip"
DEPLOYMENT_SERVICE_SYSTEM_NODE_PORT_VALUE = "system-nodeport"
DEPLOYMENT_SERVICE_SYSTEM_CLUSTER_IP_VALUE = "system-clusterip"

NAD_NETWORK_INTERFACE_TYPE_KEY="network-interface-type"
NAD_NETWORK_GROUP_CATEGORY_KEY = "network-group-category"

# Kubernetes Node Resource Key (ex - cpu, memory, ephemeral-storage, nvidia.com/gpu)
K8S_RESOURCE_CPU_KEY = "cpu" 
K8S_RESOURCE_MEMORY_KEY = "memory"
K8S_RESOURCE_EPHEMERAL_STORAGE_KEY = "ephemeral-storage"

K8S_RESOURCE_NETWORK_IB_LABEL_PREFIX = "jf.network.ib/"
K8S_RESOURCE_NETWORK_IB_LABEL_KEY = K8S_RESOURCE_NETWORK_IB_LABEL_PREFIX + "{ib_interface}"
K8S_RESOURCE_DEVICE_RDMA_IB_LABEL_PREFIX = "jf.device.rdma.ib/"
K8S_RESOURCE_DEVICE_RDMA_IB_LABEL_KEY = K8S_RESOURCE_DEVICE_RDMA_IB_LABEL_PREFIX + "{ib_interface}"


IB_RESOURCE_LABEL_KEY = "jf/ib"

NVIDIA_GPU_BASE_LABEL_KEY = "nvidia.com/"
NVIDIA_GPU_MIG_BASE_FLAG = "mig"
NVIDIA_GPU_RESOURCE_LABEL_KEY = NVIDIA_GPU_BASE_LABEL_KEY + "gpu"
NVIDIA_MIG_GPU_RESOURCE_LABEL_KEY = NVIDIA_GPU_BASE_LABEL_KEY + "{mig_key}" # nvidia.com/mig-1g.5gb, nvidia.com/mig-2g.10gb ..
                                                                            # NVIDIA_MIG_GPU_RESOURCE_LABEL_KEY.format(mig_key=NVIDIA_GPU_MIG_BASE_FLAG)

# JUPYTER_FLAG = "--jupyter"
# DEPLOYMENT_FLAG = "--deployment"
# TENSORBOARD_FLAG = "--tensorboard"
# SSH_FLAG = "--ssh"
# USERPORT_NODEPORT_FLAG = "--userport-0"
# USERPORT_CLUSTER_IP_PORT_FLAG = "--userport-1"
# SYSTEM_NODEPORT_FLAG = "--system-0"
# SYSTEM_CLUSTER_IP_PORT_FLAG = "--system-1"
# FILEBROWSER_FLAG = "--filebrowser"

# KUBE ANNOTAION
# K8S_ANNOTAION_NAD_RESOURCE_NAME_KEY = "k8s.v1.cni.cncf.io/resourceName" # NAD가 어느 resource와 맵핑 되는 것인지 정의해주는 annotation
# K8S_ANNOTAION_NAD_NETWORK_STATUS_KEY = "k8s.v1.cni.cncf.io/network-status" # 사용자 정의값 반영 및 시스템적으로 추가한 실제 동작중에 있는 정보를 포함하는 annotation
# K8S_ANNOTAION_NAD_NETWORKS_KEY = "k8s.v1.cni.cncf.io/networks" # 사용자 정의값 할당 시 사용하는 annotation


# Deployment 사용안함 --------------------------------------------------------
# CPU / RAM - deployment_api_deco, history.py 에도 쓰임
CPU_USAGE_ON_NODE_KEY = "cpu_usage_on_node" # POD 내에서 NODE의 몇%인지 
CPU_USAGE_ON_POD_KEY = "cpu_usage_on_pod" # POD 내에서 몇 %인지 # MSA 워커에서 KEY 사용
CPU_CORES_ON_POD_KEY = "cpu_cores_on_pod" # POD 내에서 코어 몇개 할당인지 

# RAM Graph
MEM_USAGE_KEY = "mem_usage"  # 사용량 절대값
MEM_LIMIT_KEY = "mem_limit"  # 사용 가능 크기
MEM_USAGE_PER_KEY = "mem_usage_per" # 사용량 비율

MEM_USAGE_PER_ON_NODE_KEY = "mem_usage_per_on_node" # TODO Pod 내에서 Node 기준에서의 사용량 percent를 기록할지 말지 ? (2022-10-19 Yeobie)

# GPU
GPU_UTIL_KEY = "util_gpu"
GPU_MEM_UTIL_KEY = "util_memory"
GPU_MEM_FREE_KEY = "memory_free"
GPU_MEM_USED_KEY = "memory_used"
GPU_MEM_TOTAL_KEY = "memory_total"

# TIME
TIMESTAMP_KEY= "timestamp"
POD_RUN_TIME_DATE_FORMAT = TIME_DATE_FORMAT
LOG_DELETE_DOWNLOAD_DATE_FORMAT = "%Y-%m-%d"
POD_RUN_TIME_START_TIME_KEY = "start_time"
POD_RUN_TIME_END_TIME_KEY = "end_time"
POD_RESOURCE_DEFAULT = { 
    CPU_USAGE_ON_NODE_KEY: 0, 
    CPU_USAGE_ON_POD_KEY: 0, 
    MEM_USAGE_KEY: 0, 
    MEM_LIMIT_KEY: 0, 
    MEM_USAGE_PER_KEY: 0,
    TIMESTAMP_KEY: 0
}

# NETWORK
NETWORK_TRANSMITTER_KEY="tx_bytes" # 송신량
NETWORK_RECEIVER_KEY="rx_bytes" # 수신량


# NGINX LOG KEY
NGINX_LOG_TIME_LOCAL_KEY = "time_local"
NGINX_LOG_STATUS_KEY = "status"
NGINX_LOG_REQUEST_TIME_KEY = "request_time"


# Unit
MEMORY_DEFAULT_UNIT = "G" # TODO G 단위를 유지할것인지 바이트 단위로 갈것인지 ?  (DB는 현재 GB 단위로 기록, kube 사용량 정보는 상황에 따라 다양한 값이 나옴)
CPU_CORES_DEFAULT_UNIT = "" # CPU 값을 정말 작게 주면 100m 과 같은 경우가 발생 가능
STORAGE_DEFAULT_UNIT = "G"


# DEPLOYMENT
DEPLOYMENT_PREFIX_MODE="prefix"
DEPLOYMENT_PORT_MODE="port"
DEPLOYMENT_API_DEFAULT_PORT=8555 # jf-bin/deployment_nginx DEPLOYMENT_NGINX_API_CONF_FILE_NAME와 연동 # API RUN
DEPLOYMENT_NGINX_DEFAULT_PORT=18555 # jf-bin/deployment_nginx DEPLOYMENT_NGINX_DEFAULT_CONF_FILE_NAME 연동 # LOG AND PROXY

DEPLOYMENT_NGINX_CONF_PATH_IN_POD="/etc/nginx_ex"
DEPLOYMENT_NGINX_API_CONF_FILE_NAME="api.conf"
DEPLOYMENT_NGINX_DEFAULT_CONF_FILE_NAME="nginx.conf"


DEPLOYMENT_NGINX_NUM_OF_LOG_PER_HOUR_DATE_FORMAT="%Y-%m-%dT%H" #"%Y-%m-%dT%H:%M"
DEPLOYMENT_API_NUM_OF_LOG_PER_HOUR_DATE_FORMAT="%Y-%m-%d %H" # "%Y-%m-%d %H:%M"
DEPLOYMENT_NGINX_PER_TIME_KEY="time"
DEPLOYMENT_NGINX_PER_TIME_NUM_OF_CALL_LOG_KEY="count"
DEPLOYMENT_NGINX_PER_TIME_RESPONSE_TIME_MEDIAN_KEY="median"
DEPLOYMENT_NGINX_PER_TIME_NUM_OF_ABNORMAL_LOG_COUNT_KEY="nginx_abnormal_count"
DEPLOYMENT_API_MONITOR_PER_TIME_NUM_OF_ABNORMAL_LOG_COUNT_KEY="api_monitor_abnormal_count"

DEFAULT_CUSTOM_DEPLOYMENT_JSON={
    "api_file_name": None,
    "checkpoint_load_dir_path_parser": None,
    "checkpoint_load_file_path_parser": None,
    "deployment_num_of_gpu_parser":None,
    "deployment_input_data_form_list": None,
    "deployment_output_types": None
}

# 템플릿 적용
DEPLOYMENT_RUN_CUSTOM="custom"
DEPLOYMENT_RUN_USERTRAINED="usertrained"
DEPLOYMENT_RUN_PRETRAINED="pretrained"
DEPLOYMENT_RUN_CHEKCPOINT="checkpoint"
DEPLOYMENT_RUN_SANDBOX="sandbox"

DEPLOYMENT_TEMPLATE_VERSION_1_TAIL = "v1"

DEPLOYMENT_TEMPLATE_TYPES = [f'{DEPLOYMENT_RUN_CUSTOM}_v1', f'{DEPLOYMENT_RUN_USERTRAINED}_v1', f'{DEPLOYMENT_RUN_PRETRAINED}_v1', f'{DEPLOYMENT_RUN_CHEKCPOINT}_v1']
DEPLOYMENT_RUN_CUSTOM_V1 = f'{DEPLOYMENT_RUN_CUSTOM}_v1'
DEPLOYMENT_RUN_USERTRAINED_V1 = f'{DEPLOYMENT_RUN_USERTRAINED}_v1'
DEPLOYMENT_RUN_PRETRAINED_V1 = f'{DEPLOYMENT_RUN_PRETRAINED}_v1'
DEPLOYMENT_RUN_CHEKCPOINT_V1 = f'{DEPLOYMENT_RUN_CHEKCPOINT}_v1'
DEPLOYMENT_RUN_SANDBOX_V1 = f'{DEPLOYMENT_RUN_SANDBOX}_v1'

DEPLOYMENT_DOCKER_IMAGE_NAME_KEY = "docker_image_name"

DEPLOYMENT_TEMPLATE_KIND_INFO_KEY = "kind"
DEPLOYMENT_TEMPLATE_TYPE_KEY = "deployment_template_type"
DEPLOYMENT_TEMPLATE_DEPLOYMENT_TYPE_KEY = "deployment_type"
DEPLOYMENT_TEMPLATE_TYPE_VERSION_KEY = "deployment_template_type_version"

DEPLOYMENT_TEMPLATE_CHECKPOINT_FILE_KEY = "checkpoint_file_path" # TODO template 수정사항 - checkpoint_file_path 로 변경?
DEPLOYMENT_TEMPLATE_CHECKPOINT_DIR_KEY = "checkpoint_dir_path"
DEPLOYMENT_TEMPLATE_RUNCODE_KEY = "run_code"
DEPLOYMENT_TEMPLATE_BUILT_IN_ID_KEY = "built_in_model_id"
DEPLOYMENT_TEMPLATE_BUILT_IN_NAME_KEY = "built_in_model_name"
DEPLOYMENT_TEMPLATE_TRAINING_ID_KEY = "training_id"
DEPLOYMENT_TEMPLATE_PROJECT_TYPE_KEY = "PROJECT_type"
DEPLOYMENT_TEMPLATE_TRAINING_NAME_KEY = "training_name"
DEPLOYMENT_TEMPLATE_JOB_ID_KEY = "job_id"
DEPLOYMENT_TEMPLATE_JOB_NAME_KEY = "job_name"
DEPLOYMENT_TEMPLATE_JOB_GROUP_INDEX_KEY = "job_group_index"
DEPLOYMENT_TEMPLATE_HPS_ID_KEY = "hps_id"
DEPLOYMENT_TEMPLATE_HPS_NAME_KEY = "hps_name"
DEPLOYMENT_TEMPLATE_HPS_GROUP_INDEX_KEY = "hps_group_index"
DEPLOYMENT_TEMPLATE_HPS_NUMBER_KEY = "hps_number"

DEPLOYMENT_TEMPLATE_RUN_COMMAND_KEY = "command"
DEPLOYMENT_TEMPLATE_RUN_BINARY_KEY = "binary"
DEPLOYMENT_TEMPLATE_RUN_SCRIPT_KEY = "script"
DEPLOYMENT_TEMPLATE_RUN_ARGUMENTS_KEY = "arguments"


DEPLOYMENT_TEMPLATE_ENVIRONMENTS_KEY = "environments"
DEPLOYMENT_TEMPLATE_MOUNT_KEY = "mount"
DEPLOYMENT_TEMPLATE_WORKING_DIRECTORY_KEY = "workdir"

DEPLOYMENT_TEMPLATE_DELETED_KEY = "is_deleted"


# DEPLOYMENT_USERTRAINED_CHECKPOINT_POD_PATH_DIC = {
#     TRAINING_ITEM_A:JF_TRAINING_JOB_CHECKPOINT_ITEM_POD_PATH,
#     TRAINING_ITEM_C:JF_TRAINING_HPS_CHECKPOINT_ITEM_POD_DIR_PATH
# }


# DEPLOYMENT_TEMPLATE_KIND_INFO = {
#     DEPLOYMENT_TEMPLATE_DEPLOYMENT_TYPE_KEY:None,
#     DEPLOYMENT_TEMPLATE_TYPE_KEY:None,
#     DEPLOYMENT_TEMPLATE_TYPE_VERSION_KEY:"v1"
# }

DEPLOYMENT_TEMPLATE_ENVIRONMENTS_INFO = {
    "name":None,
    "value":None
}
DEPLOYMENT_TEMPLATE_RUN_COMMAND_INFO = {
    DEPLOYMENT_TEMPLATE_RUN_BINARY_KEY: None,
    DEPLOYMENT_TEMPLATE_RUN_SCRIPT_KEY:None,
    DEPLOYMENT_TEMPLATE_RUN_ARGUMENTS_KEY:None
}

DEPLOYMENT_JSON_TEMPLATE = {
    DEPLOYMENT_RUN_CUSTOM_V1: {
        DEPLOYMENT_TEMPLATE_KIND_INFO_KEY: {
            DEPLOYMENT_TEMPLATE_DEPLOYMENT_TYPE_KEY: "custom",
            DEPLOYMENT_TEMPLATE_TYPE_KEY: DEPLOYMENT_RUN_CUSTOM,
            DEPLOYMENT_TEMPLATE_TYPE_VERSION_KEY:DEPLOYMENT_TEMPLATE_VERSION_1_TAIL
        },
        DEPLOYMENT_TEMPLATE_RUN_COMMAND_KEY: DEPLOYMENT_TEMPLATE_RUN_COMMAND_INFO,
        DEPLOYMENT_TEMPLATE_TRAINING_NAME_KEY: None,
        DEPLOYMENT_TEMPLATE_ENVIRONMENTS_KEY: None,
        # DEPLOYMENT_TEMPLATE_RUNCODE_KEY: None,
        DEPLOYMENT_TEMPLATE_TRAINING_ID_KEY : None
    },
    DEPLOYMENT_RUN_USERTRAINED_V1: {
        DEPLOYMENT_TEMPLATE_KIND_INFO_KEY: {
            DEPLOYMENT_TEMPLATE_DEPLOYMENT_TYPE_KEY: "built-in",
            DEPLOYMENT_TEMPLATE_TYPE_KEY: DEPLOYMENT_RUN_USERTRAINED,
            DEPLOYMENT_TEMPLATE_TYPE_VERSION_KEY: DEPLOYMENT_TEMPLATE_VERSION_1_TAIL
        },
        DEPLOYMENT_TEMPLATE_CHECKPOINT_FILE_KEY : None,
        DEPLOYMENT_TEMPLATE_CHECKPOINT_DIR_KEY : None,
        DEPLOYMENT_TEMPLATE_BUILT_IN_ID_KEY :None,
        DEPLOYMENT_TEMPLATE_BUILT_IN_NAME_KEY : None,
        DEPLOYMENT_TEMPLATE_TRAINING_NAME_KEY : None,
        DEPLOYMENT_TEMPLATE_PROJECT_TYPE_KEY : None,
        DEPLOYMENT_TEMPLATE_TRAINING_ID_KEY : None,
        DEPLOYMENT_TEMPLATE_JOB_ID_KEY : None,
        DEPLOYMENT_TEMPLATE_JOB_NAME_KEY : None,
        DEPLOYMENT_TEMPLATE_JOB_GROUP_INDEX_KEY : None,
        DEPLOYMENT_TEMPLATE_HPS_ID_KEY : None,
        DEPLOYMENT_TEMPLATE_HPS_GROUP_INDEX_KEY : None,
        DEPLOYMENT_TEMPLATE_HPS_NUMBER_KEY : None,
        DEPLOYMENT_TEMPLATE_HPS_NAME_KEY : None
    },
    DEPLOYMENT_RUN_PRETRAINED_V1: {
        DEPLOYMENT_TEMPLATE_KIND_INFO_KEY: {
            DEPLOYMENT_TEMPLATE_DEPLOYMENT_TYPE_KEY: "built-in",
            DEPLOYMENT_TEMPLATE_TYPE_KEY: DEPLOYMENT_RUN_PRETRAINED,
            DEPLOYMENT_TEMPLATE_TYPE_VERSION_KEY:DEPLOYMENT_TEMPLATE_VERSION_1_TAIL
        },
        DEPLOYMENT_TEMPLATE_BUILT_IN_NAME_KEY : None,
        DEPLOYMENT_TEMPLATE_BUILT_IN_ID_KEY :None
    },
    DEPLOYMENT_RUN_CHEKCPOINT_V1:{
        DEPLOYMENT_TEMPLATE_KIND_INFO_KEY: {
            DEPLOYMENT_TEMPLATE_DEPLOYMENT_TYPE_KEY: "built-in",
            DEPLOYMENT_TEMPLATE_TYPE_KEY: DEPLOYMENT_RUN_CHEKCPOINT,
            DEPLOYMENT_TEMPLATE_TYPE_VERSION_KEY:DEPLOYMENT_TEMPLATE_VERSION_1_TAIL
        },
        DEPLOYMENT_TEMPLATE_CHECKPOINT_FILE_KEY : None,
        DEPLOYMENT_TEMPLATE_CHECKPOINT_DIR_KEY : None,
        DEPLOYMENT_TEMPLATE_BUILT_IN_ID_KEY :None
    },
    DEPLOYMENT_RUN_SANDBOX_V1:{
        DEPLOYMENT_TEMPLATE_KIND_INFO_KEY: {
            DEPLOYMENT_TEMPLATE_DEPLOYMENT_TYPE_KEY:"custom",
            DEPLOYMENT_TEMPLATE_TYPE_KEY:DEPLOYMENT_RUN_SANDBOX,
            DEPLOYMENT_TEMPLATE_TYPE_VERSION_KEY:DEPLOYMENT_TEMPLATE_VERSION_1_TAIL
        }
    }
}

DEPLOYMENT_TEMPLATE_DEFAULT_NAME = "new-template"
DEPLOYMENT_TEMPLATE_GROUP_DEFAULT_NAME = "new-template-group"

# 사용안함
# ================================================================================================================================
# ================================================================================================================================
# ================================================================================================================================
# ================================================================================================================================
# ================================================================================================================================
# ================================================================================================================================
# ================================================================================================================================
