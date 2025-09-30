
{{- define "namespace" -}}
{{ .Values.system.namespace }}-{{ .Values.labels.workspace_id }}
{{- end }}



{{- define "name" -}}
{{ .Values.system.namespace }}-{{ .Values.labels.workspace_id }}
{{- end }}