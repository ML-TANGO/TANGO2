NODE_INFO = "resource:node_info"
GPU_INFO_RESOURCE = "resource:gpu_info"
GPU_ALLOC_USAGE = "resource:gpu_alloc_usage"
CPU_INFO_RESOURCE = "resource:cpu_info"
MEM_INFO_RESOURCE = "resource:mem_info"
STORAGE_LIST_RESOURCE="resource:storage_info"
STORAGE_USAGE = "resource:storage_usage"
DATASET_STORAGE_USAGE = "resource:dataset_storage_usage"
PROJECT_STORAGE_USAGE = "resource:project_storage_usage"


WORKSPACE_RESOURCE_QUOTA = "resource:workspace:quota"
WORKSPACE_STORAGE_USAGE = "resource:workspace:storage_usage"

WORKSPACE_INSTANCE_USED = "resource:instance:workspace:used"
WORKSPACE_ITEM_PENDING_POD = "pod:workspace:item:pending"
WORKSPACE_INSTANCE_PENDING_POD = "pod:workspace:instance:pending"
DATASET_FILEBROWSER_POD_STATUS = "pod:dataset:filebrowser"

WORKSPACE_PODS_STATUS="pod:workspace:status"

# TOOL_PODS_STATUS="pod:tool:status"
# TOOL_PODS_STATUS_WORKSPACE="pod:tool:status:{workspace_id}"
# TRAINING_PODS_STATUS="pod:training:status"
# TRAINING_PODS_STATUS_WORKSPACE="pod:training:status:{workspace_id}"
# HPS_PODS_STATUS_WORKSPACE="pod:hps:status:{workspace_id}"
# PROJECT_PENDING_PODS="pod:workspace:{workspace_id}:project:pending"
# DEPLOYMENT_PENDING_PODS="pod:workspace:{workspace_id}:deployment:pending"
# DEPLOYMENT_WORKER_STATUS="pod:deployment:status"
# DEPLOYMENT_WORKER_STATUS_WORKSPACE="pod:deployment:status:{workspace_id}"

GPU_INFO_LOCK="resource:gpu_info:lock"

WORKSPACE_INSTANCE_QUEUE="workspace:{}:instance:{}" # workspace:113:instance:182:CPU


# TODO
# kafka 오류 발생시 사용하려고 생성한 key
PROJECT_POD_QUEUE="queue:project:{project_id}"

SSE_PROGRESS =  "SSE:{user_id}"
DATASET_UPLOAD_LIST = "dataset:upload:info"
DATASET_PROGRESS = "progress:{dataset_id}"
DATASET_UPLOADSIZE= "upload:{dataset_id}"
DATASET_UPLOAD_LOCK= "lock:{dataset_id}:{name}"
DATASET_DUPLICATE = "duplicate:{dataset_id}:{user_id}"
# DATASET_PROGRESS_SUB_KEY="{job_type}:{workspace_name}.{dataset_name}.{job_name}"

JOB_LIST="job:delete:queue"


############################
# CACHE
############################

PROJECT_USER_TOOLS = "user:project:tools"

DEPLOYMENT_WORKER_RESOURCE_LIMIT = "deployment:worker:limit"