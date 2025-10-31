{{- define "labels" }}
api_mode: prefix
deployment_id: {{ .Values.labels.deployment_id | quote }}
deployment_name: {{ .Values.labels.deployment_name | quote }}
deployment_total_gpu: {{ .Values.resources.requests.gpu | quote }}
deployment_type: {{ .Values.labels.deployment_type | quote }}
deployment_worker_id: {{ .Values.labels.deployment_worker_id | quote }}
executor_id: {{ .Values.labels.executor_id | quote }}
executor_name: {{ .Values.labels.executor_name | quote }}
pod_base_name: {{ .Values.labels.pod_base_name | quote }}
pod_name: {{ .Values.labels.pod_name | quote }}
user: {{ .Values.labels.user | quote }}
workspace_id: {{ .Values.labels.workspace_id | quote }}
workspace_name: {{ .Values.metadata.name.workspaceName | quote }}
instance_id : {{ .Values.labels.instance_id | quote }}
pod_type: deployment
work_type: deployment
work_func_type: deployment
role: jfb-user-functions
index: {{ .index | quote }}
gpu_ids: {{ .cluster.gpu_ids | default "" | quote }}
node_name: {{ .cluster.node_name | default "" | quote }}
{{- end }}