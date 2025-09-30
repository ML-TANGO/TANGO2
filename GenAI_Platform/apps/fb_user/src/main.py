import os
import json
import threading
import traceback
import time
from fastapi import FastAPI, Request, Depends
from user.route import users #, users_limit, users_group
from login.route import login
from logout.route import logout
from utils.resource import CustomResponse
from utils.resource import CustomMiddleWare
from utils.settings import JF_ETC_DIR, JF_INIT_ROOT_PW
from user.service import user_passwd_change
# from utils.db import delete_expired_login_sessions

# def init_copy_etc():
#     if os.system(f"ls {JF_ETC_DIR}/shadow") == 0:
#         print('COPY ETC_HOST')
#         os.system("cp {etc_host}/group {etc_host}/gshadow {etc_host}/passwd {etc_host}/shadow /etc/".format(etc_host=JF_ETC_DIR)) # BACKUP DATA TO DOCKER
#     else :
#         print('SET ROOT ETC_HOST')
#         user_passwd_change("root", JF_INIT_ROOT_PW, decrypted=True)
#         os.system('cp /etc/group /etc/gshadow /etc/passwd /etc/shadow {etc_host}/'.format(etc_host=JF_ETC_DIR))

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
        title="JFB API",
        version='0.1',
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/users/openapi.json",
        docs_url="/users/docs",
        redoc_url="/users/redoc"
    )

    # init_copy_etc()
    # initialize_other_work_thr()

    api.include_router(users)
    # api.include_router(users_group)
    # api.include_router(users_limit)
    api.include_router(login)
    api.include_router(logout)

    app.mount('/api', api)

    import logging
    # 필터 적용
    class HealthCheckFilter(logging.Filter):
        def filter(self, record):
            return "GET /users/healthz" not in record.getMessage()

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
