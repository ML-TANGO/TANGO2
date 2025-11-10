from pydantic import BaseModel, Field, validator, StrictStr, model_validator, field_validator
from typing import Optional, List, Union, Any
import json
import utils.HELP as HELP
from utils import PATH
from utils.TYPE import TRAINING_ITEM_A, TRAINING_ITEM_B, TRAINING_ITEM_C, PROJECT_TYPE, DEPLOYMENT_TYPE, PROJECT_POD_HOSTNAME
from utils import TYPE
from utils import settings

# ============================================================================
# 1. APP -> pod info (kafka로 전송할때 사용)
# 다중상속 사용시 에러 발생
# ============================================================================
# required
class HelmRequiredCluster(BaseModel):
    node_name : str = ""
    gpu_uuids : str = ""
    gpu_ids : str = "" # label에 길이 제한이 있기 때문에 추가
    gpu_count : int = 0

class HelmRequired(BaseModel):
    # scheduler: 스케줄러 코드에서 필수로 사용되는 파라미터
    pod_type: str
    work_func_type: str
    gpu_count: int
    gpu_select: Optional[list] = []
    gpu_cluster_auto: Optional[bool] = True
    gpu_auto_cluster_case: Optional[dict] = dict()
    
    # cluster
    clusters: List[HelmRequiredCluster] = []

    # metadata
    metadata_instance_id: int
    metadata_workspace_id: int
    metadata_workspace_name: str
    metadata_user_name: str
    metadata_pod_name: Optional[str] = None
    metadata_pod_base_name: Optional[str] = None
    metadata_helm_name: Optional[str] = None
    metadata_workspace_namespace: Optional[str] = None # 안넣어도 workspace_id를 기반으로 생성됨,
    metadata_system_namespace: str = settings.JF_SYSTEM_NAMESPACE

    # resources
    resources_limits_cpu: float
    resources_limits_memory: float
    resources_limits_gpu: Optional[int] = 0
    resources_limits_npu: Optional[int] = 0
    resources_requests_cpu: Optional[float] = 0.1
    resources_requests_memory: Optional[float] = 0.1
    resources_requests_gpu: Optional[int] = 0
    resources_requests_npu: Optional[int] = 0

    # pod
    pod_host_name: Optional[str] = None
    pod_image: str
    pod_image_registry: str = settings.SYSTEM_DOCKER_REGISTRY_URL

    @validator("metadata_workspace_namespace", pre=True, always=True)
    # @field_validator("metadata_workspace_namespace", model="before")
    def set_metadata_namespace(cls, v, values):
        return TYPE.WORKSPACE_NAMESPACE.format(WORKSPACE_ID=values.get("metadata_workspace_id"))

# Deployment
class HelmDeployment(HelmRequired):
    pod_type: str = TYPE.DEPLOYMENT_TYPE
    work_func_type: str = TYPE.DEPLOYMENT_TYPE
    is_llm: bool = False
    deployment_id: int
    deployment_name: str
    deployment_worker_id: Optional[int] = None
    ingress_class_name: str = settings.INGRESS_CLASS_NAME

# Analyzer
class HelmAnalyzer(HelmRequired):
    pod_type: str = TYPE.ANALYZER_TYPE
    work_func_type: str = TYPE.ANALYZER_TYPE
    gpu_count: int = 0
    analyzer_id: int
    graph_id: int
    graph_type: str
    data_path: str
    column: str

# LLM
class HelmLlm(HelmDeployment):
    llm_type: str
    llm_id: int # rag_id or playground_id
    llm_name: str # rag_name or playground_name

    def __init__(self, **data):
        super().__init__(**data)
        self.is_llm = True

# LLM - HelmPlayground, HelmRag에서 사용하는 Model
class HelmLLMInputModel(BaseModel):
    model_type: Optional[str] = None
    model_huggingface_id: Optional[str] = None
    model_huggingface_token: Optional[str] = None
    model_allm_name: Optional[str] = None
    model_allm_commit_name: Optional[str] = None
    huggingface_api_token: Optional[str] = settings.HUGGINGFACE_TOKEN

    class Config:
        protected_namespaces = () 

