from pydantic import BaseModel, Field
from typing import Optional, List, Union
from utils import TYPE


class URLRequest(BaseModel):
    original_url: str

class FineTuningConfig(BaseModel):
    fine_tuning_type: str = Field(default=TYPE.FINE_TUNING_BASIC, description=f'find tuning types ex) {TYPE.FINE_TUNING_BASIC}, {TYPE.FINE_TUNING_ADVANCED}')
    config_file_name: str = Field(default=None, description=f'Required only if the fine tuning type is {TYPE.FINE_TUNING_ADVANCED}.')
    num_train_epochs : float = Field(default=3.0, description='Total number of training epochs to perform')
    gradient_accumulation_steps : Optional[int] = Field(default=1, description='Number of updates steps to accumulate before performing a backward/update pass.')
    cutoff_length : int = Field(default=512, description='')
    learning_rate : float = Field(default=5e-5, description='The initial learning rate for AdamW.')
    warmup_steps : int = Field(default=0, description='Linear warmup over warmup_steps.')
    load_in_8bit : int = Field(default=0, description='')
    used_lora : int = Field(default=1, description='used lora')
    used_jonathan_accelerator : int = Field(default=0, description='used jonathan accelerator')
    precision : Optional[str] = Field(default="auto", description='학습 정밀도: "auto" | "fp16" | "bf16"')
    auto_target_modules : Optional[int] = Field(default=1, description='LoRA 타겟 모듈 자동 감지: 1=auto(all-linear), 0=static map')
    dataset_format : Optional[str] = Field(default="auto", description='데이터셋 형식: "auto" | "text" | "chat" | "instruction"')
    zero_stage : Optional[int] = Field(default=1, description='DeepSpeed ZeRO stage: 1, 2, 3')
    eval_steps : Optional[int] = Field(default=500, ge=1, description='평가(eval/loss) 실행 간격(step). ⑩ 체크포인트 점 마킹과 일치.')
    save_steps : Optional[int] = Field(default=500, ge=1, description='체크포인트 저장 간격(step). ⑩ 점 마킹의 후보 step.')
    # ── 내부 VLM 2-stage 파인튜닝(LLaVA류, ETRI 요구: SDS 외 별도 내부 VLM FT 로직) ──
    # vlm=1 이면 스케줄러가 텍스트 FT(llm_model_fine_tuning.py) 대신 VLM 2-stage 스크립트
    # (llm_model_vlm_fine_tuning.py)를 선택. used_lora 가 stage2 방식(1=LoRA, 0=full)을 결정.
    vlm : Optional[int] = Field(default=0, description='내부 VLM 2-stage 파인튜닝 여부(0/1). 베이스 모델=VLM, 데이터셋=이미지+텍스트.')
    vlm_stage1_epochs : Optional[float] = Field(default=1.0, ge=0, description='VLM stage1(projector 정렬) epoch 수. stage2(LM)는 num_train_epochs.')
    # VLM 하이퍼파라미터 — 엔진(llm_model_vlm_fine_tuning.py)이 --key 로 수신. vlm_ 프리픽스라 텍스트 FT 무영향.
    vlm_stage1_lr : Optional[float] = Field(default=None, description='VLM stage1(projector) LR. 미지정 시 learning_rate 공용.')
    vlm_batch_size : Optional[int] = Field(default=1, ge=1, description='VLM per-device 배치 크기(이미지 메모리 주의).')
    vlm_weight_decay : Optional[float] = Field(default=0.0, ge=0, description='VLM stage2 weight decay.')
    vlm_lora_r : Optional[int] = Field(default=8, ge=1, description='VLM stage2 LoRA rank.')
    vlm_lora_alpha : Optional[int] = Field(default=16, ge=1, description='VLM stage2 LoRA alpha.')
    vlm_lora_dropout : Optional[float] = Field(default=0.05, ge=0, description='VLM stage2 LoRA dropout.')
    vlm_lora_target_modules : Optional[str] = Field(default=None, description='VLM stage2 LoRA 타겟 모듈(콤마구분). 미지정 시 q,k,v,o_proj.')
    vlm_max_samples : Optional[int] = Field(default=0, ge=0, description='VLM 학습 샘플 수 제한(0=전체). 대용량 데이터셋(예: CC3M 595K) 데모/스모크용.')
    vlm_image_folder : Optional[str] = Field(default=None, description='VLM 이미지 루트(데이터셋 디렉터리 기준 상대 경로). 미지정 시 직속→images/ 자동 폴백(표준 HF VLM 데이터셋 무수정 소비).')

class FineTuningPodInfo(BaseModel):
    model_id : int
    model_name : str
    commit_id: int
    commit_name : str
    workspace_id : int
    workspace_name : str
    model_dataset_id : int
    instance_count : int = 1
    image_name : str
    owner_id : int
    gpu_count : int = 0
    gpu_cluster_auto : bool = False
    gpu_auto_cluster_case : dict = {}
    gpu_select : List[dict] = []
    instance_id : int
    resource_type : str
    pod_type : str
    pod_per_gpu : Optional[int] = 1 # 수동선택을 위한 값
    fine_tuning_config: FineTuningConfig = FineTuningConfig()
    class Config:
        protected_namespaces = ()





