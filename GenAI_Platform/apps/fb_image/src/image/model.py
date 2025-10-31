from pydantic import BaseModel, Field

class UpdateModel(BaseModel):
    image_id: int
    image_name: str
    description: str
    access: int
    workspace_id_list: list = []

class DeleteModel(BaseModel):
    delete_all_list: list = []
    delete_ws_list: list = []
    workspace_id: int = None