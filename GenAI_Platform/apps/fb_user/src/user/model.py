from pydantic import BaseModel, Field
from typing import Optional

class UserGetModel(BaseModel):
    search_key: str = None # 검토 필요
    search_value: str = None # 검토 필요 
    size: int = None # 검토 필요
    page: int = None # 검토 필요

class UserCreateModel(BaseModel):
    # workspaces_id: list = []
    new_user_name: str
    password: str
    user_type: int
    nickname: Optional[str] = None
    job: Optional[str] = None
    email: Optional[str] = None
    team: Optional[str] = None
    usergroup_id: Optional[int] = None

class UserUpdateModel(BaseModel):
    select_user_id: int
    new_password: Optional[str] = None
    # workspaces_id: list = []
    usergroup_id: Optional[int] = None
    nickname: Optional[str] = None
    job: Optional[str] = None
    email: Optional[str] = None
    team: Optional[str] = None
    
class UserPasswordUpdateMode(BaseModel):
    password: str = Field(description = "password (encryt)")
    new_password: str = Field(description = "new password (encryt)")
    
    
class UserGroupCreateModel(BaseModel):
    usergroup_name: str = None
    user_id_list: list = []
    description: str = None
    
class UserGroupUpdateModel(BaseModel):
    usergroup_id: int
    usergroup_name: str
    user_id_list: list = []
    description: str = None
    
class UserRecoverLinuxModel(BaseModel):
    user_ids: str # 기존 백엔드는 list, 프론트는 str로 보냄? -> 일단 동작되는 str에 맞춤
    password: str = None
    
class UserRegisterModel(BaseModel):
    name: str = Field(description = "회원가입 ID")
    password: str
    nickname: Optional[str] = None
    job: Optional[str] = None
    email: Optional[str] = None
    team: Optional[str] = None
    
class UserRegisterConfirmModel(BaseModel):
    register_id: str
    approve: bool = Field(description = "승인 True, 거절 False")
    usergroup_id: Optional[int] = None