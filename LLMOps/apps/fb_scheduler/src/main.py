# from scheduler.scheduler_update import pod_start_new #, workspace_item_pod_check
# import threading



# def main():
    
#     # workspace_item_thread = threading.Thread(target=workspace_item_pod_check)
#     pod_start_thread = threading.Thread(target=pod_start_new)
#     # workspace_item_thread.start()
#     pod_start_thread.start()


# if __name__=="__main__":
#     main()

from scheduler.scheduler import run_scheduler, create_topic
from scheduler.dto import ExternalPodInfo
from scheduler.external_run import create_external_pod
from scheduler.helm_run import delete_helm_external
from utils import topic_key
import threading
import time
import asyncio
import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from utils.connection_manager import connection_manager

logger = logging.getLogger("scheduler-server")

# Health check FastAPI app
health_app = FastAPI()

@health_app.get("/health")
async def health_check():
    try:
        await connection_manager.get_redis_client()
        return JSONResponse(status_code=200, content={"status": "healthy", "redis_healthy": connection_manager.redis_healthy})
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "redis_healthy": False, "error": str(e)})

@health_app.get("/ready")
async def readiness_check():
    try:
        await connection_manager.get_redis_client()
        return JSONResponse(status_code=200, content={"status": "ready", "redis_healthy": connection_manager.redis_healthy})
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "not ready", "redis_healthy": False, "error": str(e)})


# ── External container s2s endpoints (called by apps/fb_external_container) ──
# A thin HTTP shim around the existing external_run / helm_run functions.
# Kafka-based triggering is the long-term pattern (consistent with the rest
# of fb_scheduler), but HTTP keeps the SP-Ext.8 lifecycle simple while we
# bring the new external container path up; swap to a topic later via the
# same SchedulerClient interface on the caller side.

class ExternalUninstallRequest(BaseModel):
    helm_release: str = Field(min_length=1)
    namespace: str = Field(min_length=1)


@health_app.post("/external/launch")
async def external_launch(pod_info: ExternalPodInfo):
    """Run helm install for an external partner container."""
    ok, msg = create_external_pod(pod_info)
    if not ok:
        raise HTTPException(status_code=500, detail=f"helm install failed: {msg}")
    return {"ok": True, "stdout": msg}


@health_app.post("/external/uninstall")
async def external_uninstall(payload: ExternalUninstallRequest):
    """Run helm uninstall to clean up an external partner release."""
    ok, msg = delete_helm_external(payload.helm_release, payload.namespace)
    if not ok:
        raise HTTPException(status_code=500, detail=f"helm uninstall failed: {msg}")
    return {"ok": True, "stdout": msg}

def run_health_server():
    """Health check 서버를 별도 스레드에서 실행"""
    uvicorn.run(health_app, host="0.0.0.0", port=8000)

def main():
    # Health check 서버 시작
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    # Redis 연결 초기화 시도
    async def init_redis():
        try:
            await connection_manager.get_redis_client()
        except Exception as e:
            logger.warning(f"초기 Redis 연결 실패: {str(e)}")
    
    # 비동기 초기화 실행
    asyncio.run(init_redis())

    # # 스레드 1: Kafka Consumer
    # t1 = threading.Thread(target=run_kafka_consumer, daemon=True)
    # t1.start()
    create_topic([topic_key.SCHEDULER_TOPIC])
    # 스레드 2: Scheduler
    t2 = threading.Thread(target=run_scheduler, daemon=True)
    t2.start()

    # 메인 스레드를 계속 살려두기
    while True:
        time.sleep(3600)


if __name__=="__main__":
    main()