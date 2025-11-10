from fastapi import APIRouter, Depends
from fastapi import Form, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import Field
from typing import Annotated
from utils.resource import response, get_auth, get_user_id
from werkzeug.datastructures import FileStorage
from utils.exception.exceptions import CustomErrorList
from utils.access_check import admin_access_check, workspace_access_check, image_access_check, check_image_access_level
from image import service as svc
from image import service_new as svc_new
from image import model
import traceback

images = APIRouter(
    prefix = "/images"
    
)

from utils.redis import get_redis_client_async
from utils.redis_key import WORKSPACE_PODS_STATUS
@images.get("/healthz")
async def healthz():
    try:
        redis_client = await get_redis_client_async()
        await redis_client.hgetall(WORKSPACE_PODS_STATUS)
        return JSONResponse(status_code=200, content={"status": "healthy"})
    except:
        return JSONResponse(status_code=500, content={"status": "not healthy"})

# #######################################################
# ###################### POST ############f###############
# #######################################################

@images.post("/pull", description="이미지 생성: pull")
def create_image_pull(
    url: Annotated[str, Form()], # description="[DOCKER_REGISTRY_IP]:[DOCKER_REGISTRY_PORT]/[REPOGITORY]/[IMAGE_NAME]:[TAG]")
    image_name: Annotated[str, Form()],
    access: Annotated[int, Form()],
    description: Annotated[str, Form()] = None,
    workspace_id_list:  Annotated[str, Form()] = [],
):
    try:
        user_id = get_user_id()
        res = svc_new.create_image(
            image_name=image_name, access=access, description=description, workspace_id_list=workspace_id_list,
            image_type="pull", item={'url' : url}, user_id=user_id
        )
        return response(status=1, message="OK", result=res)
    except CustomErrorList as ce:
        traceback.print_exc()
        return response(status=0, message=str(ce), result=None)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)
    

@images.post("/build", description="이미지 생성: build")
#@
def create_image_build(
    file: Annotated[UploadFile, File()],  # file: Annotated[bytes, File()],
    image_name: Annotated[str, Form()],
    access: Annotated[int, Form()],
    description: Annotated[str, Form()] = None,
    workspace_id_list:  Annotated[str, Form()] = [],
    chunk_file_name: Annotated[str, Form()] = None,
    end_of_file: Annotated[bool, Form()] = False,
):
    try:
        file_ = convert_uploadfile_filestorage(file)
        user_id = get_user_id()
        res = svc_new.create_image_file(
            image_name=image_name, access=access, description=description, workspace_id_list=workspace_id_list,
            image_type="build", item={"file_":file_, "chunk_file_name":chunk_file_name, "end_of_file":end_of_file}, user_id=user_id
        )
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@images.post("/tar", description="이미지 생성: tar")
def create_image_tar(
    file: Annotated[UploadFile, File()],  # file: Annotated[bytes, File()],
    image_name: Annotated[str, Form()],
    access: Annotated[int, Form()],
    description: Annotated[str, Form()] = None,
    workspace_id_list:  Annotated[str, Form()] = [],
    chunk_file_name: Annotated[str, Form()] = None,
    end_of_file: Annotated[bool, Form()] = False,
):
    try:
        file_ = convert_uploadfile_filestorage(file)
        user_id = get_user_id()
        res = svc_new.create_image_file(
            image_name=image_name, access=access, description=description, workspace_id_list=workspace_id_list,
            image_type="tar", item={"file_":file_, "chunk_file_name":chunk_file_name, "end_of_file":end_of_file}, user_id=user_id
        )
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

@images.post("/commit", description="이미지 생성: commit")
def create_image_commit(
    training_tool_id: Annotated[int, Form()],
    image_name: Annotated[str, Form()],
    access: Annotated[int, Form()],
    description: Annotated[str, Form()] = None,
    workspace_id_list:  Annotated[str, Form()] = [],
    message: Annotated[str, Form()] = None,
):
    # TODO MSA training 완료 후 확인
    try:
        user_id = get_user_id()
        res = svc_new.create_image(
            image_name=image_name, access=access, description=description, workspace_id_list=workspace_id_list,
            image_type="commit", item={"training_tool_id" : training_tool_id, "message" : message}, user_id=user_id
        )
        return response(status=1, message="OK", result=res)
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))


@images.post("/copy", description="이미지 생성: copy")
def create_image_copy(
    image_id: Annotated[int, Form()],
    image_name: Annotated[str, Form()],
    access: Annotated[int, Form()],
    description: Annotated[str, Form()] = None,
    workspace_id_list:  Annotated[str, Form()] = [],
):
    try:
        user_id = get_user_id()
        res = svc_new.create_image(
            image_name=image_name, access=access, description=description, workspace_id_list=workspace_id_list,
            image_type="copy", item={"image_id" : image_id}, user_id=user_id
        )
        return response(status=1, message="OK", result=res)
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


