{{- define "volume" -}}
    volumeMounts:
    - name: jf-ws
      mountPath: /root/project
      subPath: projects/{{ .Values.metadata.name.trainingName }}
    - name: jf-ws
      mountPath: /root/project/datasets_ro
      subPath: datasets/0/
    - name: jf-ws
      mountPath: /root/project/datasets_rw
      subPath: datasets/1/
    - name: jf-ws
      mountPath: /log
      subPath: deployments/{{ .Values.metadata.name.deploymentName }}/log/{{ (splitList "-" .Values.pod.metadata.name ) | last }}
      {{/*
    - name: jf-ws
      mountPath: /resource_log
      subPath: pod_resource_usage/{{ .Values.pod.metadata.name }}
      */}}
    - name: jf-ws
      mountPath: /jf-deployment-home
      subPath: deployments/{{ .Values.metadata.name.deploymentName }}
    - name: jf-ws
      mountPath: /resource_log
      subPath: deployments/{{ .Values.metadata.name.deploymentName }}/pod_resource_usage/{{ .Values.pod.metadata.name }}
    - name: jf-bin
      mountPath: /addlib
      subPath: deployment_log
    - name: jf-bin
      mountPath: /etc/nginx_ex
      subPath: deployment_nginx
    - name: jf-bin
      mountPath: /usr/bin/support
      subPath: support
  volumes:
    - name: jf-ws
      persistentVolumeClaim:
        claimName: {{ include "name" . }}-main-pvc
    - name: jf-data
      persistentVolumeClaim:
        claimName: {{ include "name" . }}-data-pvc
    - name: jf-bin
      persistentVolumeClaim:
        claimName: {{ include "name" . }}-bin-pvc
{{- end }}


{{/*
    - name: jf-data
      mountPath: /pod-status
      subPath: pod-status/{{ .Values.pod.metadata.name }}
*/}}