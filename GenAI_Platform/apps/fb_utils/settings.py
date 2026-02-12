import configparser
import os
import requests
import sys
# ====================== DEFAULT ======================

FLIGHTBASE_USED = True

PASSWORD_KEY = "$6$"
ADMIN_NAME = "admin"
ADMIN_TYPE = 0
JF_SYSTEM_NAMESPACE = os.getenv('JF_SYSTEM_NAMESPACE', None)
# [Maria DB Settings]
JF_DB_HOST = os.getenv('JF_DB_HOST',None)
JF_DB_PORT = int(os.getenv('JF_DB_PORT',0))
JF_DB_USER = os.getenv('JF_DB_USER','root')
JF_DB_PW = os.getenv('JF_DB_PW',None) 
JF_DB_NAME = os.getenv('JF_DB_NAME',"msa_jfb")
JF_LLM_DB_NAME = os.getenv('JF_LLM_DB_NAME',"jonathan_llm") 
JF_DUMMY_DB_NAME = "jfb_dummy"
JF_DB_CHARSET = os.getenv('JF_DB_CHARSET', "utf8") 
JF_DB_DOCKER = os.getenv('JF_DB_DOCKER', None)
JF_DB_ATTEMP_TO_CREATE = True if os.getenv('JF_DB_ATTEMP_TO_CREATE') == "true" else False # Attempt to create (DB TABLE and DUMMPY TABE) at every startup. can be slow.
JF_DB_MAX_CONNECTIONS = 10000
JF_DB_UNIX_SOCKET = os.getenv('JF_DB_UNIX_SOCKET',None)
JF_DB_COLLATION = os.getenv('JF_LLM_DB_COLLATION', 'utf8_general_ci')

# [Docker Registry URL]
DOCKER_REGISTRY_URL = os.getenv('DOCKER_REGISTRY_URL', None) # '192.168.1.13:5000/' # Should be an empty string or finished with slash(`/')
SYSTEM_DOCKER_REGISTRY_URL = os.getenv('SYSTEM_DOCKER_REGISTRY_URL', None) # '192.168.1.13:5000/' # Should be an empty string or finished with slash(`/')
if SYSTEM_DOCKER_REGISTRY_URL:
    JF_DEFAULT_UBUNTU_20_IMAGE = SYSTEM_DOCKER_REGISTRY_URL + "jfb/" +  'jbi_ubuntu-20.04.6:latest'
    JF_DEFAULT_UBUNTU_22_IMAGE = SYSTEM_DOCKER_REGISTRY_URL + "jfb/" +  'jbi_ubuntu-22.04.6:latest'
DOCKER_REGISTRY_PROTOCOL = os.getenv('DOCKER_REGISTRY_PROTOCOL', "http://") # "http://" | "https://"
SYSTEM_DOCKER_REGISTRY_PROTOCOL = os.getenv('SYSTEM_DOCKER_REGISTRY_PROTOCOL', "http://")
IMAGE_NAMESPACE = f"{JF_SYSTEM_NAMESPACE}-image" if JF_SYSTEM_NAMESPACE else "default-image"

# [Docker image (*.tar/Dockerfile) upload base path]
BASE_IMAGE_PATH = '/jf-data/images' # in docker
BASE_DOCKERFILE_PATH = '/jf-data/images' # in docker
HOST_BASE_IMAGE_PATH = '/jfbcore/jf-data/images' # in host
HOST_BASE_DOCKERFILE_PATH = '/jfbcore/jf-data/images' # in host



#[Built in images]
JF_DEFAULT_UBUNTU_20="JBI_Ubuntu-20.04.6"
JF_DEFAULT_UBUNTU_22="JBI_Ubuntu-22.04.4"
DEPLOYMENT_LLM_IMAGE="acrylaaai/llm_deployment:dev"
ANALYZER_IMAGE="jfb/analyzer:0.0.1"



JONATHAN_IMAGE_PULL_SECRETS_EABLED= True if os.getenv("JONATHAN_IMAGE_PULL_SECRETS_EABLED") == "true" else False

