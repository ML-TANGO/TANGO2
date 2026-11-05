import os
import json
import threading
import traceback
import time
import uvicorn
from fastapi import FastAPI, Request, Depends
from user.route import users
from login.route import login
from logout.route import logout
from utils.resource import CustomResponse
from utils.resource import CustomMiddleWare

# def other_work():
#     # import utils.kube_certs as kube_certs
#     while (1):
#         try:
#             delete_expired_login_sessions()
#             # kube_certs.auto_update_jf_kube_cert() # 9 year certs 생성 시 불필요
#             time.sleep(10)
#         except Exception as e:
#             traceback.print_exc()

# def initialize_other_work_thr():
#     other_work_thr = threading.Thread(target=other_work)
#     other_work_thr.start()

def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB USER API",
        version='0.1',
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/users/openapi.json",
        docs_url="/users/docs",
        redoc_url="/users/redoc"
    )
    
    # initialize_other_work_thr()
    
    api.include_router(users)
    api.include_router(login)
    api.include_router(logout)
    
    app.mount('/api', api)

    import logging
    # 필터 적용
    class HealthCheckFilter(logging.Filter):
        def filter(self, record):
            return "GET /api/users/healthz" not in record.getMessage()
    
    # 로깅 설정
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(HealthCheckFilter())

    return app
    
def main():
    app = initialize_app()
    return app

if __name__=="__main__":
    app = main()
    uvicorn.run(app, port=8000, host='0.0.0.0', reload=True)
