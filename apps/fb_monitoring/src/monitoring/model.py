# from pydantic import BaseModel, Field, create_model
# from typing import Optional
# # from utils.settings imposrt *
# from utils.TYPE import *

# def create_dynamic_model(model_name, field_list):
#     fields = {}
#     for key, (field_type, default_value) in field_list.items():
#             fields[key] = (field_type, default_value)
#     model = create_model(model_name, **fields)
#     return model

# class GetModel(BaseModel):
#     workspace_name: Optional[str] = Field(default=None, description='Workspace name', type=str)