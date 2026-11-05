{{- define "readinessProbe" -}}
    {{- if eq .index 0 }}
    {{- if eq $.Values.labels.tool_type "jupyter" }}
    readinessProbe:
        httpGet:
            path: /{{ $.Values.labels.tool_type }}/{{ $.Values.pod_name }}-{{ .index }}/api
            port: {{ $.Values.service.port }}
        initialDelaySeconds: 10
        periodSeconds: 5
        timeoutSeconds: 3
        successThreshold: 1
    {{- else if eq $.Values.labels.tool_type "vscode" }}
    readinessProbe:
        httpGet:
            path: /healthz
            port: {{ $.Values.service.port }}
        initialDelaySeconds: 15
        periodSeconds: 5
        timeoutSeconds: 3
        successThreshold: 1
    {{- else if eq $.Values.labels.tool_type "shell" }}
    readinessProbe:
        httpGet:
            path: /{{ $.Values.labels.tool_type }}/{{ $.Values.pod_name }}-{{ .index }}
            port: {{ $.Values.service.port }}
        initialDelaySeconds: 15
        periodSeconds: 5
        timeoutSeconds: 3
        successThreshold: 1
    {{- end }}
    {{- end }}
{{- end }}