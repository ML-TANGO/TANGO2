{{- define "lib.nodeSelector.manage" -}}
node-role.kubernetes.io/manage: ""
{{- end -}}

{{- define "lib.nodeSelector.db" -}}
node-role.kubernetes.io/db: ""
{{- end -}}