JONATHAN_PRIVATE_REPO_ENABLED= os.getenv("JONATHAN_PRIVATE_REPO_ENABLED", "false") 
JONATHAN_PRIVATE_PIP_ENABLED= os.getenv("JONATHAN_PRIVATE_PIP_ENABLED", "false")


# JONATHAN_IMAGE_PULL_SECRETS_NAME=os.environ.get("JONATHAN_IMAGE_PULL_SECRETS_NAME")

#[Others]
# ENABLE_LOG_FUNCTION_CALL = True
# NO_INIT_SCHEDULER = False # For debuging (TEST API in A server, DB and Kuber in B server)
# RUNNING_API_WITHOUT_SYSTEM_CHECK = False # True = Force running
# NODE_DB_IP_AUTO_CHAGE_TO_KUBER_INTERNAL_IP = False # True = If DB IP and KUBER INTERNAL IP are different, change to KUBER INTERNAL IP
# NODE_DB_NAME_AUTO_CHAGE_TO_KUBER_NODE_NAME = False # True = If DB NAME and KUBER NODE NAME are different, change to KUBER NODE NAME
# IMAGE_LIBRARY_INIT = True # image.py

#[Ingress option (jupyter, service, deployment))
EXTERNAL_HOST = os.getenv('EXTERNAL_HOST', None) # ex) flightbase.iacryl.com or None (then use local ip)
EXTERNAL_HOST_PORT = os.getenv('EXTERNAL_HOST_PORT', None)
EXTERNAL_HOST_REDIRECT = True if os.getenv('EXTERNAL_HOST_REDIRECT') == "true" else False # Redirect = True ( EXTERNAL_HOST ) , False ( EXTERNAL_HOST:nginx_port )
INGRESS_PROTOCOL = os.getenv('INGRESS_PROTOCOL', "http")  # http, https ( for communication with front protocol )
INGRESS_CLASS_NAME = os.getenv('INGRESS_CLASS_NAME', None)

#[Login option]
NO_TOKEN_VALIDATION_CHECK = True # Allow Multiple Login, Ignore Token expired etc..
TOKEN_EXPIRED_TIME = 3600 * 8 # 마지막 API 요청 이후로 부터 선언한 시간이 지나도록 사용이 없으면 TOKEN 자동 만료 (초)
TOKEN_UPDATE_TIME = 600 # 새 TOKEN 으로 업데이트 하는 주기 (초)
MAX_NUM_OF_LOGINS = 5

#[Login method]
LOGIN_METHOD =  "jfb" # jfb(default), jonathan, kisti
LOGIN_VALIDATION_CHECK_API = "" # jonathan("http://api.acryl.ai/accounts/profile"), kisti("http://10.211.55.52:8080/auth")

#[Kuber Settings]
KUBER_CONFIG_PATH = os.getenv('KUBER_CONFIG_PATH', None)

#[SSH BANNER and MOTD]
SSH_BANNER_FILE_PATH = None # BANNER FILE PATH (None = Default Banner)
SSH_MOTD_FILE_PATH = None # MOTD FILE PATH (None = Default MOTD) 

#[Dataset] FB에서 다운로드 지원여부
DATASET_DOWNLOAD_ALLOW = True

#[Deployment]
DEPLOYMENT_RESPONSE_TIMEOUT = 1000 # "n"
DEPLOYMENT_API_MODE = "prefix" # "prefix" | "port" (TYPE.py - DEPLOYMENT_PREFIX_MODE, DEPLOYMENT_PORT_MODE)
DEPLOYMENT_TEMPLATE_DB_UPDATE = False # 기존에 만들어진 Deployment 내용을 template화 (업데이트 시 최초 1회 사용으로 충분)

# [HPS]
# HYPERPARAM_SEARCH_RUN_FILE = "python3 /hps_runfile/search_ver3-inter/search.py" # "/hps_runfile/hps_u" # /hps_runfile = /jfbcore/jf-bin/hps
HYPERPARAM_SEARCH_CUSTOM_RUN_FILE = "python3 /hps/custom_search_new.py"
# [FS-SETTING]
FILESYSTEM_OPTION = "Unknown" # Unknown, MFS, Mounted
MAIN_STORAGE_PATH = "/jfbcore" # TODO 임시. MAIN STORAGE 영역 이외에 SUB STORAGE 개념 추가 시 조정 필요

