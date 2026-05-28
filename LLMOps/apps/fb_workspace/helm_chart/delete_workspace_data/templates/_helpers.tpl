{{- define "check_unique_volumes" }}
{{- $main_storage := .Values.main_storage -}}
{{- $data_storage := .Values.data_storage -}}

{{- if eq $main_storage $data_storage -}}
- name: storage
  persistentVolumeClaim:
    claimName: {{ .Values.main_storage }}
{{- else -}}
- name: main_storage
  persistentVolumeClaim:
    claimName: {{ .Values.main_storage }}
- name: data_storage
  persistentVolumeClaim:
    claimName: {{ .Values.data_storage }}
{{- end -}}
{{- end -}}

{{- define "check_unique_volumeMounts" -}}
{{- $main_storage := .Values.main_storage -}}
{{- $data_storage := .Values.data_storage -}}

{{- if eq $main_storage $data_storage -}}
- name: storage
  mountPath: /jf-data/{{ .Values.main_storage }}
{{- else -}}
- name: main_storage
  mountPath: /jf-data/{{ .Values.main_storage }}
- name: data_storage
  mountPath: /jf-data/{{ .Values.data_storage }}
{{- end -}}
{{- end -}}

