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



{{/*
lifecycle: # 배포는 따로 lifecycle command 가져오지는 않음
  postStart:
    exec:
      command: [/bin/sh, -c, echo START]
  preStop:
    exec:
      command: [/bin/sh, -c, echo END]
*/}}