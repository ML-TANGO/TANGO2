{{- define "src.baseDir" -}}
{{- if eq .Values.global.developer "acryl" -}}
/home/acryl/jfbcore_msa
{{- else if eq .Values.global.developer "luke" -}}
/home/luke/jfbcore_msa
{{- else if eq .Values.global.developer "klod" -}}
/home/klod/jfbcore_msa
{{- else if eq .Values.global.developer "jake" -}}
/home/jake/jfbcore_msa
{{- else if eq .Values.global.developer "walter" -}}
/home/walter/jfbcore_msa
{{- else if eq .Values.global.developer "min" -}}
/home/min/jfbcore_msa
{{- else -}}
/jfbcore_msa
{{- end -}}
{{- end -}}


{{- define "db.nodePort" -}}
{{- if eq .Values.global.developer "acryl" -}}
30000
{{- else if eq .Values.global.developer "luke" -}}
30031
{{- else if eq .Values.global.developer "klod" -}}
30032
{{- else if eq .Values.global.developer "jake" -}}
30033
{{- else if eq .Values.global.developer "walter" -}}
30034
{{- else if eq .Values.global.developer "min" -}}
30036
{{- else -}}
30035
{{- end -}}
{{- end -}}


{{/* launcher.daemonset */}}
{{- define "launcher.hostPort" -}}
{{- if eq .Values.global.developer "acryl" -}}
20000
{{- else if eq .Values.global.developer "luke" -}}
20001
{{- else if eq .Values.global.developer "jake" -}}
20002
{{- else if eq .Values.global.developer "klod" -}}
20003
{{- else if eq .Values.global.developer "walter" -}}
20004
{{- else if eq .Values.global.developer "min" -}}
20006
{{- else -}}
20005
{{- end -}}
{{- end -}}


{{- define "nodeName" -}}
nodeName: {{ .Values.nodeName.name }}
{{- end }}

{{- define "dir.data" -}}
{{- $baseDir := include "src.baseDir" . -}}
{{- $baseDir }}/data
{{- end -}}

{{- define "dir.bin" -}}
{{- $baseDir := include "src.baseDir" . -}}
{{- $baseDir }}/bin
{{- end -}}



{{- define "frontVolume" -}}
{{- if eq .Values.front.volume "pvc" -}}
persistentVolumeClaim:
  claimName: jfb-{{ .Values.global.developer }}-front-pvc
{{- else if eq .Values.front.volume "emptyDir" -}}
emptyDir: {}
{{- end -}}
{{- end -}}




{{/* volume options:  kube, docker, built_in_models, data, data_ws, data_image, etc_host_dir, etc_host_file, pod_status, pod_usage */}}
{{- define "appVolumeMounts" -}}
volumeMounts:
{{- if $.src }}
  - name: jfb-src
    mountPath: /app
  - name: jfb-utils
    mountPath: /utils
{{- end }}
{{- range $val := .dir }}
{{- if eq $val "kube" }}
  - name: jfb-kube
    mountPath: /jf-bin/.kube
    readOnly: true
{{- end }}
{{- if eq $val "docker" }}
  - name: jfb-docker
    mountPath: /var/run/docker.sock
{{- end }}
{{- if eq $val "built_in_model" }}
  - name: jfb-built-in-model
    mountPath: /jf-bin/built_in_models
{{- end }}
{{- if eq $val "data" }}
  - name: jfb-data
    mountPath: /jf-data
{{- end }}
{{- if eq $val "data_ws" }}
  - name: jfb-data-ws
    mountPath: /jf-data/workspaces
{{- end }}
{{- if eq $val "data_image" }}
  - name: jfb-images
    mountPath: /jf-data/images
{{- end }}
{{- if eq $val "pod_status" }}
  - name: jfb-pod-status
    mountPath: /jf-data/pod-status
{{- end }}
{{- if eq $val "pod_usage" }}
  - name: jfb-pod-usage
    mountPath: /jf-data/pod_resource_usage
{{- end }}
{{- if eq $val "etc_host_dir" }}
  - name: jfb-etc
    mountPath: /etc_host
{{- end }}
{{- if eq $val "etc_host_file" }}
  - name: jfb-etc
    mountPath: /etc/passwd
    subPath: passwd
    readOnly: true
  - name: jfb-etc
    mountPath: /etc/shadow
    subPath: shadow
    readOnly: true
  - name: jfb-etc
    mountPath: /etc/gshadow
    subPath: gshadow
    readOnly: true
  - name: jfb-etc
    mountPath: /etc/group
    subPath: group
    readOnly: true
{{- end }}
{{- end }}
{{- end }}



{{- define "appVolumes" -}}
volumes:
{{- if $.src }}
- name: jfb-src
  persistentVolumeClaim:
    claimName: jfb-{{ $.developer }}-src-{{ $.app }}-pvc
- name: jfb-utils
  persistentVolumeClaim:
    claimName: jfb-{{ $.developer }}-utils-pvc
{{- end }}
{{- range $val := .dir }}
{{- if eq $val "kube" }}
- name: jfb-kube
  persistentVolumeClaim:
    claimName: jfb-{{ $.developer }}-kube-pvc
{{- end }}
{{- if eq $val "docker" }}
- name: jfb-docker
  persistentVolumeClaim:
    claimName: jfb-{{ $.developer }}-docker-pvc
{{- end }}
{{- if eq $val "built_in_model" }}
- name: jfb-built-in-model
  persistentVolumeClaim:
    claimName: jfb-{{ $.developer }}-built-in-model-pvc
{{- end }}
{{- if eq $val "data" }}
- name: jfb-data
  persistentVolumeClaim:
    claimName: jfb-{{ $.developer }}-data-pvc
{{- end }}
{{- if eq $val "data_ws" }}
- name: jfb-data-ws
  persistentVolumeClaim:
    claimName: jfb-{{ $.developer }}-data-ws-pvc
{{- end }}
{{- if eq $val "data_image" }}
- name: jfb-images
  persistentVolumeClaim:
    claimName: jfb-{{  $.developer  }}-data-image-pvc
{{- end }}
{{- if eq $val "pod_status" }}
- name: jfb-pod-status
  persistentVolumeClaim:
    claimName: jfb-{{ $.developer }}-data-pod-status-pvc
{{- end }}
{{- if eq $val "pod_usage" }}
- name: jfb-pod-usage
  persistentVolumeClaim:
    claimName: jfb-{{ $.developer }}-data-pod-usage-pvc
{{- end }}
{{- end }}
{{- if has (or "etc_host_dir" "etc_host_file") .dir}}
- name: jfb-etc
  persistentVolumeClaim:
    claimName: jfb-{{ $.developer }}-etc-pvc
{{- end }}
{{- end }}