# #######################################################
# ####################### ngc ###########################
# #######################################################
@images.get("/ngc")
def get_ngc_tag():
    try:
        res = svc.get_ngc_image_list()
        return res
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@images.get("/ngc/tags")
def get_ngc_tag(ngc_image_name: str):
    try:
        res = svc.get_ngc_image_tag_list(ngc_image_name)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)


@images.post("/ngc", description="이미지 생성: ngc")
def create_image_ngc(
    image_name: Annotated[str, Form()],
    access: Annotated[int, Form()],
    selected_image_url: Annotated[str, Form()],
    description: Annotated[str, Form()] = None,
    workspace_id_list:  Annotated[str, Form()] = [],
):
    try:
        user_id = get_user_id()
        res = svc_new.create_image(
            image_name=image_name, access=access, description=description, workspace_id_list=workspace_id_list,
            image_type="ngc", item={'url' : selected_image_url}, user_id=user_id
        )
        return response(status=1, message="OK", result=res)
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)

# #######################################################
# ####################### tag ###########################
# #######################################################
@images.get("/tag", description="모든 tag 조회 (admin)")
# @admin_access_check()
def get_tag_images():
    try:
        res = svc.get_tag_list()
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)


# TODO MSA 전환
@images.post("/tag", description="이미지 생성: tag")
def create_image_tag(
    image_name: Annotated[str, Form()],
    access: Annotated[int, Form()],
    selected_image_name: Annotated[str, Form()],
    description: Annotated[str, Form()] = None,
    workspace_id_list:  Annotated[str, Form()] = [],
    node_ip: Annotated[str, Form()] = None
):
    try:
        user_id = get_user_id()
        res = svc_new.create_image(
            image_name=image_name, access=access, description=description, workspace_id_list=workspace_id_list,
            image_type="tag", item={'selected_image_name' : selected_image_name, "node_ip" : node_ip}, user_id=user_id
        )
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)


#######################################################
####################### 기타 ##########################
#######################################################


@images.get("/history", description="이미지 히스토리")
def get_history(image_id:int):
    try:
        res = svc.get_image_history(image_id)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)
    
    
@images.get("/install-log", description="이미지 설치로그")
async def get_image_install_log(image_id:int):
    try:
        res = await svc.get_image_install_log(image_id)
        return response(status=1, message="OK", result=res)
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)
    
    
        
# #######################################################
# ####################### CRUD ##########################
# #######################################################
@images.get("", description="이미지 조회 - 목록")
# @workspace_access_check()
def get_images(workspace_id: int=None):
    try:
        user_id = get_user_id()
        res = svc.get_image_list(workspace_id, user_id=user_id)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)


@images.put("", description="이미지 수정")
# @image_access_check(method="IMAGE_UPDATE", priority="OWNER")
def put(body: model.UpdateModel):
    try:
        image_id = body.image_id
        image_name = body.image_name
        workspace_id_list = body.workspace_id_list if body.workspace_id_list is not None else []
        access = body.access
        description = body.description
        
        user_name, _ = get_auth()
        res = svc.update_image(image_id=image_id, image_name=image_name, workspace_id_list=workspace_id_list,
                        access=access, description=description, user=user_name)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)


@images.delete("",  description="이미지 삭제")
# @image_access_check(method="IMAGE_DELETE", priority="OWNER")
def delete(body: model.DeleteModel):
    """
    TODO: image sync 관련 함수 -> 작업 미완료
    """
    try:
        delete_all_list = body.delete_all_list
        delete_ws_list = body.delete_ws_list
        workspace_id = body.workspace_id

        user_id = get_user_id()
        res = svc.delete_image(delete_all_list=delete_all_list, delete_ws_list=delete_ws_list,
                        workspace_id=workspace_id, delete_user=user_id)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)
    

@images.get("/{image_id}", description="이미지 조회 - 단일")
def get_image(image_id: int):
    try:
        res = svc.get_image_single(image_id)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)
    
    

def convert_uploadfile_filestorage(data):
    """fastapi UploadFile -> werkzeug filestorage"""
    # https://werkzeug.palletsprojects.com/en/2.0.x/datastructures/#werkzeug.datastructures.FileStorage
    try:
        class ParsedData:
            def __setattr__(self, key, value):
                # 속성 이름을 유효한 파이썬 식별자 형식으로 변환 (예: "form-data" -> "form_data")
                super().__setattr__(key.replace("-", "_"), value)
            
        def parse_string(s: str) -> ParsedData:
            items = s.split(";")
            result = ParsedData()

            for item in items:
                item = item.strip()

                if "=" in item:
                    key, value = item.split("=", 1)
                    setattr(result, key.strip(), value.strip('"'))
                else:
                    setattr(result, item, None)

            return result

        headers = data.headers
        content_disposition = parse_string(headers["content-disposition"])
        content_type = headers["content-type"]

        res = FileStorage(stream=data.file,
                        filename=data.filename,
                        name=content_disposition.name,
                        headers=headers)
    except:
        traceback.print_exc()
        return data # 원래 데이터 반환
    return res
    