"""llm_data_pipeline — LLM · VLM 학습 데이터 파이프라인 서비스 (LLM 도메인 MSA).

업로드 → 전처리 → 필터 → 생성 → VLM 심사 → 사람 검수 → 분포 분석 → 구성·분할 →
버전 릴리스까지를 한 서비스가 관장한다. 컴퓨트(실제 전처리·생성·심사 잡)는 직접
돌리지 않고 외부 컨테이너에 위임하며, 여기서는 구성·판정·영속화를 맡는다.
llm_evaluation / llm_model / llm_playground 와 동일한 FastAPI 팩토리 패턴.
"""
import logging

import uvicorn
from fastapi import FastAPI

from data_pipeline.route import data_pipelines
from utils.resource import CustomResponse, CustomMiddleWare


def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB DATA PIPELINE API",
        version="0.1",
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/data-pipelines/openapi.json",
        docs_url="/data-pipelines/docs",
        redoc_url="/data-pipelines/redoc",
    )
    api.include_router(data_pipelines)
    app.mount("/api", api)

    # 헬스체크가 접근 로그를 가득 채우면 실제 요청이 묻힌다.
    class HealthCheckFilter(logging.Filter):
        def filter(self, record):
            return "GET /data-pipelines/healthz" not in record.getMessage()

    logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())
    return app


def main():
    logging.getLogger(__name__).info("llm_data_pipeline starting")
    return initialize_app()


if __name__ == "__main__":
    uvicorn.run(main(), port=8000, host="0.0.0.0", reload=True)
