import os
import json
import logging
import threading
import traceback
from fastapi import FastAPI, Request, Depends
from huggingface_hub import login
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
    # 허깅페이스 토큰: values_tango2.yaml → jfb-settings ConfigMap → env 로 주입.
    # offline/nexus 모드에서는 비어 있을 수 있으므로 빈 값이면 login 자체를 스킵한다.
    hf_token = settings.HUGGINGFACE_TOKEN
    if hf_token:
        try:
            login(token=hf_token, add_to_git_credential=False)
        except Exception as exc:
            logging.getLogger(__name__).warning("Hugging Face login failed: %s", exc)
    else:
        logging.getLogger(__name__).info(
            "HUGGINGFACE_TOKEN not set; skipping Hugging Face login (offline mode)"
        )
    
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
