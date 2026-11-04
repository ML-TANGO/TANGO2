from pydantic import BaseModel, Field
from typing import Optional, List, Union, Any
from utils import TYPE
from enum import Enum
from typing import Literal


class Response(BaseModel):
    status : int = 1
    message : str = ""
    result : Any = None
    

class PipelineTaskPosition(BaseModel):
    x_index : int
    y_index : int
    x_position : int

class ResponseTaskInfo(BaseModel):
    id: int
    task_item_id: Optional[int] = None
    task_type: str = ""
    task_item_type : str = ""
    task_name: str = ""
    run_code: Optional[str] = None
    project_training_type : Optional[str] = None
    image_name: Optional[str] =None
    gpu_count: int = 0
    parameter: Optional[list] = []
    built_in_params : Optional[list] = []
    successors: List[str] =[]
    predecessors: List[str] = []
    coordinate : PipelineTaskPosition
    status : dict 
    task_item_tool_status : int = Field(default=0, description="project, data preprocessing의 경우만 사용")

class ResponseTasks(BaseModel):
    preprocessing_task : List[ResponseTaskInfo] = []
    project_task: List[ResponseTaskInfo] = []
    deployment_task: List[ResponseTaskInfo] = []
    generation_task: List[ResponseTaskInfo] = []  # 생성형 데이터 파이프라인 노드 (WBS 1.2)
    finetuning_task: List[ResponseTaskInfo] = []   # GenAI 통합 파이프라인 LLM 파인튜닝
    quantize_task: List[ResponseTaskInfo] = []     # 양자화·포팅 (SP-4)
    llm_deploy_task: List[ResponseTaskInfo] = []   # LLM 배포 (cluster/edge)
    prompt_gen_task: List[ResponseTaskInfo] = []   # SP-7 LLM1 프롬프트 생성기
    data_gen_task: List[ResponseTaskInfo] = []     # SP-7 LLM2 데이터 생성기
    algo_call_task: List[ResponseTaskInfo] = []    # SP-7 LLM3 알고리즘 호출자

class RetrainingConfig(BaseModel):
    type : Optional[str] #= TYPE.RETRAINING_DATA_TYPE
    unit : Optional[str] #= TYPE.RETRAINING_DATA_UNITS[0]
    value : Optional[int] #= 1

class PipelineInfo(BaseModel):
    id: int
    name: str
    type: str = "advanced"
    built_in_type : Optional[str] = None
    built_in_sub_type : Optional[str] = None
    built_in_specification : Optional[str] = None
    built_in_data_type : Optional[str] = None
    built_in_preprocessing_list : Optional[list] = None
    access: int
    create_datetime: str
    owner_name: str
    create_user_name: str
    description: str
    create_datetime: str
    update_datetime: str

class DatasetInfo(BaseModel):
    id : Optional[int] = None
    name : Optional[str] = None
    description : Optional[str] = None
    create_user_name : Optional[str] = None
    create_datetime : Optional[str] = None 



class PipelineInfoDetail(BaseModel):
    pipeline_info : Optional[PipelineInfo]   
    dataset_info : Optional[DatasetInfo]
    restart_setting : Optional[RetrainingConfig]

class PipelineInfoResponse(BaseModel):
    status : int = 1
    message : str = ""
    result : Optional[PipelineInfoDetail] #= PipelineInfoDetail()

class Pipeline(BaseModel):
    tasks: ResponseTasks= ResponseTasks()
    pipeline_name: str =""
    create_datetime: str = ""
    increase_size: int = 0
    owner_name: str =""
    create_user_name: str =""
    description: str ="" 
    retraining_config : Optional[RetrainingConfig] #= RetrainingConfig()
    dataset_info : dict = {}
    retraining_wait_start_time : Optional[str] = None
    retraining_count : int = 0
    start_datetime : str = ""
    end_datetime : str = ""
    status : str = TYPE.KUBE_POD_STATUS_DONE
    
    
class Pipelines(BaseModel):
    id : int = None
    type: str = "advanced"
    name : str = ""
    description : str = ""
    bookmark: int = 0
    access : int = 1
    create_datetime : str = ""
    start_datetime : Optional[str]
    owner_name : str = ""
    private_user_list : Optional[List[dict]] = []
    retraining_wait_start_time : Optional[str]
    retraining_count : Optional[int]
    retraining_type : Optional[str]
    retraining_unit : Optional[str]
    retraining_value : Optional[int]
    end_datetime : Optional[str]


    
class PipelineResponse(Response):
    result : Optional[Pipeline] # = Pipeline()

class PipelinesResponse(Response):
    status : int = 1
    result : List[Pipelines]  = []

class CreatePipelineTask(BaseModel):
    pipeline_id : int
    task_item_id : int
    task_type: Literal["project", "deployment", "preprocessing", "generation", "finetuning", "quantize", "llm_deploy", "prompt_gen", "data_gen", "algo_call"]
    task_item_type: Literal["advanced", "built-in", "huggingface"]
    dataset_data_path: Optional[str] = None
    gpu_auto_select : Optional[dict] = None
    project_training_type: Optional[str] = None
    run_code : Optional[str] = None
    parameter : Optional[str] = None
    built_in_params : Optional[dict] = {}
    image_id : Optional[str] = None
    gpu_count : int = Field(default=0, description='')
    x_index : int
    y_index : int
    
class UpdatePipelineTaskPosition(BaseModel):
    x_position : int
    x_index: int
    y_index: int
    task_id: int

class CreatePipeline(BaseModel):
    name : str
    type: str = "advanced"
    built_in_type: Optional[str] = None
    built_in_sub_type: Optional[str] = None
    built_in_specification : Optional[str] = None
    built_in_data_type: Optional[str] = None
    built_in_preprocessing_list : Optional[list] = None
    description: str
    access : int
    owner_id : int
    workspace_id : int
    users_id: List[int] = []

class Task(BaseModel):
    id : int
    predecessors : List[str] = []
    successors : List[str] = []
    
class UpdateTaskGraph(BaseModel):
    pipeline_id : int
    predecessor_task : Task = Field(description='선행 task의 업데이트 정보')
    successor_task : Task = Field(description='후행 task의 업데이트 정보')

class UpdateRetrainingSetting(BaseModel):
    pipeline_id : int
    retraining_type : Literal["data", "time"] = Field(default= "data")
    retraining_unit : Literal["TB","GB", "MB", "KB", "hours", "minutes"] = Field(default="TB", description="type data : 'TB','GB', 'MB', 'KB' | type time : 'hours', 'minutes'")
    retraining_value : int 
    
    
class PipelineHistory(BaseModel):
    id : int
    pipeline_id : int
    increase_dataset_size : int = 0
    retraining_count : int = 0
    end_status : Optional[str] = None
    start_user_name : str
    start_datetime : str
    end_datetime : Optional[str] = None
    is_retraining_setting : int = 0
    
    
class PipelineHistoryResponse(BaseModel):
    status : int = 1
    message : str = ""
    result : List[PipelineHistory] = []
    
    
class PipelineUpdate(BaseModel):
    pipeline_id : int
    description : Optional[str] = None
    access : int
    owner_id : int
    users_id : List[int] = []
