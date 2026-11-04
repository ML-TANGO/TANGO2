import json
from utils.msa_db.db_base import get_db
from utils import settings


"""
>의료 (Healthcare/Medical AI Solutions)
화상 심도 탐지
욕창 심도 예측
우울증 조기 진단  
전립선 증식증 감별 진단  
전립선 증식증 예후 예측  
전립선 초음파 영상 기반 세그멘테이션
 
>시각 (Object detection AI Solutions)
DNA+ 드론 균열 탐지
DNA+ 드론 녹 탐지
OX 플래카드 실시간 탐지기
손 제스쳐 탐지기
 
공감감성지능  (Emphathy Sentiment Analysis)
복합 감성 분석
텍스트 공감 분석
음성 공감 분석
영상 공감 분석
멀티모달 감성 추론
 
 
자연어 이해 (Natural Language Understanding)
텍스트 개체명 인식 
SW 코드 결함 탐지
 
 
대화 생성 (Dialogue Generation)
자율주행 상황 인식을 위한 LLM 기반 개체명 인식
"""

data = {
    "의료 (Healthcare/Medical AI Solutions)": {
        "화상 심도 탐지": {
            "huggingface_model_id": "Acryl-aLLM/BurnDepthAnalysisIntelligence",
            "target_metric": "Val_loss",
            "task" : "",
            "readme": "",
            "resource" : "CPU/GPU",
            "image" : "registry.jonathan.acryl.ai/built-in-model/burn:latest",
            "deploy_params": [
                {
                    "name": "checkpoint"
                }
            ],
            "system_params": [
                {
                    "name": "dataset_csv_file",
                    "type": "str",
                    "format": "{data_path}/meta.csv"
                },
                {
                    "name": "image_dir",
                    "type": "str",
                    "format": "{data_path}/images"
                },
                {
                    "name": "final_checkpoint_file",
                    "type": "str",
                    "format": "{checkpoint_file}"
                }
            ],
            "user_params": [
                {
                    "name": "batch",
                    "default_value": 32,
                    "description": "",
                    "type": "int"
                },
                {
                    "name": "num_workers",
                    "default_value": 16,
                    "description": "",
                    "type": "int"
                },
                {
                    "name": "max_epoch",
                    "default_value": 20,
                    "description": "",
                    "type": "int"
                },
                {
                    "name": "lr",
                    "default_value": 1e-5,
                    "description": "",
                    "type": "float"
                }
            ],
            "data_form" : {
                "location" : "file",
                "method" : "POST",
                "api_key" : "burn_img",
                "value_type" : "image of jpg file",
                "category" : "image",
                "category_description" : "image of jpg file",
            }
        },
        "욕창 심도 예측": {
            "huggingface_model_id": "Acryl-aLLM/PressureUlcerAnalysis",
            "target_metric": "Accuracy",
            "readme": "",
            "task" : "",
            "image" : "",
            "resource" : "CPU/GPU",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        },
        "우울증 조기 진단": {
            "huggingface_model_id": "Acryl-aLLM/DepressionAnalysis",
            "target_metric": "ROC_AUC",
            "readme": "",
            "task" : "",
            "resource" : "CPU/GPU",
            "image" : "",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        },
        "전립선 증식증 감별 진단": {
            "huggingface_model_id": "Acryl-aLLM/ProstateAnalysis1",
            "target_metric": "Precision",
            "readme": "",
            "task" : "",
            "resource" : "CPU/GPU",
            "image" : "",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        },
        "전립선 증식증 예후 예측": {
            "huggingface_model_id": "Acryl-aLLM/ProstateAnalysis2",
            "target_metric": "Recall",
            "readme": "",
            "task" : "",
            "resource" : "CPU/GPU",
            "image" : "",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        },
        "전립선 초음파 영상 기반 세그멘테이션": {
            "huggingface_model_id": "Acryl-aLLM/ProstateAnalysis2",
            "target_metric": "Recall",
            "readme": "",
            "task" : "",
            "resource" : "CPU/GPU",
            "image" : "",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        }
    },
    "시각 (Object detection AI Solutions)": {
        "DNA+ 드론 균열 탐지": {
            "huggingface_model_id": "Acryl-aLLM/dna_pothole_crack",
            "target_metric": "mAP",
            "readme": "",
            "image" : "",
            "resource" : "CPU/GPU",
            "task" : "",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        },
        "DNA+ 드론 녹 탐지": {
            "huggingface_model_id": "Acryl-aLLM/dna_rust",
            "target_metric": "mAP",
            "readme": "",
            "image" : "",
            "resource" : "CPU/GPU",
            "task" : "",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        },
        "OX 플래카드 실시간 탐지기": {
            "huggingface_model_id": "Acryl-aLLM/dna_rust",
            "target_metric": "mAP",
            "readme": "",
            "image" : "",
            "resource" : "CPU/GPU",
            "task" : "",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        },
        "손 제스쳐 탐지기": {
            "huggingface_model_id": "Acryl-aLLM/dna_rust",
            "target_metric": "mAP",
            "readme": "",
            "image" : "",
            "resource" : "CPU/GPU",
            "task" : "",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        },
    },
    "자연어 이해 (Natural Language Understanding)": {
        "SW 코드 결함 탐지": {
            "huggingface_model_id": "Acryl-aLLM/NamedEntityRecognition",
            "target_metric": "F1_score",
            "readme": "",
            "image" : "",
            "resource" : "CPU/GPU",
            "task" : "",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        },
        "텍스트 개체명 인식": {
            "huggingface_model_id": "Acryl-aLLM/NamedEntityRecognition",
            "target_metric": "F1_score",
            "readme": "",
            "image" : "",
            "resource" : "CPU/GPU",
            "task" : "",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        }
    },
    "공감감성지능  (Emphathy Sentiment Analysis)": {
        "복합 감성 분석": {
            "huggingface_model_id": "Acryl-aLLM/Ethical-Intent-Recognition",
            "target_metric": "Accuracy",
            "readme": "",
            "image" : "",
            "task" : "",
            "resource" : "CPU/GPU",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        },
        "텍스트 공감 분석": {
            "huggingface_model_id": "Acryl-aLLM/Ethical-Intent-Recognition",
            "target_metric": "Accuracy",
            "readme": "",
            "image" : "",
            "task" : "",
            "resource" : "CPU/GPU",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        },
        "멀티모달 감성 추론": {
            "huggingface_model_id": "Acryl-aLLM/Ethical-Intent-Recognition",
            "target_metric": "Accuracy",
            "readme": "",
            "image" : "",
            "task" : "",
            "resource" : "CPU/GPU",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        },
        "영상 공감 분석": {
            "huggingface_model_id": "Acryl-aLLM/Ethical-Intent-Recognition",
            "target_metric": "Accuracy",
            "readme": "",
            "image" : "",
            "task" : "",
            "resource" : "CPU/GPU",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        },
        "음성 공감 분석": {
            "huggingface_model_id": "Acryl-aLLM/Ethical-Intent-Recognition",
            "target_metric": "Accuracy",
            "readme": "",
            "image" : "",
            "task" : "",
            "resource" : "CPU/GPU",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        },
    },
    "대화 생성 (Dialogue Generation)": {
        "자율주행 상황 인식을 위한 LLM 기반 개체명 인식": {
            "huggingface_model_id": "Acryl-Jonathan-2/autodrive-ner",
            "target_metric": "BLEU",
            "readme": "",
            "task" : "",
            "resource" : "CPU/GPU",
            "image" : "",
            "deploy_params": [],
            "system_params": [],
            "user_params": [],
            "data_form" : None
        }
    },
}

