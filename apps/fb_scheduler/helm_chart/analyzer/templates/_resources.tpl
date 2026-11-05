{{- define "resources" }}
limits:
  cpu: {{ printf "%0.2f"  (subf (float64 .Values.resources.limits.cpu)  "0.1")   | quote }}
  memory: {{ printf "%.2fG" (subf (float64 .Values.resources.limits.memory) "0.1")  | quote }}
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
