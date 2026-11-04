{{- define "lib.volume.type" -}}
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

