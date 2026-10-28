from fastapi import FastAPI, Request, Depends
from analyzer.route import analyzer
from utils.redis import get_redis_client_async
from utils.resource import CustomMiddleWare
import uvicorn

# 전역 Redis 클라이언트 변수
# redis_client = None

def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB ANALYZER API",
        version='0.1',
        # default_response_class=CustomResponse,
        middleware=CustomMiddleWare, # TODO starlette 0.41.3 이상에서는 사용 못함
        openapi_url="/analyzer/openapi.json",
        docs_url="/analyzer/docs",
        redoc_url="/analyzer/redoc"
    ) 
    # api.add_middleware(CustomMiddleWare)
    api.include_router(analyzer)
    
    app.mount('/api', api)

    import logging
    # 필터 적용
    class HealthCheckFilter(logging.Filter):
        def filter(self, record):
            return "GET /analyzer/healthz" not in record.getMessage()
    
    # 로깅 설정
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(HealthCheckFilter())
    
    # 앱의 startup 이벤트 설정
    @app.on_event("startup")
    async def startup_event():
        await get_redis_client_async()
    return app
    
def main():
    app = initialize_app()
    return app

if __name__=="__main__":
    app = main()
    uvicorn.run(app, port=8000, host='0.0.0.0', reload=True)
    