from pydantic import BaseModel, Field
from fastapi import UploadFile, File, Form , Query
from typing import List, Annotated, Optional, Dict

class AnalyzerIdModel(BaseModel):
    analyzer_id : int
    
class AnalyzerGetListModel(BaseModel):
    workspace_id: Optional[int] = None

class AnalyzerGetInfoModel(AnalyzerGetListModel):
    id : Optional[int] = None
    name : Optional[str] = None

class AnalyzerCreateModel(BaseModel):
    name: str = Field(..., description="분석 이름")
    description: Optional[str] = Field(None, description="분석 설명")
    instance_id: int = Field(description="인스턴스 ID")
    instance_allocate: int = Field(ge=1, description="인스턴스 갯수 (1 이상)")
    access: int = Field(ge=0, le=1, description="접근 권한 (0 또는 1)")
    owner_id: int = Field(description="소유자 ID")
    workspace_id: int = Field(description="워크스페이스 ID")
    users_id: Optional[list] = Field(default=list(), description='Users Id')

class AnalyzerUpdateModel(BaseModel):
    id: int
    description: Optional[str] = Field(None, description="분석 설명")
    instance_id: Optional[int] = Field(None, description="인스턴스 ID")
    instance_allocate: Optional[int] = Field(None, ge=1, description="인스턴스 갯수 (1 이상)")
    access: Optional[int] = Field(None, ge=0, le=1, description="접근 권한 (0 또는 1)")
    owner_id: Optional[int] = Field(None, description="소유자 ID")
    users_id: Optional[list] = Field(default=list(), description='Users Id')

# ========================================================================
# Graph
# ========================================================================
class AnalyzerGraphCreateModel(BaseModel):
    analyzer_id: int
    name: str = Field(description="그래프 이름")
    description: Optional[str] = Field(None, description="그래프 설명")
    workspace_id: int = Field(description="워크스페이스 ID")
    dataset_id: int = Field(description="데이터셋 id")
    file_path: str = Field(description="데이터셋 데이터 full path")
    graph_type: int = Field(description="그래프유형, LINE=0, BAR=1, PIE=2")
    column: str = Field(description="컬럼")

class AnalyzerGraphDeleteModel(BaseModel):
    analyzer_id: Optional[int] = Field(None, description="전체 삭제일 경우 analyzer_id")
    graph_id_list: Optional[list[int]] = Field(None, description="선택 삭제일 경우 [graph_id, graph_id, ...]")