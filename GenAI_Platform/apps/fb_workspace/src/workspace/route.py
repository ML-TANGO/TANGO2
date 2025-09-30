from fastapi import APIRouter, Depends, Request, Path
from fastapi.responses import JSONResponse
from utils.resource import CustomResource, response, token_checker, def_token_checker
from workspace import service_2 as svc2
from workspace import model
from utils.exceptions import *
from utils.access_check import admin_access_check

workspaces = APIRouter(
    prefix = "/workspaces"
)

@workspaces.get("/healthz")
async def healthz():
    return JSONResponse(status_code=200, content={"status": "healthy"})

@workspaces.get("/option")
# @def_token_checker
def get_workspace_option(workspace_id : int = None):
    cr = CustomResource()
    res = svc2.workspace_option(headers_user=cr.check_user(), workspace_id=workspace_id)
    return res

@workspaces.get("/request-option")
# @def_token_checker
def get_workspace_option(request_workspace_id : int):
    cr = CustomResource()
    res = svc2.request_workspace_option( request_workspace_id=request_workspace_id)
    return res

### GET
@workspaces.get("", description="워크스페이스 목록 조회")
# @def_token_checker
def get_workspaces(args : model.WsSearchModel = Depends()):
    # MSA 전환 : page, size, search_key, search_value ==> None
    try:
        page = args.page
        size = args.size
        search_key = args.search_key
        search_value = args.search_value
        cr = CustomResource()
        res = svc2.get_workspaces(headers_user=cr.check_user(), page=page, size=size, search_key=search_key, search_value=search_value)
        return res
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Workspace Create Error : {}".format(e))


### POST
@workspaces.post("", description="워크스페이스 생성")
# @def_token_checker
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

        res = svc2.create_workspace(manager_id=manager_id,
                                    workspace_name=workspace_name,
                                    allocate_instances=allocate_instances,
                                    start_datetime=start_datetime,
                                    end_datetime=end_datetime,
                                    description=description,
                                    users=users,
                                    data_storage_id=data_storage_id,
                                    data_storage_request=data_storage_request,
                                    main_storage_id=main_storage_id,
                                    main_storage_request=main_storage_request)
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
# @def_token_checker
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

        cr = CustomResource()
        # res = svc.update_workspace(workspace_id=workspace_id, workspace_name=workspace_name, training_gpu=training_gpu,
        #                                                 deployment_gpu=deployment_gpu, start_datetime=start_datetime, end_datetime=end_datetime, users=users,
        #                                                 description=description, guaranteed_gpu=guaranteed_gpu, headers_user=cr.check_user(), manager_id=manager_id, workspace_size=workspace_size)
        # db.request_logging(self.check_user(), 'workspaces', 'put', str(args), res['status)
        res = svc2.update_workspace(workspace_id=workspace_id, workspace_name=workspace_name, allocate_instances=allocate_instances, start_datetime=start_datetime, end_datetime=end_datetime, \
            users=users, description=description, manager_id=manager_id)
        return res
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Workspace Create Error : {}".format(e))



@workspaces.post("/favorites", description="워크스페이스 즐겨찾기 추가/삭제")
@def_token_checker
def workspace_favorite(body: model.WsFavoritesModel):
    try:
        cr = CustomResource()
        workspace_id = body.workspace_id
        action = body.action
        res = svc2.update_favorites(workspace_id=workspace_id, action=action, headers_user=cr.check_user())
        # db.request_logging(self.check_user(), 'workspaces/favorites', 'post', str(args), res['status'])
        return res
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Workspace Create Error : {}".format(e))

@workspaces.post("/request", description="워크스페이스 생성 & 수정 요청")
def request_worksapce(body: model.WsRequestModel):
    try:
        cr = CustomResource()
        res, message = svc2.request_workspace(headers_user=cr.check_user(),
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
                                    request_type=body.request_type)
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
        cr = CustomResource()
        res = svc2.refuse_workspace_request(request_workspace_id=args.request_workspace_id)
        return res
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Workspace Create Error : {}".format(e))

@workspaces.post("/request-accept", description="워크스페이스 생성 수락")
def accept_request_workspace(body : model.RWsCreateModel):
    try:
        cr = CustomResource()
        request_workspace_id = body.request_workspace_id
        # manager_id = body.manager_id
        # workspace_name = body.workspace_name
        # allocate_instances = body.allocate_instances
        # start_datetime = body.start_datetime
        # end_datetime = body.end_datetime
        # users = body.users_id
        # description = body.description
        # data_storage_id = body.data_storage_id
        # data_storage_request = body.data_storage_request
        # main_storage_id = body.main_storage_id
        # main_storage_request = body.main_storage_request

        res = svc2.request_workspace_accept(request_workspace_id=request_workspace_id)
        # res = svc2.request_workspace_accept(manager_id=manager_id,
        #                             request_workspace_id=request_workspace_id,
        #                             workspace_name=workspace_name,
        #                             allocate_instances=allocate_instances,
        #                             start_datetime=start_datetime,
        #                             end_datetime=end_datetime,
        #                             description=description,
        #                             users=users,
        #                             data_storage_id=data_storage_id,
        #                             data_storage_request=data_storage_request,
        #                             main_storage_id=main_storage_id,
        #                             main_storage_request=main_storage_request)
        if res == True:
            return response(status=1, message="success")
        else:
            return response(status=0, message="fail")
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Workspace Create Error : {}".format(e))


