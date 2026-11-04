{{- define "volume.volumeMounts.data" -}}
- name: data
  mountPath: /var/lib/registry
{{- end }}

{{- define "volume.volumes.data" -}}
- name: data
{{- if eq .Values.volume.type "hostPath" }}
  hostPath:
    path: {{ .Values.volume.path  }}
{{- else if eq .Values.volume.type "nfs" }}
  nfs:
    server: {{ .Values.volume.server }}
    path: {{ .Values.volume.path  }}
{{- end }}
{{- end }}


{{- define "volume.volumeMounts.auth" -}}
{{- if .Values.auth.enabled -}}
{{- if eq .Values.auth.env.registryAuth "htpasswd" }}
- name: registry-htpasswd
  mountPath: {{ .Values.auth.env.registryAuthHtpasswdPath }}
  subPath: {{ .Values.auth.env.registryAuthHtpasswdPathSubPath }}
{{- end }}
{{- end }}
{{- end }}


{{- define "volume.volumes.auth" -}}
{{- if .Values.auth.enabled -}}
{{- if eq .Values.auth.env.registryAuth "htpasswd" }}
- name: registry-htpasswd
  configMap:
    name: registry-htpasswd
{{- end }}
{{- end }}
{{- end }}


{{- define "volume.volumeMounts.tls" -}}
{{- if .Values.tls.enabled -}}
- name: registry-tls-cert
  mountPath: {{ .Values.tls.env.registryHttpTlsCertificate }}
  subPath: {{ .Values.tls.env.registryHttpTlsCertificateSubPath }}
- name: registry-tls-key
  mountPath: {{ .Values.tls.env.registryHttpTlsKey }}
  subPath: {{ .Values.tls.env.registryHttpTlsKeySubPath }}
{{- end }}
{{- end }}

{{- define "volume.volumes.tls" -}}
{{- if .Values.tls.enabled -}}
- name: registry-tls-cert
  configMap:
    name: registry-tls-cert
- name: registry-tls-key
  configMap:
    name: registry-tls-key
{{- end }}
{{- end }}