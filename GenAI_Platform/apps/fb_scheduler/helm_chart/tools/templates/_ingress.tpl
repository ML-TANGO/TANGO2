

{{- define "ingress_path" -}}
{{- if eq .Values.labels.tool_type "jupyter" }} "/{{ .Values.labels.tool_type }}/{{ trimSuffix "/" .Values.pod_name }}-0/"
{{- else if eq .Values.labels.tool_type "vscode" }} "/{{ .Values.labels.tool_type }}/{{ $.Values.pod_name }}-0"
{{- else if eq .Values.labels.tool_type "shell" }} "/{{ .Values.labels.tool_type }}/{{ $.Values.pod_name }}-0"
{{- end }}
{{- end }}