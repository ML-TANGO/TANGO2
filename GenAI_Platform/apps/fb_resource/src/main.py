from fastapi import FastAPI
from node.route import nodes
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
        try:
            await connection_manager.get_redis_client()
        except Exception as e:
            import logging
            logger = logging.getLogger("resource-server")
            logger.warning(f"초기 Redis 연결 실패: {str(e)}")
    
    return app
    
def main():
    app = initialize_app()
    # initialize_scheduler()
    return app

if __name__=="__main__":
    app = main()
    uvicorn.run(app, port=8000, host='0.0.0.0', reload=True)