import time
def insert_built_in_model(data):
    try:
        with get_db() as conn:  # 데이터베이스 연결 (사용자 정의 `get_db` 함수)
            cur = conn.cursor()

            for category, models in data.items():
                for name, details in models.items():
                    huggingface_model_id = details.get("huggingface_model_id", "")
                    target_metric = details.get("target_metric", "")
                    readme = details.get("readme", "")
                    task = details.get("task", "")
                    image = details.get("image", "")
                    resource = details.get("resource", "")
                    deploy_params = json.dumps(details.get("deploy_params", []))
                    system_params = json.dumps(details.get("system_params", []))
                    user_params = json.dumps(details.get("user_params", []))
                    data_form = details.get("data_form")

                    # 기존 데이터 확인
                    sql_check = """
                        SELECT COUNT(*) as count
                        FROM built_in_model
                        WHERE name = %s AND category = %s
                    """
                    cur.execute(sql_check, (name, category))
                    result = cur.fetchone()

                    # 데이터가 없으면 삽입
                    if result.get("count") == 0:
                        sql_insert = """
                            INSERT INTO built_in_model (
                                name, category, task, token, huggingface_model_id, 
                                huggingface_git_url, readme, user_parameter, 
                                system_parameter, deploy_parameter, target_metric, 
                                resource_type, image
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                            )
                        """
                        cur.execute(sql_insert, (
                            name,           # `name`
                            category,       # `category`
                            task,       # `task` (여기선 category를 기본 task로 사용)
                            settings.HUGGINGFACE_TOKEN,
                            huggingface_model_id,
                            f"https://huggingface.co/{huggingface_model_id}",
                            readme,
                            user_params,
                            system_params,
                            deploy_params,
                            target_metric,
                            resource,
                            image
                        ))
                        print(f"Inserted: {name} in category {category}")

                        # DB table: built_in_data_form 삽입
                        built_in_model_id = cur.lastrowid
                        if data_form is not None:
                            sql_insert = """
                                INSERT INTO built_in_model_data_form (
                                    built_in_model_id, location, method, api_key, value_type, category, category_description
                                ) VALUES (
                                    %s,%s,%s,%s,%s,%s,%s
                                )
                                """
                            print(built_in_model_id, 
                                                    data_form.get("location"), data_form.get("method"), data_form.get("api_key"), 
                                                    data_form.get("value_type"),data_form.get("category"),data_form.get("category_description"),)
                            cur.execute(sql_insert,(built_in_model_id, 
                                                    data_form.get("location"), data_form.get("method"), data_form.get("api_key"), 
                                                    data_form.get("value_type"),data_form.get("category"),data_form.get("category_description"), ))
                    else:
                        print(f"Skipped: {name} in category {category} (already exists)")

            conn.commit()
            print("데이터 삽입 완료!")
    except Exception as e:
        # conn.rollback()
        print(f"오류 발생: {e}")
        raise e
