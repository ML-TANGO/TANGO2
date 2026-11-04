{{- define "env" }}
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
  value: '/jf-training-home'
- name: JF_HUGGINGFACE_TOKEN
  value: {{ .Values.deployment.huggingface_token | quote | default "" }}
- name: JF_HUGGINGFACE_MODEL_ID
  value: {{ .Values.deployment.huggingface_model_id | quote | default "" }}
- name: JF_MODEL_PATH
  value: '/model'
- name: DEPLOYMENT_MODEL_TYPE
  value: {{ .Values.deployment.model_type | quote }}
- name: DEPLOYMENT_WORKER_ID
  value: {{ .Values.command.deploymentWorkerId | quote }}
- name: RUN_CODE
  value: {{ .Values.command.runCode | quote }}
{{- if and (eq .node.device.type "GPU") .node.device.uuids }}
- name: "NVIDIA_VISIBLE_DEVICES"
  value: {{ .node.device.uuids }}
{{- end }}
{{- end }}
{{/*JF_CPU, JF_  변수들은 command 에서 사용했었음 -> command 제거 -> env 제거*/}}