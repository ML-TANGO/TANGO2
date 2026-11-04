{{- define "env.base" }}
- name: PYTHONUNBUFFERED
  value: "1"
{{- end }}

{{- define "env.analyzer" }}
- name: JF_ANALYZER_ID
  value: {{ .Values.analyzer.analyzer_id | quote | default "" }}
- name: JF_GRAPH_ID
  value: {{ .Values.analyzer.graph_id | quote | default "" }}
- name: JF_GRAPH_TYPE
  value: {{ .Values.analyzer.graph_type | quote | default "" }}
- name: JF_DATA_PATH
  value: {{ .Values.analyzer.data_path | quote | default "" }}
- name: JF_COLUMN
  value: {{ .Values.analyzer.column | quote | default "" }}
{{- end }}

{{- define "env.gpu" }}
{{- if and (eq .node.device.type "GPU") .node.device.uuids }}
- name: "NVIDIA_VISIBLE_DEVICES"
  value: {{ .node.device.uuids }}
{{- end }}
{{- end }}

{{- define "env.db" }}
- name: JF_DB_HOST
  value: {{ .Values.db.host | quote | default "" }}
- name: JF_DB_PORT  
  value: {{ .Values.db.port | quote | default "" }}
- name: JF_DB_USER
  value: {{ .Values.db.user | quote | default "" }}
- name: JF_DB_PW
  value: {{ .Values.db.pw | quote | default "" }}
- name: JF_DB_NAME
  value: {{ .Values.db.name | quote | default "" }}
- name: JF_DB_CHARSET
  value: {{ .Values.db.charset | quote | default "" }}
- name: JF_DB_COLLATION
  value: {{ .Values.db.collation | quote | default "" }}
{{- end }}
