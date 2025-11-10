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