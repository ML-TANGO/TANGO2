{{- define "name" -}}
{{ .Values.metadata.system.namespace }}-{{ .Values.metadata.workspace.id }}
{{- end }}

{{- define "namespace" -}}
{{ .Values.metadata.system.namespace }}-{{ .Values.metadata.workspace.id }}
{{- end }}