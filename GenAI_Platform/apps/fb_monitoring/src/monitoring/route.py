from fastapi import APIRouter, Depends
from monitoring import monitoring_service as svc
# from monitoring import model
from utils.resource import response
from utils.access_check import admin_access_check
# from utils import kube_network_attachment_definitions as kube_nad
from utils.TYPE import *

# monitoring = APIRouter(
#     prefix = "/monitoring"
# )

# @monitoring.get("/init-test")
# async def test2():
#     res = svc.test()
#     return res

# @monitoring.get("/storage_info")
# async def get_storage_info():
#     res = response(status=1, result=svc.get_storage_usage_info())
#     return svc.get_storage_usage_info()

# @monitoring.get("/workspace_info")
# async def get_workspace_info():
#     res = response(status=1, result=svc.get_workspace_usage())
#     return res

# @monitoring.get("/get_workspace_path")
# async def update_workspace_path(args: model.GetModel = Depends()):
#     res = svc.get_workspace_path(workspace_name=args.workspace_name)
#     return res