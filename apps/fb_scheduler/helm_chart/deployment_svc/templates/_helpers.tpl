{{- define "name" -}}
{{ .Values.metadata.namespace.systemNamespace }}-{{ .Values.metadata.id.workspaceId }}
{{- end }}

{{- define "namespace" -}}
{{ .Values.metadata.namespace.systemNamespace }}-{{ .Values.metadata.id.workspaceId }}
{{- end }}