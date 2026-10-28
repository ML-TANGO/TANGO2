from pydantic import BaseModel
from typing import Optional, Any


class Response(BaseModel):
    status: int = 1
    message: str = ""
    result: Any = None


class CreateSynthesisProject(BaseModel):
    workspace_id: int
    name: str
    field: Optional[str] = None
    description: Optional[str] = ""
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    mode: str = "wizard"  # wizard | canvas
    manifest_name: str
    manifest_version: str
    params: Optional[dict] = {}  # meta_prompt / optimize_method / count / instruction
    gpu_count: int = 0
    dataset_id: Optional[int] = None


class UpdateSynthesisProject(BaseModel):
    # 부분 업데이트 — 설정/수정 모달 (P2)
    name: Optional[str] = None
    field: Optional[str] = None
    description: Optional[str] = None
    mode: Optional[str] = None
    manifest_name: Optional[str] = None
    manifest_version: Optional[str] = None
    params: Optional[dict] = None
    gpu_count: Optional[int] = None
    dataset_id: Optional[int] = None


class SaveDatasetBody(BaseModel):
    # 생성 결과 → 데이터셋 저장 (P3)
    dataset_name: str
    access: Optional[str] = "0"
