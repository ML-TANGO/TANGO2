from fastapi import FastAPI
# from deployment_template.route import deployments_template
# from deployment_worker.route import deployments_worker
# from deployment_options.route import deployments_options
# from deployment_worker.route_new import deployments_worker as deployments_worker_new
from deployment.route import deployments as deployment
from deployment_test.route import deployment_simulation

from utils.resource import CustomResponse
from utils.resource import CustomMiddleWare
# from utils.scheduler_init import initialize_scheduler
import os
import json
import threading
import logging
import uvicorn

def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB DEPLOYMENT API",
        version='0.1',
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/deployments/openapi.json",
        docs_url="/deployments/docs",
        redoc_url="/deployments/redoc",
        # swagger_ui_parameters={"jf-user": "root"}
    )
    
    # 순서 테스트
    # api.include_router(deployment_serving_test, tags=['service test'])
    api.include_router(deployment_simulation)
    api.include_router(deployment)
    # api.include_router(deployments_worker_new, tags=["deployment worker new"])
    # api.include_router(deployments_worker, tags=["deployment/worker"])
    # api.include_router(deployments_options, tags=["deployments/options"])
    # api.include_router(deployments)
    app.mount('/api', api)

    import logging
    # 필터 적용
    class HealthCheckFilter(logging.Filter):
        def filter(self, record):
            return "GET /deployments/healthz" not in record.getMessage()
    
    # 로깅 설정
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(HealthCheckFilter())
    return app

def main():
    app = initialize_app()
    # initialize_scheduler()
    # thread.start()
    return app

if __name__=="__main__":
    app = main()
    uvicorn.run(app, port=8000, host='0.0.0.0', reload=True)