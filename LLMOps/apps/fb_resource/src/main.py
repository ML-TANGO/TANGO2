from fastapi import FastAPI
from node.route import nodes
from edge.route import edge
# from pod.route import pod
# from gpu.route import gpu
# from option.route import options
# from network.route import networks
from storage.route import storage
from records.route import records

from utils.resource import CustomResponse
from utils.resource import CustomMiddleWare
# from utils.scheduler_init import initialize_scheduler
import uvicorn
from utils.connection_manager import connection_manager


def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB RESOURCE API",
        version='0.1',
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/resources/openapi.json",
        docs_url="/resources/docs",
        redoc_url="/resources/redoc"
    )

    api.include_router(nodes, tags=["nodes"])
    api.include_router(edge, tags=["edge"])
    # api.include_router(pod, tags=["pod"])
    # api.include_router(gpu, tags=["gpu"])
    # api.include_router(options, tags=["options"])
    # api.include_router(networks, tags=["networks"])
    api.include_router(storage, tags=["storage"])
    api.include_router(records, tags=["records"] )

    # Health check endpoint
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse
    
    health_router = APIRouter(prefix="/resources")
    
    @health_router.get("/healthz")
    async def healthz():
        try:
            await connection_manager.get_redis_client()
            return JSONResponse(status_code=200, content={"status": "healthy", "redis_healthy": connection_manager.redis_healthy})
        except Exception as e:
            return JSONResponse(status_code=503, content={"status": "unhealthy", "redis_healthy": False, "error": str(e)})
    
    api.include_router(health_router)
    app.mount('/api', api)
    
    import logging
    # 필터 적용
    class HealthCheckFilter(logging.Filter):
        def filter(self, record):
            return "GET /resources/healthz" not in record.getMessage()
    
    # 로깅 설정
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(HealthCheckFilter())

    @app.on_event("startup")
    async def startup_event():
        import logging
        logger = logging.getLogger("resource-server")
        # 후행 추가 컬럼 멱등 보정. schema.sql 두 파일은 CREATE TABLE IF NOT EXISTS
        # 안쪽이라 **기존 설치에는 새 컬럼이 생기지 않고**, 이 리포에는 마이그레이션
        # 러너가 없다(apps/*/migrations 는 아무도 실행하지 않음). last_heartbeat_at 이
        # 없으면 heartbeat UPDATE 가 실패해 record_heartbeat 가 전건 거부되고
        # (→ last_seen 정지 → 300초 후 전 디바이스 offline) 그 사실이 조용히 묻힌다.
        # 기동 시 여기서 메운다. never fatal — 보정 실패가 CrashLoop 이 되면 안 된다.
        # ⚠️ 이 보정은 replicas=1 을 전제한다(devops/fb_resource/helm/templates/
        #    deployment.yaml 에 리터럴로 박혀 있음). 스케일아웃하면 동시 기동 ALTER 가
        #    Galera TOI 락에서 경쟁하므로, 그 전제가 사라지는 순간 재검토해야 한다.
        try:
            from utils.msa_db import db_edge
            res = db_edge.ensure_edge_worker_schema()
            # 실패를 성공과 구분해 올린다 — 삼키면 컬럼 없는 서비스가 조용히 계속
            # 살아 heartbeat 가 전건 실패한다(그게 이 보정이 막으려던 상태다).
            if res.get("failed"):
                logger.warning(
                    "edge_worker 스키마 보정 실패 — heartbeat 영속이 깨질 수 있음: "
                    f"{res['failed']} (적용됨: {res.get('applied')})"
                )
            else:
                logger.info(f"edge_worker 스키마 보정: 적용 {res.get('applied')}")
        except Exception as e:
            logger.warning(f"edge_worker 스키마 보정 호출 실패(계속 진행): {str(e)}")
        try:
            await connection_manager.get_redis_client()
        except Exception as e:
            logger.warning(f"초기 Redis 연결 실패: {str(e)}")
    
    return app
    
def main():
    app = initialize_app()
    # initialize_scheduler()
    return app

if __name__=="__main__":
    app = main()
    uvicorn.run(app, port=8000, host='0.0.0.0', reload=True)