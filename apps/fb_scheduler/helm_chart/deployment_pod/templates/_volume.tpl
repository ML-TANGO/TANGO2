{{- define "volumeMounts" -}}
volumeMounts:
- name: jf-ws
  mountPath: /root/project
  subPath: projects/{{ .Values.metadata.name.trainingName }}/src
- name: jf-ws
  mountPath: /built_in_checkpoint
  subPath: projects/{{ .Values.metadata.name.trainingName }}/built_in_checkpoint/{{ .Values.deployment.training_id }}
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
- name: jf-nginx
  mountPath: /etc/nginx/nginx.conf
  subPath: nginx.conf
- name: jf-nginx
  mountPath: /etc/nginx/conf.d/api.conf
  subPath: api.conf
- name: jf-log
  mountPath: /addlib/deployment_api_deco.py
  subPath: deployment_api_deco.py
- name: jf-log
  mountPath: /addlib/history.py
  subPath: history.py
- name: jf-log
  mountPath: /addlib/built_in_model_download.py
  subPath: built_in_model_download.py
- name: jf-log
  mountPath: /addlib/collect.py
  subPath: collect.py
{{- if .Values.offlineMode }}
{{- if .Values.privateRepo }}
- name: apt-gpg-key
  mountPath: /root/.apt
{{- end }}
{{- if .Values.privatePip }}
- name: pip-conf
  mountPath: /root/.config/pip
{{- end }}
{{- end }}
{{- end }}


{{- define "volumes" -}}
volumes:
{{- if .Values.offlineMode }}
{{- if .Values.privateRepo }}
- name: apt-gpg-key
  configMap:
    name: jonathan-private-repo-cm
{{- end }}
{{- if .Values.privatePip }}
- name: pip-conf
  configMap:
    name: jonathan-pip-cm
{{- end }}
{{- end }}
- name: jf-ws
  persistentVolumeClaim:
    claimName: {{ include "name" . }}-main-pvc
- name: jf-data
  persistentVolumeClaim:
    claimName: {{ include "name" . }}-data-pvc
- name: jf-bin
  persistentVolumeClaim:
    claimName: {{ include "name" . }}-bin-pvc
- name: jf-nginx
  configMap:
    name: {{ .Values.metadata.name.podName }}-nginx-cm
- name: jf-log
  configMap:
    name: {{ .Values.metadata.name.podName }}-log-cm
{{- end }}



{{/*
    - name: jf-ws
      mountPath: /resource_log
      subPath: pod_resource_usage/{{ .Values.metadata.name.podName }}
    - name: jf-bin
      mountPath: /etc/nginx_ex
      subPath: deployment_nginx
    - name: jf-data
      mountPath: /pod-status
      subPath: pod-status/{{ .Values.metadata.name.podName }}
*/}}