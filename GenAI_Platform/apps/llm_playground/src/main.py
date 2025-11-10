import os
import json
import threading
import traceback
import uvicorn
from fastapi import FastAPI, Request, Depends
from playground.route import playgrounds
from utils.resource import CustomResponse, CustomMiddleWare
from huggingface_hub import HfFolder
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
    return app

def set_llm_deployment_image():
    with get_db() as conn:
        try:
            real_name=f"{settings.DOCKER_REGISTRY_URL}{settings.DEPLOYMENT_LLM_IMAGE}"
            user_id = db_user.get_user(user_name='admin').get("id")
            image = db_image.get_image_id_by_real_name(real_name=real_name)
            if image is None or len(image) == 0:
                sql = """INSERT INTO image (user_id, name, real_name, status, access) VALUES (%s, %s, %s, %s, %s)"""
                conn.cursor().execute(sql, (user_id, "JBI_LLM_Deployment_image", real_name, 2, 1))
                conn.commit()
        except:
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
    # 허깅페이스 토큰을 여기에 입력하세요
    hf_token = settings.HUGGINGFACE_TOKEN
    # 토큰 설정 및 저장
    HfFolder.save_token(hf_token)
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
