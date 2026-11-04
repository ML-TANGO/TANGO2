# RESOURCE
NODE_INFO = "resource:node_info"
GPU_INFO_RESOURCE = "resource:gpu_info"
GPU_INFO_RESOURCE2 = "resource:gpu_info2"
GPU_ALLOC_USAGE = "resource:gpu_alloc_usage"
# external 컨테이너 잡이 GPU 를 원자적으로 선점할 때 쓰는 예약 키(SETNX, TTL).
# ⚠️ 이 예약은 GPU_INFO_RESOURCE 의 `used_info` 를 **건드리지 않는다**. 그래서
#    used_info 만으로 가용량을 세면 external 잡이 잡고 있는 GPU 가 '가용' 으로 잡혀,
#    화면은 "가용 N장" 이라 말하는데 실행은 실패하는 어긋남이 생긴다(실측). 가용량을
#    세는 쪽은 반드시 이 키까지 봐야 한다 — 그 계산은 utils.gpu_pool.snapshot 한 곳에 있다.
#    쓰는 쪽 = fb_scheduler(external_run), 읽는 쪽 = fb_resource. 포맷이 갈리면 예약이
#    통째로 안 보이므로 상수를 여기 둔다.
GPU_RESERVE_KEY = "resource:gpu:reserved:{uuid}"
CPU_INFO_RESOURCE = "resource:cpu_info"
MEM_INFO_RESOURCE = "resource:mem_info"
NODE_RESOURCE_USAGE = "resource:node:usage"
STORAGE_LIST_RESOURCE="resource:storage_info"
STORAGE_USAGE = "resource:storage_usage"
DATASET_STORAGE_USAGE = "resource:dataset_storage_usage"
PROJECT_STORAGE_USAGE = "resource:project_storage_usage"
MODEL_STORAGE_USAGE = "resource:model_storage_usage"
RAG_STORAGE_USAGE = "resource:rag_storage_usage"
WORKSPACE_POD_RESOURCE_USAGE = "resource:workspace_pod_usage"
WORKSPACE_RESOURCE_QUOTA = "resource:workspace:quota"
WORKSPACE_STORAGE_USAGE = "resource:workspace:storage_usage"
WORKSPACE_NETWORK_USAGE= "resource:network:usage"
GPU_INFO_LOCK="resource:gpu_info:lock"
WORKSPACE_INSTANCE_USED = "resource:instance:workspace:used"


# POD STATUS

WORKSPACE_ITEM_PENDING_POD = "pod:workspace:item:pending"
WORKSPACE_ITEM_PENDING_POD2 = "pod:workspace:item:pending2"
WORKSPACE_INSTANCE_PENDING_POD = "pod:workspace:instance:pending"
DATASET_FILEBROWSER_POD_STATUS = "pod:dataset:filebrowser"
WORKSPACE_PODS_STATUS="pod:workspace:status"
# WORKSPACE_PODS_STATUS2="pod:workspace:status2"

# WORKSPACE INSTANCE QUEUE (scheduler)
WORKSPACE_INSTANCE_QUEUE="workspace:{}:instance:{}" # workspace:113:instance:182


# TODO
# kafka 오류 발생시 사용하려고 생성한 key
# FB
PROJECT_POD_STREAM="project:{}:workspace:{}"
DEPLOYMENT_POD_STREAM="deployment:{}:workspace:{}"
PREPROCESSING_POD_STREAM="preprocessing:{}:workspace:{}"
ANALYZER_POD_STREAM="analyzer:{}:workspace:{}"
COLLECT_POD_STREAM="collect:{}:workspace:{}"
# ALLM
MODEL_POD_STREAM="model:{}:workspace:{}"
RAG_POD_STREAM="rag:{}:workspace:{}"
PLAYGROUND_POD_STREAM="playground:{}:workspace:{}"


# DATASET 
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

DEPLOYMENT_WORKER_RESOURCE_LIMIT = "deployment:worker:limit"
DEPLOYMENT_WORKER_RESOURCE = "pod:deployment:workers:resource"

GPU_RESOUCE_UTILIZATION="resource:gpu_utilization"


############################
# URL
############################

SHORTEN_URL = "request:url"


############################
# ALERT
############################

USER_ALERT_CHANNEL = "alert:user:{}"