import configparser
from utils.PATH import *
import os
# ====================== DEFAULT ======================
JF_INIT_ROOT_PW = os.environ['JF_INIT_ROOT_PW'] # root 초기 비밀번호
PASSWORD_KEY = "$6$"
ADMIN_NAME = "admin"

# [Maria DB Settings]
JF_DB_HOST = os.environ['JF_DB_HOST']
JF_DB_PORT = int(os.environ['JF_DB_PORT'])
JF_DB_USER = os.environ['JF_DB_USER']
JF_DB_PW = os.environ['JF_DB_PW']
JF_DB_NAME = os.environ['JF_DB_NAME']
JF_DUMMY_DB_NAME = "jfb_dummy"
JF_DB_CHARSET = os.environ['JF_DB_CHARSET']
JF_DB_DOCKER = os.environ['JF_DB_DOCKER']
JF_DB_ATTEMP_TO_CREATE = os.environ['JF_DB_ATTEMP_TO_CREATE'] == "true" # Attempt to create (DB TABLE and DUMMPY TABE) at every startup. can be slow.
JF_DB_MAX_CONNECTIONS = 10000
JF_DB_UNIX_SOCKET = os.environ['JF_DB_UNIX_SOCKET']
JF_DB_COLLATION = os.environ['JF_DB_COLLATION']

# [Docker Registry URL]
DOCKER_REGISTRY_URL = os.environ['DOCKER_REGISTRY_URL'] # '192.168.1.13:5000/' # Should be an empty string or finished with slash(`/')
DOCKER_REGISTRY_PROTOCOL = os.environ['DOCKER_REGISTRY_PROTOCOL'] # "http://" | "https://"
REGISTRY_SVC_DNS = os.environ['REGISTRY_SVC_DNS']
REGISTRY_SVC_PORT = os.environ['REGISTRY_SVC_PORT']

# [Docker image (*.tar/Dockerfile) upload base path]
BASE_IMAGE_PATH = '/jf-data/images' # in docker
BASE_DOCKERFILE_PATH = '/jf-data/images' # in docker
HOST_BASE_IMAGE_PATH = '/jfbcore/jf-data/images' # in host
HOST_BASE_DOCKERFILE_PATH = '/jfbcore/jf-data/images' # in host

# JF_DEFAULT_IMAGE =  DOCKER_REGISTRY_URL + "jfb/" 'jf_default:latest'
# JF_CPU_DEFAULT_IMAGE = DOCKER_REGISTRY_URL + "jfb/" + 'jf_ml_cpu_image:latest'
# JF_GPU_TF2_IMAGE = DOCKER_REGISTRY_URL + "jfb/" + 'jf_ml_gpu_tf2_image:latest'
# JF_GPU_TORCH_IMAGE = DOCKER_REGISTRY_URL + "jfb/" +  'jf_ml_gpu_torch_image:latest'
JF_DEFAULT_UBUNTU_20_IMAGE = DOCKER_REGISTRY_URL + "jfb/" +  'jbi_ubuntu-20.04.6:latest'
JF_DEFAULT_UBUNTU_22_IMAGE = DOCKER_REGISTRY_URL + "jfb/" +  'jbi_ubuntu-22.04.6:latest'

#[Built in images]
JF_DEFAULT_UBUNTU_20="JBI_Ubuntu-20.04.6-linux_5.4.0-182-generic"
JF_DEFAULT_UBUNTU_22="JBI_Ubuntu-22.04.4-linux_5.4.0-187-generic"

JONATHAN_IMAGE_PULL_SECRETS_EABLED=os.environ.get("JONATHAN_IMAGE_PULL_SECRETS_EABLED") == "true"
# JONATHAN_IMAGE_PULL_SECRETS_NAME=os.environ.get("JONATHAN_IMAGE_PULL_SECRETS_NAME")

#[Others]
# ENABLE_LOG_FUNCTION_CALL = True
# NO_INIT_SCHEDULER = False # For debuging (TEST API in A server, DB and Kuber in B server)
# RUNNING_API_WITHOUT_SYSTEM_CHECK = False # True = Force running
# NODE_DB_IP_AUTO_CHAGE_TO_KUBER_INTERNAL_IP = False # True = If DB IP and KUBER INTERNAL IP are different, change to KUBER INTERNAL IP
# NODE_DB_NAME_AUTO_CHAGE_TO_KUBER_NODE_NAME = False # True = If DB NAME and KUBER NODE NAME are different, change to KUBER NODE NAME
# IMAGE_LIBRARY_INIT = True # image.py

