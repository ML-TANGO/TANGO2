from fastapi import FastAPI, Request, Depends
from utils.resource import CustomResponse
from utils.resource import CustomMiddleWare
# from utils.settings import JF_ETC_DIR
from collect.route import collect
import threading
import traceback
from utils.connection_manager import connection_manager
import asyncio
import logging
import random

logger = logging.getLogger("collect-server")

def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB COLLECT API",
        version='0.1',
        # default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/collect/openapi.json",
        docs_url="/collect/docs",
        redoc_url="/collect/redoc"
    )
    
    api.include_router(collect)
    app.mount('/api', api)

    import logging
    # 필터 적용
    class HealthCheckFilter(logging.Filter):
        def filter(self, record):
            return "GET /collect/healthz" not in record.getMessage()
    
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
    try:
        app = initialize_app()
        return app
    except:
        traceback.print_exc()

if __name__=="__main__":
    main()
    uvicorn.run("main:app", port=8000, host='0.0.0.0', reload=True)
