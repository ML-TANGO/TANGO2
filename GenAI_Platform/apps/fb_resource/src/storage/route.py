from fastapi import APIRouter, Form 
from utils.resource import response
from storage import service as storage_svc
from storage import storage_service
from storage import model
from typing import Annotated

storage = APIRouter(
    prefix = "/storage"
)

@storage.get("")
async def get_storage_info_list():
    """ 
        storage list 정보 조회(워크스페이스 사용량 포함)
        ---
    """        
    res = response(status=1 , result =storage_service.get_storage_usage_info())
    return res


@storage.post("/update")
async def update_storage():
    """ 
        임시로 만들어진 기능
        기존 스토리지 reclaimPolicy 변경 delete -> retain
    """
    res = storage_service.update_storage()
    return res

@storage.post("")
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
async def storage_sync():
    """ 
        storage 동기화
        return {"result": true, "message": null, "status": 1}
    """  
    res = storage_svc.get_workspace_usage_list()
    return res


#TODO 필요없음
@storage.get("/sync")
async def storage_sync_check():
    """ 
        storage 전체 동기화 체크
        
    """   
    try:
        return response(status=1, message="success sync check")
    except :
        return response(status=0, message="fail sync check")
    
@storage.put("/{id}")
async def update_storage(args : model.StorageUpdateModel): # model 필요
    """ 
        storage 수정
    """ 
    return response(status=1, message="success update storage")


@storage.put("/{id}/workspace")
async def workspace_usage_sync(id):
    """ 
        사용자 페이지
        workspace 사용량 동기화 동기화
    """        
    
    return response(status=1, message="TBD - PUT /storage/id/workspace")