# LLM - Rag
class HelmRag(HelmLlm, HelmLLMInputModel):
    rag_id: Optional[int] = None
    rag_chunk_len: Optional[int] = None
    rag_embedding_run: Optional[int] = None

# LLM - playground
class HelmPlayground(HelmLlm, HelmLLMInputModel):
    playground_id: Optional[int] = None
    param_temperature: Optional[float] = None
    param_top_p: Optional[float] = None
    param_top_k: Optional[int] = None
    param_repetition_penalty: Optional[float] = None
    param_max_new_tokens: Optional[float] = None
    prompt_system_message: Optional[str] = None
    prompt_user_message: Optional[str] = None
    run_rag: Optional[bool] = None
    run_rag_reranker: Optional[bool] = None
    run_prompt: Optional[bool] = None
    rag_id: Optional[int] = None
    accelerator: Optional[bool] = False

    class Config:
        protected_namespaces = () 


# ============================================================================
# parser: YamlToValue에서 parsing할때 사용
# ============================================================================
class BaseConfig(BaseModel):
    @model_validator(mode='before')
    def flatten_to_nested(cls, values):
        # 평평한 형태의 데이터를 중첩된 형태로 변환
        res = {
            "metadata": {
                "id": {
                    "instanceId": values.get("metadata_instance_id"),
                    "workspaceId": values.get("metadata_workspace_id"),
                },
                "name": {
                    "workspaceName": values.get("metadata_workspace_name"),
                    "userName": values.get("metadata_user_name"),
                    "podName": values.get("metadata_pod_name"),
                    "podBaseName": values.get("metadata_pod_base_name"),
                    "helmName": values.get("metadata_helm_name"),
                }, 
                "namespace": {
                    "workspaceNamespace": values.get("metadata_workspace_namespace"),
                    "systemNamespace": values.get("metadata_system_namespace"),
                }
            },
            "resources": {
                "limits": {
                    "cpu": values.get("resources_limits_cpu"),
                    "memory": values.get("resources_limits_memory"),
                    "gpu": values.get("resources_limits_gpu"),
                    "npu": values.get("resources_limits_npu"),
                },
                "requests": {
                    "cpu": values.get("resources_requests_cpu"),
                    "memory": values.get("resources_requests_memory"),
                    "gpu": values.get("resources_requests_gpu"),
                    "npu": values.get("resources_requests_npu"),
                }
            },
            "pod" : {
                "image" : values.get("pod_image"),
                "imageRegistry" : values.get("pod_image_registry"),
                "cpuInstance" : values.get('pod_cpu_instance'),
                "hostName" : values.get("pod_host_name"),
            },
            "labels" : {
                "work_func_type": values.get("work_func_type"),
            },
            "ingress" : {
                "ingressClassName": values.get("ingress_class_name"),
            },
            "deployment" : {
                "deploymentId": values.get("deployment_id"),
                "deploymentWorkerId": values.get("deployment_worker_id"),
                "deploymentName" : values.get("deployment_name")
            },
            # "gpu_cluster_auto" : values.get("gpu_cluster_auto"),
            # "gpu_auto_cluster_case" : json.dumps(values.get("gpu_auto_cluster_case")),
            "gpu_auto_cluster_case" : {
                "server" : values.get("gpu_auto_cluster_case", {}).get("server", 1),
                "gpu_count" : values.get("gpu_auto_cluster_case", {}).get("gpu_count", 0), # node당 gpu 개수
                "total_device_count" : values.get("gpu_auto_cluster_case", {}).get("server", 1) * values.get("gpu_auto_cluster_case", {}).get("gpu_count", 0), # 총 gpu 개수
            },
            "analyzer" : {
                "analyzer_id" : values.get("analyzer_id"),
                "graph_id" : values.get("graph_id"),
                "graph_type" : values.get("graph_type"),
                "data_path" : values.get("data_path"),
                "column" : values.get("column"),
            },
            "db" : {
                "host": settings.JF_DB_HOST,
                "port": settings.JF_DB_PORT,
                "user": settings.JF_DB_USER,
                "pw": settings.JF_DB_PW,
                "name": settings.JF_DB_NAME,
                "charset": settings.JF_DB_CHARSET,
                "collation": settings.JF_DB_COLLATION,
            }
        }
        if settings.LLM_USED:
            res["llm"] = {
                "db" : {
                    "host": settings.JF_DB_HOST,
                    "port": settings.JF_DB_PORT,
                    "user": settings.JF_DB_USER,
                    "pw": settings.JF_DB_PW,
                    "name": settings.JF_LLM_DB_NAME,
                    "charset": settings.JF_DB_CHARSET,
                    "collation": settings.JF_DB_COLLATION,
                },
                "id": values.get("llm_id"),
                "name": values.get("llm_name"),
                "type": values.get("llm_type"),
                # "gpu_count" : values.get("gpu_count"),
                "model" : {
                    "type": values.get("model_type"),
                    "huggingface_id": values.get("model_huggingface_id"),
                    "huggingface_token": values.get("model_huggingface_token"),
                    "allm_name": values.get("model_allm_name"),
                    "allm_commit_name": values.get("model_allm_commit_name"),
                    "huggingface_api_token" : values.get("huggingface_api_token")
                },
                "rag" : {
                    "id": values.get("rag_id"),
                    "chunk_len": values.get("rag_chunk_len"),
                    "embedding_run": values.get("rag_embedding_run"), # reranker에서 필요한 값
                },
                "playground": {
                    "playground_id": values.get("playground_id"),
                    "param_temperature": values.get("param_temperature"),
                    "param_top_p": values.get("param_top_p"),
                    "param_top_k": values.get("param_top_k"),
                    "param_repetition_penalty": values.get("param_repetition_penalty"),
                    "param_max_new_tokens": values.get("param_max_new_tokens"),
                    "prompt_system_message": values.get("prompt_system_message"),
                    "prompt_user_message": values.get("prompt_user_message"),
                    "run_rag": values.get("run_rag"),
                    "run_rag_reranker": values.get("run_rag_reranker"),
                    "run_prompt": values.get("run_prompt"),
                },
            }

        return res

    def __str__(self):
        return self._to_key_value_str(self.__dict__)

    @staticmethod
    def _to_key_value_str(data: Any, parent_key: str = '') -> str:
        """재귀적으로 모든 데이터를 key=value 형식으로 변환"""
        lines = []
        for key, value in data.items():
            if not parent_key:
                full_key = f"--set {key}"
            else:
                full_key = f"{parent_key}.{key}"
                
            if isinstance(value, dict):
                lines.append(YamlToValues._to_key_value_str(value, full_key))
            elif isinstance(value, BaseModel):
                lines.append(YamlToValues._to_key_value_str(value.__dict__, full_key))
            else:
                if value is None or value == "None":
                    continue
                try:
                    value = str(value).replace(",", "\\,").replace("{", '\\{').replace("}", '\\}')
                    lines.append(f'{full_key}="{value}"')
                except:
                    pass
                    # print("values", value)
        return " ".join(lines)

