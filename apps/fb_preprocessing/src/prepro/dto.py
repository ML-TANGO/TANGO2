from pydantic import BaseModel, Field
from typing import Optional, List
import utils.HELP as HELP
from utils.TYPE import PREPROCESSING_TYPES, PREPROCESSING_TYPE, PREPROCESSING_BUILT_IN_DATA_TYPES

class PreprocessingModelGET(BaseModel):
    search_key: Optional[str] = Field(default=None, description='training Search Key "name" or "user_name"... ')
    size: Optional[int] = Field(default=None, description='training List Item Size')
    page: Optional[int] = Field(default=None, description='training Page Number')
    search_value: Optional[str] = Field(default=None, description='training Search value')
    workspace_id: Optional[int] = Field(default=None, description='choosen workspace value')
    sort: Optional[str] = Field(default=None, description='sort value')
    preprocessing_type: Optional[str] = Field(default=None, description='training type value')
    
class PreprocessingModelDelete(BaseModel):
    id_list : Optional[list] = Field(default=[], description='preprocessing id')

class PreprocessingToolModelDelete(BaseModel):
    preprocessing_tool_id : int
class PreprocessingJobModelDelete(BaseModel):
    preprocessing_job_id : int
class PreprocessingJobModelAllDelete(BaseModel):
    preprocessing_id : int

class PreprocessingModelPOST(BaseModel):
    preprocessing_name: str = Field(description='preprocessing Name' )
    preprocessing_type: str = Field(description='preprocessing Type : {}'.format(PREPROCESSING_TYPES) )
    workspace_id: int = Field(description='training Location')
    owner_id: int = Field(description='Owner Id' )
    built_in_data_type : Optional[str] = Field(default=None, description='built in type : {}'.format(PREPROCESSING_BUILT_IN_DATA_TYPES) )
    built_in_data_tf : Optional[str] = Field(default=None )
    instance_id: Optional[int] = Field(description="할당한 instance id")
    instance_allocate: Optional[int] = Field(description="할당한 instance id")
    access: int = Field(description='Access')
    description: Optional[str] = Field(default="", description="description 200 len")
    user_list: Optional[list] = Field(default=[], description="private user list")

class PreprocessingModelPUT(BaseModel):
    preprocessing_id: int = Field(description='preprocessing id')
    owner_id : int = Field(description='owner user id')
    user_list: Optional[list] = Field(default=[], description='Users Id - private 생성 시 사용함')
    instance_id: Optional[int] = Field(description="할당한 instance id")
    instance_allocate: Optional[int] = Field(description="할당한 instance id")
    access: int = Field(description='Access')
    description: Optional[str] = Field(default="", description="description 200 len")
    
class FormatConvertEnsureModel(BaseModel):
    """데이터셋 상세 '포맷 변환' 전용 built-in 프로젝트 find-or-create 요청."""
    workspace_id: int = Field(description='workspace id')

class DataPipelineEnsureModel(BaseModel):
    """데이터 파이프라인 전용 built-in 프로젝트 find-or-create 요청.

    파이프라인당 프로젝트 하나 — dp_dataset_id 가 그 파이프라인(llm_dp_dataset)을 가리킨다.
    """
    workspace_id: int = Field(description='workspace id')
    dp_dataset_id: int = Field(description='llm_dp_dataset id (파이프라인)')

class JOBCRUDModel(BaseModel):
    search_key: Optional[str] = Field(default=None, description='training JOB Search Key "name" or "user_name"... ')
    size: Optional[int] = Field(default=None, description='training JOB List Item Size')
    page: Optional[int] = Field(default=None, description='training JOB Page Number')
    search_value: Optional[str] = Field(default=None, description='training JOB Search value')
    preprocessing_id: Optional[int] = Field(description='choosen preprocessing_id value')
    sort: Optional[str] = Field(default=None, description='sort value .. start_datetime, end_datatime')

# class JOBBookmarkModel(BaseModel):
#     preprocessing_id: int = Field(description='Preprocessing ID')

class ToolControlModel(BaseModel):
    preprocessing_tool_id: int = Field(description="tool id")
    dataset_id : int = Field(default=None, description="dataset id")
    action: str = Field(description="action = 'on' | 'off'")
    gpu_count : int = Field(default=0, description="gpu 개수")
    gpu_cluster_auto : bool = Field(default=False, description="gpu cluster 자동 설정인 경우 True, 수동 설정인 경우 False")
    gpu_select : list = Field(default=[], description="gpu cluster 수동 설정일 경우 선택한 노드 gpu 리스트")
    gpu_auto_select : dict = {}
    gpu_cluster_case_old : List[dict] = []
    docker_image_id : int = None
    gpu_cluster_list_old : dict = {}
    pod_per_gpu : int = 0

class GpuClusterInfoModel(BaseModel):
    preprocessing_id : int
    gpu_count : int
    gpu_select : List[dict] = []  

