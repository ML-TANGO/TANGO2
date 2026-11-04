from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class UserCreateModel(BaseModel):
    new_user_name: str
    workspace_id: int
    password: str
    user_type: int
    nickname: Optional[str] = None
    job: Optional[str] = None
    email: Optional[str] = None
    team: Optional[str] = None