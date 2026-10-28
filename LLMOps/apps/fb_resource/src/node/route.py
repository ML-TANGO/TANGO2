from fastapi import APIRouter
from node import model
from utils.resource import response
from utils.access_check import admin_access_check
# from utils import kube_network_attachment_definitions as kube_nad
from utils.TYPE import *
from node import node_service 
from utils import gpu_pool
from utils.redis import get_redis_client
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

@nodes.get('/gpu-availability')
def get_gpu_availability(workspace_id: int = None):
    """GPU 풀 가용량 — {total, in_use, reserved, free, nodes}.

    node-info 와 나눈 이유 둘. (1) node-info 는 관리자 화면용 큰 페이로드라 "지금 GPU 를
    잡을 수 있나" 하나만 알고 싶은 화면이 그걸 파싱하게 만들 이유가 없다. (2) 더 중요한
    건 **세는 술어가 다르다**는 것이다 — node-info 의 `used` 는 모니터링이 채우는
    `used_info` 만 보는데, external 컨테이너 잡은 GPU 를 예약 키(SETNX)로 잡고 그건
    `used_info` 를 건드리지 않는다. 그 차이를 무시하면 화면은 "가용 3장" 이라 말하고
    실행은 실패한다(실측). 그래서 두 술어를 함께 보는 utils.gpu_pool.snapshot 을 쓴다.

    소비자는 GPU 를 실제로 쓰는 런을 **만들기 전에** 가능 여부를 묻는 화면이다(평가의
    포맷 학습). 스케줄러의 GPU claim 은 대기열 없이 즉시 실패하므로, 미리 막지 않으면
    런이 만들어졌다가 failed 로 떨어져 이력만 남는다.

    workspace_id 를 주면 `workspace {hard, used, free}` 가 함께 실린다 — 사용자가
    '내 몫' 으로 이해하는 축이고 화면이 보여줄 숫자다. 다만 **실행을 막는 축은 아니다**:
    external 경로는 워크스페이스 쿼터를 읽지 않고 차트도 nvidia.com/gpu 를 요청하지
    않아 K8s ResourceQuota 의 GPU 항목이 증가하지 않는다. 실제 게이트는 클러스터
    풀(free)이므로, 화면은 workspace 로 말하고 차단은 둘 중 빡빡한 쪽을 따라야 한다.
    ⚠️ 보장이 아니라 사전 안내다(TOCTOU) — 최종 판정은 스케줄러의 원자적 claim 이다.
    """
    try:
        res = gpu_pool.snapshot(get_redis_client(), workspace_id=workspace_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e))


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
    