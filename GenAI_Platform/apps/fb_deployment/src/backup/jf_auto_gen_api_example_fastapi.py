"""
시스템 정보
아래 스크립트 삭제시 JF deploy 실행이 안됩니다.
#JF_DEPLOYMENT_INPUT_DATA_INFO_START
#JF_DEPLOYMENT_INPUT_DATA_INFO_END
"""
import sys
sys.path.append('/addlib')
from deployment_api_deco import api_monitor
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
import argparse
import base64
import os

file_path = __file__
file_name = os.path.basename(file_path)
file_name = os.path.splitext(file_name)[0]
app = FastAPI()

"""
배포 실행 명령어 관련 자동생성 영역
"""


"""
사용자 추가 영역
"""


@app.get("/")
@api_monitor()
async def get_api():
    return "JF DEPLOYMENT RUNNING"

@app.post("/")
@api_monitor()
async def post_api(request : Request):
    """
    TEST API 받아오는 부분 자동 생성 영역
    """
    
    
    """
    사용자 영역
    # 필요한 전처리
    # 배포 테스트에 필요한 처리 등 
    """


    """
    Output 자동 생성 영역 (OUTPUT Category)

    output = {
        "text": [
            {
                "@TITLE": "Hello"
            }
        ],
        "image": [
            {
                "@TITLE": base64.b64encode(image_file.read()).decode()
            }
        ],
        "audio": [
            {
                "@TITLE": base64.b64encode(audio_file.read()).decode()
            }
        ],
        "video": [
            {
                "@TITLE": base64.b64encode(video_file.read()).decode()
            }
        ],
        "piechart": [
            {
                "@TITLE": [{"class_a": 8.0},{"class_b": 12.0},{"class_c": 50.0}]
            }
        ],
        "columnchart": [
            {
                "@TITLE": [{"class_a": 8.0},{"class_b": 12.0},{"class_c": 50.0}]
            }
        ],
        "obj": [
            {
                "@TITLE": {"obj": "# https://github.com/mikedh/trimesh\nv -0.03366653 -0.24951957 0.14774530 0.11372549 ..."}
            }
        ],
        "ner-table": [
            {
                "@TITLE": [{"sentence": "오늘 밥 먹자","entities":[{"word":"오늘","main_entity_name":"시각/시간","detail_entity_name": "시각/시간 - 일반"},{"word":"밥","main_entity_name":"음식/음료","detail_entity_name": "음식"}]}]
            }
        ],
        "llm": [
            {
                "type": "input|output", "message" : "This is an input/output message"
            }
        ],
        "table": [
            {
                "@TITLE": [{"column_name_1":22,"column_name_2":33},{"column_name_1":44,"column_name_2":55}]
            }
        ],
    }
    """
    
    return output

if __name__ == "__main__":
    """
    모델 로드를 권장하는 위치
    사용자 영역
    """
    uvicorn.run(f"{file_name}:app", port=8555, host='0.0.0.0')