{{- define "lib.volume.volumeMounts.storage" -}}
{{- range $index, $volume := $.Values.global.jfb.volume.jfStorage -}}
- name: storage-{{ $volume.name }}
  mountPath: /jf-data/storage-{{ $volume.name }}
{{ end }}
{{- end }}


{{- define "lib.volume.claim.storage" -}}
{{- range $index, $volume := $.Values.global.jfb.volume.jfStorage -}}
- name: storage-{{ $volume.name }}
  persistentVolumeClaim:
    claimName: storage-{{ $volume.name }}
{{ end }}
{{- end }}