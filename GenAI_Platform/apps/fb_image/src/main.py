from fastapi import FastAPI
from image.route import images
# from image.status import status_check
from utils.resource import CustomResponse
from utils.resource import CustomMiddleWare
import os
import json
import logging
import traceback
import threading
from utils.common import run_func_with_print_line
from init import init_default_image
import uvicorn

def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB IMAGE API",
        version='0.1',
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/images/openapi.json",
        docs_url="/images/docs",
        redoc_url="/images/redoc",
        # redirect_slashes=True,
    )
    api.include_router(images)
    
    app.mount('/api', api)

    import logging
    # 필터 적용
    class HealthCheckFilter(logging.Filter):
        def filter(self, record):
            return "GET /images/healthz" not in record.getMessage()
    
    # 로깅 설정
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(HealthCheckFilter())

    return app

def main():
    # image_status_thread = threading.Thread(target=status_check, daemon=True)
    # image_status_thread.start()
    run_func_with_print_line(func=init_default_image, line_message="INIT DEFAULT IMAGE")
    # run_func_with_print_line(func=set_image_namespace, line_message="SET IMAGE NAMESPACE")
    app = initialize_app()
    # start_refresh_loop()
    return app


if __name__=="__main__":
    app = main()
    uvicorn.run(app, port=8000, host='0.0.0.0', reload=True)