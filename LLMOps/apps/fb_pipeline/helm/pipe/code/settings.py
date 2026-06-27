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

PROJECT_DNS = "jfb-app-training-svc.jonathan-system.svc.cluster.local"
PREPROCESSING_DNS = "jfb-app-preprocessing-svc.jonathan-system.svc.cluster.local"
DEPLOYMENT_DNS = "jfb-app-deployment-svc.jonathan-system.svc.cluster.local"
EXTERNAL_CONTAINER_DNS = "jfb-app-external-container-svc.jonathan-system.svc.cluster.local"
# GenAI 통합 파이프라인 신규 task_type(finetuning/quantize/llm_deploy)용.
LLM_MODEL_DNS = "jfb-llm-model-svc.jonathan-system.svc.cluster.local"
RESOURCE_DNS = "jfb-app-resource-svc.jonathan-system.svc.cluster.local"
# llm_deploy(cluster) 노드 → Playground s2s 배포(spec #4).
LLM_PLAYGROUND_DNS = "jfb-llm-playground-svc.jonathan-system.svc.cluster.local"