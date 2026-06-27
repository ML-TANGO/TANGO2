from fastapi import APIRouter, Query
from starlette.concurrency import run_in_threadpool
from typing import Optional

from edge import model
from edge import edge_service
from utils.resource import response
from utils.access_check import admin_access_check
import traceback

# SP-8 / 수용계획서 3.1 — Edge 워커 노드 + 커스텀 레이블. 노드 관리와 동일하게 admin.
# edge_service 는 sync(requests + pymysql) — async 라우트에서 직접 호출하면 이벤트루프를
# 막으므로(특히 register→refresh 의 최대 5s 폴링) run_in_threadpool 로 오프로드.
edge = APIRouter(prefix="/edge")


@edge.post('/workers')
@admin_access_check()
async def register_worker(body: model.RegisterEdgeWorkerModel):
    try:
        res = await run_in_threadpool(edge_service.register_edge_worker, body)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.get('/workers')
@admin_access_check()
async def list_workers():
    try:
        res = await run_in_threadpool(edge_service.list_edge_workers)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.get('/workers/{worker_id}')
@admin_access_check()
async def get_worker(worker_id: int):
    try:
        res = await run_in_threadpool(edge_service.get_edge_worker, worker_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.post('/workers/{worker_id}/refresh')
@admin_access_check()
async def refresh_worker(worker_id: int):
    # remoteManager /metrics 폴링 → 연결상태/자원/배포 갱신 (blocking → threadpool).
    try:
        res = await run_in_threadpool(edge_service.refresh_edge_worker, worker_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.post('/workers/{worker_id}/deploy')
@admin_access_check()
async def deploy_worker(worker_id: int, body: model.DeployEdgeModel):
    # SP-6 / 3.10 — 양자화 패키지를 Edge 워커에 remoteManager /ops 로 배포 (blocking → threadpool).
    try:
        res = await run_in_threadpool(edge_service.deploy_edge_worker, worker_id, body)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


# ── 통합 파이프라인 s2s (llm_deploy edge 노드) ────────────────────────────────
# fb_pipeline 런타임이 호출 — admin 세션이 없으므로 admin_access_check 미적용.
# 위 admin deploy/get 과 동일 서비스 함수를 재사용하되 게이트만 s2s 로 연다
# (llm_playground pipeline-deploy 선례와 동형). 클러스터 내부 DNS 전용.
@edge.post('/workers/{worker_id}/pipeline-deploy')
async def pipeline_deploy_worker(worker_id: int, body: model.DeployEdgeModel):
    try:
        res = await run_in_threadpool(edge_service.deploy_edge_worker, worker_id, body)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.get('/workers/{worker_id}/pipeline-status')
async def pipeline_status_worker(worker_id: int):
    # 배포 노드 폴러용 — refresh 가 remoteManager /metrics 를 폴링해 deploying→running/error
    # 를 확정한다(deploy 가 202 async 면 deploy_state=deploying 으로 남으므로).
    try:
        res = await run_in_threadpool(edge_service.refresh_edge_worker, worker_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.delete('/workers/{worker_id}')
@admin_access_check()
async def delete_worker(worker_id: int):
    try:
        res = await run_in_threadpool(edge_service.delete_edge_worker, worker_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


# ── 커스텀 레이블 (노드 + 엣지워커 공용) ──────────────────────────────────────

@edge.post('/labels')
@admin_access_check()
async def upsert_label(body: model.CustomLabelModel):
    try:
        res = await run_in_threadpool(edge_service.upsert_label, body)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.get('/labels')
@admin_access_check()
async def list_labels(target_type: Optional[str] = Query(default=None),
                      target_id: Optional[str] = Query(default=None)):
    try:
        res = await run_in_threadpool(edge_service.list_labels, target_type, target_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)


@edge.delete('/labels/{label_id}')
@admin_access_check()
async def delete_label(label_id: int):
    try:
        res = await run_in_threadpool(edge_service.delete_label, label_id)
        return response(status=1, result=res)
    except Exception as e:
        traceback.print_exc()
        return response(status=0, message=str(e), result=None)
