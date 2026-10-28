from pydantic import BaseModel, Field
from fastapi import UploadFile, File, Form , Query
from typing import List, Annotated, Optional, Dict


# class TimeUnit(str, Enum):
#     second = "second"
#     minute = "minute"
#     hour = "hour"
#     month = "month"

# class InstanceCostPalnModel(BaseModel):
#     name: Optional[str]
#     instance_list : Optional[List[InstanceItem]]
#     time_unit : Optional[TimeUnit] = Field(..., description="시간 단위")
#     time_unit_cost : Optional[int]
#     type: Optional[str] = None


# class InstanceItem(BaseModel):
#     source: str
#     instance_id: inth
#     instance_allocate: int
class PageModel(BaseModel):
    page : Optional[int] = 1

class GetDirListModel(BaseModel):
    dataset_id: Optional[int]
    path : Optional[str] = ""

class CollectModel(BaseModel):
    id : Optional[int] = None

class BookMarkModel(CollectModel):
    bookmark: Optional[bool] = False
    
class CollectGetListModel(BaseModel):
    workspace_id: Optional[int] = None

class CollectGetInfoModel(CollectGetListModel):
    id : Optional[int] = None
    name : Optional[str] = None

class HistoryModel(CollectModel):
    history_id : Optional[int] = None
# class CollectInfomation(BaseModel):
#     source: Optional[int] = None
#     user: Optional[str] = None
#     password: Optional[int] = None
#     path: Optional[str] = None
#     nameh: Optional[int] = None
#     api_key: Optional[str] = None
#     api: Optional[str] = None


class CollectCreateModel(BaseModel):
    name : Optional[str] = Field(None, description="수집 이름")
    description : Optional[str] = Field(None, description="수집 설명")
    workspace_id : Optional[int] = Field(None, description="수집이 생성될 워크스페이스 ID") 
    dataset_id: Optional[int] = Field(None, description="수집한 데이터를 저장할 데이터셋 ID")
    dataset_path: Optional[str] = Field(None, description="수집한 데이터를 저장할 데이터셋 내부 경로")
    instance_id: Optional[int] = Field(None, description="수집에 사용할 인스턴스 ID")
    instance_count: Optional[int] = Field(None, description="수집에 사용할 인스턴스 갯수")
    collect_method : Optional[str] = Field(None, description="수집 방법")
    collect_cycle : Optional[int] = Field(None, description="수집 주기")
    collect_cycle_unit : Optional[str] = Field(None, description="수집 주기 단위")
    collect_storage_limit : Optional[bool] = Field(None, description="수집 용량제한 여부")
    collect_storage_size : Optional[int] = None
    collect_storage_unit : Optional[str] = None
    collect_information_list: Optional[List[Dict]] = Field(None, description="수집을 위한 정보 리스트")
    access : Optional[int] = Field(None, description="접근권한")
    owner_id : Optional[int] = Field(None, description="소유자")
    members : Optional[List[int]] = Field(None, description="private members")

class CollectUpdateModel(CollectCreateModel):
    workspace_id: int
