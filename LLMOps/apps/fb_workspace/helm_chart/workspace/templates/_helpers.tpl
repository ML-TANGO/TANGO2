{{- define "name" -}}
{{ .Values.system.namespace }}-{{ .Values.workspace.id }}
{{- end }}



{{- define "namespace" -}}
{{ .Values.system.namespace }}-{{ .Values.workspace.id }}
{{- end }}


{{- define "volume.type" -}}
{{- if eq .type "hostPath" -}}
hostPath:
  path: {{ .path  }}
{{- else if eq .type "nfs" -}}
nfs:
  server: {{ .server }}
  path: {{ .path  }}
{{- else if eq .type "csi" -}}
csi:
{{- end }}
{{- end }}