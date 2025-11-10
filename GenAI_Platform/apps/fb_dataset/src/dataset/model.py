from pydantic import BaseModel, Field
from fastapi import UploadFile, File, Form , Query
from typing import List, Annotated, Optional


# class CreateDatasetModel(BaseModel):
#     workspace_id : int = Form(...)
#     dataset_name : str = Form(...)
#     access : int = Form(...)
#     doc : UploadFile = Form(...)
#     path : str = Form(...) #TODO 고도화시 삭제 고려 
#     filepath : str = Form(...)#TODO 고도화시 삭제 고려
#     description : str = Form(...)
#     google_info : str  = Form(...) #TODO 구글 업로드 유지하지 않을 경우 삭제
#     built_in_model_id : int = Form(...)
#     upload_method : int = Form(...) #TODO 고도화시 삭제 고려
    
# class CreateDatasetModel(BaseModel):
#     workspace_id : int
#     dataset_name : str
#     doc : UploadFile
#     path : str
#     filepath : str
#     description : str
#     google_info : str
#     built_in_model_id : str
#     upload_method : str
    
#     @classmethod
#     def as_form(
#         cls,
#         workspace_id : int = Form(...),
#         dataset_name : str = Form(...),
#         access : int = Form(...),
#         doc : UploadFile = Form(...),
#         path : str = Form(...), #TODO 고도화시 삭제 고려 
#         filepath : str = Form(...), #TODO 고도화시 삭제 고려
#         description : str = Form(...),
#         google_info : str  = Form(...), #TODO 구글 업로드 유지하지 않을 경우 삭제
#         built_in_model_id : int = Form(...),
#         upload_method : int = Form(...) 
#         ): #TODO 고도화시 삭제 고려 
#         return cls(workspace_id=workspace_id,
#                    dataset_name=dataset_name,
#                    access=access,
#                    doc=doc,
#                    path=path,
#                    filepath=filepath,
#                    description=description,
#                    google_inf=google_info,
#                    built_in_model_id=built_in_model_id,
#                    upload_method=upload_method)
        
class GetDataTrainingFormModel(BaseModel):
    dataset_id: int
    data_training_form: list
        
class ReadDatasetsModel(BaseModel):
    workspace_id : Optional[int] =None
    page : Optional[str] = "1"
    size : Optional[str] = "10"
    search_key : Optional[str] = None
    search_value : Optional[str] = None

# class UpdateDatasetModel(BaseModel):
#     workspace_id : int
#     dataset_id : int
#     dataset_name : str
#     original_name: str #TODO 삭제 고려
#     new_name : str #TODO 삭제고려
#     access : int
#     doc : Annotated[List[bytes], File()]
#     path : str = None
#     type : str #TODO file인지 dir인지 구분하는건데 고도화 시 수정
#     filepath : str #TODO 고도화시 삭제 고려
#     remove_files : str
#     description : str
#     upload_list : str #TODO 고도화시 삭제고려
    
class DataSearchModel(BaseModel):
    search_path : Optional[str] = None
    search_page : Optional[str] = None
    search_size : Optional[str] = None
    search_type : Optional[str] = None
    search_key : Optional[str] = None
    search_value : Optional[str] = None
    sort_type : Optional[str] = "name"
    reverse : Optional[bool] = False

class DeleteDatasetModel(BaseModel):
    dataset_ids: List[int]

class DeleteDataModel(BaseModel):
    data_list : List[str] = None,
    path : str= None
    
class GoogleDriveModel(BaseModel):
    google_info : str
    dataset_id : int
    path : str
    
class UpdateInfoModel(BaseModel):
    dataset_id : int
    dataset_name : str
    workspace_id : int
    access : str
    description : str

#args
class DecompressModel(BaseModel):
    dataset_id : Optional[str]
    file : Optional[str]
    path : Optional[str] = None
    
#args
class PreviewModel(BaseModel):
    dataset_id :  Optional[str]
    file_name :  Optional[str]
    path :  Optional[str] = None
    
    
class GithubModel(BaseModel):
    url : str
    username : Optional[str] = None
    accesstoken : Optional[str] = None
    dataset_id : int
    dir : str
    current_path : str
    
class CopyModel(BaseModel):
    dataset_id : int
    target_path : str = None
    destination_path : str = None
    items : List[str]
    # items : str
    is_copy : bool = False

class FileBrowser(BaseModel):
    active : str