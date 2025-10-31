from pydantic import BaseModel, Field
from fastapi import UploadFile, File, Form , Query
from typing import List, Annotated, Optional


class StorageUpdateModel(BaseModel):
    name : Optional[str] = None
    share : Optional[int] = None
    lock : Optional[int] = None
    description : Optional[str] = None
# class StorageCreateModel(BaseModel):
#     ip : str = Form(...)
#     mountpint: str = Form(...)
#     name : str = Form(...)
#     type : str = Form(...)
