from fastapi import APIRouter, Depends, Request, Path, Form, Query
from utils.resource import response, get_auth
from utils.settings import LOGIN_METHOD
from pydantic import BaseModel, Field
from fastapi import UploadFile, File, Form, BackgroundTasks
from typing import List, Annotated
from upload import model
import time
from upload import service as upload_svc 
from dataset import service as dataset_svc
upload = APIRouter(
    prefix = "/upload"
)

# upload_parser = reqparse.RequestParser(bundle_errors=True)
# upload_parser.add_argument("workspace_id", type=int, location="form", required=False, help="workspace_id")
# upload_parser.add_argument("dataset_id", type=int, location="form", required=False, help="dataset_id")
# upload_parser.add_argument("file", type=FileStorage, location="files",action="append", required=False, help="업로드할 파일")
# upload_parser.add_argument("path", type=str, location="form", required=False, help="업로드할 경로")

# @dataset_ns_v1.route("/upload", methods=["POST"])
# class Dataset_Upload(CustomResource):
#     @dataset_ns_v1.expect(upload_parser)
#     async def post(self):
#         try:
#             # print(request.files)
#             args = upload_parser.parse_args()
#             upload = Upload(workspace_id=args['workspace_id'], dataset_id=args['dataset_id'], upload_path = args['path'])
#             upload.save_data(args['file'])
#             return self.send({"message": "success"}, code=200)
#         except:
#             traceback.print_exc()
#             return self.send({"message": "error"}, code=986)


@upload.post("")
async def data_upload(dataset_id : Annotated[int, Form()],
                    files : Annotated[List[UploadFile], File(...)],
                    path : Annotated[str, Form()] = None,
                    size : Annotated[int, Form()] = None,
                    type : Annotated[str, Form()] = "file",
                    start : Annotated[bool, Form()] = False,
                    chunk_start:  Annotated[bool, Form()] = False,
                    overwrite : Annotated[bool, Form()] = True,
                    chunk_id : Annotated[int, Form()] = None ):
    dataset_id = dataset_id
    files = files
    path = path
    size = size
    type = type
    start = start
    chunk_start=chunk_start
    overwrite = overwrite
    chunk_id = chunk_id
    background_tasks=None
    user_name, _ = get_auth()

    # dataset_path = dataset_svc.get_dataset_path(dataset_id)
    res = await upload_svc.upload_data(files=files, 
                                 dataset_id=dataset_id, 
                                 path=path, 
                                 type_=type, 
                                 size=size,
                                 overwrite=overwrite, 
                                 chunk_start=chunk_start,
                                 chunk_id=chunk_id,
                                 headers_user=user_name)

    return res

# @upload.get("/progress")
# async def progress(args : model.ProgressModel = Depends()):
#     cr = CustomResource()
#     res = upload_svc.get_upload_progress(body=args, headers_user=user_name)
#     return res

@upload.post("/wget")
def wget_upload(body: model.WgetUploadModel):

    user_name, _ = get_auth()
    res =  upload_svc.wget_upload(body=body, headers_user=user_name)
    return res

@upload.post("/scp")
def scp_upload(body: model.ScpUploadModel):

    user_name, _ = get_auth()
    res =  upload_svc.scp_upload(body=body, headers_user=user_name)
    return res

@upload.post("/git")
def git_upload(body: model.GitModel):

    user_name, _ = get_auth()
    res =  upload_svc.git_upload(body=body, headers_user=user_name)
    return res

@upload.post("/check")
async def upload_check(body : model.UploadCheckModel):
    res = await upload_svc.upload_name_check(dataset_id=body.dataset_id, data_list=body.data_list, path=body.path)
    return res

@upload.post("/pre-upload")
def upload_check(body : model.PreUploadModel):
    res = upload_svc.upload_dummy_create(dataset_id=body.dataset_id, data_list=body.data_list, type_=body.upload_type, path=body.path)
    return response(status=1, result=res)
# @upload.post("/git-pull")
# async async def git_upload(body: model.GitModel):

#     cr = CustomResource()
#     res = upload_svc.git_pull(body=body, headers_user=user_name)
#     return res