# [JF STORAGE SETTING]
JF_VOLUME_DATA_TYPE = os.getenv('JF_VOLUME_DATA_TYPE', None)
JF_VOLUME_DATA_PATH = os.getenv('JF_VOLUME_DATA_PATH', None)
JF_VOLUME_DATA_SERVER = os.getenv('JF_VOLUME_DATA_SERVER', None)
JF_VOLUME_BIN_TYPE = os.getenv('JF_VOLUME_BIN_TYPE', None)
JF_VOLUME_BIN_PATH = os.getenv('JF_VOLUME_BIN_PATH', None)
JF_VOLUME_BIN_SERVER = os.getenv('JF_VOLUME_BIN_SERVER', None)
JF_VOLUME_WORKSPACE_STORAGE_CLASS_NAME = os.getenv('JF_VOLUME_WORKSPACE_STORAGE_CLASS_NAME', None)


# [JF MONGODB SETTING]
JF_MONGODB_PASSWORD= os.getenv('JF_MONGODB_PASSWORD', None)
JF_MONGODB_DNS = os.getenv('JF_MONGODB_DNS', None)
JF_MONGODB_PORT = os.getenv('JF_MONGODB_PORT', None)
JF_MONGODB_USER = os.getenv('JF_MONGODB_USER', None)

# [JF REDIS SETTING]
JF_REDIS_PROT = int(os.getenv("JF_REDIS_PROT", 0))
JF_REDIS_PASSWORD = os.getenv("JF_REDIS_PASSWORD", None)
JF_REDIS_CLUSTER_ENABLED = True if os.getenv("JF_REDIS_CLUSTER_ENABLED") == "true" else False
JF_REDIS_CLUSTER_DNS = os.getenv("JF_REDIS_CLUSTER_DNS", None)
JF_REDIS_MASTER_DNS = os.getenv("JF_REDIS_MASTER_DNS", None)
JF_REDIS_SLAVES_DNS = os.getenv("JF_REDIS_SLAVES_DNS", None)

# [JF MONITORING SETTING]
JF_NODE_EXPORTER_PORT = os.getenv("NODE_EXPORTER_PORT", None)

# [JF INSTANCE SETTING] # example) 80% 사용하고 싶으면 0.8 입력
JF_COMPUTING_NODE_CPU_PERCENT = float(os.getenv("JF_COMPUTING_NODE_CPU_PERCENT", 0.8))
JF_COMPUTING_NODE_RAM_PERCENT = float(os.getenv("JF_COMPUTING_NODE_RAM_PERCENT", 0.8)) 

# [PROMETHEUS]
PROMETHEUS_DNS="http://monitoring-kube-prometheus-prometheus.jake.svc.cluster.local:9090/prometheus"

# [EFK]
LOG_MIDDLEWARE_DNS = os.environ.get("LOG_MIDDLEWARE_DNS", None)

# [KONG]
JF_KONG_ADMIN_DNS = os.getenv('JF_KONG_ADMIN_DNS', None)
JF_KONG_ADMIN_HTTP_PORT = os.getenv('JF_KONG_ADMIN_HTTP_PORT', "8001")
JF_KONG_PROXY_DNS = os.getenv('JF_KONG_PROXY_DNS', None)

# [INGRESS MANAGEMENT]
JF_INGRESS_MANAGEMENT_SVC_HOST = os.getenv('JFB_APP_INGRESS_MANAGEMENT_SVC_SERVICE_HOST', None)
JF_INGRESS_MANAGEMENT_SVC_PORT = os.getenv('JFB_APP_INGRESS_MANAGEMENT_SVC_SERVICE_PORT', None)
JF_INGRESS_MANAGEMENT_DNS = f"{JF_INGRESS_MANAGEMENT_SVC_HOST}:{JF_INGRESS_MANAGEMENT_SVC_PORT}"

# [KAFKA]
JF_KAFKA_DNS = os.getenv('JF_KAFKA_DNS', None)

