{{- define "lib.volume.volumeMounts" -}}
{{- if eq .name "jf-src" -}}
{{- if .enabled -}}
- name: jf-src
  mountPath: /app
- name: jf-utils
  mountPath: /fb_utils
{{- end -}}{{/*end of enabled*/}}
{{- /* ================data================ */ -}}
{{- else if eq .name "etc_host" -}}
- name: jf-data
  mountPath: /etc_host
  subPath: etc_host
{{- else if eq .name "workspaces" -}}
- name: jf-data
  mountPath: /jf-data/workspaces
  subPath: workspaces
{{- else if eq .name "images" -}}
- name: jf-data
  mountPath: /jf-data/images
  subPath: images
{{- else if eq .name "pod-status" -}}
- name: jf-data
  mountPath: /jf-data/pod-status
  subPath: pod-status
{{- else if eq .name "pod_resource_usage" -}}
- name: jf-data
  mountPath: /jf-data/pod_resource_usage
  subPath: pod_resource_usage
{{- /* ================bin================ */ -}}
{{- else if eq .name "jf-bin" -}}
- name: jf-bin
  mountPath: /jf-bin
{{- else if eq .name "jf-kube" -}}
{{/*kube config는 volume.configMap으로 마운트*/}}
- name: jf-kube
  mountPath: /jf-bin/.kube/config
  subPath: config
{{- else if eq .name "built_in_models" -}}
- name: jf-bin
  mountPath: /jf-bin/built_in_models
  subPath: built_in_models
{{- else if eq .name "deployment_logs" -}}
- name: jf-bin
  mountPath: /jf-bin/deployment_logs
  subPath: deployment_logs
{{- else if eq .name "deployment_nginx" -}}
- name: jf-bin
  mountPath: /jf-bin/deployment_nginx
  subPath: deployment_nginx
{{- else if eq .name "support" -}}
- name: jf-bin
  mountPath: /jf-bin/support
  subPath: support
{{- else if eq .name "sample" -}}
- name: jf-bin
  mountPath: /jf-bin/sample
  subPath: sample
{{- /*======================================*/ -}}
{{- else if eq .name "etc_file" -}}
- name: jf-data
  mountPath: /etc/passwd
  subPath: etc_host/passwd
- name: jf-data
  mountPath: /etc/shadow
  subPath: etc_host/shadow
- name: jf-data
  mountPath: /etc/group
  subPath: etc_host/group
- name: jf-data
  mountPath: /etc/gshadow
  subPath: etc_host/gshadow
{{- end -}}{{/*end of if*/}}
{{- end -}}{{/*end of define*/}}


{{- define "lib.volume.sbvolumeMounts" -}}
{{- if eq .name "jf-src" -}}
{{- if .enabled -}}
- name: jf-src
  mountPath: /app
- name: jf-utils
  mountPath: /fb_utils
- name: js-utils
  mountPath: /sb_utils
{{- end -}}{{/*end of enabled*/}}
{{- /* ================data================ */ -}}
{{- else if eq .name "etc_host" -}}
- name: jf-data
  mountPath: /etc_host
  subPath: etc_host
{{- else if eq .name "workspaces" -}}
- name: jf-data
  mountPath: /jf-data/workspaces
  subPath: workspaces
{{- else if eq .name "images" -}}
- name: jf-data
  mountPath: /jf-data/images
  subPath: images
{{- else if eq .name "pod-status" -}}
- name: jf-data
  mountPath: /jf-data/pod-status
  subPath: pod-status
{{- else if eq .name "pod_resource_usage" -}}
- name: jf-data
  mountPath: /jf-data/pod_resource_usage
  subPath: pod_resource_usage
{{- /* ================bin================ */ -}}
{{- else if eq .name "jf-bin" -}}
- name: jf-bin
  mountPath: /jf-bin
{{- else if eq .name "jf-kube" -}}
{{/*kube config는 volume.configMap으로 마운트*/}}
- name: jf-kube
  mountPath: /jf-bin/.kube/config
  subPath: config
{{- else if eq .name "built_in_models" -}}
- name: jf-bin
  mountPath: /jf-bin/built_in_models
  subPath: built_in_models
{{- else if eq .name "deployment_logs" -}}
- name: jf-bin
  mountPath: /jf-bin/deployment_logs
  subPath: deployment_logs
{{- else if eq .name "deployment_nginx" -}}
- name: jf-bin
  mountPath: /jf-bin/deployment_nginx
  subPath: deployment_nginx
{{- else if eq .name "support" -}}
- name: jf-bin
  mountPath: /jf-bin/support
  subPath: support
{{- else if eq .name "sample" -}}
- name: jf-bin
  mountPath: /jf-bin/sample
  subPath: sample
{{- /*======================================*/ -}}
{{- else if eq .name "etc_file" -}}
- name: jf-data
  mountPath: /etc/passwd
  subPath: etc_host/passwd
- name: jf-data
  mountPath: /etc/shadow
  subPath: etc_host/shadow
- name: jf-data
  mountPath: /etc/group
  subPath: etc_host/group
- name: jf-data
  mountPath: /etc/gshadow
  subPath: etc_host/gshadow
{{- end -}}{{/*end of if*/}}
{{- end -}}{{/*end of define*/}}