{{- define "resources" }}
limits:
  cpu: {{ .Values.resources.limits.cpu | quote }}
  memory: {{ printf "%dG" (int .Values.resources.limits.memory) | quote }}
  {{- if gt (int .Values.resources.limits.npu) 0 }}
  acryl.ai/dummy-npu: {{ .Values.resources.limits.npu }}
  {{- end }}
requests:
  cpu: "0"
  memory: "0"
  {{- if gt (int .Values.resources.limits.npu) 0 }}
  acryl.ai/dummy-npu: {{ .Values.resources.limits.npu }}
  {{- end }}
{{- end }}
