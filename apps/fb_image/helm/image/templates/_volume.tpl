{{- define "volumeMounts.containerRuntime" -}}
{{- if eq .Values.common.systemContainerRuntime "containerd" -}}
- name: socket
  mountPath: /run/containerd/containerd.sock
- name: root
  mountPath: /var/lib/containerd
  readOnly: false
{{- else if eq .Values.common.systemContainerRuntime "docker" -}}
- name: socket
  mountPath: /var/run/docker.sock
- name: root
  mountPath: /var/lib/docker
  readOnly: false
{{- end }}
{{- end }}

{{- define "volume.containerRuntime" -}}
{{- if eq .Values.common.systemContainerRuntime "containerd" -}}
- name: socket
  hostPath:
    type: Socket
    path: /run/containerd/containerd.sock
- name: root
  hostPath:
    path: {{ .Values.common.systemContainerDataRoot }}
{{- else if eq .Values.common.systemContainerRuntime "docker" -}}
- name: socket
  hostPath:
    type: Socket
    path: /var/run/docker.sock
- name: root
  hostPath:
    path: {{ .Values.common.systemContainerDataRoot }}
{{- end }}
{{- end }}



{{- define "volumeMounts.imageSecret" -}}
{{- if .Values.common.systemImagePullSecrets.enabled -}}
- name: image-secret
  mountPath: "/root/.docker"  # Secret이 마운트될 디렉토리
  subPath: "config.json"
  readOnly: true  # 파일을 읽기 전용으로 설정
{{- end }}
{{- end }}

{{- define "volume.imageSecret" -}}
{{- if .Values.common.systemImagePullSecrets.enabled -}}
- name: image-secret
  secret:
    secretName: jonathan-image-secrets
{{- end }}
{{- end }}





{{- define "volumeMounts.imageData" -}}
{{- if or (eq .Values.common.imageType "build") (eq .Values.common.imageType "tar")  }}
- name: jf-data
  mountPath: /jf-data
{{- end }}
{{- end }}


{{- define "volume.imageData" -}}
{{- if or (eq .Values.common.imageType "build") (eq .Values.common.imageType "tar")  }}
- name: jf-data
  persistentVolumeClaim:
    claimName: jfb-{{ .Values.common.systemNamespace }}-data-images-pvc
{{- end }}
{{- end }}