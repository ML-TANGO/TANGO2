from fastapi import FastAPI, Request, Depends
from upload.route import upload
from dataset.route import dataset
from download.route import download
from upload.service import upload_progress_check
from utils.resource import CustomResponse
from utils.resource import CustomMiddleWare
# from utils.settings import JF_ETC_DIR
import threading
from utils.connection_manager import connection_manager
import logging

logger = logging.getLogger("dataset-server")

def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB DATASET API",
        version='0.1',
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/datasets/openapi.json",
        docs_url="/datasets/docs",
        redoc_url="/datasets/redoc"
    )
    
    api.include_router(upload)
    api.include_router(dataset)
    api.include_router(download)

    app.mount('/api', api)
    
    import logging
    # 필터 적용
    class HealthCheckFilter(logging.Filter):
        def filter(self, record):
            return "GET /datasets/healthz" not in record.getMessage()
    
    # 로깅 설정
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(HealthCheckFilter())

    @app.on_event("startup")
    async def startup_event():
        try:
            await connection_manager.get_redis_client()
        except Exception as e:
            logger.warning(f"초기 Redis 연결 실패: {str(e)}")
    
    return app
    
def main():
    app = initialize_app()
    upload_check = threading.Thread(target=upload_progress_check)
    upload_check.start()
    return app

import uvicorn
if __name__=="__main__":
    app = main()
    uvicorn.run(app, port=8000, host='0.0.0.0', reload=True)