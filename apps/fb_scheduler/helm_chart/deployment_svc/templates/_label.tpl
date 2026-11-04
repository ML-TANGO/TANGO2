{{- define "labels" }}
api_mode: prefix
pod_type: deployment
work_func_type: {{ .Values.labels.work_func_type | default "deployment" | quote }}
role: jfb-user-functions
deployment_type: {{ .Values.labels.deployment_type | default "" | quote }}
deployment_name: {{ .Values.labels.deployment_name | default "" | quote }}
deployment_id: {{ .Values.labels.deployment_id | default "" | quote }}
workspace_id: {{ .Values.labels.workspace_id | default "" | quote }}
workspace_name: {{ .Values.metadata.name.workspaceName | default "" | quote }}
instance_id : {{ .Values.labels.instance_id | default "" | quote }}
user: {{ .Values.labels.user | default "" | quote }}
pod_base_name: {{ .Values.metadata.name.podBaseName | default "" | quote }}
helm_name: {{ .Values.labels.helm_name | quote }}
{{- end }}
