

{{- define "labels.base" }}
api_mode: prefix
pod_type: deployment
work_func_type: deployment
role: jfb-user-functions
instance_id : {{ .Values.metadata.id.instanceId | default "" | quote }}
workspace_id: {{ .Values.metadata.id.workspaceId | default "" | quote }}
workspace_name: {{ .Values.metadata.name.workspaceName | default "" | quote }}
user: {{ .Values.metadata.name.userName | default "" | quote }}
pod_name: {{ .Values.metadata.name.podName | default "" | quote }}
helm_name: {{ .Values.metadata.name.helmName | default "" | quote }}
{{- end }}

{{- define "labels.node" }}
index: {{ .index | quote }}
device_type: {{ .node.device.type | default "" | quote }}
device_model: {{ .node.device.model | default "" | quote }}
device_count: {{ .node.device.count | default "" | quote }}
device_ids: {{ .node.device.ids | default "" | quote }}
node_name: {{ .node.node_name | default "" | quote }}
{{- end }}

{{- define "labels.deployment" }}
deployment_type: "deployment"
deployment_name: {{ .Values.deployment.deploymentName | default "" | quote }}
deployment_id: {{ .Values.deployment.deploymentId | default "" | quote }}
deployment_worker_id: {{ .Values.deployment.deploymentWorkerId | default "" | quote }}
{{- end }}


{{- define "labels.rag" }}
rag_id: {{ .Values.labels.rag.id | default "" | quote }}
rag_name: {{ .Values.labels.rag.name | default "" | quote }}
{{- end }}