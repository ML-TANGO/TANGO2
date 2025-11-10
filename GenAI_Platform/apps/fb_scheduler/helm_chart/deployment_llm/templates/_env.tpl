{{- define "env.base" }}
- name: POD_API_LOG_BASE_PATH_IN_POD
  value: /log
- name: POD_API_LOG_FILE_PATH_IN_POD
  value: /log/monitor.txt
- name: POD_API_LOG_FILE_NAME
  value: monitor.txt
- name: POD_API_LOG_COUNT_FILE_NAME
  value: count.json
- name: POD_API_LOG_IMPORT_CHECK_FILE_PATH_IN_POD
  value: /log/import.txt
- name: POD_GPU_USAGE_RECORD_FILE_PATH_IN_POD
  value: /resource_log/gpu_usage.json
- name: POD_CPU_RAM_RESOURCE_USAGE_RECORD_FILE_PATH_IN_POD
  value: /resource_log/resource_usage.json
- name: PYTHONUNBUFFERED
  value: "1"
- name: JF_HOME
  value: '/jf-deployment-home'
{{- end }}
{{/*JF_CPU, JF_  변수들은 command 에서 사용했었음 -> command 제거 -> env 제거*/}}

{{- define "env.node" }}
- name: JF_NODE_NAME
  value: {{ .node.node_name | default "" | quote }}
{{- end }}

{{- define "env.gpu" }}
{{- if and (eq .node.device.type "GPU") .node.device.uuids }}
- name: "NVIDIA_VISIBLE_DEVICES"
  value: {{ .node.device.uuids }}
{{- end }}
{{- end }}

{{- define "env.rdma" }}
{{- if .Values.rdma.enabled }}
- name: "JF_RDMA_ENABLED"
  value: {{ .Values.rdma.enabled | quote }}

{{- if .Values.rdma.mp.enabled }}
- name: "JF_MP_ENABLED"
  value: "true"

{{- if and .Values.rdma.mp.seed_num .Values.rdma.mp.seed_list }}
{{- with .node }}
{{- range $.Values.rdma.mp.seed_list }}
{{- if eq .nodeName $.node.node_name }}
{{- if .seed }}
- name: "JFB_MP_SEED_LIST"
  value: {{ .seed | quote }}
- name: "JFB_MP_SEED_NUM"
  value: {{ $.Values.rdma.mp.seed_num | quote }} 
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}

{{- end }}

{{- if .Values.rdma.p2p }}
{{- with .node }}  # with를 사용하여 .node의 범위를 고정
{{- range $.Values.rdma.p2p }}
{{- if eq .nodeName $.node.node_name }}
- name: "JF_RDMA_IS_P2P"
  value: "true"
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}


{{- define "env.deployment" }}
- name: POD_DEPLOYMENT_WORKER_ID
  value: {{ .Values.deployment.deploymentWorkerId | quote | default "" }}
{{- end }}



{{- define "env.llm" }}
- name: LLM_SYSTEM_NAMESPACE
  value: {{ .Values.metadata.namespace.systemNamespace }}
- name: LLM_POD_NAMESPACE
  value: {{ include "namespace" . }}
- name: LLM_POD_BASE_NAME
  value: {{ .Values.metadata.name.podBaseName | quote | default "" }}
- name: LLM_TYPE
  value: {{ .Values.llm.type  }}
- name: LLM_GPU_TOTAL_COUNT
  value: {{ .Values.gpu_auto_cluster_case.total_device_count  | default "0" | quote }}
- name: LLM_GPU_SERVER_COUNT
  value: {{ .Values.gpu_auto_cluster_case.server  | default "0" | quote }}
- name: LLM_GPU_COUNT
  value: {{ .Values.gpu_auto_cluster_case.gpu_count  | default "0" | quote }}
- name: LLM_POD_INDEX
  value: {{ .index | default "0" | quote }}
{{- end }}

{{- define "env.llm.db" }}
- name: JF_LLM_DB_HOST
  value: {{ .Values.llm.db.host | quote | default "" }}
