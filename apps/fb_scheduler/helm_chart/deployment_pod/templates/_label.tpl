{{- define "labels" }}
api_mode: prefix
pod_type: deployment
work_func_type: deployment
role: jfb-user-functions
deployment_type: {{ .Values.labels.deployment_type | default "" | quote }}
deployment_name: {{ .Values.labels.deployment_name | default "" | quote }}
deployment_id: {{ .Values.labels.deployment_id | default "" | quote }}
deployment_worker_id: {{ .Values.labels.deployment_worker_id | default "" | quote }}
workspace_id: {{ .Values.labels.workspace_id | default "" | quote }}
workspace_name: {{ .Values.metadata.name.workspaceName | default "" | quote }}
instance_id : {{ .Values.labels.instance_id | default "" | quote }}
user: {{ .Values.labels.user | default "" | quote }}
pod_name: {{ .Values.labels.pod_name | default "" | quote }}
helm_name: {{ .Values.labels.helm_name | quote }}
index: {{ .index | quote }}
device_type: {{ .node.device.type | default "" | quote }}
device_model: {{ .node.device.model | default "" | quote }}
device_count: {{ .node.device.count | default "" | quote }}
device_ids: {{ .node.device.ids | default "" | quote }}
node_name: {{ .node.node_name | default "" | quote }}
{{- end }}