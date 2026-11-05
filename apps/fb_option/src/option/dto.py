from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import datetime


#######################################################
#######################################################
######################REQUEST##########################

class HuggingfaceModelInput(BaseModel):
    model_name : Optional[str] = None
    huggingface_token : Optional[str] = None
    private : Optional[int] = 0
    task: Optional[str] = None

    class Config:
        protected_namespaces = () 