
{{- define "lib.volume.claim" -}}
{{- if eq .name "jf-bin" -}}
- name: jf-bin
  persistentVolumeClaim:
    claimName: jf-bin-pvc
{{- else if eq .name "jf-data" -}}
- name: jf-data
  persistentVolumeClaim:
    claimName: jf-data-pvc
{{- else if eq .name "jf-kube" -}}
- name: jf-kube
  configMap:
    name: jf-kube
{{- else if eq .name "jf-src" -}}
{{- if .enabled -}}
- name: jf-src
  persistentVolumeClaim:
    claimName: jf-src-{{ .app }}-pvc
- name: jf-utils
  persistentVolumeClaim:
    claimName: jf-src-utils-pvc
{{- end -}}
{{- else if eq .name "jf-storage" -}}
- name: storage-{{ .storageName }}
  mountPath: /jf-data/storage-{{ .storageName }}
{{- end -}}
{{- end -}}