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
from utils import topic_key
import threading
import time
import asyncio
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
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