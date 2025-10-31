from fastapi import APIRouter, Depends, Request, Path, Form, UploadFile, BackgroundTasks
from utils.resource import CustomResource, def_token_checker, token_checker
from utils.settings import LOGIN_METHOD
from typing import List, Annotated, Optional
from upload import model
from dataset import model
from upload import service as upload_svc
from dataset import service as dataset_svc
from utils.access_check import workspace_access_check, dataset_access_check
from utils.resource import response
dataset = APIRouter(
    prefix = "/datasets"
)
from fastapi.responses import JSONResponse
@dataset.get("/healthz")
async def healthz():
    return JSONResponse(status_code=200, content={"status": "healthy"})

#Dataset 목록조회
@dataset.get("")
@def_token_checker
# @workspace_access_check()
def get_datasets(args: model.ReadDatasetsModel = Depends()):
    workspace_id = args.workspace_id
    page = int(args.page)
    size = int(args.size)
    search_key = args.search_key
    search_value = args.search_value

    cr = CustomResource()
    res = dataset_svc.get_datasets(search_key=search_key,
                                search_value=search_value,
                                workspace_id=workspace_id,
                                page=page,
                                size=size,
                                headers_user=cr.check_user())
    if res:
        return response(result=res, status =1)
    else:
        return response(message="Get Dataset Erorr" , status=0)

#Dataset 생성
@dataset.post("")
@def_token_checker
# @workspace_access_check()
def create_dataset(workspace_id : Annotated[int, Form()],
                         dataset_name : Annotated[str, Form()],
                         access : Annotated[str, Form()] = None,
                         description : Annotated[str, Form()] = None
                         ):
                        #  doc : Annotated[UploadFile, Form()] = None,
                        #  path : Annotated[str, Form()] = None,
                        #  google_info : Annotated[str, Form()] = None,
                        #  built_in_model_id : Annotated[str, Form()] = None,
                        #  upload_method : Annotated[int, Form()] = None
                        #  filepath : Annotated[str, Form()] = None,
    try:
        args={
        "workspace_id" : workspace_id,
        "dataset_name" : dataset_name,
        "access" : access,
        "description" : description
        }

        cr = CustomResource()
        res = dataset_svc.create_dataset(body=args, headers_user=cr.check_user())
        if res:
            return response(status = 1, message = 'Dataset Create Complete')
        else:
            raise Exception("Dataset DB Insert Error")
    except Exception as e:
        return response(status = 0, message = f"Dataset Create Fail '{e}' ")



    # dataset_path = dataset_svc.get_dataset_path(dataset_id)
    # upload_svc.upload_data(files=doc, path=dataset_path, headers_user=cr.check_user())

#Dataset 정보 업데이트
# @dataset.put("")
# @def_token_checker
# async def dataset_update(workspace_id : Annotated[int, Form()],
#                          dataset_id : Annotated[int, Form()],
#                          dataset_name : Annotated[str, Form()],
#                          access : Annotated[str, Form()] = None,
#                          description : Annotated[str, Form()] = None):
#     cr = CustomResource()
#     args={
#         "workspace_id" : workspace_id,
#         "dataset_name" : dataset_name,
#         "access" : access,
#         "description" : description,
#         "dataset_id" : dataset_id
#     }

#     res = dataset_svc.update_dataset_info(body = args, headers_user=cr.check_user())
#     return res

@dataset.post("/data_training_form")
@def_token_checker
def update_data_training_form_option(body: model.GetDataTrainingFormModel):
    "Data training form 의 children data_list 전달용"
    res = dataset_svc.update_data_training_form(dataset_id=body.dataset_id, data_training_form=body.data_training_form)
    return res

@dataset.get("/data_training_form")
@def_token_checker
def get_update_data_training_form_option(body: model.GetDataTrainingFormModel):
    "Data training form 의 children data_list 전달용"
    res = dataset_svc.update_data_training_form(dataset_id=body.dataset_id, data_training_form=body.data_training_form)
    return res


@dataset.get("/preview")
@def_token_checker
@dataset_access_check(allow_max_level=4)
def preview(args: model.PreviewModel = Depends()):
    cr = CustomResource()
    res = dataset_svc.preview(body=args,headers_user=cr.check_user())
    return res



@dataset.get("/decompress")
@def_token_checker
@dataset_access_check(allow_max_level=4)
def decompress(args: model.DecompressModel = Depends()):
    cr = CustomResource()
    res = dataset_svc.decompress(body = args, headers_user=cr.check_user())
    return res


# @dataset.get("/decompression_check")
# @def_token_checker
# async def decompress_check(args : model.DecompressModel = Depends()):
#     cr = CustomResource()
#     res = dataset_svc.decompress_check(args,headers_user=cr.check_user())
#     return res



