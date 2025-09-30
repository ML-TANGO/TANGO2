from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import datetime


#######################################################
#######################################################
######################REQUEST##########################

class WsSearchModel(BaseModel):
    page: Optional[int] = None
    size: Optional[int] = None
    search_key: Optional[int] = None
    search_value: Optional[int] = None

class WsCreateModel(BaseModel):
    # class AllocateInstanceListModel(BaseModel):
    #     instance_id: int
    #     instance_allocate: int

    manager_id: int
    workspace_name: str
    # allocate_gpus: List[dict] = []
    allocate_instances: List[Dict[str, Any]] = []
    start_datetime: str
    end_datetime: str
    users_id: List[int] = []
    description: str = ""
    data_storage_id : int
    data_storage_request: int = None
    main_storage_id : int
    main_storage_request: int = None

class RWsCreateModel(BaseModel):
    # class AllocateInstanceListModel(BaseModel):
    #     instance_id: int
    #     instance_allocate: int
    request_workspace_id : int
    # manager_id: int
    # workspace_name: str
    # # allocate_gpus: List[dict] = []
    # allocate_instances: List[Dict[str, Any]] = []
    # start_datetime: str
    # end_datetime: str
    # users_id: List[int] = []
    # description: str = ""
    # data_storage_id : int
    # data_storage_request: int = None
    # main_storage_id : int
    # main_storage_request: int = None

class WsUpdateModel(BaseModel):
    workspace_id: int
    workspace_name: str
    start_datetime: str
    end_datetime: str
    description: str = ""
    users_id: List[int]
    manager_id: int
    allocate_instances: List[dict] = []
    # allocate_gpus: List[dict] = []


class WsFavoritesModel(BaseModel):
    workspace_id: int
    action: int = Field(description="삭제(0), 추가(1)")

class WsDescriptionUpdateModel(BaseModel):
    description: str

class WsGpuUpdateModel(BaseModel):
    training_gpu: int
    deployment_gpu: int

class RefuseWorkspace(BaseModel):
    request_workspace_id : int

class WsRequestModel(BaseModel):
    manager_id: int
    workspace_name: str
    # allocate_gpus: List[dict] = []
    allocate_instances: List[Dict[str, Any]] = []
    start_datetime: str
    end_datetime: str
    users_id: List[int] = []
    description: str = ""
    data_storage_id : int = None
    data_storage_request: int = None
    main_storage_id : int = None
    main_storage_request: int = None
    workspace_id: Optional[int] = None
    request_type: Optional[str] = None # TODO optional 제거

"""
allocate_instances = {
    "instance_id" : int,
    "instance_allocate" : int, # 할당수
}
"""

class WsResourceUpdateModel(BaseModel):
    workspace_id: int
    tool_cpu_limit: float
    tool_ram_limit: float
    job_cpu_limit: float
    job_ram_limit: float
    hps_cpu_limit: float
    hps_ram_limit: float
    deployment_cpu_limit: float
    deployment_ram_limit: float

#######################################################
#######################################################
######################RETURN###########################

# class Workspaces(BaseModel):
#     id: int
#     name: str
#     status: str
#     description: str
#     create_datetime: datetime
#     start_datetime: datetime
#     end_datetime: datetime

