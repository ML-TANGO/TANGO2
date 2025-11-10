import os
# =================================================================================
# ENV 
# =================================================================================
# env.llm
LLM_SYSTEM_NAMESPACE = os.environ.get("LLM_SYSTEM_NAMESPACE")
LLM_POD_NAMESPACE = os.environ.get("LLM_POD_NAMESPACE")
LLM_POD_BASE_NAME = os.environ.get("LLM_POD_BASE_NAME")

LLM_SVC_MODEL = f"http://{LLM_POD_BASE_NAME}---deployment-model.{LLM_POD_NAMESPACE}:18555"
LLM_SVC_RAG = f"http://{LLM_POD_BASE_NAME}---deployment-rag.{LLM_POD_NAMESPACE}:18555"
LLM_SVC_PROMPT = f"http://{LLM_POD_BASE_NAME}---deployment-prompt.{LLM_POD_NAMESPACE}:18555"

LLM_TYPE= os.environ.get("LLM_TYPE")

# env.llm.db
TIME_DATE_FORMAT_SQL = "%Y-%m-%d %H:%i:%S"
JF_LLM_DB_HOST = os.environ.get("JF_LLM_DB_HOST") if os.environ.get("JF_LLM_DB_HOST") else '192.168.1.20'
JF_LLM_DB_PORT = int(os.environ.get("JF_LLM_DB_PORT")) if os.environ.get("JF_LLM_DB_PORT") else 30001
JF_LLM_DB_USER = os.environ.get("JF_LLM_DB_USER") if os.environ.get("JF_LLM_DB_USER") else 'root'
JF_LLM_DB_PW = os.environ.get("JF_LLM_DB_PW") if os.environ.get("JF_LLM_DB_PW") else 'acryl4958@'
JF_LLM_DB_NAME = os.environ.get("JF_LLM_DB_NAME") if os.environ.get("JF_LLM_DB_NAME") else 'jonathan_llm'

# env.llm.model
LLM_MODEL_TYPE = os.environ.get("LLM_MODEL_TYPE")
LLM_MODEL_HUGGINGFACE_ID = os.environ.get("LLM_MODEL_HUGGINGFACE_ID")
LLM_MODEL_HUGGINGFACE_TOKEN = os.environ.get("LLM_MODEL_HUGGINGFACE_TOKEN")
LLM_MODEL_ALLM_NAME = os.environ.get("LLM_MODEL_ALLM_NAME")
LLM_MODEL_ALLM_COMMIT_NAME = os.environ.get("LLM_MODEL_ALLM_COMMIT_NAME")
LLM_HUGGINGFACE_API_TOKEN = os.environ.get("LLM_HUGGINGFACE_API_TOKEN")

# env.llm.rag
LLM_RAG_ID = os.environ.get("LLM_RAG_ID")
LLM_RAG_CHUNK_LEN = int(os.environ.get("LLM_RAG_CHUNK_LEN", 0)) if os.environ.get("LLM_RAG_CHUNK_LEN") != '' else 0
LLM_RAG_EMBEDDING_RUN = int(os.environ.get("LLM_RAG_EMBEDDING_RUN", 0))

# env.llm.playground
LLM_PLAYGROUND_ID = os.environ.get("LLM_PLAYGROUND_ID")

LLM_PARAM_TEMPERATURE = float(os.environ.get("LLM_PARAM_TEMPERATURE", 0)) if os.environ.get("LLM_PARAM_TEMPERATURE") != '' else 0
LLM_PARAM_TOP_P = float(os.environ.get("LLM_PARAM_TOP_P", 0)) if os.environ.get("LLM_PARAM_TOP_P") != '' else 0
LLM_PARAM_TOP_K = int(os.environ.get("LLM_PARAM_TOP_K", 0)) if os.environ.get("LLM_PARAM_TOP_K") != '' else 0
LLM_PARAM_REPETITION_PENALTY = float(os.environ.get("LLM_PARAM_REPETITION_PENALTY", 0)) if os.environ.get("LLM_PARAM_REPETITION_PENALTY") != '' else 0
LLM_PARAM_MAX_NEW_TOKENS = int(float(os.environ.get("LLM_PARAM_MAX_NEW_TOKENS", 0))) if os.environ.get("LLM_PARAM_MAX_NEW_TOKENS") != '' else 0
LLM_PLAYGROUND_RAG_CHUNK_MAX = int(os.environ.get("LLM_PLAYGROUND_RAG_CHUNK_MAX", 0)) if os.environ.get("LLM_PLAYGROUND_RAG_CHUNK_MAX") != '' else 0

LLM_PROMPT_SYSTEM_MESSAGE = os.environ.get("LLM_PROMPT_SYSTEM_MESSAGE")
LLM_PROMPT_USER_MESSAGE = os.environ.get("LLM_PROMPT_USER_MESSAGE")

LLM_RUN_RAG = os.environ.get("LLM_RUN_RAG") == "true"
LLM_RUN_RAG_RERANKER = os.environ.get("LLM_RUN_RAG_RERANKER") == "true"
LLM_RUN_PROMPT = os.environ.get("LLM_RUN_PROMPT") == "true"

# env.llm
LLM_GPU_TOTAL_COUNT = int(os.environ.get('LLM_GPU_TOTAL_COUNT')) if os.environ.get("LLM_GPU_TOTAL_COUNT") != '' else 0
LLM_GPU_SERVER_COUNT = int(os.environ.get('LLM_GPU_SERVER_COUNT')) if os.environ.get("LLM_GPU_SERVER_COUNT") != '' else 0
LLM_GPU_COUNT = int(os.environ.get('LLM_GPU_COUNT')) if os.environ.get("LLM_GPU_COUNT") != '' else 0

# =================================================================================
# env.deployment
# =================================================================================
# POD_COUNT=int(os.environ.get("POD_COUNT")) if os.environ.get("POD_COUNT") != '' else 0

# =================================================================================
# 직접 입력 
# =================================================================================
# MILVUS
MILVUS_COLLECTION_NAME = f"rag_{LLM_RAG_ID}"
MILVUS_CONNECTION_URI = 'tcp://milvus.jonathan-milvus.svc.cluster.local:19530'
MILVUS_CONNECTION_ARGS = {
    "uri": MILVUS_CONNECTION_URI,
    # "db_name": "jonathan_rag", # default 사용 (default만 조회하는 이슈? 버전??)
}

HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN", "")
