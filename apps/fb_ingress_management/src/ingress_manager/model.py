from pydantic import BaseModel
from typing import List, Optional

class AuthenticateUserModel(BaseModel):
    username: str

class CreateConsumerGroupModel(BaseModel):
    workspace_id: str
    project_id: Optional[str] = None
    project_type: Optional[str] = None  # training, inference, preprocessing

class ProjectAccessModel(BaseModel):
    project_id: str
    project_type: str
    workspace_id: str
    is_public: bool
    user_list: List[str]

class RouteACLModel(BaseModel):
    route_id: str
    workspace_id: str
    project_id: Optional[str] = None
    project_type: Optional[str] = None
    is_public: bool