import os
import json
import threading
import traceback
import tracemalloc
from fastapi import FastAPI, Request, Depends
from pipeline.route import pipeline
# from utils.resource import AddHeaderMiddleware
from utils.redis import get_redis_client_async
from utils.resource import CustomMiddleWare, CustomResponse
from utils import settings


def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB PIPELINE API",
        version='0.1',
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/pipelines/openapi.json",
        docs_url="/pipelines/docs",
        redoc_url="/pipelines/redoc"
    )
    
    api.include_router(pipeline)
    app.mount('/api', api)
    
    import logging
    # 필터 적용
    class HealthCheckFilter(logging.Filter):
        def filter(self, record):
            return "GET /pipelines/healthz" not in record.getMessage()
    
    # 로깅 설정
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(HealthCheckFilter())
    
    # app.add_middleware(AddHeaderMiddleware)
    
    # 앱의 startup 이벤트 설정
    @app.on_event("startup")
    async def startup_event():
        # await initialize_redis()
        await get_redis_client_async()
    
    return app
    
def main():
    app = initialize_app()
    return app

if __name__=="__main__":
    main()
    uvicorn.run("main:app", port=8000, host='0.0.0.0', reload=True)