class PostFineTuningRun(BaseModel):
    model_id : int = Field(default=None, description='llmops model id')
    # TODO dataset 추가
    model_dataset_id : int = Field(default=None, description='llmops model dataset id')
    fine_tuning_config : FineTuningConfig = Field(default=FineTuningConfig(), description=f'find tuning config')
    # TODO instance 설정 추가
    instance_id : int = Field(description='jonathan instance id')
    instance_count : int = Field(description='jonathan instance count')
    gpu_count : int = Field(description='fine tuning used gpu count')
    class Config:
        protected_namespaces = ()
    
class PostHuggingface(BaseModel):
    model_name : str = None
    huggingface_token : str = None
    private : int = 0
    # 검색 대상 — 'text'(텍스트 LLM, text-generation) | 'vision'(비전 인코더, CLIP/SigLIP).
    # 멀티모달(VLM) 비전 슬롯은 'vision', 그 외(단일/LLM 슬롯)는 기본 'text'.
    model_kind : str = 'text'

class PostModel(BaseModel):
    workspace_id : int = Field(description='llmops workspace id')
    create_user_id : int = Field(default=0,description='llmops user id')
    access : int = Field(default=0, description='llmops model access')
    users_id : List[int] = []
    model_name : str = Field(description='llmops model name')
    huggingface_model_id : Optional[str] = Field(default=None, description='hugging face model id')
    huggingface_token : Optional[str] = Field(default=None, description='hugging face access token')
    private: int = Field(default=0, description='llmops model commit id')
    commit_model_id : Optional[int] = Field(default=None, description='llmops model commit id')
    description : str = Field(default=None, description='llmops model description')
    # 외부 협력기관 컨테이너 학습 모델 (eva-vlm 등).
    # training_type='external' 일 때만 external_manifest_* 가 의미 있고,
    # 그 경우 huggingface/commit 경로는 모두 무시된다.
    training_type : Optional[str] = Field(default='internal', description="'internal' | 'external'")
    external_manifest_name : Optional[str] = Field(default=None, description='manifest name (external only)')
    external_manifest_version : Optional[str] = Field(default=None, description='manifest version (external only)')
    # domain(3.5) — SDS/SDM/SDF. 신규 모델 생성 UI 는 manifest 대신 domain 만 보내고,
    # create_model 이 domain=SDS → training_type='external' + 고정 manifest 로 해석한다.
    # SDM/SDF 는 현재 비활성(create_model 에서 거부).
    domain : Optional[str] = Field(default=None, max_length=16, pattern=r'^[A-Za-z]{2,8}$', description="'SDS' | 'SDM' | 'SDF' (SDM/SDF disabled)")
    # 멀티모달(VLM) — 비전 인코더 + LLM 두 HF 모델. load_type='multimodal' 이면
    # huggingface_model_id='{vision},{llm}' 콤마결합. composite VLM 파인튜닝 진입(생성은 메타행).
    load_type : Optional[str] = Field(default=None, max_length=16, pattern=r'^[a-z]{2,16}$', description="None(단일) | 'multimodal'(VLM)")
    class Config:
        protected_namespaces = ()
        
class IngestCheckpointBody(BaseModel):
    # 3.6 Custom 모델 — 운영자 전용 by-reference 체크포인트 ingestion.
    # 사용자 파일 업로드 아님(기관이 Nexus/HF 에 올린 걸 레퍼런스로 당겨옴).
    workspace_id : int = Field(description='workspace id')
    target_manifest_name : str = Field(description='bound runtime manifest (e.g. eva-vlm-infer)')
    target_manifest_version : str = Field(description='runtime manifest version')
    ref_type : str = Field(default='hf', description="'hf' | 'url'")
    ref : str = Field(description='HF repo id or download URL')
    token : Optional[str] = Field(default=None, description='private registry/HF token (pull only, not stored)')
    commit_name : Optional[str] = Field(default=None, description='commit name (slug); auto if omitted')
    description : Optional[str] = Field(default=None, description='commit message / note')
    metadata : Optional[dict] = Field(default=None, description='provenance metadata')
    class Config:
        protected_namespaces = ()

class PutModel(BaseModel):
    model_id: int = Field(description='llmops model id')
    description : str = Field(default=None, description='llmops model description')
    create_user_id : int = Field(default=0,description='llmops user id')
    access : int = Field(default=0, description='llmops model access')
    user_list : List[int] = Field(default=[], description='llmops model user list')
    class Config:
        protected_namespaces = ()

class PostModelCommit(BaseModel):
    commit_message : str = Field(default="", description='llmops commit message')
    commit_name : str = Field(description='llmops commit name')
    model_id : int = Field(description='llmops model id')
    class Config:
        protected_namespaces = ()
    

class GpuClusterInfoModel(BaseModel):
    model_id : int = Field(description='llmops model id')
    instance_id : int = Field(description='jonathan instance id')
    gpu_count : int = Field(description='used gpu count')
    gpu_select : List[dict] = Field(default = [] , description='user select gpu model')
    class Config:
        protected_namespaces = ()
    
    
class AddDataset(BaseModel):
    dataset_id : int
    model_id : int
    training_data_path : str
    class Config:
        protected_namespaces = ()