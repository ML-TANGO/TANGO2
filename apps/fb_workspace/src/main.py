from fastapi import FastAPI, Request, Depends
from workspace.route import workspaces
from utils.resource import CustomResponse
from utils.resource import CustomMiddleWare
import os
import json
import uvicorn
import logging
from utils.connection_manager import connection_manager

logger = logging.getLogger("workspace-server")

def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB WORKSPACE API",
        version='0.1',
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/workspaces/openapi.json",
        docs_url="/workspaces/docs",
        redoc_url="/workspaces/redoc"
    )

    api.include_router(workspaces)
    app.mount('/api', api)

    import logging
    # 필터 적용
    class HealthCheckFilter(logging.Filter):
        def filter(self, record):
            return "GET /api/workspaces/healthz" not in record.getMessage()
    
    # 로깅 설정
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(HealthCheckFilter())

    @app.on_event("startup")
    async def startup_event():
        try:
            await connection_manager.get_redis_client()
        except Exception as e:
            logger.warning(f"초기 Redis 연결 실패: {str(e)}")

    return app
    
def main():
    app = initialize_app()
    return app

if __name__=="__main__":
    app = main()
    uvicorn.run(app, port=8000, host='0.0.0.0', reload=True)
