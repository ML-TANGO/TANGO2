from fastapi import APIRouter, Depends, FastAPI, Request, HTTPException
from pydantic import BaseModel

from dashboard import service as svc
# from dashboard.service import workspace_user_info
from utils.resource import response, CustomResource, token_checker, def_token_checker
from utils.access_check import workspace_access_check
from utils.exceptions import *

import time

dashboard = APIRouter(
    prefix = "/dashboard"
)

from fastapi.responses import JSONResponse
@dashboard.get("/healthz")
async def healthz():
    return JSONResponse(status_code=200, content={"status": "healthy"})

@dashboard.get("/admin")
@def_token_checker
def get_dashboard_admin():
    try:
        res = svc.get_admin_dashboard_info()
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        return response(status=0, message=e)

# @dashboard.get("/resource-info")
# @token_checker
# async def get_dashboard_admin_resource_info():
#     try:
#         res = svc.get_dashboard_admin_resource_info()
#         return res
#     except CustomErrorList as ce:
#         traceback.print_exc()
#         return ce.response()
#     except Exception as e:
#         return response(status=0, message=e)

@dashboard.get("/user")
# @def_token_checker
# @def_workspace_access_check() # @workspace_access_check(dashboard_parser)
def get_dashboard_user(workspace_id: int):
    try:
        cr = CustomResource()
        # res = svc.get_user_dashboard_info(workspace_id, cr.check_user())
        res = svc.get_dashboard_user(workspace_id, cr.check_user_id())
        return response(status=1, result=res)
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        return response(status=0, message=e)

@dashboard.get("/user/resource-usage")
@def_token_checker
# @workspace_access_check() # @workspace_access_check(dashboard_parser)
def get_dashboard_user(workspace_id: int):
    try:
        cr = CustomResource()
        # time.sleep(30)
        res = svc.get_user_resource_usage_info(workspace_id)
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        return response(status=0, message=e, result=dict())

@dashboard.get("/admin/resource-usage")
@def_token_checker
# @workspace_access_check() # @workspace_access_check(dashboard_parser)
def get_dashboard_user():
    try:
        cr = CustomResource()
        # res = svc.get_admin_resource_usage_info()
        res = svc.get_admin_resource_usage_info()
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        return response(status=0, message=e)


@dashboard.get("/test")
# @token_checker
# @workspace_access_check() # @workspace_access_check(dashboard_parser)
def get_dashboard_user():
    try:
        cr = CustomResource()
        res = svc.get_admin_resource_usage_dummy()
        return res
    except CustomErrorList as ce:
        traceback.print_exc()
        return ce.response()
    except Exception as e:
        return response(status=0, message=e)

