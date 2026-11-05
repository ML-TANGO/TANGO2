{{ define "lib.render" }}
{{/* "Double render of the value, which contains helm template" */}}
  {{- if kindIs "string" .value }}
    {{- tpl .value .context }}
  {{- else }}
    {{- tpl (.value | toYaml) .context }}     
  {{- end }}
{{- end }}
