from fastapi import APIRouter, Depends, FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.responses import JSONResponse, StreamingResponse
from utils.settings import ADMIN_TYPE
from dashboard import service as svc
from utils.msa_db import db_user
# from dashboard.service import workspace_user_info
from utils.resource import response, get_user_id, get_auth
from utils.exception.exceptions import *
from utils import TYPE
from dashboard import model

import gc
import time

dashboard = APIRouter(prefix="/dashboard")


@dashboard.on_event("startup")
async def startup_event():  # Min added - GC 완화
    # gc.set_threshold(7000, 10, 50)
    gc.freeze()

@dashboard.get("/healthz")
async def healthz():
    try:
        await svc.check_healthz()
        return response(status_code=200, result={"status": "healthy"}, status=1)
    except:
        return response(status_code=500, result={"status": "not healthy"}, status=0)


@dashboard.get("/admin")
def get_dashboard_admin():
    try:
        user_name, _ = get_auth()
        user_info = db_user.get_user(user_name=user_name)
        if user_info["user_type"] != ADMIN_TYPE:
            raise GetAdminDashboardError()
        res = svc.get_admin_dashboard_info()
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=e)
    
@dashboard.post("/create_user")
#@token_checker
async def create_users(
    args: model.UserCreateModel,
    dep = Depends(get_auth)
    ):
    header_user_name ,_ = dep
    new_user_name = args.new_user_name
    workspace_id = args.workspace_id
    password = args.password
    user_type = 3 #args.user_type
    email = args.email
    job = args.job
    nickname = args.nickname
    team = args.team
    
    res = svc.create_user_new(new_user_name=new_user_name, workspace_id=workspace_id, password=password,
                              user_type=user_type, email=email, job=job, nickname=nickname,
                              team=team, headers_user=header_user_name)
    return response(status=1, result=res)


# @dashboard.get("/user")
# async def get_dashboard_user(workspace_id: int, platform_type : str = TYPE.PLATFORM_FLIGHTBASE):
#     try:
#         # res = svc.get_user_dashboard_info(workspace_id, cr.check_user())
#         res = await svc.get_dashboard_user(workspace_id, cr.check_user_id())
#         return response(status=1, result=res)
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         return ce.response()
#     except Exception as e:
#         return response(status=0, message=e)


@dashboard.get("/user/sse")
async def sse_dashboard_user(
    workspace_id: int,
    request: Request,
    platform_type: str = TYPE.PLATFORM_FLIGHTBASE,
):
    try:
        user_id = get_user_id()
        return StreamingResponse(
            svc.sse_get_dashboard_user(
                workspace_id,
                user_id,
                platform_type=platform_type,
                request=request,
            ),
            media_type="text/event-stream",
        )
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message="server error", result=[])


@dashboard.get("/user")
async def get_dashboard_user_new(
    workspace_id: int, platform_type: str = TYPE.PLATFORM_FLIGHTBASE
):
    try:
        user_id = get_user_id()
        res = await svc.get_dashboard_user(
            workspace_id, user_id, platform_type
        )
        return response(status=1, result=res)
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        return response(status=0, message=e)


@dashboard.get("/user/project-items")
async def get_dashboard_user_project_items(
    workspace_id: int, platform_type: str = TYPE.PLATFORM_FLIGHTBASE
):
    try:
        res = await svc.get_dashboard_user_project_items(workspace_id, platform_type)
        return response(status=1, result=res)
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        return response(status=0, message=e)


@dashboard.get("/user/resource-usage")
async def get_dashboard_user_async(workspace_id: int):
    try:
        res = await svc.get_async_user_resource_usage_info(workspace_id)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        return response(status=0, message=e, result=dict())


# @dashboard.get("/user/resource-usage")
# def get_dashboard_user(workspace_id: int):
#     try:
#         cr = CustomResource()
#         # time.sleep(30)
#         res = svc.get_user_resource_usage_info(workspace_id)
#         return res
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         return ce.response()
#     except Exception as e:
#         return response(status=0, message=e, result=dict())


@dashboard.get("/admin/resource-usage")
def get_dashboard_user():
    try:
        # res = svc.get_admin_resource_usage_info()
        res = svc.get_admin_resource_usage_info()
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        return response(status=0, message=e)


@dashboard.get("/test")
def get_dashboard_user():
    try:
        res = svc.get_admin_resource_usage_dummy()
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        return response(status=0, message=e)
