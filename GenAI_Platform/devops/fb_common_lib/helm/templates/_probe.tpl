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
{{- else if eq .app "ssh" -}}
readinessProbe:
  httpGet:
    path: api/ssh/healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 1
  failureThreshold: 3
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
{{- else if eq .app "ssh" -}}
livenessProbe:
  httpGet:
    path: api/ssh/healthz
    port: 8000
  initialDelaySeconds: 5
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
{{- end -}}
{{- end -}}