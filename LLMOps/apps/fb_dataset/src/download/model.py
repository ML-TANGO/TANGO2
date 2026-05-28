from pydantic import BaseModel, Field
from fastapi import UploadFile, File, Form
from typing import List, Annotated, Optional

class DownLoadModel(BaseModel):
    dataset_id : Optional[str]
    download_files : Optional[str]
    path : Optional[str] = None