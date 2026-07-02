from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import datetime
from utils.TYPE import DEPLOYMENT_TYPE


######################REQUEST##########################
class CreatePlaygroundInput(BaseModel):
    workspace_id: int
    name: str = Field(description="생성이름", examples=["Foo"])
    description: Optional[str] = None
    access: int = Field(default=1, description='Access Type : 0 = private, 1 = public')
    owner_id: int = Field(default=None, description='Users Id' )
    users_id: Optional[list] = Field(default=list(), description='Users Id' )

class UpdatePlaygroundInput(BaseModel):
    playground_id: int
    description: Optional[str] = None
    access: int = Field(description='Access Type : 0 = private, 1 = public')
    owner_id: int = Field(description='Owner Id' )
    users_id: Optional[list] = Field(default=list(), description='Users Id' )

class UpdatePlaygroundDescriptionInput(BaseModel):
    playground_id: int
    description: Optional[str] = None

class UpdatePlaygroundOptionsInput(BaseModel):
    playground_id: int
    # togle
    is_rag: bool = Field(description="토글 true or false")
    is_prompt: bool = Field(description="토글 true or false")
    accelerator: Optional[bool] = Field(default=False, description="jonathan accelerator")
    # model
    model_type: Optional[str] = Field(default=None, description="모델: huggingface or commit")
    model_huggingface_id: Optional[str] = Field(default=None, description="모델: huggingface 선택시 모델 id")
    model_huggingface_token: Optional[str] = Field(default=None, description="모델: huggingface 선택 -> private 모델 선택 -> token")
    model_allm_id: Optional[str] = Field(default=None, description="모델: allm 모델 선택시 id")
    model_allm_commit_id: Optional[str] = Field(default=None, description="모델: commit 선택시 model commit id")
    model_info: Optional[dict] = Field(default=None, description="모델 정보 - 설명, 커밋버전, 접근권한, 생성일시, 최근업데이트일시")
    # model parameter
    model_temperature: Optional[float] = Field(default=None, description="모델 파라미터: temperature")
    model_top_p: Optional[float] = Field(default=None, description="모델 파라미터: top_p")
    model_top_k: Optional[int] = Field(default=None, description="모델 파라미터: top_k")
    model_repetition_penalty:  Optional[float] = Field(default=None, description="모델 파라미터: repetition_penalty")
    model_max_new_tokens:  Optional[float] = Field(default=None, description="모델 파라미터: max_new_tokens")
    # rag
    rag_id:  Optional[int] = Field(default=None, description="rag: rag id")
    rag_chunk_max: Optional[int] = Field(default=0, description="rag: 최대 청크 수")
    # prompt
    prompt_id: Optional[str] = Field(default=None, description="prompt: prompt id")
    prompt_name: Optional[str] = Field(default=None, description="prompt: prompt name")
    prompt_commit_name: Optional[str] = Field(default=None, description="rag: prompt commit name")
    prompt_system_message: Optional[str] = Field(default=None, description="prompt: system message")
    prompt_user_message: Optional[str] = Field(default=None, description="prompt: user message")

    class Config:
        protected_namespaces = () 

class UpdatePlaygroundModelInput(BaseModel):
    """
    /usr/local/lib/python3.11/site-packages/pydantic/_internal/_fields.py:128: UserWarning: Field "model_type" has conflict with protected namespace "model_".
    You may be able to resolve this warning by setting `model_config['protected_namespaces'] = ()`.
    """
    playground_id: int

class UpdatePlaygroundRagInput(BaseModel):
    playground_id: int

class UpdatePlaygroundPromptInput(BaseModel):
    playground_id: int

class PosHuggingfaceModelInput(BaseModel):
    model_name : str = None
    huggingface_token : str = None
    private : int = 0

    class Config:
        protected_namespaces = () 
    

