{{- define "name" -}}
{{ .Values.metadata.namespace.systemNamespace }}-{{ .Values.metadata.namespace.workspaceId }}
{{- end }}

{{- define "namespace" -}}
{{ .Values.metadata.namespace.systemNamespace }}-{{ .Values.metadata.namespace.workspaceId }}
{{- end }}


{{- define "specSetting" }}
hostNetwork: false
hostIPC: true  #TODO JI Docker에서 사용하는 부분이 있음
restartPolicy: Never
terminationGracePeriodSeconds: 0
securityContext:
  fsGroup: 0 # fsGroup은 spec 하위에서 설정
{{- end }}


{{- define "containerSetting" }}
lifecycle: # 배포는 따로 lifecycle command 가져오지는 않음
  postStart:
    exec:
      command: [/bin/sh, -c, echo START]
  preStop:
    exec:
      command: [/bin/sh, -c, echo END]
securityContext:
  capabilities:
    add:
    - IPC_LOCK
  privileged: false # deployment false
  runAsUser: 0
  runAsGroup: 0
startupProbe:
  tcpSocket:
    port: 8555  # FastAPI의 포트
  initialDelaySeconds: 15
  periodSeconds: 5
  failureThreshold: 1000
{{- end }}
