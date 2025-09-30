from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, APIRouter, Request
# from fastapi.responses import HTMLResponse

from utils.redis import get_redis_client
from utils import settings, TYPE, PATH
from utils.resource import CustomResponse, CustomMiddleWare

from notification.route import notification, collection_init
from progress.route import progress
import uvicorn

def main():
    app = FastAPI()
    api = FastAPI(
        title="JFB API",
        version='0.1',
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/notification/openapi.json",
        docs_url="/notification/docs",
        redoc_url="/notification/redoc"
    )
    api.include_router(progress)
    api.include_router(notification)

    app.mount('/api', api)
    collection_init()

    import logging
    # 필터 적용
    class HealthCheckFilter(logging.Filter):
        def filter(self, record):
            return "GET /notification/healthz" not in record.getMessage()

    # 로깅 설정
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(HealthCheckFilter())

    return app


if __name__ == "__main__":
    app = main()

    uvicorn.run(app, host="0.0.0.0", port=8000)
