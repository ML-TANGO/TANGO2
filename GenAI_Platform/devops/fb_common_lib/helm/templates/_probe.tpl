{{- define "lib.probe.readiness" -}}
{{- if eq .app "dashboard" -}}
readinessProbe:
  httpGet:
    path: api/dashboard/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 1
  failureThreshold: 3
  successThreshold: 1
{{- else if eq .app "dataset" -}}
readinessProbe:
  httpGet:
    path: api/datasets/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 1
  failureThreshold: 3
  successThreshold: 1
{{- else if eq .app "collect" -}}
readinessProbe:
  httpGet:
    path: api/collect/healthz
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 5
  successThreshold: 1
{{- else if eq .app "resource" -}}
readinessProbe:
  httpGet:
    path: api/resources/healthz
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 5
  successThreshold: 1
{{- else if eq .app "scheduler" -}}
readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 5
  successThreshold: 1
{{- else if eq .app "deployment" -}}
readinessProbe:
  httpGet:
    path: api/deployments/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 1
  failureThreshold: 3
  successThreshold: 1
{{- else if eq .app "image" -}}
readinessProbe:
  httpGet:
    path: api/images/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 1
  failureThreshold: 3
  successThreshold: 1
{{- else if eq .app "notification" -}}
readinessProbe:
  httpGet:
    path: api/notification/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 1
  failureThreshold: 3
  successThreshold: 1
{{- else if eq .app "alert_management" -}}
readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 5
  successThreshold: 1
{{- else if eq .app "ssh" -}}
readinessProbe:
  httpGet:
    path: api/ssh/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 5
  successThreshold: 1
{{- else if eq .app "training" -}}
readinessProbe:
  httpGet:
    path: api/projects/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 1
  failureThreshold: 3
  successThreshold: 1
{{- else if eq .app "preprocessing" -}}
readinessProbe:
  httpGet:
    path: api/preprocessing/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 1
  failureThreshold: 3
  successThreshold: 1
{{- else if eq .app "user" -}}
readinessProbe:
  httpGet:
    path: api/users/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 1
  failureThreshold: 3
  successThreshold: 1
{{- else if eq .app "workspace" -}}
readinessProbe:
  httpGet:
    path: api/workspaces/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 1
  failureThreshold: 3
  successThreshold: 1
{{- else if eq .app "model" -}}
readinessProbe:
  httpGet:
    path: api/models/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 1
  failureThreshold: 3
  successThreshold: 1
{{- else if eq .app "cost-management" -}}
readinessProbe:
  httpGet:
    path: api/cost-management/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 1
  failureThreshold: 3
  successThreshold: 1
{{- else if eq .app "sb-rag" -}}
readinessProbe:
  httpGet:
    path: api/sb/rags/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 1
  failureThreshold: 3
  successThreshold: 1
{{- else if eq .app "sb-service" -}}
readinessProbe:
  httpGet:
    path: api/sb/services/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 1
  failureThreshold: 3
  successThreshold: 1
{{- end -}}
{{- end -}}


{{- define "lib.probe.liveness" -}}
{{- if eq .app "dashboard" -}}
livenessProbe:
  httpGet:
    path: api/dashboard/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3
{{- else if eq .app "dataset" -}}
livenessProbe:
  httpGet:
    path: api/datasets/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3
{{- else if eq .app "collect" -}}
livenessProbe:
  httpGet:
    path: api/collect/healthz
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 15
  timeoutSeconds: 3
  failureThreshold: 3
{{- else if eq .app "resource" -}}
livenessProbe:
  httpGet:
    path: api/resources/healthz
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 15
  timeoutSeconds: 3
  failureThreshold: 3
{{- else if eq .app "scheduler" -}}
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 15
  timeoutSeconds: 5
  failureThreshold: 3
{{- else if eq .app "deployment" -}}
livenessProbe:
  httpGet:
    path: api/deployments/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3
{{- else if eq .app "image" -}}
livenessProbe:
  httpGet:
    path: api/images/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3
{{- else if eq .app "notification" -}}
livenessProbe:
  httpGet:
    path: api/notification/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3
{{- else if eq .app "alert_management" -}}
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 15
  timeoutSeconds: 3
  failureThreshold: 3
{{- else if eq .app "ssh" -}}
livenessProbe:
  httpGet:
    path: api/ssh/healthz
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3
{{- else if eq .app "training" -}}
livenessProbe:
  httpGet:
    path: api/projects/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3
{{- else if eq .app "preprocessing" -}}
livenessProbe:
  httpGet:
    path: api/preprocessing/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3
{{- else if eq .app "user" -}}
livenessProbe:
  httpGet:
    path: api/users/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3
{{- else if eq .app "workspace" -}}
livenessProbe:
  httpGet:
    path: api/workspaces/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3
{{- else if eq .app "model" -}}
livenessProbe:
  httpGet:
    path: api/models/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3
{{- else if eq .app "cost-management" -}}
livenessProbe:
  httpGet:
    path: api/cost-management/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3
{{- else if eq .app "sb-rag" -}}
livenessProbe:
  httpGet:
    path: api/sb/rags/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3
{{- else if eq .app "sb-service" -}}
livenessProbe:
  httpGet:
    path: api/sb/services/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3
{{- end -}}
{{- end -}}