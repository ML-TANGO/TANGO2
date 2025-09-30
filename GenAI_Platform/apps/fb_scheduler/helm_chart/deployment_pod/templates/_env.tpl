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
- name: DEPLOYMENT_RUNNING_TYPE
  value: ""
- name: JF_DEPLOYMENT_PWD
  value: ""
{{- range $key, $val := .Values.env }}
- name: {{ $key }}
  value: {{ $val | quote }}
{{- end }}
{{- if .cluster.gpu_uuids }}
- name: "CUDA_VISIBLE_DEVICES"
  value: {{ .cluster.gpu_uuids }}
- name: "NVIDIA_VISIBLE_DEVICES"
  value: {{ .cluster.gpu_uuids }}
{{- end }}
{{- end }}
{{/*JF_CPU, JF_  변수들은 command 에서 사용했었음 -> command 제거 -> env 제거*/}}