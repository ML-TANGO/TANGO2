import os
TIME_DATE_FORMAT_SQL = "%Y-%m-%d %H:%i:%S"
JF_DB_HOST = os.environ['JF_DB_HOST']
JF_DB_PORT = int(os.environ['JF_DB_PORT'])
JF_DB_USER = os.environ['JF_DB_USER'] if os.environ.get('JF_DB_USER') else 'root'
JF_DB_PW = os.environ.get('JF_DB_PW', '')
JF_DB_NAME = os.environ['JF_DB_NAME'] if os.environ.get('JF_DB_NAME') else "msa_jfb"

JF_REDIS_PROT = int(os.environ["JF_REDIS_PROT"])
JF_REDIS_PASSWORD = os.environ["JF_REDIS_PASSWORD"]
JF_REDIS_CLUSTER_ENABLED = os.environ["JF_REDIS_CLUSTER_ENABLED"] == "true"
JF_REDIS_CLUSTER_DNS = os.environ["JF_REDIS_CLUSTER_DNS"]
JF_REDIS_MASTER_DNS = os.environ["JF_REDIS_MASTER_DNS"]
JF_REDIS_SLAVES_DNS = os.environ["JF_REDIS_SLAVES_DNS"]

WORKSPACE_ID = os.environ.get("WORKSPACE_ID")
PIPELINE_ID = os.environ.get("PIPELINE_ID")
OWNER_NAME = os.environ.get("OWNER_NAME")
# SP-7 Jump — 빈 값이면 일반 실행(전체 리셋). 값(task_id)이면 해당 노드부터 단일패스 재실행.
RERUN_FROM_TASK = os.environ.get("RERUN_FROM_TASK") or ""

# 서빙/개발 인스턴스 분리 — 이 잡 파드는 envFrom jfb-settings 로 JF_SYSTEM_NAMESPACE 를
# 이미 받는다(pod.yaml). 리터럴로 두면 개발 인스턴스의 파이프라인 잡이 서빙 서비스를 호출한다.
SYSTEM_NAMESPACE = os.environ.get("JF_SYSTEM_NAMESPACE") or "jonathan-system"

PROJECT_DNS = f"jfb-app-training-svc.{SYSTEM_NAMESPACE}.svc.cluster.local"
PREPROCESSING_DNS = f"jfb-app-preprocessing-svc.{SYSTEM_NAMESPACE}.svc.cluster.local"
DEPLOYMENT_DNS = f"jfb-app-deployment-svc.{SYSTEM_NAMESPACE}.svc.cluster.local"
EXTERNAL_CONTAINER_DNS = f"jfb-app-external-container-svc.{SYSTEM_NAMESPACE}.svc.cluster.local"
# GenAI 통합 파이프라인 신규 task_type(finetuning/quantize/llm_deploy)용.
LLM_MODEL_DNS = f"jfb-llm-model-svc.{SYSTEM_NAMESPACE}.svc.cluster.local"
RESOURCE_DNS = f"jfb-app-resource-svc.{SYSTEM_NAMESPACE}.svc.cluster.local"
# llm_deploy(cluster) 노드 → Playground s2s 배포(spec #4).
LLM_PLAYGROUND_DNS = f"jfb-llm-playground-svc.{SYSTEM_NAMESPACE}.svc.cluster.local"