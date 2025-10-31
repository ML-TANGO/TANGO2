
{{- define "namespace" -}}
{{ .Values.system.namespace }}-{{ .Values.labels.workspace_id }}
{{- end }}


{{- define "name" -}}
{{ .Values.system.namespace }}-{{ .Values.labels.workspace_id }}
{{- end }}

{{/* 임시 default 사용
{{- define "runcode" -}}
{{- if eq .Values.spec.containers.command.run_code_type "py" }}                                                                                                    
python3 -u {{ .Values.spec.containers.command.run_code }} {{ .Values.spec.containers.command.parameter }}
{{- else if eq .Values.spec.containers.command.run_code_type "sh" }}
bash {{ .Values.spec.containers.command.run_code }} {{ .Values.spec.containers.command.parameter }}
{{- end }}
{{- end }}
*/}}