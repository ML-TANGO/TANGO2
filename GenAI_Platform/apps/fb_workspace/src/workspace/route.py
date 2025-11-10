from fastapi import APIRouter, Depends, Request, Path
from utils.resource import (
    response, 
    get_auth, 
    get_user_id, 
    get_user_info
)
from workspace import service as svc
from workspace import model
from utils.exception.exceptions import *
from utils.access_check import admin_access_check
from utils.connection_manager import connection_manager
from fastapi.responses import JSONResponse

workspaces = APIRouter(
    prefix = "/workspaces"
)

@workspaces.get("/healthz")
async def healthz():
    try:
        await connection_manager.get_redis_client()
        return JSONResponse(status_code=200, content={"status": "healthy", "redis_healthy": connection_manager.redis_healthy})
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "redis_healthy": False, "error": str(e)})

@workspaces.get("/option")
def get_workspace_option(workspace_id : int = None):
    user_name, _ = get_auth()
    res = svc.workspace_option(headers_user=user_name, workspace_id=workspace_id)
    return res 

@workspaces.get("/request-option")
def get_workspace_option(request_workspace_id : int):
    res = svc.request_workspace_option( request_workspace_id=request_workspace_id)
    return res 

### GET
@workspaces.get("", description="워크스페이스 목록 조회")
def get_workspaces(args : model.WsSearchModel = Depends()):
    # MSA 전환 : page, size, search_key, search_value ==> None 
    try:
        page = args.page
        size = args.size
        search_key = args.search_key
        search_value = args.search_value
        user_name, _ = get_auth()
        res = svc.get_workspaces(headers_user=user_name, page=page, size=size, search_key=search_key, search_value=search_value)
        return res
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Get Workspace List Error : {}".format(e))


### POST
@workspaces.post("", description="워크스페이스 생성")
# @admin_access_check()
def create_workspace(body: model.WsCreateModel):
    try:
        manager_id = body.manager_id
        workspace_name = body.workspace_name
        allocate_instances = body.allocate_instances
        start_datetime = body.start_datetime
        end_datetime = body.end_datetime
        users = body.users_id
        description = body.description
        data_storage_id = body.data_storage_id
        data_storage_request = body.data_storage_request
        main_storage_id = body.main_storage_id
        main_storage_request = body.main_storage_request
        use_marker = body.use_marker

        res = svc.create_workspace(manager_id=manager_id,
                                    workspace_name=workspace_name,
                                    allocate_instances=allocate_instances,
                                    start_datetime=start_datetime,
                                    end_datetime=end_datetime, 
                                    description=description,
                                    users=users,
                                    data_storage_id=data_storage_id,
                                    data_storage_request=data_storage_request,
                                    main_storage_id=main_storage_id,
                                    main_storage_request=main_storage_request,
                                    use_marker=use_marker)
        if res == True:
            return response(status=1, message="success")
        else:
            return response(status=0, message="workspace Create failed")
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Workspace Create Error : {}".format(e))

@workspaces.put("",  description="워크스페이스 수정")
# @admin_access_check()
def update_workspace(body: model.WsUpdateModel):
    try:
        workspace_id = body.workspace_id        
        workspace_name = body.workspace_name
        start_datetime = body.start_datetime
        end_datetime = body.end_datetime
        description = body.description
        users = body.users_id
        manager_id = body.manager_id
        allocate_instances = body.allocate_instances
        data_storage_request = body.data_storage_request
        main_storage_request = body.main_storage_request
        data_storage_id = body.data_storage_id
        main_storage_id = body.main_storage_id
        use_marker = body.use_marker
        # res = svc.update_workspace(workspace_id=workspace_id, workspace_name=workspace_name, training_gpu=training_gpu,
        #                                                 deployment_gpu=deployment_gpu, start_datetime=start_datetime, end_datetime=end_datetime, users=users, 
        #                                                 description=description, guaranteed_gpu=guaranteed_gpu, headers_user=user_name, manager_id=manager_id, workspace_size=workspace_size)
        # db.request_logging(self.check_user(), 'workspaces', 'put', str(args), res['status)
        res = svc.update_workspace(workspace_id=workspace_id, workspace_name=workspace_name, allocate_instances=allocate_instances, start_datetime=start_datetime, end_datetime=end_datetime, \
            users=users, description=description, manager_id=manager_id, data_storage_request=data_storage_request, main_storage_request=main_storage_request, data_storage_id=data_storage_id, main_storage_id=main_storage_id, use_marker=use_marker)
        return res
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Workspace Update Error : {}".format(e))



@workspaces.post("/favorites", description="워크스페이스 즐겨찾기 추가/삭제")
def workspace_favorite(body: model.WsFavoritesModel):
    try:
        user_name, _ = get_auth()
        workspace_id = body.workspace_id
        action = body.action
        res = svc.update_favorites(workspace_id=workspace_id, action=action, headers_user=user_name)
        # db.request_logging(self.check_user(), 'workspaces/favorites', 'post', str(args), res['status'])
        return res
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Workspace Favorites Error : {}".format(e))

