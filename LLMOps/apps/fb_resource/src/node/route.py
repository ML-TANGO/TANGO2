from fastapi import APIRouter
from node import model
from utils.resource import response
from utils.access_check import admin_access_check
# from utils import kube_network_attachment_definitions as kube_nad
from utils.TYPE import *
from node import node_service 
import traceback

nodes = APIRouter(
    prefix = "/nodes"
)

@nodes.post('/active')
@admin_access_check()
async def get_node_list(body: model.PostActiveNodeModel):

    res = node_service.set_node_active(node_id = body.node_id, active = body.active)
    # res = node_service.server_type()
    # db.request_logging(self.check_user(), 'nodes', 'get', None, res['status'])
    return res

@nodes.get('/node-info')
def get_node_info():
    try:
        res = node_service.get_node_resource_info()
        return res
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))


# ==================================================================================
from node import service_instance as svc_instance
from typing import List, Annotated, Optional
from fastapi import Body


@nodes.post("/instance-validation")
async def post_instance_validation(body: model.GetNodeInstanceModel):
    try:
        res = svc_instance.get_instance_validation(**body.dict())
        return res
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))
@nodes.get("/instance")
async def get_instance_list(node_id: int):
    try:
        res = svc_instance.get_instance_list(node_id)
        return res
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))
    
@nodes.put("/instance")
async def put_instance_list(body: model.PutInstanceModel):
    try:
        res = svc_instance.update_instance_list(node_id=body.node_id, 
                instance_list=body.instance_list)
        return response(status=1, result="ok")
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))
    