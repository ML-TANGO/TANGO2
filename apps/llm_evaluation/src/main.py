"""llm_evaluation — 평가 오케스트레이션 서비스 (LLM 도메인 MSA).

평가 런(벤치마크 → P2 judge → P3 전문가)을 오케스트레이션한다. 컴퓨트는 직접 하지
않고 job_type=evaluate 외부 컨테이너(P1a mock / apps/evaluate 실측 / 고려대 plugin)에
위임하며, fb_external_container 런치 + eval_result 영속화(fb_utils.llm_db)를 재사용한다.
llm_playground/llm_model 과 동일한 FastAPI 팩토리 패턴.
"""
import asyncio
import logging

import uvicorn
from fastapi import FastAPI

from evaluation.route import evaluations
from evaluation.service import finalize_finished_runs_loop
from utils.resource import CustomResponse, CustomMiddleWare


def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB EVALUATION API",
        version="0.1",
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/evaluations/openapi.json",
        docs_url="/evaluations/docs",
        redoc_url="/evaluations/redoc",
    )
    api.include_router(evaluations)
    app.mount("/api", api)

    # 끝난 평가 런의 백그라운드 마감(결과 화면을 아무도 열지 않아도 metrics.json 이 생긴 런을
    # completed 로) — 루프 한 바퀴의 실패는 루프 안에서 삼키므로 서비스 기동을 막지 않는다.
    finalize_task = {}

    @app.on_event("startup")
    async def start_finalize_loop():
        finalize_task["task"] = asyncio.create_task(finalize_finished_runs_loop())

    @app.on_event("shutdown")
    async def stop_finalize_loop():
        task = finalize_task.get("task")
        if task:
            task.cancel()

    return app


def main():
    logging.getLogger(__name__).info("llm_evaluation starting")
    app = initialize_app()
    return app


if __name__ == "__main__":
    app = main()
    uvicorn.run(app, port=8000, host="0.0.0.0", reload=True)
