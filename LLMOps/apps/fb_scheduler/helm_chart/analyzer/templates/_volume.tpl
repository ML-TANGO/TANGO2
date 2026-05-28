{{- define "volumeMounts" }}
- name: jf-data
  mountPath: /jf-data/datasets_ro
  subPath: "0"
- name: jf-data
  mountPath: /jf-data/datasets_rw
  subPath: "1"
- name: jf-analyzer
  mountPath: /analyzer
{{- end }}

{{- define "volumes" -}}
- name: jf-data
  persistentVolumeClaim:
    claimName: {{ include "name" . }}-data-pvc
- name: jf-analyzer
  configMap:
    name: {{ .Values.metadata.name.podName }}-src
    defaultMode: 0777
{{- end }}





{{/*
- name: nfs
  mountPath: /nfs
- name: nfs
  nfs:
    server: 192.168.0.20
    path: /jp/apps/fb_scheduler/helm_chart/analyzer/src
*/}}