# 실행 관련 기능 ==========================================================
# - 배포, 중지, 테스트 실행, 테스트 결과 
class RunPlaygroundInput(BaseModel):
    playground_id:int
    # init_deployment: bool = Field(description="최초 배포일경우 False, 이미 배포되어 재배포하는 경우 True")
    # playground_deployment_type: Optional[str] = Field(default="new", description="(init_deployment가 False) and (신규 프로젝트일경우 new, 기존 프로젝트 선택인 경우 old)")
    # 신규 프로젝트 선택
    # new_deployment_name: Optional[str] = None
    # new_deployment_description: Optional[str] = None
    # 기존 프로젝트 선택
    # old_deployment_id: Optional[int] = None

    # 모델 자원할당
    model_instance_id: Optional[int] = Field(default=0, description="모델 - 자원할당 - 인스턴스id")
    model_instance_count: Optional[int] = Field(default=0, description="모델 - 자원할당 - 인스턴스 할당 개수")
    model_gpu_count: Optional[int] = Field(default=0, description="모델 - 자원할당 - gpu 할당 개수")
    
    # 임베딩 자원할당
    embedding_instance_id: Optional[int] = Field(default=0, description="임베딩 - 자원할당 - 인스턴스id")
    embedding_instance_count: Optional[int] = Field(default=0, description="임베딩 - 자원할당 - 인스턴스 할당 개수")
    embedding_gpu_count: Optional[int] = Field(default=0, description="임베딩 - 자원할당 - gpu 할당 개수")
    
    # 리랭커 자원할당
    reranker_instance_id: Optional[int] = Field(default=0, description="리랭커 - 자원할당 - 인스턴스id")
    reranker_instance_count: Optional[int] = Field(default=0, description="리랭커 - 자원할당 - 인스턴스 할당 개수")
    reranker_gpu_count: Optional[int] = Field(default=0, description="리랭커 - 자원할당 - gpu 할당 개수")
    
    # 재시작
    restart: Optional[bool] = Field(default=False, description="재시작 True, 재시작 아님 False")

    class Config:
        protected_namespaces = () 
    
class PipelineDeployInput(BaseModel):
    """파이프라인(통합 파이프라인 llm_deploy 노드)의 s2s 클러스터 배포 요청(spec #4).
    create→옵션(모델 바인딩)→start 를 원자적으로 수행. FE 수동 배포와 동일 경로 재사용."""
    workspace_id: int
    model_id: int = Field(description="배포할 학습완료 모델(allm) id")
    user_name: str = Field(description="배포 소유자(파이프라인 실행 사용자, OWNER_NAME)")
    model_instance_id: int = Field(description="모델 자원 인스턴스 id")
    model_commit_id: Optional[int] = Field(default=None, description="배포할 commit id(생략 시 미지정)")
    name: Optional[str] = Field(default=None, description="배포명(생략 시 자동)")
    model_instance_count: Optional[int] = Field(default=1, description="인스턴스 할당 개수")
    model_gpu_count: Optional[int] = Field(default=1, description="GPU 할당 개수")

    class Config:
        protected_namespaces = ()

class CreateDualSessionInput(BaseModel):
    """이중모델 추론 세션 생성(WBS 추론 4.2) — 프롬프트생성 모델(LLM1) + 추론 모델(LLM2)을
    한 세션으로 동시 배포(co-provision). 각 모델은 기존 배포 경로(pipeline_deploy)로 올라가고,
    추론 playground(부모)-프롬프트생성 playground(자식)를 JSON 링크한다.
    자원 블록은 두 모델에 각각 적용(a안)."""
    workspace_id: int
    name: str = Field(min_length=1, max_length=64, description="세션 이름")
    prompt_gen_model_id: int = Field(description="프롬프트 생성 모델(LLM1, allm) id")
    inference_model_id: int = Field(description="추론 모델(LLM2, allm) id")
    model_instance_id: int = Field(description="자원 인스턴스 id (두 모델 공통 적용)")
    prompt_gen_commit_id: Optional[int] = Field(default=None, description="LLM1 배포 commit id(생략 시 latest)")
    inference_commit_id: Optional[int] = Field(default=None, description="LLM2 배포 commit id(생략 시 latest)")
    # instance/gpu 상한 = 폭주 입력 backstop(실제 상한은 워크스페이스 쿼터가 다운스트림 강제). gpu 0=CPU 허용.
    model_instance_count: Optional[int] = Field(default=1, ge=1, le=16, description="인스턴스 할당 개수(모델당)")
    model_gpu_count: Optional[int] = Field(default=1, ge=0, le=16, description="GPU 할당 개수(모델당)")

    class Config:
        protected_namespaces = ()

