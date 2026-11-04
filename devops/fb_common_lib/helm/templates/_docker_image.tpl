{{- define "lib.image" -}}
{{- $registry := .registry -}}
{{- $image := .image -}}

{{/* "Check leftmost part divided with : or /, check registry is contained" */}}
{{- $firstPart := (split ":" (split "/" $image)._0)._0 -}}

{{- if contains "." $firstPart }}
  {{- $image }}
{{- else }}
  {{- printf "%s/%s" $registry $image }}
{{- end }}
{{- end }}

{{/* Usage: double curly brackets with 'include "lib.image" (dict "registry" .Values.to.registry "image" .Values.to.image.which.may.contains.registry.or.not)' */}}