# ============================================================================
# Dict: YamlToValues에서 pydantic 쓸 수 있도록 dict 구조 클래스화
# None 적어줘야지 안쓰는 쪽에서 에러 안남
# ============================================================================
# metadata
class DictMetadataId(BaseModel):
    instanceId: int
    workspaceId: int

class DictMetadataName(BaseModel):
    workspaceName: str
    userName: str
    podName: str
    podBaseName: Optional[str] = None
    helmName: Optional[str] = None

class DictMetadataNamespace(BaseModel):
    workspaceNamespace: str
    systemNamespace: str

class DictResourcesItems(BaseModel):
    cpu: Optional[float] = 0
    memory: Optional[float] = 0
    gpu: Optional[int] = 0
    npu: Optional[int] = 0

class DictMetadata(BaseModel):
    id: DictMetadataId
    name: DictMetadataName
    namespace: DictMetadataNamespace

# resource
class DictResources(BaseModel):
    requests: DictResourcesItems
    limits: DictResourcesItems

# pod
class DictPod(BaseModel):
    image: str
    imageRegistry: str
    cpuInstance: Optional[str] = None
    hostName: Optional[str] = None

# labels
class DictLabels(BaseModel):
    work_func_type: str

# ingress
class DictIngress(BaseModel):
    ingressClassName: Optional[str] = None

