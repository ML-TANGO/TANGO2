{{- define "resources" }}
limits:
  cpu: {{ .Values.resources.limits.cpu | quote }}
  memory: {{ printf "%sGi" (toString .Values.resources.limits.ram) | quote }}
  nvidia.com/gpu: {{ .cluster.gpu_count | quote }}
requests:
  cpu: "0"
  memory: "0"
  nvidia.com/gpu: {{ .cluster.gpu_count | quote }}  
{{- end }}
