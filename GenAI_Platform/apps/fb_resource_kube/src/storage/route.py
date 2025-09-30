from fastapi import APIRouter, Form ,UploadFile, Depends
from utils.resource import response, token_checker, CustomResource
from storage import service as storage_svc
from storage import storage_service
from storage import model
from typing import Annotated
from utils.exceptions import *

storage = APIRouter(
    prefix = "/storage"
)


@storage.get("")
@token_checker
async def get_storage_info_list():
    """
        storage list 정보 조회(워크스페이스 사용량 포함)
        ---
    """
    res = response(status=1 , result =storage_service.get_storage_usage_info())
    return res

@storage.post("")
#@token_checker
async def create_storage(ip : Annotated[str, Form()],
                         mountpoint : Annotated[str, Form()],
                         name : Annotated[str, Form()],
                         type : Annotated[str, Form()] ):
    """
        storage 추가(스토리지를 추가한다고 바로 사용가능하지 않음)
    """
    res = storage_service.create_storage(ip=ip, mountpoint=mountpoint, name=name, type=type)
    # res = response(status=1, message="success storage create")
    return res

# TODO 필요없음
@storage.post("/sync")
@token_checker
async def storage_sync():
    """
        storage 동기화
        return {"result": true, "message": null, "status": 1}
    """
    res = storage_svc.get_workspace_usage_list()
    return res


#TODO 필요없음
@storage.get("/sync")
@token_checker
async def storage_sync_check():
    """
        storage 전체 동기화 체크

    """
    try:
        return response(status=1, message="success sync check")
    except :
        return response(status=0, message="fail sync check")

@storage.put("/{id}")
@token_checker
async def update_storage(args : model.StorageUpdateModel): # model 필요
    """
        storage 수정
    """
    return response(status=1, message="success update storage")


@storage.put("/{id}/workspace")
@token_checker
async def workspace_usage_sync(id):
    """
        사용자 페이지
        workspace 사용량 동기화 동기화
    """

    return response(status=1, message="TBD - PUT /storage/id/workspace")


