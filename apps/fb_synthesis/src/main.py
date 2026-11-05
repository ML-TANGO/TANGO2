from fastapi import FastAPI
from synthesis.route import synthesis
from utils.redis import get_redis_client_async
from utils.resource import CustomMiddleWare
import uvicorn


def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB SYNTHESIS API",
        version='0.1',
        middleware=CustomMiddleWare,
        openapi_url="/synthesis/openapi.json",
        docs_url="/synthesis/docs",
        redoc_url="/synthesis/redoc"
    )
    api.include_router(synthesis)

    app.mount('/api', api)

    import logging
    class HealthCheckFilter(logging.Filter):
        def filter(self, record):
            return "GET /synthesis/healthz" not in record.getMessage()

    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(HealthCheckFilter())

    @app.on_event("startup")
    async def startup_event():
        await get_redis_client_async()
    return app


def main():
    app = initialize_app()
    return app


if __name__ == "__main__":
    app = main()
    uvicorn.run(app, port=8000, host='0.0.0.0', reload=True)
