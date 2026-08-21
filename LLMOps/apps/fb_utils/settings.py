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
# 인스턴스 분리(서빙 jonathan-system / 개발 tango-dev)용 파생 기준값.
# JF_SYSTEM_NAMESPACE 가 안 주입되는 경로(단독 스크립트·일부 잡)에서는 기존 리터럴로
# 폴백하므로 기존 배포 동작은 바뀌지 않는다. namespace 를 끼우는 상수/기본값은 모두 이 값을 쓴다.
SYSTEM_NAMESPACE = JF_SYSTEM_NAMESPACE or "jonathan-system"
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
    # built-in 전처리/pipeline 기본 실행 이미지. 기존 jfb/jbi_ubuntu(사내 레지스트리·pull불가)
    # 대신 docker.io/acrylaaai 게시 lean 베이스(python3+pandas/pyarrow/pillow/numpy). 소스=libs/fb_image/preprocessing.
    # FORMAT_CONVERT(데이터 포맷 변환) 포함 활성 빌트인 4종이 이 베이스에서 실행(스크립트는 NFS /built_in 마운트).
    # v2.2.0: 데이터 파이프라인 노드용 imagehash(pHash 중복제거)·pymupdf(PDF 페이지화) 추가.
    # 기존 4핀(pandas/pyarrow/pillow/numpy)은 그대로라 빌트인 4종에 영향 없음.
    JF_DEFAULT_UBUNTU_22_IMAGE = SYSTEM_DOCKER_REGISTRY_URL + "acrylaaai/genai-platform-builtin-preprocess:tango_v2.4.0"
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
# [멀티엔진 서빙 로드맵 Phase 2] llama.cpp 서빙 이미지(별도 서빙-레이어, FROM ghcr.io/ggml-org/llama.cpp:full).
DEPLOYMENT_LLM_LLAMACPP_IMAGE="acrylaaai/llm_deployment_llamacpp:dev"
# [멀티엔진 서빙 로드맵 Phase 3 / Tier B] TGI 서빙 이미지(별도 HTTP 서버, FROM ghcr.io/huggingface/text-generation-inference).
DEPLOYMENT_LLM_TGI_IMAGE="acrylaaai/llm_deployment_tgi:dev"
# [멀티엔진 서빙 로드맵 Phase 3 / Tier B] Ollama 서빙 이미지(별도 HTTP 서버, FROM ollama/ollama). safetensors→모델스토어 등록 후 /api/chat 서빙.
DEPLOYMENT_LLM_OLLAMA_IMAGE="acrylaaai/llm_deployment_ollama:dev"
# [멀티엔진 서빙 로드맵 Phase 3 / Tier B] Triton 서빙 이미지(NVIDIA Triton + vLLM backend, FROM nvcr.io/nvidia/tritonserver:*-vllm-python-py3). model repository + KServe generate.
DEPLOYMENT_LLM_TRITON_IMAGE="acrylaaai/llm_deployment_triton:dev"
# [멀티엔진 서빙 로드맵 Phase 3 / Tier B] TensorRT-LLM 서빙 이미지(FROM nvcr.io/nvidia/tritonserver:*-trtllm-python-py3). trtllm-serve OpenAI 호환 서버(PyTorch 백엔드 = HF 직접, AOT 컴파일 불요).
DEPLOYMENT_LLM_TENSORRT_IMAGE="acrylaaai/llm_deployment_tensorrt:dev"
# 서빙 엔진별 배포 이미지 맵. vLLM(GPU/CPU 폴백) + llama.cpp(GGUF 직접 / HF 온더플라이 변환) + TGI/Ollama/Triton/TensorRT(HF/safetensors).
# vLLM 서빙이 확보할 GPU 메모리 비율(전체 용량 기준). vLLM 은 이 값을 **여유 메모리**와
# 비교해 검사하므로, 서빙과 물리 노드를 공유해 GPU 가 부분 점유된 클러스터에서는 0.90 으로
# 기동이 거부된다. 클러스터별로 env 로 낮춘다(기본은 종전과 같은 0.90).
DEPLOYMENT_LLM_GPU_MEMORY_UTILIZATION = float(os.getenv("DEPLOYMENT_LLM_GPU_MEMORY_UTILIZATION") or 0.90)
SERVING_ENGINE_IMAGE_MAP = {"vllm": DEPLOYMENT_LLM_IMAGE, "llama_cpp": DEPLOYMENT_LLM_LLAMACPP_IMAGE, "tgi": DEPLOYMENT_LLM_TGI_IMAGE, "ollama": DEPLOYMENT_LLM_OLLAMA_IMAGE, "triton": DEPLOYMENT_LLM_TRITON_IMAGE, "tensorrt": DEPLOYMENT_LLM_TENSORRT_IMAGE}
# 지금 실제 지원하는 서빙 엔진(그 외 값은 서버측 거부).
SUPPORTED_SERVING_SYSTEMS = ("vllm", "llama_cpp", "tgi", "ollama", "triton", "tensorrt")
def resolve_serving_system(value):
    # 읽기 시점 정규화(defense-in-depth): None/미지원 → vllm(fail-safe). 쓰기 경로는 reject.
    v = value or "vllm"
    return v if v in SUPPORTED_SERVING_SYSTEMS else "vllm"
