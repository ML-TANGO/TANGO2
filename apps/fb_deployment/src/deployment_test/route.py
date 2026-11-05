# Deployment Simulation
from fastapi import APIRouter
from utils.resource import response
from utils.access_check import workspace_access_check
from utils.exception.exceptions import CustomErrorList
import traceback
# import logging
from deployment_test import service as svc

deployment_simulation = APIRouter(
    prefix = "/services"
)

@deployment_simulation.get("")
# @workspace_access_check()
def get_service_list(workspace_id: int = None):
    try:
        res = svc.get_simulation_list(workspace_id=workspace_id)
        return response(status=1, result={"list" : res})
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))

@deployment_simulation.get('/{service_id}')
def get_detail(service_id):
    try:
        res = svc.get_service(service_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))


# @deployment_serving_test.get('/error_log/{service_id}')
# async def get_service_detail_error(service_id):
#     """Service error log 조회 / 사용 확인 안됨 -> 막아둠"""
#     # services app 분리시 deployment 코드 처리
#     res = deployment_svc.get_error_log(deployment_id=service_id)
#     return res