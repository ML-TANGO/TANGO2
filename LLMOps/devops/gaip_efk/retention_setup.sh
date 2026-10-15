#!/bin/sh
set -eu

# Run inside an Elasticsearch pod. A dated index is deleted one extra day
# after its requested retention so records written late in the day are kept
# for at least the full requested period.
ES_URL=${ES_URL:-https://elasticsearch:9200}
ES_USER=${ES_USER:-elastic}

if [ "${EFK_DRY_RUN:-0}" != "1" ]; then
    if [ -n "${ELASTICSEARCH_PASSWORD_FILE:-}" ]; then
        ES_PASSWORD=$(cat "$ELASTICSEARCH_PASSWORD_FILE")
    elif [ -n "${ELASTICSEARCH_PASSWORD:-}" ]; then
        ES_PASSWORD=$ELASTICSEARCH_PASSWORD
    else
        echo "Elasticsearch password is required" >&2
        exit 1
    fi
fi

put_json() {
    path=$1
    payload=$2
    if [ "${EFK_DRY_RUN:-0}" = "1" ]; then
        printf '%s\n' "$payload"
        return
    fi
    response=$(printf '%s' "$payload" | curl -fsSk \
        --user "$ES_USER:$ES_PASSWORD" \
        -H 'Content-Type: application/json' \
        -X PUT "$ES_URL/$path" --data-binary @-)
    case "$response" in
        *'"acknowledged":true'*) ;;
        *) echo "Elasticsearch did not acknowledge $path: $response" >&2; exit 1 ;;
    esac
}

for period in '1:2' '7:8' '15:16' '30:31'; do
    requested=${period%%:*}
    expiry=${period#*:}
    put_json "_ilm/policy/efk-retain-${requested}d" \
        "{\"policy\":{\"phases\":{\"delete\":{\"min_age\":\"${expiry}d\",\"actions\":{\"delete\":{}}}}}}"
done

# Date-based indices are written directly by Fluent Bit. Rollover aliases and
# data stream templates do not apply to this output configuration.
for rule in \
    'congregate_failed:1' \
    'system-kubecomp:1' \
    'thirdparty:1' \
    'system-event:1' \
    'system-kubelet:1' \
    'jonathan-control-unmarked:7' \
    'jonathan-control:30' \
    'jonathan-user:15' \
    'jonathan-usage:keep' \
    'jonathan-resource:keep' \
    'jonathan-resource-workspace_usage:keep' \
    'jonathan-resource-jonathan_usage:keep' \
    'jonathan-resource-gpu_usage:keep' \
    'jonathan-worker:keep'; do
    prefix=${rule%%:*}
    retention=${rule#*:}
    if [ "$retention" = keep ]; then
        settings='{}'
    else
        settings="{\"index.lifecycle.name\":\"efk-retain-${retention}d\"}"
    fi
    put_json "_index_template/efk-daily-${prefix}" \
        "{\"index_patterns\":[\"${prefix}-20*\"],\"priority\":650,\"template\":{\"settings\":$settings,\"mappings\":{\"properties\":{\"@timestamp\":{\"type\":\"date_nanos\"},\"time\":{\"type\":\"date_nanos\"}}}}}"
done

# Catch new control/resource subcategories. The explicit templates above have
# a higher priority, so unmarked control logs keep their shorter period.
put_json "_index_template/efk-daily-jonathan-control-other" \
    '{"index_patterns":["jonathan-control-*-20*"],"priority":640,"template":{"settings":{"index.lifecycle.name":"efk-retain-30d"},"mappings":{"properties":{"@timestamp":{"type":"date_nanos"},"time":{"type":"date_nanos"}}}}}'
put_json "_index_template/efk-daily-jonathan-resource-other" \
    '{"index_patterns":["jonathan-resource-*-20*"],"priority":640,"template":{"mappings":{"properties":{"@timestamp":{"type":"date_nanos"},"time":{"type":"date_nanos"}}}}}'

put_json "_ingest/pipeline/deduplicate_logs" \
    '{"description":"Deduplicate Kubernetes events","processors":[{"fingerprint":{"fields":["log","lastTimestamp","metadata.uid"],"target_field":"_dedupe_hash","method":"SHA-256","ignore_missing":true}},{"set":{"field":"_id","value":"{{_dedupe_hash}}","if":"ctx._dedupe_hash != null"}},{"script":{"source":"if (ctx._dedupe_hash != null) { ctx._version_type = \"external\"; ctx._version = System.currentTimeMillis(); }"}}]}'

echo "EFK daily index templates and retention policies are ready"