# 데이터셋 분석 워커 pod 이미지. 기존 jfb/analyzer(사내 레지스트리·pull불가 → ImagePullBackOff)
# 대신 docker.io/acrylaaai 게시 이미지. 소스=libs/fb_image/analyzer.
ANALYZER_IMAGE="acrylaaai/genai-platform-analyzer:tango_v2.0.1"



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
# 위 두 값은 kubelet 이 넣어주는 service-link env 로, "파드 생성 시점에 이미 존재하는
# Service" 만 주입된다. run.sh 의 설치 순서상 user 차트가 ingress_management 보다 먼저
# 설치되므로 신규 설치에서는 항상 미주입 → "http://None:None/api/ingress/auth" 로 로그인 실패.
# env 가 있으면 기존 값을 그대로 쓰고, 없을 때만 클러스터 DNS 로 폴백한다
# (LLM_PLAYGROUND_DNS 등 다른 상수와 같은 방식).
if JF_INGRESS_MANAGEMENT_SVC_HOST and JF_INGRESS_MANAGEMENT_SVC_PORT:
    JF_INGRESS_MANAGEMENT_DNS = f"{JF_INGRESS_MANAGEMENT_SVC_HOST}:{JF_INGRESS_MANAGEMENT_SVC_PORT}"
else:
    JF_INGRESS_MANAGEMENT_DNS = os.getenv(
        'JF_INGRESS_MANAGEMENT_DNS',
        f'jfb-app-ingress-management-svc.{SYSTEM_NAMESPACE}.svc.cluster.local',
    )

# [EXTERNAL CONTAINER]
# fb_external_container service (SP-Ext.2) — domain BFFs route partner
# container traffic here. Default points at the in-cluster ClusterIP; set
# explicitly to override per environment.
# ⚠️ 기본값은 실제 배포되는 Service 이름과 같아야 한다. 이전 기본값
# 'fb-external-container...:8000' 은 어떤 환경에도 그런 Service 가 없어서(실 이름은
# jfb-app-external-container-svc, port 80) env 오버라이드가 없는 인스턴스에서는 BFF 가
# 외부 컨테이너 잡을 아예 띄울 수 없었다(NXDOMAIN). 다른 서비스 DNS 기본값
# (LLM_PLAYGROUND_DNS = jfb-llm-playground-svc...)과 같은 규약으로 맞춘다.
FB_EXTERNAL_CONTAINER_URL = os.getenv(
    'FB_EXTERNAL_CONTAINER_URL',
    f'http://jfb-app-external-container-svc.{SYSTEM_NAMESPACE}.svc.cluster.local',
)

# [LLM PLAYGROUND] — A4 실 모델출력 배선. 배포(running) 모델의 추론 test_url 해석을
# playground s2s(get_test_options)에 위임하기 위한 ClusterIP DNS.
LLM_PLAYGROUND_DNS = os.getenv(
    'LLM_PLAYGROUND_DNS',
    f'jfb-llm-playground-svc.{SYSTEM_NAMESPACE}.svc.cluster.local',
)

# convert(양자화·포팅, SP-4) job 이 사용할 외부 컨테이너 manifest.
# mock-convert(SP-4 Step1)로 시작 — 실제 llama.cpp convert 컨테이너 도착 시
# 동일 계약(job_type=convert, /model 입력, /output 포팅 패키지)이라 env 만
# 교체하면 플랫폼 코드 변경 없이 전환된다.
CONVERT_MANIFEST_NAME = os.getenv('CONVERT_MANIFEST_NAME', 'mock-convert')
CONVERT_MANIFEST_VERSION = os.getenv('CONVERT_MANIFEST_VERSION', '1.0.0')