# class JOBFileBrowserModel(BaseModel):
#     training_tool_id: int = Field(description="training_tool_id")
#     protocol: str = Field(description="protocol")

# class JOBDownloadModel(BaseModel):
#     training_id: int = Field(description='Job ID')

# class JobLogModel(BaseModel):
#     job_id: int = Field(description='Job ID')

# class JOBDeleteModel(BaseModel):
#     preprocessing_id: Optional[int] = Field(default=None, description="JOB ID - 전체 삭제")
#     training_id_list: Optional[list] = Field(default=None, description="JOB id list - 지정 삭제 [3,6,8,10]")

class JOBPipelinePostModel(BaseModel):
    preprocessing_id : int
    get_job_id : int = 0
    image_id : Optional[int] = None
    job_name : str
    run_code: Optional[str] = None
    parameter: str = ""
    gpu_count: int = 0
    gpu_cluster_auto : bool = False
    gpu_select : List[dict] = []
    gpu_auto_select : dict = {}
    gpu_cluster_case_old : List[dict] = []
    gpu_cluster_list_old : dict = {}
    pod_per_gpu : int = 0
    dataset_id : int
    dataset_data_path : Optional[str] = None
    built_in_param : Optional[dict] = None
    create_user_name : str


class JOBPostModel(BaseModel):
    preprocessing_id : int
    get_job_id : int = 0
    image_id : Optional[int] = None
    job_name : str
    run_code: Optional[str] = None
    parameter: str = ""
    gpu_count: int = 0
    gpu_cluster_auto : bool = False
    gpu_select : List[dict] = []
    gpu_auto_select : dict = {}
    gpu_cluster_case_old : List[dict] = []
    gpu_cluster_list_old : dict = {}
    pod_per_gpu : int = 0
    dataset_id : int
    dataset_data_path : Optional[str] = None
    built_in_param : Optional[dict] = None
    # get_training_id : bool = False

# class RunCodeModel(BaseModel):
#     training_id: int = Field(description='JOB ID')

# class SshLoginCmdModel(BaseModel):
#     training_tool_id: int = Field(description="training_tool_id")

# class JOBStopModel(BaseModel):
#     training_id: int = Field(description='프로젝트ID')
#     # gpu_model: Optional[str] = Field(description='Run GPU Type ex) gtx-1080, rtx-2080')

# class HPSStopModel(BaseModel):
#     hps_id: int = Field(description="Hps id ")

# class HPSsStopModel(BaseModel):
#     hps_group_id: int = Field(description="Hps id ")

# class StopJobModel(BaseModel):
#     job_id: int = Field(description="Job id ")

# class ToolDeleteModel(BaseModel):
#     preprocessing_tool_id : int = Field(description="preprocessing id")

# class ToolPasswordModel(BaseModel):
#     preprocessing_tool_id : int
#     new_password : str 




# class StopJobsModel(BaseModel):
#     training_id: int = Field(description="training id")

# class JOBToolGetModel(BaseModel):
#     training_id: int = Field(description="training_id")

# class JOBToolInfoModel(BaseModel):
#     training_tool_id: int = Field(description="training_tool_id - ")

# class JOBToolTypeInfoModel(BaseModel):
#     training_tool_type: int = Field(description="tool_type - ")

# class JOBToolNameModel(BaseModel):
#     training_tool_id: int = Field(description="training_tool_id")
#     training_tool_name: str = Field(description="training tool name : 규칙 없음. 자유")

# class ToolReplicaDeleteModel(BaseModel):
#     training_tool_id: int = Field(description="training_tool_id")

# class JOBNameGetModel(BaseModel):
#     training_id: int = Field(description='JOB ID')
    
    
# class ToolGPUPostModel(BaseModel):
#     preprocessing_tool_id : int
#     gpu_count : int
    
    
    
#==========================
# DTO
#==========================

class PreprocessingBase(BaseModel):
    id : int
    preprocessing_id : int
    preprocessing_name : str
    preprocessing_type : str
    workspace_id : int
    workspace_name : str
    image_id : int
    image_name : str
    dataset_id : int
    owner_id : int
    owner_name : str
    gpu_count : int = 0
    gpu_cluster_auto : bool = False
    gpu_auto_cluster_case : dict = {}
    gpu_select : List[dict] = []
    instance_id : int
    resource_type : str
    pod_type : str = PREPROCESSING_TYPE
    work_func_type : str 
    pod_per_gpu : Optional[int] = 1 # 수동선택을 위한 값


class PreprocessingTool(PreprocessingBase):
    tool_type : int
    resource_name : Optional[str] = ""
    request_status : int
    tool_password : str = ""

class PreprocessingJob(PreprocessingBase):
    create_user_id : int
    built_in_data_type : Optional[str]
    built_in_data_tf : Optional[str]
    job_name : str
    run_code : Optional[str]
    parameter : str
    dataset_data_path : Optional[str]