# DB
class DictDb(BaseModel):
    host: str
    port: int
    user: str
    pw: str
    name: str
    charset: str
    collation: str

# gpu auto cluster case
class DictGpuAutoClusterCase(BaseModel):
    server: Optional[int] = 1
    gpu_count: Optional[int] = 0 # 노드당 gpu
    total_device_count: Optional[int] = 0 # 전체 gpu

# deployment
class DictDeployment(BaseModel):
    deploymentId: Optional[int] = None
    deploymentWorkerId: Optional[int] = None
    deploymentName: Optional[str] = None

# analyzer
class DictAnalyzer(BaseModel):
    analyzer_id: Optional[int] = None
    graph_id: Optional[int] = None
    graph_type: Optional[str] = None
    data_path: Optional[str] = None
    column: Optional[str] = None

# LLM
class DictLlmDb(BaseModel):
    host: str
    port: int
    user: str
    pw: str
    name: str
    charset: str
    collation: str

class DictPlayground(BaseModel):
    playground_id: Optional[int] = None
    param_temperature: Optional[float] = None
    param_top_p: Optional[float] = None
    param_top_k: Optional[int] = None
    param_repetition_penalty: Optional[float] = None
    param_max_new_tokens: Optional[int] = None
    prompt_system_message: Optional[str] = None
    prompt_user_message: Optional[str] = None
    run_rag: Optional[bool] = None
    run_rag_reranker: Optional[bool] = None
    run_prompt: Optional[bool] = None

    class Config:
        protected_namespaces = () 

class DictRag(BaseModel):
    type: Optional[str] = None # embedding, reranker
    deployment_type: Optional[str] = None # retrieval, test
    id: Optional[int] = None
    chunk_len: Optional[int] = None
    embedding_run: Optional[int] = None

class DictModel(BaseModel):
    type: Optional[str] = None
    huggingface_id: Optional[str] = None
    huggingface_token: Optional[str] = None
    allm_name: Optional[str] = None
    allm_commit_name: Optional[str] = None
    huggingface_api_token: Optional[str] = settings.HUGGINGFACE_TOKEN

class DictLlm(BaseModel):
    db: Optional[DictLlmDb] = None
    id: Optional[int] = None
    name: Optional[str] = None
    type: Optional[str] = None
    model: Optional[DictModel] = None
    playground: Optional[DictPlayground] = None
    rag: Optional[DictRag] = None
    # gpu_count: Optional[int] = 0

    class Config:
        protected_namespaces = () 


# ============================================================================
# 2. pod_info -> helm set values (pod_info를 values command로 변경할때 사용)
# ============================================================================

class YamlToSetValuesAnalyzer(BaseConfig):
    metadata: DictMetadata
    resources: DictResources
    pod: DictPod
    labels: DictLabels
    analyzer: Optional[DictAnalyzer] = None
    db: Optional[DictDb] = None

class YamlToValues(BaseConfig):
    metadata: DictMetadata
    resources: DictResources
    pod: DictPod
    labels: DictLabels
    ingress: Optional[DictIngress] = None
    deployment: Optional[DictDeployment] = None
    llm: Optional[DictLlm] = None
    gpu_auto_cluster_case: Optional[DictGpuAutoClusterCase] = None

    # BaseConfig 대체