#[Ingress option (jupyter, service, deployment)]
EXTERNAL_HOST = os.environ['EXTERNAL_HOST'] # ex) flightbase.iacryl.com or None (then use local ip)
EXTERNAL_HOST_REDIRECT = os.environ['EXTERNAL_HOST_REDIRECT'] == "true" # Redirect = True ( EXTERNAL_HOST ) , False ( EXTERNAL_HOST:nginx_port )
INGRESS_PROTOCOL = os.environ['INGRESS_PROTOCOL']  # http, https ( for communication with front protocol )
INGRESS_CLASS_NAME = os.environ['INGRESS_CLASS_NAME']

#[Login option]
NO_TOKEN_VALIDATION_CHECK = True # Allow Multiple Login, Ignore Token expired etc..
TOKEN_EXPIRED_TIME = 3600 * 8 # 마지막 API 요청 이후로 부터 선언한 시간이 지나도록 사용이 없으면 TOKEN 자동 만료 (초)
TOKEN_UPDATE_TIME = 600 # 새 TOKEN 으로 업데이트 하는 주기 (초)
MAX_NUM_OF_LOGINS = 5

#[Login method]
LOGIN_METHOD =  "jfb" # jfb(default), jonathan, kisti
LOGIN_VALIDATION_CHECK_API = "" # jonathan("http://api.acryl.ai/accounts/profile"), kisti("http://10.211.55.52:8080/auth")

#[Kuber Settings]
KUBER_CONFIG_PATH = os.environ['KUBER_CONFIG_PATH']

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
HYPERPARAM_SEARCH_RUN_FILE = "python3 /hps_runfile/search_ver3-inter/search.py" # "/hps_runfile/hps_u" # /hps_runfile = /jfbcore/jf-bin/hps

# [FS-SETTING]
FILESYSTEM_OPTION = "Unknown" # Unknown, MFS, Mounted
MAIN_STORAGE_PATH = "/jfbcore" # TODO 임시. MAIN STORAGE 영역 이외에 SUB STORAGE 개념 추가 시 조정 필요

# [JF STORAGE SETTING]
JF_VOLUME_DATA_TYPE = os.environ['JF_VOLUME_DATA_TYPE']
JF_VOLUME_DATA_PATH = os.environ['JF_VOLUME_DATA_PATH']
JF_VOLUME_DATA_SERVER = os.environ['JF_VOLUME_DATA_SERVER']
JF_VOLUME_BIN_TYPE = os.environ['JF_VOLUME_BIN_TYPE']
JF_VOLUME_BIN_PATH = os.environ['JF_VOLUME_BIN_PATH']
JF_VOLUME_BIN_SERVER = os.environ['JF_VOLUME_BIN_SERVER']
JF_VOLUME_WORKSPACE_STORAGE_CLASS_NAME = os.environ['JF_VOLUME_WORKSPACE_STORAGE_CLASS_NAME']
JF_SYSTEM_NAMESPACE = os.environ['JF_SYSTEM_NAMESPACE']

# [JF MONGODB SETTING]
JF_MONGODB_PASSWORD= os.environ['JF_MONGODB_PASSWORD']
JF_MONGODB_DNS = os.environ['JF_MONGODB_DNS']
JF_MONGODB_PORT = os.environ['JF_MONGODB_PORT']
JF_MONGODB_USER = os.environ['JF_MONGODB_USER']

# [JF REDIS SETTING]
JF_REDIS_PROT = int(os.environ["JF_REDIS_PROT"])
JF_REDIS_PASSWORD = os.environ["JF_REDIS_PASSWORD"]
JF_REDIS_CLUSTER_ENABLED = os.environ["JF_REDIS_CLUSTER_ENABLED"] == "true"
JF_REDIS_CLUSTER_DNS = os.environ["JF_REDIS_CLUSTER_DNS"]
JF_REDIS_MASTER_DNS = os.environ["JF_REDIS_MASTER_DNS"]
JF_REDIS_SLAVES_DNS = os.environ["JF_REDIS_SLAVES_DNS"]

# [JF MONITORING SETTING]
JF_NODE_EXPORTER_PORT = os.environ["NODE_EXPORTER_PORT"]

# [JF INSTANCE SETTING] # example) 80% 사용하고 싶으면 0.8 입력
JF_COMPUTING_NODE_CPU_PERCENT = float(os.environ["JF_COMPUTING_NODE_CPU_PERCENT"])
JF_COMPUTING_NODE_RAM_PERCENT = float(os.environ["JF_COMPUTING_NODE_RAM_PERCENT"])

# [PROMETHEUS]
PROMETHEUS_DNS="http://monitoring-kube-prometheus-prometheus.jake.svc.cluster.local:9090/prometheus"

# [EFK]
LOG_MIDDLEWARE_DNS = os.environ.get("LOG_MIDDLEWARE_DNS")

# [KAFKA]
JF_KAFKA_DNS = os.environ['JF_KAFKA_DNS']