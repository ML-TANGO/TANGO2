{{- define "volumeMounts" }}
- name: jf-ws
  mountPath: /root/project
  subPath: projects/{{ .Values.metadata.name.trainingName }}
- name: jf-data
  mountPath: /root/project/datasets_ro
  subPath: "0"
- name: jf-data
  mountPath: /root/project/datasets_rw
  subPath: "1"
- name: jf-ws
  mountPath: /log
  subPath: deployments/{{ .Values.metadata.name.deploymentName }}/log/{{ (splitList "-" .Values.metadata.name.podName ) | last }}
- name: jf-ws
  mountPath: /jf-deployment-home
  subPath: deployments/{{ .Values.metadata.name.deploymentName }}
- name: jf-ws
  mountPath: /resource_log
  subPath: deployments/{{ .Values.metadata.name.deploymentName }}/pod_resource_usage/{{ .Values.metadata.name.podName }}
- name: jf-bin
  mountPath: /addlib
  subPath: deployment_log
- name: jf-bin
  mountPath: /usr/bin/support
  subPath: support
- name: jf-bin
  mountPath: /usr/bin/distributed
  subPath: distributed
- name: jf-src
  mountPath: /etc/nginx/nginx.conf
  subPath: nginx.conf
- name: jf-src
  mountPath: /etc/nginx/conf.d/api.conf
  subPath: api.conf
- name: jf-src
  mountPath: /addlib/deployment_api_deco.py
  subPath: deployment_api_deco.py
- name: jf-src
  mountPath: /addlib/history.py
  subPath: history.py
- name: jf-src
  mountPath: /addlib/command.sh
  subPath: command.sh
- name: jf-src
  mountPath: /addlib/log.sh
  subPath: log.sh
{{- end }}


{{- define "volumeMounts.llm" }}
- name: llm
  mountPath: /llm
- name: jf-data
  mountPath: /jf-data/dataset/datasets_ro
  subPath: "0"
- name: jf-data
  mountPath: /jf-data/dataset/datasets_rw
  subPath: "1"
- name: jf-ws
  mountPath: /jf-data/rags
  subPath: rags
{{- if .Values.llm.model.allm_name }}
- name: jf-ws
  mountPath: /model
  subPath: models/{{ .Values.llm.model.allm_name }}/commit_models/{{ .Values.llm.model.allm_commit_name }}
{{- end }}
{{- end }}


{{- define "volumes" -}}
- name: jf-ws
  persistentVolumeClaim:
    claimName: {{ include "name" . }}-main-pvc
- name: jf-data
  persistentVolumeClaim:
    claimName: {{ include "name" . }}-data-pvc
- name: jf-bin
  persistentVolumeClaim:
    claimName: {{ include "name" . }}-bin-pvc
- name: jf-src
  configMap:
    name: {{ printf "%s-src" ( include "name.worker" . ) }}
    defaultMode: 0777
- name: llm
  configMap:
    name: {{ printf "%s-src-llm" ( include "name.worker" . ) }}
{{- end }}









{{/*
- name: nfs
  mountPath: /nfs
- name: nfs
  nfs:
    server: 192.168.0.20
    path: /jp/apps/fb_scheduler/helm_chart/deployment_llm/src/llm
- name: jf-nginx
  configMap:
    name: {{ .Values.metadata.name.podName }}-nginx-cm
- name: jf-log
  configMap:
    name: {{ .Values.metadata.name.podName }}-log-cm
*/}}