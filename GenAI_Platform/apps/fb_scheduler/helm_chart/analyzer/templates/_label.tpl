{{- define "labels.base" }}
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


{{- define "labels.analyzer" }}
analyzer_id: {{ .Values.analyzer.analyzer_id | default "" | quote }}
graph_id: {{ .Values.analyzer.graph_id | default "" | quote }}
graph_type: {{ .Values.analyzer.graph_type | default "" | quote }}
{{- end }}
