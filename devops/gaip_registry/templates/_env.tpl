{{- define "env.tls" -}}
{{- if .Values.tls.enabled -}}
- name: REGISTRY_HTTP_ADDR
  value: {{ .Values.auth.env.registryHttpAddr | quote }}
- name: REGISTRY_HTTP_TLS_CERTIFICATE
  value: {{ .Values.auth.env.registryHttpTlsCertificate | quote }}
- name: REGISTRY_HTTP_TLS_KEY
  value: {{ .Values.auth.env.registryHttpTlsKey | quote }}
{{- end }}
{{- end }}

{{- define "env.auth" -}}
{{- if .Values.auth.enabled -}}
- name: REGISTRY_AUTH
  value: {{ .Values.auth.env.registryAuth | quote }}
{{- if eq .Values.auth.env.registryAuth "htpasswd" }}
- name: REGISTRY_AUTH_HTPASSWD_REALM
  value: {{ .Values.auth.env.registryAuthHtpasswdRealm | quote }}
- name: REGISTRY_AUTH_HTPASSWD_PATH
  value: {{ .Values.auth.env.registryAuthHtpasswdPath | quote }}
{{- else if eq .Values.auth.env.registryAuth "token" }}
- name: REGISTRY_AUTH_TOKEN_REALM
  value: {{ .Values.auth.env.registryAuthTokenRealm | quote }}
- name: REGISTRY_AUTH_TOKEN_SERVICE
  value: {{ .Values.auth.env.registryAuthTokenService | quote }}
- name: REGISTRY_AUTH_TOKEN_ISSURE
  value: {{ .Values.auth.env.registryAuthTokenIssuer | quote }}
{{- else if eq .Values.auth.env.registryAuth "basic" }}
- name: REGISTRY_AUTH_BASIC_REALM
  value: {{ .Values.auth.env.registryAuthBasicRealm | quote }}
{{- end }}
{{- end }}
{{- end }}
{{/*REGISTRY_AUTH None은 추가 변수 없음*/}}


