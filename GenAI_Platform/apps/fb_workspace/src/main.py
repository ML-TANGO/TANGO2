from fastapi import FastAPI, Request, Depends
from workspace.route import workspaces
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
            return "GET /workspaces/healthz" not in record.getMessage()

    # 로깅 설정
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(HealthCheckFilter())

    return app

def main():
    app = initialize_app()
    return app

if __name__=="__main__":
    main()
    uvicorn.run("main:app", port=8000, host='0.0.0.0', reload=True)