class DualBatchInput(BaseModel):
    """이중모델 데이터셋 일괄 추론(WBS 4.3 배치). N 샘플에 LLM1→LLM2 체인 실행 + 인-프로세스
    BLEU/ROUGE 채점(reference 있을 때). 동기 배치라 sample_count 상한 10."""
    playground_id: int
    test_dataset_id: int
    test_dataset_filename: str = Field(description="데이터셋 파일명(데이터셋 디렉터리 하위 상대경로)")
    sample_count: Optional[int] = Field(default=5, ge=1, le=10, description="샘플 수(동기 배치 상한 10)")
    metrics: Optional[List[str]] = Field(default=None, description="채점 메트릭 [bleu, rouge] (reference 필요)")
    session_id: Optional[str] = None
    system_prompt: Optional[str] = Field(default=None, max_length=4000, description="LLM1 시스템 지침(예시기반 최적화)")
    dual_examples: Optional[List[Dict[str, Any]]] = Field(default=None, max_length=10, description="LLM1 few-shot 예시")
    prompt_gen_playground_id: Optional[int] = Field(default=None, description="미지정 시 세션 링크에서 서버 파생")

    class Config:
        protected_namespaces = ()

class PlaygroundIdInput(BaseModel):
    playground_id: int



class PlaygroundTestInput(BaseModel):
    playground_id: int
    test_type: Optional[str] = None
    test_dataset_id: Optional[int] = None
    test_dataset_filename: Optional[str] = None
    test_question: Optional[str] = None
    session_id: Optional[str] = None
    network_load: Optional[int] = Field(default=0, description="없음 0, 저 1, 중 2, 고3")
    external_payload: Optional[dict] = Field(
        default=None,
        description=(
            "External partner container 호출 시 /run body 의 params 로 그대로 전달. "
            "image_base64, ais_rows 등 partner 전용 필드. None 이면 internal 분기."
        ),
    )
    prompt_gen_playground_id: Optional[int] = Field(
        default=None,
        description=(
            "이중모델 추론(SP-7 슬라이스). 지정 시 이 playground(LLM1, 프롬프트 생성기)가 "
            "test_question 을 최적 프롬프트로 재작성 → 현 playground(LLM2)가 그 프롬프트로 추론. "
            "test_type=question 에서만 동작. (이중 세션은 서버가 자동 파생)"
        ),
    )
    system_prompt: Optional[str] = Field(
        default=None,
        max_length=4000,
        description="이중모델: LLM1 에 줄 시스템 지침(예시기반 최적화, WBS 4.2).",
    )
    dual_examples: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        max_length=10,
        description="이중모델: LLM1 few-shot 예시 [{query, answer}, ...] (예시기반 최적화, WBS 4.2).",
    )


######################KAFKA##########################

class DeploymentResourcesDetail(BaseModel):
    cpu: Optional[float] = 0.0
    memory: Optional[float] = 0.0
    gpu: Optional[int] = 0
    npu: Optional[int] = 0

class DeploymentResources(BaseModel):
    limits: Optional[DeploymentResourcesDetail] = None
    requests: Optional[DeploymentResourcesDetail] = None

class DeploymentLlm(BaseModel):
    playground_id: int
    run_rag: Optional[bool] = ""
    run_prompt: Optional[bool] = ""
    model_type: Optional[str] = ""
    model_huggingface_id: Optional[str] = ""
    model_huggingface_token: Optional[str] = ""
    model_name: Optional[str] = ""
    model_commit_name: Optional[str] = ""
    prompt_system_message: Optional[str] = ""
    prompt_user_message: Optional[str] = ""
    param_temperature: Optional[float] = ""
    param_top_p: Optional[float] = ""
    param_top_k: Optional[float] = ""
    param_repetition_penalty: Optional[float] = ""
    param_max_new_tokens: Optional[float] = ""

    class Config:
        protected_namespaces = ()

class DeploymentLlmDb(BaseModel):
    jf_llm_db_host: Optional[str] = ""
    jf_llm_db_port: Optional[int] = ""
    jf_llm_db_user: Optional[str] = ""
    jf_llm_db_pw: Optional[str] = ""
    jf_llm_db_name: Optional[str] = ""
    jf_llm_db_charset: Optional[str] = ""
    jf_llm_db_collation: Optional[str] = ""

class DeploymentInfo(BaseModel):
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
    deployment_worker_id: Optional[int] = None
    project_name: Optional[str] = None
    # -------------------------
    pod_name: Optional[str] = None
    pod_base_name: Optional[str] = None
    pod_image: str
    run_code: Optional[str] = None
    # -------------------------
    instance_id: int
    resource_group_id : Optional[int] = None
    gpu_count: Optional[int] = 0
    gpu_cluster_auto: Optional[bool] = False
    gpu_auto_cluster_case: Optional[dict] = dict()
    gpu_select: Optional[list] = []
    resources: DeploymentResources
    deployment_llm: Optional[DeploymentLlm] = None
    deployment_llm_db: Optional[DeploymentLlmDb] = None