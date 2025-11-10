from pydantic import BaseModel, Field
from fastapi import UploadFile, File, Form
from typing import List, Annotated


class UploadModel(BaseModel):
    workspace_id : Annotated[int, Form()]
    dataset_id : Annotated[int, Form()]
    files : Annotated[List[UploadFile], File()]
    path : Annotated[str, Form()] = None
    
class UploadModelByte(BaseModel):
    workspace_id : int
    dataset_id : int
    files : Annotated[List[bytes], File()]
    path : str = None

class WgetUploadModel(BaseModel):
    dataset_id : int
    upload_url : str
    path : str = None

class ScpUploadModel(BaseModel):
    dataset_id : int
    ip : str
    path : str = None
    username : str
    password : str
    file_path : str

class ProgressModel(BaseModel):
    dataset_id : int
    path : str = None
    upload_type : str

class GitModel(BaseModel):
    dataset_id : int
    path : str = None
    git_repo_url : str = None
    git_cmd : str
    git_access : str
    git_id : str = None
    git_access_token : str = None

class UploadCheckModel(BaseModel):
    dataset_id : int
    path : str = None
    data_list: List[str]

class PreUploadModel(BaseModel):
    dataset_id : int
    path : str = None
    data_list: List[str]
    upload_type : str