@workspaces.put("/resource",  description="워크스페이스 자원관리")
# @def_token_checker
# @admin_access_check()
def update_workspace_resource(body: model.WsResourceUpdateModel):
    try:
        res = svc2.update_workspace_resource(
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
# @def_token_checker
# @admin_access_check()
def get_workspace_resource(workspace_id: int):
    try:
        res = svc2.get_workspace_resource(workspace_id=workspace_id)
        return response(status=1, message="OK", result=res)
    # except CustomErrorList as ce:
    #     return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))


# @workspaces.get("/{workspace_id}", description="워크스페이스 정보 조회 (해당 id)")
# @def_token_checker
# def get_workspace(workspace_id: int):
#     try:
#         cr = CustomResource()
#         res = svc.get_workspace(workspace_id=workspace_id, user=cr.check_user())
#         # db.request_logging(self.check_user(), 'workspaces/'+str(workspace_id), 'get', None, res['status)
#         return res
#     except CustomErrorList as ce:
#         return ce.response()
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Workspace Create Error : {}".format(e))

# @workspaces.get("/{workspace_id}/description", description="워크스페이스 매니저 description 조회")
# @def_token_checker
# def get(workspace_id: int):
#     try:
#         cr = CustomResource()
#         res = svc.get_workspace_description(workspace_id, cr.check_user())
#         return res
#     except CustomErrorList as ce:
#         return ce.response()
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Workspace manager description Error : {}".format(e))

# @workspaces.get("/{workspace_id}/gpu", description="워크스페이스 매니저 GPU 수정관련 조회")
# @def_token_checker
# def get(workspace_id: int):
#     try:
#         cr = CustomResource()
#         res = svc.get_workspace_gpu(workspace_id, cr.check_user())
#         return res
#     except CustomErrorList as ce:
#         return ce.response()
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Workspace manager description Error : {}".format(e))


# @workspaces.put("/{workspace_id}/description", description="워크스페이스 매니저 description 조회")
# @def_token_checker
# def update_workspace_description(workspace_id: int, body: model.WsDescriptionUpdateModel):
#     try:
#         description = body.description

#         cr = CustomResource()
#         res = svc.update_workspace_description(workspace_id, description, cr.check_user())
#         return res
#     except CustomErrorList as ce:
#         return ce.response()
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Workspace Create Error : {}".format(e))

# @workspaces.put("/{workspace_id}/gpu", description="워크스페이스 매니저 GPU 수정")
# @def_token_checker
# def update_workspace_description(workspace_id: int, body: model.WsGpuUpdateModel):
#     try:
#         training_gpu = body.training_gpu
#         deployment_gpu = body.deployment_gpu

#         cr = CustomResource()
#         res = svc.update_workspace_gpu(workspace_id, training_gpu, deployment_gpu, cr.check_user())
#         return res
#     except CustomErrorList as ce:
#         return ce.response()
#     except Exception as e:
#         traceback.print_exc()
#         return response(status=0, message="Workspace Create Error : {}".format(e))


@workspaces.get("/check/{workspace_name}")
# @def_token_checker
def check_workspace_name(workspace_name: str):
    # cr = CustomResource()
    # res = svc.check_user_name(user_name=user_name, headers_user=cr.check_user())
    status, message = svc2.check_workspace_name(workspace_name=workspace_name)
    # db.request_logging(self.check_user(), 'users/check/'+str(user_name), 'get', None, res['status'])
    return response(status=status, message=message)


@workspaces.delete("/{id_list}", description="워크스페이스 삭제")
# @def_token_checker
# @admin_access_check()
def delete_workspaces(id_list: str):
    try:
        cr = CustomResource()
        id_list = id_list.split(',')
        res = svc2.delete_workspaces(workspace_list=id_list)
        # db.request_logging(self.check_user(), 'workspaces/'+str(id_list), 'delete', None, res['status)
        return response(status=1, message="success")
    except CustomErrorList as ce:
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="Workspace Create Error : {}".format(e))




# ==== quota ===

# @workspaces.get("/get_ws_quota", description="워크스페이스당 디스크 용량 제한 설정값 불러오기")
# # @token_chsecker
# def get_workspace_quota(body: model.GetWsQuotaModel):
#     """워크스페이스당 디스크 용량 제한 설정값 불러오기"""
#     cr = CustomResource()
#     workspace_name = body.workspace_name
#     res = svc.get_workspace_quota(workspace_name)
#     return res

# @workspaces.get("/set_ws_quota", description="워크스페이스당 디스크 용량 제한 설정")
# # @token_chsecker
# def set_workspace_quota(body: model.SetWsQuotaModel):
#     cr = CustomResource()
#     workspace_name = body.workspace_name
#     size = body.size
#     unit = body.unit
#     res = svc.set_workspace_quota(workspace_name, size, unit)
#     return res