@workspaces.post("/request", description="워크스페이스 생성 & 수정 요청")
def request_worksapce(body: model.WsRequestModel):
    try:
        user_name, _ = get_auth()
        res, message = svc.request_workspace(headers_user=user_name,
                                    manager_id=body.manager_id,
                                    workspace_name=body.workspace_name,
                                    allocate_instances=body.allocate_instances,
                                    start_datetime=body.start_datetime,
                                    end_datetime=body.end_datetime, 
                                    description=body.description,
                                    users=body.users_id,
                                    data_storage_id=body.data_storage_id,
                                    data_storage_request=body.data_storage_request,
                                    main_storage_id=body.main_storage_id,
                                    main_storage_request=body.main_storage_request,
                                    workspace_id=body.workspace_id,
                                    request_type=body.request_type,
                                    use_marker=body.use_marker)
                                    # 생성일때는 workspace_id None, 수정일때는 workspace_id 필수
        return response(status=1, result=res, message=message)
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))
    
@workspaces.delete("/request-refuse", description="워크스페이스 생성 거절")
def refuse_request_workspace(args : model.RefuseWorkspace):
    try:
        res = svc.refuse_workspace_request(request_workspace_id=args.request_workspace_id)   
        return res
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Workspace Request Refuse Error : {}".format(e))

@workspaces.post("/request-accept", description="워크스페이스 생성 수락")
def accept_request_workspace(body : model.RWsCreateModel):
    try:
        request_workspace_id = body.request_workspace_id


        res = svc.request_workspace_accept(request_workspace_id=request_workspace_id)

        if res == True:
            return response(status=1, message="success")
        else:
            return response(status=0, message="fail")
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Workspace Request Accept Error : {}".format(e))


## TODO 워크스페이스 관리자인지 확인 필요?

@workspaces.get("/resource/items",  description="워크스페이스 아이템 자원관리 정보")
def get_workspace_resource_by_item(workspace_id: int):
    try:
        res = svc.get_workspace_item_list(workspace_id=workspace_id)
        return response(status=1, message="OK", result=res)
    # except CustomErrorList as ce:
    #     return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))


@workspaces.put("/resource/items",  description="워크스페이스 아이템 자원관리 정보")
def put_workspace_resource_by_item(body:  model.WsItemResourceUpdateModel):
    try:
        res = svc.update_workspace_item_resource(workspace_id=body.workspace_id, item_type=body.item_type, item_id=body.item_id,
                                                  job_cpu_limit=body.job_cpu_limit, job_ram_limit=body.job_ram_limit, tool_cpu_limit=body.tool_cpu_limit, tool_ram_limit=body.tool_ram_limit,
                                                  deployment_cpu_limit=body.deployment_cpu_limit, deployment_ram_limit=body.deployment_ram_limit, hps_cpu_limit=body.hps_cpu_limit, hps_ram_limit=body.hps_ram_limit)
        return response(status=1, message="OK", result=res)
    # except CustomErrorList as ce:
    #     return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))

@workspaces.put("/resource/reset",  description="워크스페이스 자원 설정 초기화")
def put_workspace_resource_reset(workspace_id: int):
    try:
        res = svc.update_workspace_resource_reset(workspace_id=workspace_id)
        return response(status=1, message="OK", result=res)
    # except CustomErrorList as ce:
    #     return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))


@workspaces.put("/resource",  description="워크스페이스 자원관리")
def update_workspace_resource(body: model.WsResourceUpdateModel):
    try:
        res = svc.update_workspace_resource(
            workspace_id=body.workspace_id,
            tool_cpu_limit=body.tool_cpu_limit, tool_ram_limit=body.tool_ram_limit,
            job_cpu_limit=body.job_cpu_limit, job_ram_limit=body.job_ram_limit,
            hps_cpu_limit=body.hps_cpu_limit, hps_ram_limit=body.hps_ram_limit,
            deployment_cpu_limit=body.deployment_cpu_limit, deployment_ram_limit=body.deployment_ram_limit,
        )
        return response(status=1, message="OK")
    # except CustomErrorList as ce:
    #     return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))

@workspaces.get("/resource",  description="워크스페이스 자원관리 정보")
def get_workspace_resource(workspace_id: int):
    try:
        res = svc.get_workspace_resource(workspace_id=workspace_id)
        return response(status=1, message="OK", result=res)
    # except CustomErrorList as ce:
    #     return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))
    


@workspaces.get("/check/{workspace_name}")
def check_workspace_name(workspace_name: str):
    status, message = svc.check_workspace_name(workspace_name=workspace_name)
    # db.request_logging(self.check_user(), 'users/check/'+str(user_name), 'get', None, res['status'])
    return response(status=status, message=message)


@workspaces.delete("/{id_list}", description="워크스페이스 삭제")
def delete_workspaces(id_list: str):
    try:
        id_list = id_list.split(',')
        user_type, user_id = get_user_info()

        res = svc.delete_workspaces(workspace_list=id_list, headers_user_id=user_id, headers_user_type=user_type)
        # db.request_logging(self.check_user(), 'workspaces/'+str(id_list), 'delete', None, res['status)
        return response(status=1, message="success")
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Workspace Delete Error : {}".format(e))