# 프롬프트 최적화(fewshot-prompt-optimizer, ETRI) 외부 컨테이너 manifest.
#   convert 와 동일 관행 — 컨테이너 버전이 올라가도 env 만 바꾸면 코드 변경 없이 전환된다.
PROMPT_OPT_MANIFEST_NAME = os.getenv('PROMPT_OPT_MANIFEST_NAME', 'fewshot-prompt-optimizer')
PROMPT_OPT_MANIFEST_VERSION = os.getenv('PROMPT_OPT_MANIFEST_VERSION', '1.0.0')

# evaluate(자동평가, SP-5) job 이 사용할 외부 컨테이너 manifest.
# 기본=플랫폼 소유 evaluate-selfmetric(자체 메트릭). 고려대 평가 plugin(⑪) 도착 시
# 동일 계약(job_type=evaluate, /model+/dataset 입력, /output/metrics.json)이라
# env 만 교체하면 플랫폼 코드 변경 없이 전환된다.
EVALUATE_MANIFEST_NAME = os.getenv('EVALUATE_MANIFEST_NAME', 'evaluate-selfmetric')
EVALUATE_MANIFEST_VERSION = os.getenv('EVALUATE_MANIFEST_VERSION', '1.0.0')

# benchmark(벤치마크 평가, llm_evaluation P1) job 이 사용할 외부 컨테이너 manifest.
# 기본=mock(evaluate-benchmark-mock, P1a) — 오케스트레이션/FE e2e 테스트용. 정식 벤치마크
# 컨테이너(고려대 plugin / 실측) 도착 시 동일 계약(job_type=evaluate)이라 env 만 교체하면
# 플랫폼 코드 변경 없이 전환된다. (기본 메트릭은 evaluate-selfmetric 으로 라우팅 가능.)
BENCHMARK_MANIFEST_NAME = os.getenv('BENCHMARK_MANIFEST_NAME', 'evaluate-benchmark-mock')
BENCHMARK_MANIFEST_VERSION = os.getenv('BENCHMARK_MANIFEST_VERSION', '0.2.0')

# SDS 도메인(3.5) 모델 생성 시 자동 바인딩되는 외부 컨테이너 manifest 의 고정 버전.
# 사용자는 모델 생성에서 domain=SDS 만 고르고 버전은 안 고른다 → create_model 이
# 이 상수로 external_manifest_name/version 을 해석. 바인딩 버전은 **env 로 flip**
# (FE 리빌드/코드 커밋 없이). 아래는 fresh-install 용 기본값(canonical base)일 뿐,
# 실 클러스터는 env `SDS_MANIFEST_VERSION` 로 운영 버전을 지정한다
# (예: 운영 클러스터 = `1.0.0-acryl-patched-v7`, recipe 포함). recipe 가 있는
# 버전이어야 FT 탭이 master-detail(레시피 파이프라인)로 렌더된다.
SDS_MANIFEST_NAME = os.getenv('SDS_MANIFEST_NAME', 'eva-vlm-train')
SDS_MANIFEST_VERSION = os.getenv('SDS_MANIFEST_VERSION', '1.0.0')

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
    FINE_TUNING_IMAGE= SYSTEM_DOCKER_REGISTRY_URL + "acrylaaai/finetuning:cuda12.4-transformers4.52.4-peft0.15-torch2.5.1-ubuntu22.04"
else:
    FINE_TUNING_IMAGE = "built-in-model/finetuning:cuda12.4-transformers4.52.4-peft0.15-torch2.5.1-ubuntu22.04"

# [JONATHAN PRICING MODE]

JF_PRICING_MODE = True if os.getenv("JF_PRICING_MODE",None) == "True" else False


# [JONATHAN INTELLIGENCE]
JONATHAN_INTELLIGENCE_USED = True
if JONATHAN_INTELLIGENCE_USED:
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
JF_KAFKA_SASL_USERNAME = os.getenv("JF_KAFKA_SASL_USERNAME", "tango")
JF_KAFKA_SASL_PASSWORD = os.getenv("JF_KAFKA_SASL_PASSWORD", "tango1234@")

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
