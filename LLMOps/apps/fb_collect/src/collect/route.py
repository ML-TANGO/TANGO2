from fastapi import APIRouter, Depends, Request, Path, Form, UploadFile, BackgroundTasks
from utils.settings import LOGIN_METHOD
from typing import List, Annotated, Optional
from collect import model
# from upload import service as upload_svc 
from collect import service as collect_svc
from utils.resource import response, get_user_id
from utils.redis import get_redis_client_async
from utils.connection_manager import connection_manager
collect = APIRouter(
    prefix = "/collect"
)
from fastapi.responses import JSONResponse
@collect.get("/healthz")
async def healthz():
    try:
        await connection_manager.get_redis_client()
        return JSONResponse(status_code=200, content={"status": "healthy", "redis_healthy": connection_manager.redis_healthy})
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "redis_healthy": False, "error": str(e)})

#collector 목록조회
@collect.get("")
async def get_collect_list(args: model.CollectGetListModel = Depends()):
    workspace_id = args.workspace_id
    
    res = await collect_svc.get_collectors_async(workspace_id=workspace_id)
    if res:
        return response(result=res, status =1)
    else:
        return response(message="Get Collect Erorr" , status=0)

@collect.get("/collect-info")
async def get_collect_info(args: model.CollectGetInfoModel = Depends()):
    id = args.id
    name = args.name
    
    res = await collect_svc.get_collector_info_async(id=id, name=name)

    if res:
        return response(result=res, status =1)
    else:
        return response(message="Get Collect information Erorr" , status=0)

@collect.get("/history")
def get_collect_info(args: model.CollectModel = Depends()):
    id = args.id
    res = collect_svc.get_collector_history(id=id)

    return response(result=res, status =1)

@collect.post("")
def create_collect(body: model.CollectCreateModel):
    """
        METHOD : public_api, crawling, remote_server, fightbase\n
        CYLCEL UNIT :\n   
                        h -> hour\n
                        d -> day\n
                        w -> week\n
                        m -> month\n
        STORAGE UNIT :  GB , TB\n
        COLLECT INFO :\n
                        공공API : name, url , api_key, providing_organization, detail_url, method, data_type(Form, Body) params   등등 기획화면 확인바람 \n
                        웹 크롤러 : name, url \n
                        원격 서버 : name , user, passwd, ip, path \n
                        FB 배포 : name, id \n
    """
    try:
        print("=======================")
        res = collect_svc.create_collector(body=body)
        if res:
            return response(status = 1, message = 'Collect Create Complete')
        else:
            raise Exception("Collect DB Insert Error")
    except Exception as e:
        return response(status = 0, message = f"Collect Create Fail '{e}' ")
    
@collect.get("/options")
def get_collect_option(body: model.CollectGetListModel= Depends()):
    user_id = get_user_id()
    res = collect_svc.collect_options(body.workspace_id, headers_user=user_id)
    return response(status = 1, result = res)

@collect.get("/options/dir-list")
async def get_collect_dir_list(args: model.GetDirListModel= Depends()):
    try:
        res = await collect_svc.get_dataset_dir_list(dataset_id=args.dataset_id, path=args.path)
        return response(status = 1, result = res)
    except Exception as e:
        return response(status=0 , message = str(e))



@collect.post("/delete/{id}")
async def delete_collect(id):
    try:
        res = await collect_svc.delete_collect(id=id)
        if res:
            return response(status = 1, message = 'Collect delete Complete')
        else:
            return response(status = 1, message = 'Collect delete Fail')
    except Exception as e:
        return response(status = 0, message = f"Collect delete Fail '{e}' ")

@collect.post("/update/{id}")
async def update_collect(id, body: model.CollectCreateModel) :
    try:
        print(body)
        res = await collect_svc.update_collector(id=id, body=body.dict())
        if res:
            return response(status = 1, message = 'Collect Update Complete')
        else:
            raise Exception("Collect DB Update Error")
    except Exception as e:
        return response(status = 0, message = f"Collect Update Fail '{e}' ")
    

@collect.post("/start")
async def start_collect(body: model.CollectModel) :
    try:
        res = await collect_svc.start_collector(collect_id=body.id) #
        if res:
            return res #response(status = 1, message = 'Collect Start Complete')
        else:
            raise Exception("Collect Start Error")
    except Exception as e:
        return response(status = 0, message = f"Collect Start Fail '{e}' ")
    
@collect.post("/stop")
async def stop_collect(body: model.CollectModel) :
    try:
        print(body.id)
        res = await collect_svc.stop_collector(collect_id=body.id)
        print(res)
        if res:
            return res #response(status = 1, message = 'Collect Start Complete')
        else:
            raise Exception("Collect stop Error")
    except Exception as e:
        return response(status = 0, message = f"Collect Start Fail '{e}' ")
    
@collect.get("/public-api")
async def get_public_api_data():
    try:
        res = await collect_svc.get_public_data_api_list()
        if res:
            return response(status = 1, result = res)
        else:
            raise Exception("Collect Start Error")
    except Exception as e:
        return response(status = 0, message = f"Get Public API Fail '{e}' ")
    
@collect.post("/bookmark")
async def set_bookmark(body: model.BookMarkModel):
    try:
        res = await collect_svc.update_bookmark(id=body.id, bookmark=body.bookmark)
        if res:
            return res
    except Exception as e:
        return response(status = 0, message = f"Update collect bookmark Fail '{e}' ")
    
@collect.post("/history/delete")
async def delete_history(body:model.HistoryModel):
    """
        history_id is None -> all history delete\n
        history_id is not None -> specific history delete
    """
    try:
        res = await collect_svc.delete_history_data(collect_id=body.id, history_id=body.history_id)
        if res :
            return res
    except Exception as e:
        return response(status=0, message=f"{e}")