- name: JF_LLM_DB_PORT  
  value: {{ .Values.llm.db.port | quote | default "" }}
- name: JF_LLM_DB_USER
  value: {{ .Values.llm.db.user | quote | default "" }}
- name: JF_LLM_DB_PW
  value: {{ .Values.llm.db.pw | quote | default "" }}
- name: JF_LLM_DB_NAME
  value: {{ .Values.llm.db.name | quote | default "" }}
- name: JF_LLM_DB_CHARSET
  value: {{ .Values.llm.db.charset | quote | default "" }}
- name: JF_LLM_DB_COLLATION
  value: {{ .Values.llm.db.collation | quote | default "" }}
{{- end }}



{{/*LLM_MODEL_TYPE : "huggingface", "commit"*/}}
{{- define "env.llm.model" }}
- name: LLM_MODEL_TYPE
  value: {{ .Values.llm.model.type | quote | default "" }}
- name: LLM_MODEL_HUGGINGFACE_ID
  value: {{ .Values.llm.model.huggingface_id | quote | default "" }}
- name: LLM_MODEL_HUGGINGFACE_TOKEN
  value: {{ .Values.llm.model.huggingface_token | quote | default "" }}
- name: LLM_MODEL_ALLM_NAME
  value: {{ .Values.llm.model.allm_name | quote | default "" }}
- name: LLM_MODEL_ALLM_COMMIT_NAME
  value: {{ .Values.llm.model.allm_commit_name | quote | default "" }}
- name: LLM_HUGGINGFACE_API_TOKEN
  value: {{ .Values.llm.model.huggingface_api_token | quote | default "" }}
{{- end }}



{{- define "env.llm.rag" }}
- name: LLM_RAG_ID
  value: {{ .Values.llm.rag.id | quote | default "" }}
- name: LLM_RAG_CHUNK_LEN
  value: {{ .Values.llm.rag.chunk_len | default "" | quote }}
- name: LLM_RAG_EMBEDDING_RUN
  value: {{ .Values.llm.rag.embedding_run | default "0"  | quote }}
{{- end }}






{{- define "env.llm.playground" }}
- name: LLM_PLAYGROUND_ID
  value: {{ .Values.llm.playground.playground_id | default "" | toString | quote }}
- name: LLM_RUN_RAG
  value: {{ .Values.llm.playground.run_rag | default "false" | toString | quote }}
- name: LLM_RUN_RAG_RERANKER
  value: {{ .Values.llm.playground.run_rag_reranker | default "false" | toString | quote }}
- name: LLM_RUN_PROMPT
  value: {{ .Values.llm.playground.run_prompt | default "false" | toString | quote }}
- name: LLM_PARAM_TEMPERATURE
  value: {{ .Values.llm.playground.param_temperature | quote | default "" }}
- name: LLM_PARAM_TOP_P
  value: {{ .Values.llm.playground.param_top_p | quote | default "" }}
- name: LLM_PARAM_TOP_K
  value: {{ .Values.llm.playground.param_top_k | quote | default "" }}
- name: LLM_PARAM_REPETITION_PENALTY
  value: {{ .Values.llm.playground.param_repetition_penalty | quote | default "" }}
- name: LLM_PARAM_MAX_NEW_TOKENS
  value: {{ .Values.llm.playground.param_max_new_tokens | quote | default "" }}
- name: LLM_PLAYGROUND_RAG_CHUNK_MAX
  value: {{ .Values.llm.playground.rag_chunk_max | quote | default "" }}
- name: LLM_PROMPT_SYSTEM_MESSAGE
  value: {{ .Values.llm.playground.prompt_system_message | quote | default "" }}
- name: LLM_PROMPT_USER_MESSAGE
  value: {{ .Values.llm.playground.prompt_user_message | quote | default "" }}
{{- end }}


{{- define "env.cuda" }}
- name: PYTORCH_CUDA_ALLOC_CONF
  value: "expandable_segments:True"
{{- end }}
