from fastapi import FastAPI
from dashboard.route import dashboard
from dashboard.service import set_dashboard_user #initialize_redis #, test,
import threading
from utils.resource import CustomResponse
from utils.resource import CustomMiddleWare
import os
import json

def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB API",
        version='0.1',
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/dashboard/openapi.json",
        docs_url="/dashboard/docs",
        redoc_url="/dashboard/redoc"
    )

    api.include_router(dashboard)

    app.mount('/api', api)
    # 앱의 startup 이벤트 설정
    # @app.on_event("startup")
    # def startup_event():
    #     initialize_redis()

    import logging
    # 필터 적용
    class HealthCheckFilter(logging.Filter):
        def filter(self, record):
            return "GET /dashboard/healthz" not in record.getMessage()

    # 로깅 설정
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(HealthCheckFilter())

    return app

def main():
    app = initialize_app()
    # t=threading.Thread(target=test)
    # t.daemon=True
    # t.start()
    set_dashboard_user_thread=threading.Thread(target=set_dashboard_user)
    set_dashboard_user_thread.daemon=True
    set_dashboard_user_thread.start()
    return app

if __name__=="__main__":
    main()
    uvicorn.run("main:app", port=8000, host='0.0.0.0', reload=True)