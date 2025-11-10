import os
import json
import threading
import traceback
from fastapi import FastAPI, Request, Depends
from huggingface_hub import HfFolder
from model.route import model
from utils.resource import CustomResponse
from utils.redis import get_redis_client_async
from utils.resource import CustomMiddleWare
from utils import settings
import uvicorn


def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB MODEL API",
        version='0.1',
        # default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/models/openapi.json",
        docs_url="/models/docs",
        redoc_url="/models/redoc"
    )
    # 허깅페이스 토큰을 여기에 입력하세요
    hf_token = settings.HUGGINGFACE_TOKEN
    # 토큰 설정 및 저장
    HfFolder.save_token(hf_token)
    
    api.include_router(model)
    app.mount('/api', api)

    
    import logging
    # 필터 적용
    class HealthCheckFilter(logging.Filter):
        def filter(self, record):
            return "GET /models/healthz" not in record.getMessage()
    
    # 로깅 설정
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(HealthCheckFilter())
    
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
    app = main()
    uvicorn.run(app, port=8000, host='0.0.0.0', reload=True)
