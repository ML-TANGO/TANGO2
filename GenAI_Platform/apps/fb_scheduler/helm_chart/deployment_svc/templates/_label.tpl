{{- define "labels" }}
api_mode: prefix
deployment_id: {{ .Values.labels.deployment_id | quote }}
deployment_name: {{ .Values.labels.deployment_name | quote }}
deployment_total_gpu: {{ .Values.labels.deployment_total_gpu | quote }}
deployment_type: {{ .Values.labels.deployment_type | quote }}
deployment_worker_id: {{ .Values.labels.deployment_worker_id | quote }}
executor_id: {{ .Values.labels.executor_id | quote }}
executor_name: {{ .Values.labels.executor_name | quote }}
pod_base_name: {{ .Values.metadata.pod.podBaseName | quote }}
pod_name: {{ .Values.labels.pod_name | quote }}
pod_type: deployment
user: {{ .Values.labels.user | quote }}
workspace_id: {{ .Values.labels.workspace_id | quote }}
workspace_name: {{ .Values.labels.workspace_name | quote }}
work_type: deployment
work_func_type: deployment
instance_id : {{ .Values.labels.instance_id | quote }}
{{- end }}