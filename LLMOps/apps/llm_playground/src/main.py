import os
import json
import logging
import threading
import traceback
import uvicorn
from fastapi import FastAPI, Request, Depends
from playground.route import playgrounds
from utils.resource import CustomResponse, CustomMiddleWare
from huggingface_hub import login
from utils import settings
from utils import TYPE
from utils.msa_db.db_base import get_db
from utils.msa_db import db_user, db_image
from huggingface_hub import HfApi, hf_hub_download

def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB PLAYGROUND API",
        version='0.1',
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/playgrounds/openapi.json",
        docs_url="/playgrounds/docs",
        redoc_url="/playgrounds/redoc"
    )
    api.include_router(playgrounds)
    app.mount('/api', api)

    @app.on_event("startup")
    async def _resume_prompt_optimizations():
        # 진행 중이던 프롬프트 최적화의 폴링을 재개한다. 파드가 재시작하면 폴러가
        # 사라지고, 그 job 의 산출물은 컨테이너 TTL 과 함께 영구 유실된다
        # (external_container 의 startup_recovery 와 같은 이유·같은 관행).
        # 어떤 실패도 기동을 막지 않는다.
        try:
            from playground.service import recover_prompt_optimizations
            await recover_prompt_optimizations()
        except Exception:
            traceback.print_exc()

    return app

def set_llm_deployment_image():
    with get_db() as conn:
        user_id = db_user.get_user(user_name='admin').get("id")
        # [멀티엔진] 지원 서빙 엔진 배포 이미지를 image 테이블에 시드/정합.
        #   create_deployment 의 get_image_id_by_real_name 조회가 성공하려면 각 엔진 이미지가
        #   현재 레지스트리(real_name)로 등록돼 있어야 함 — 미등록/드리프트 시 배포 시점 crash.
        #   레지스트리 IP 변경(클러스터 마이그레이션) 등으로 real_name 이 바뀌면 같은 name 행을
        #   UPDATE 해 자가복구(옛 real_name 잔존 → vllm 배포 crash 재발 방지). 엔진별 격리.
        for _engine, _img in settings.SERVING_ENGINE_IMAGE_MAP.items():
            try:
                real_name = f"{settings.DOCKER_REGISTRY_URL}{_img}"
                # 이미 현재 real_name 으로 등록됨 → skip. (헬퍼는 DB 예외 시 (False,e) 튜플 반환 →
                #   dict 매칭일 때만 skip; tuple(DB오류)/None(미등록)은 아래 시드/정합으로 진행)
                if isinstance(db_image.get_image_id_by_real_name(real_name=real_name), dict):
                    continue
                name = "JBI_LLM_Deployment_image" if _engine == "vllm" else f"JBI_LLM_Deployment_image_{_engine}"
                cur = conn.cursor()
                # name 은 전역 UNIQUE 라, 시스템 예약명을 사용자가 선점했을 수 있음.
                #   admin(user_id) 소유 행으로 스코프해 사용자 이미지 오염(hijack) 방지.
                #   사용자 선점 시 SELECT=None → INSERT 가 UNIQUE 위반으로 except → 조용한 덮어쓰기 대신 가시적 실패.
                cur.execute("""SELECT id FROM image WHERE name=%s AND user_id=%s""", (name, user_id))
                existing = cur.fetchone()
                if existing:
                    # 같은 name 행이 옛 real_name 으로 남아있음(레지스트리 드리프트) → 현재 값으로 정정
                    cur.execute("""UPDATE image SET real_name=%s, status=%s WHERE id=%s""",
                                (real_name, 2, existing["id"]))
                else:
                    cur.execute("""INSERT INTO image (user_id, name, real_name, status, access) VALUES (%s, %s, %s, %s, %s)""",
                                (user_id, name, real_name, 2, 1))
                conn.commit()
            except Exception:
                print(f"[set_llm_deployment_image] '{_engine}' 엔진 이미지 시드/정합 실패")
                traceback.print_exc()

# def set_download_huggingface_readme():
#     # 허깅페이스 불러오기할때  readme 를 다운로드하여 불러오는데 미리 불러오기
#     try:
#         api = HfApi()
#         models = api.list_models(limit=10, task="text-generation", library="transformers", model_name=model_name)
#         for model in models: 
#             model_info = api.model_info(model.id) # list_models 에서 가져온 정보로 조회가 안되 model_info사용 (author, last_modified...)
            
#             try:
#                 file_path = hf_hub_download(repo_id=model_info.id, filename="README.md")
#                 with open(file_path, 'r', encoding='utf-8') as file:
#                     description = file.read()
                
#                 if len(description) > 300:
#                     description = description[:300] + "..."
#             except:
#                 description = None
#     except:
#         pass

def init_setting():
    # 허깅페이스 토큰: values_tango2.yaml → jfb-settings ConfigMap → env 로 주입.
    # offline/nexus 모드에서는 비어 있을 수 있으므로 빈 값이면 login 자체를 스킵한다.
    hf_token = settings.HUGGINGFACE_TOKEN
    if hf_token:
        try:
            login(token=hf_token, add_to_git_credential=False)
        except Exception as exc:
            logging.getLogger(__name__).warning("Hugging Face login failed: %s", exc)
    else:
        logging.getLogger(__name__).info(
            "HUGGINGFACE_TOKEN not set; skipping Hugging Face login (offline mode)"
        )
    # llm 이미지 세팅
    set_llm_deployment_image()
    # set_download_huggingface_readme()
    
def main():
    init_setting()
    app = initialize_app()
    return app

if __name__=="__main__":
    app = main()
    uvicorn.run(app, port=8000, host='0.0.0.0', reload=True)
