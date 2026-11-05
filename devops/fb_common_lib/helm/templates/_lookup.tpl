{{- define "lib.lookup.kong" -}}
{{- $services := (lookup "v1" "Service" .Values.global.jfb.namespace "" ) }}
    {{- range $service := $services.items -}}
        {{- if (contains "kong-proxy" $service.metadata.name ) -}}
            {{- (index $service.status.loadBalancer.ingress 0 ).ip }}
        {{- end -}}
    {{- end -}}
{{- end -}}

{{- define "lib.lookup.nfsProvisioner" -}}
{{- $namespace := .Values.global.jfb.namespace }}
{{- $storageClass := (lookup "storage.k8s.io/v1" "StorageClass" .Values.global.jfb.namespace "" ) }}
    {{- range $sc := $storageClass.items -}}
        {{- if (and (contains "jfb2-workspaces-provisioner" $sc.metadata.labels.chart ) (contains $namespace $sc.metadata.labels.release )) -}}
            {{- $sc.metadata.name -}}
        {{- end -}}
    {{- end -}}
{{- end -}}

{{- define "lib.lookup.kafka" -}}
{{- $namespace := .Values.global.jfb.namespace }}
{{- $services := (lookup "v1" "Service" .Values.global.jfb.namespace "" ) }}
    {{- range $service := $services.items -}}
        {{- $labels := $service.metadata.labels -}}
        {{- $key := "app.kubernetes.io/component" }}
        {{- if hasKey $labels $key -}}
            {{- if eq "kafka" (index $labels $key) -}}
                {{- $kafkaname := index $labels $key -}}
                    {{- printf "%s.%s.svc.cluster.local" $kafkaname $namespace -}}
            {{- end -}}
        {{- end -}}
    {{- end -}}
{{- end -}}

{{- define "lib.lookup.settings" -}}
{{- $configMap := . -}}
{{- $configMap := (lookup "v1" "ConfigMap" .Values.global.jfb.namespace "jfb-settings" ) }}
{{- $hash := sha256sum (toYaml $configMap.data ) -}}
{{- $hash -}}
{{- end -}}