@dataset.post("/github_clone")
@def_token_checker
def github_upload(args :model.GithubModel):
    cr = CustomResource()
    res = dataset_svc.git_clone(args, headers_user=cr.check_user())
    return res


@dataset.post("/data-handle")
@def_token_checker
# @dataset_access_check(allow_max_level=4)
def handle(args :model.CopyModel):
    cr = CustomResource()
    res = dataset_svc.handle_data(args, headers_user=cr.check_user())
    return res



from download import model as download_model
from download import service as download_svc
from starlette.responses import FileResponse

# download에서 처리해야함
# @dataset.get("/download")
# @def_token_checker
# async def donwload_data(args : download_model.DownLoadModel = Depends()):
#     cr = CustomResource()
#     res = download_svc.download(args,headers_user=cr.check_user())
#     return res

@dataset.get("/{dataset_id}")
@def_token_checker
def get_dataset_info(dataset_id):
    cr = CustomResource()
    res = dataset_svc.get_dataset_info(dataset_id=dataset_id,user_id=cr.check_user_id())
    return res

@dataset.put("/{dataset_id}")
@def_token_checker
@dataset_access_check(allow_max_level=4)
def update_dataset_info(dataset_id,
                              workspace_id : Annotated[int, Form()]=None,
                              dataset_name : Annotated[str, Form()]=None,
                              access : Annotated[str, Form()] = None,
                              description : Annotated[str, Form()] = None):
    cr = CustomResource()
    args={
        "dataset_name" : dataset_name,
        "access" : access,
        "description" : description,
        "dataset_id" : dataset_id,
        "workspace_id" : workspace_id
    }

    res = dataset_svc.update_dataset_info(body = args, headers_user=cr.check_user())
    return res


@dataset.get("/{dataset_id}/files")
# @def_token_checker
def get_file_list(dataset_id, args : model.DataSearchModel = Depends()):
    search_path = args.search_path
    search_page = int(args.search_page)
    search_size = int(args.search_size)
    search_type = args.search_type
    search_key = args.search_key
    search_value = args.search_value
    sort_type = args.sort_type
    reverse = args.reverse
    cr = CustomResource()

    if search_page < 1 :
            search_page = 1
    if search_size < 1 :
        search_size = 10
    # if len(fnmatch.filter(os.listdir('/jf-data/dataset_download/'),self.check_user()+'*')) > 0 :
    #     os.system('rm -r /jf-data/dataset_download/{}*'.format(self.check_user()))
    res = dataset_svc.get_dataset_files(dataset_id=dataset_id, search_path=search_path, search_page=search_page, search_size=search_size,
                            search_type=search_type, search_key=search_key, search_value=search_value, sort_type=sort_type, reverse=reverse, headers_user=cr.check_user())
    return res




@dataset.post("/{dataset_id}/files")
# @def_token_checker
def remove_data(dataset_id,
                body: model.DeleteDataModel):

    cr = CustomResource()
    res = dataset_svc.remove_data(dataset_id=dataset_id, body=body, headers_user=cr.check_user())
    return res

@dataset.put("/{dataset_id}/files/update")
@def_token_checker
def update_data(dataset_id,
                      path : Annotated[str, Form()] = None,
                      data: Annotated[str, Form()] = None,
                      new_name: Annotated[str, Form()] = None,
                      ):
    body={
        "path" : path,
        "data" : data,
        "dataset_id" : dataset_id,
        "new_name" : new_name
    }

    cr = CustomResource()
    res = dataset_svc.update_data(body=body, headers_user=cr.check_user())
    return res

#폴더생성 API
@dataset.post("/{dataset_id}/makedir")
@def_token_checker
def makedir(dataset_id,
                  dir_name : Annotated[str, Form()],
                  path : Annotated[str, Form()] = None
                  ):

    args={
        "dataset_id" : dataset_id,
        "path" : path,
        "dir_name" : dir_name
    }
    cr = CustomResource()
    res = dataset_svc.make_empty_dir(args, cr.check_user())
    return res

@dataset.get("/{dataset_id}/files/info")
@def_token_checker
def get_dataset_info_detail(dataset_id):
    cr = CustomResource()
    res= dataset_svc.get_dataset_info(dataset_id=dataset_id, user_id=cr.check_user_id())
    return res


@dataset.get("/{dataset_id}/marker_files")
@def_token_checker
def get_dataset_marker(dataset_id, search_path : str = '/'):
    cr = CustomResource()
    res = dataset_svc.get_dataset_marker_files(dataset_id=dataset_id, search_path=search_path, headers_user=cr.check_user())
    return res

# 데이터셋 수정시 기존 데이터셋의 정보를 불러오는 API

#Dataest 삭제
@dataset.delete("/{id_list}")
@def_token_checker
# @dataset_access_check(allow_max_level=4)
def delete_dataset(id_list):
    dataset_ids = id_list
    cr = CustomResource()
    res = dataset_svc.remove_dataset(id_list=dataset_ids, headers_user=cr.check_user())
    return res

