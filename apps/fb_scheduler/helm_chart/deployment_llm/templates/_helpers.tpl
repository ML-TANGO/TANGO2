{{- define "name" -}}
{{ .Values.metadata.namespace.systemNamespace }}-{{ .Values.metadata.id.workspaceId }}
{{- end }}

{{- define "namespace" -}}
{{ .Values.metadata.namespace.systemNamespace }}-{{ .Values.metadata.id.workspaceId }}
{{- end }}

{{- define "name.network" -}}
deployment-llm-{{ .Values.llm.type }}-{{ .Values.llm.id }}
{{- end }}
{{/*
deployment-llm-{{ .Values.llm.type }}-{{ .Values.llm.id }}{{- if eq .Values.llm.type "rag" }}-{{ .Values.llm.rag.deployment_type }}-{{ .Values.llm.rag.type }}{{- end }}
*/}}

{{- define "name.worker" -}}
deployment-worker-{{ .Values.deployment.deploymentWorkerId }}
{{- end }}


{{- define "helpers.spec.setting" }}
hostNetwork: false
hostIPC: true  #TODO JI Docker에서 사용하는 부분이 있음
restartPolicy: Never
terminationGracePeriodSeconds: 0
securityContext:
  fsGroup: 0 # fsGroup은 spec 하위에서 설정
{{- end }}


{{- define "helpers.spec.containers.setting" }}
securityContext:
  capabilities:
    add:
    - IPC_LOCK
  privileged: false # deployment false
  runAsUser: 0
  runAsGroup: 0
{{- end }}

{{- define "helpers.startupProbe" }}
startupProbe:
  tcpSocket:
    port: 8555  # FastAPI 애플리케이션 포트
  initialDelaySeconds: 15
  periodSeconds: 5
  failureThreshold: 1000
readinessProbe:
  tcpSocket:
    port: 8555  # FastAPI 애플리케이션 포트
  initialDelaySeconds: 15
  periodSeconds: 10
  failureThreshold: 3
{{- end }}


{{/*
lifecycle: # 배포는 따로 lifecycle command 가져오지는 않음
  postStart:
    exec:
      command: [/bin/sh, -c, echo START]
  preStop:
    exec:
      command: [/bin/sh, -c, echo END]
*/}}