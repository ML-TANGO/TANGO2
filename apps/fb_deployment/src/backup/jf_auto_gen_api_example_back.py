"""
시스템 정보
아래 스크립트 삭제시 JF deploy 실행이 안됩니다.
#JF_DEPLOYMENT_INPUT_DATA_INFO_START
#JF_DEPLOYMENT_INPUT_DATA_INFO_END
"""
import sys
sys.path.append('/addlib')
from deployment_api_deco import api_monitor
from flask import Flask, request, jsonify
from flask.views import MethodView
from flask_cors import CORS
import argparse
import base64

"""
배포 실행 명령어 관련 자동생성 영역
"""

"""
사용자 추가 영역
"""

app = Flask(__name__)
CORS(app, resources={r'/*': {"origins": '*'}})

class run_api(MethodView):
    def __init__(self):
        pass

    @api_monitor()
    def get(self):
        return "JF DEPLOYMENT RUNNING"

    @api_monitor()
    def post(self):
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
        
        return jsonify(output)

app.add_url_rule("/", view_func=run_api.as_view("run_api"))
if __name__ == "__main__":
    """
    모델 로드를 권장하는 위치
    사용자 영역
    """
    app.run('0.0.0.0',8555,threaded=True)