# [SSH]
JF_SSH_PORT = os.getenv('JF_SSH_PORT', None)
BASE_SSH_JUMP_FORMAT= 'ssh -o ProxyCommand="ssh -i /path/to/pem -p {ssh_port} -W %h:%p {header_user}@{ingress_ip}" root@{tool_pod_ip}'
# JF_SSH_SVC_TYPE = os.getenv('JF_SSH_SVC_TYPE']

# [DATASET]

USER_UUID_SET = 20000


# [HUGGINGFACE]
LLM_USED = True # os.environ.get("LLM_USED") == "true"
# [GITC]
GITC_USED = False # RAG, PROMPT 사용 여부 flag (GITC에서만 rag, prompt 사용)

HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN", "")
if SYSTEM_DOCKER_REGISTRY_URL:
    FINE_TUNING_IMAGE= SYSTEM_DOCKER_REGISTRY_URL + "acrylaaai/finetuning:cuda12.4-transformers4.52.4-torch2.5.1-ubuntu22.04" # "built-in-model/jonathan-finetuning:0.1.2-cuda12.4.1"
else:
    FINE_TUNING_IMAGE = "built-in-model/finetuning:cuda12.4-transformers4.52.4-torch2.5.1-ubuntu22.04"  # 기본값 설정 

# [JONATHAN PRICING MODE]

JF_PRICING_MODE = True if os.getenv("JF_PRICING_MODE",None) == "True" else False


# [JONATHAN INTELLIGENCE]
JONATHAN_INTELLIGENCE_USED = True
if JONATHAN_INTELLIGENCE_USED:
    HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN", HUGGINGFACE_TOKEN)
    JF_BUILT_IN_MODEL_BURN = SYSTEM_DOCKER_REGISTRY_URL + "built-in-model/" +  'burn:latest'
    
    


# [JONATHAN RDMA]
JF_RDMA_ENABLED = os.getenv("JF_RDMA_ENABLED", None)
JF_MP_ENABLED = os.getenv("JF_MP_ENABLED", None)
JFB_MP_SEED_NUM = os.getenv("JFB_MP_SEED_NUM", None)
JFB_MP_SEED_LIST = os.getenv("JFB_MP_SEED_LIST", None)
JF_PERF_ENABLED = os.getenv("JF_PERF_ENABLED", None)
JF_P2P_LIST = os.getenv("JF_P2P_LIST", None)

# [JONATHAN KAFKA]
JF_KAFKA_SECURITY_PROTOCOL = os.getenv("JF_KAFKA_SECURITY_PROTOCOL", "SASL_PLAINTEXT")
JF_KAFKA_SASL_MECHANISM = os.getenv("JF_KAFKA_SASL_MECHANISM", "PLAIN")
JF_KAFKA_SASL_USERNAME = os.getenv("JF_KAFKA_SASL_USERNAME", "acryl")
JF_KAFKA_SASL_PASSWORD = os.getenv("JF_KAFKA_SASL_PASSWORD", "acryl4958@")

# [NEXUS]

JONATHAN_NEXUS_PREFIX = os.getenv("JONATHAN_NEXUS_PREFIX", "")
JONATHAN_NEXUS_HOST = os.getenv("JONATHAN_NEXUS_HOST", "nexus-nexus-repository-manager.jonathan-nexus.svc.cluster.local")
JONATHAN_NEXUS_PORT = os.getenv("JONATHAN_NEXUS_PORT", "8081")

def check_offline_status(url="https://github.com", timeout=2):
    """
    socket을 사용하여 인터넷 연결 상태를 확인하여 오프라인 여부를 반환합니다.
    """
    try:
        # DNS 조회로 연결 상태 확인 (timeout 3초)
        requests.get(url, timeout=timeout)
        print("Online environment", file=sys.stderr)
        return "false"  # 온라인
    except requests.RequestException:
        print("Offline environment", file=sys.stderr)
        return "true"   # 오프라인

# 오프라인 상태 체크
JF_OFFLINE_MODE = check_offline_status()

# Kubernetes 설정
KUBERNETES_API_SERVER = os.getenv('KUBERNETES_API_SERVER', 'kubernetes.default.svc.cluster.local:443')
KUBERNETES_TOKEN = os.getenv('KUBERNETES_TOKEN', '')  # 서비스 계정 토큰