@dataset.get("/{dataset_id}/filebrowser")
@def_token_checker
def get_filebrowser(dataset_id):
    cr = CustomResource()
    res= dataset_svc.get_filebrowser_url(dataset_id=dataset_id, headers_user=cr.check_user())
    return res

@dataset.post("/{dataset_id}/filebrowser")
@def_token_checker
def active_filebrowser(dataset_id, body :model.FileBrowser, background_tasks : BackgroundTasks):
    cr = CustomResource()
    res= dataset_svc.active_filebrowser_pod(dataset_id=dataset_id, active=body.active, background_tasks=background_tasks, headers_user=cr.check_user() )
    return res

@dataset.get("/{dataset_id}/tree")
@def_token_checker
def get_tree(dataset_id):
    cr = CustomResource()
    res= dataset_svc.get_tree(dataset_id=dataset_id, headers_user=cr.check_user())
    return res
# @dataset.post("/import")
# @def_token_checker
# async def create_built_in_dataset(default_dataset : Annotated[str, Form()] = None,
#                                   workspace_id : Annotated[str, Form()] = None
#                                   ):
#     """
#     데이터셋 가져오기
#     """
#     res = dataset_svc.create_built_in_dataset(default_dataset = default_dataset, workspace_id=workspace_id)
#     # db.request_logging(self.check_user(), 'datasets', 'post', str(args), res['status'])
#     return res


# @dataset.post("/google_drive")
# @def_token_checker
# async def google_upload(args :model.GoogleDriveModel):
#     cr = CustomResource()
#     res = dataset_svc.google_drive_upload(args, headers_user=cr.check_user())
#     return res

# @dataset.get("/new_model_template")
# @def_token_checker
# async def template_model_list():
#     from utils.built_in_model import built_in_model_list_for_dataset
#     res = built_in_model_list_for_dataset()
#     return res

# @dataset.get("/{dataset_id}/built_in_model_compatibility")
# @def_token_checker
# async def built_in_model_compatibility(dataset_id):
#     from utils.built_in_model import built_in_model_list_compatibility_check
#     res = built_in_model_list_compatibility_check(dataset_id)
#     return res


# @dataset.post("/ws_upload")
# @def_token_checker
# async def ws_upload(args):
#     cr = CustomResource()
#     res = dataset_svc.upload_ws_dataset(args, headers_user=cr.check_user())
#     return res



# @dataset.post("/{dataset_id}/files/info")
# @def_token_checker
# async def get_dataset_info_detail_sync(dataset_id):
#     cr = CustomResource()
#     res= dataset_svc.dataset_info_sync(dataset_id=dataset_id)
#     return res

# @dataset.get("/{dataset_id}/tree")
# @def_token_checker
# async def tree(dataset_id):
#     cr = CustomResource()
#     res = dataset_svc.get_tree(dataset_id=dataset_id, headers_user=cr.check_user())
#     return res


# @dataset.put("/synchronization")
# @def_token_checker
# async def ws_sync_check(workspace_id : Annotated[int, Form()] = None,
#                         dataset_id : Annotated[str, Form()] = None
#                         ):
#     """
#     동기화 thread check
#     # Inputs:
#         worskpace_id(int)   : workspace_id 값 (Root계정에서 전체동기화 진행시 None)
#         dataset_id(int)     : 특정 데이터셋의 동기화버튼 클릭시 dataset_id값 존재
#     ---
#     # Returns:
#         status(int)     : 해당 작업에 대한 스레드가 종료 되었을 때 1 리턴 아닐경우 0 리턴
#         message(str)    : API에서 보내는 리턴 메세지
#     """
#     args={
#         "workspace_id" : workspace_id
#     }

#     res = dataset_svc.sync_ws_check(args)
#     return res

# @dataset.post("/synchronization")
# @def_token_checker
# async def ws_sync(dataset_id : Annotated[str, Form()] = None,
#                   dataset_name : Annotated[str, Form()] = None,
#                   access : Annotated[str, Form()] = None,
#                   description : Annotated[str, Form()] = None,
#                   workspace_id : Annotated[int, Form()] = None
#                   ):
#     """
#         Dataset 동기화
#         ---
#         # Returns:
#             status(int) : 0(실패), 1(성공)
#             message : API에서 보내는 메세지

#             example :
#             {
#                 "message": "ws_synchronization success"
#                 "result": null
#                 "status": 1
#             }
#     """
#     args={
#         "workspace_id" : workspace_id,
#         "dataset_id" : dataset_id,
#         "dataset_name" : dataset_name,
#         "access" : access,
#         "description" : description
#     }
#     res = dataset_svc.sync_ws(args)
#     return res
