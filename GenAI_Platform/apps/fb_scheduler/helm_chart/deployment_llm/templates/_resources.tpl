{{- define "resources" }}
limits:
  cpu: {{ printf "%0.2f"  (subf (float64 .Values.resources.limits.cpu)  "0.1")   | quote }}
  memory: {{ printf "%0.2fG"  (subf (float64 .Values.resources.limits.memory)  "0.1")   | quote }}
  {{- if gt (int .Values.resources.limits.npu) 0 }}
  acryl.ai/dummy-npu: {{ .Values.resources.limits.npu }}
  {{- end }}
  {{- if .Values.rdma.enabled }}
  rdma/jf_roce: 1
  {{- end }}
requests:
  cpu: "0"
  memory: "0"
  {{- if gt (int .Values.resources.limits.npu) 0 }}
  acryl.ai/dummy-npu: {{ .Values.resources.limits.npu }}
  {{- end }}
  {{- if .Values.rdma.enabled }}
  rdma/jf_roce: 1
  {{- end }}
{{- end }}



{{- define "resources.log" }}
limits:
  cpu: "0.1"
  memory: "100M"
requests:
  cpu: "0"
  memory: "0"
{{- end }}
