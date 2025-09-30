#!/bin/bash

# Elasticsearch 연결 정보
ES_HOST="elasticsearch-master-hl:9200"
ES_USER="${ELASTICSEARCH_USERNAME}"
ES_PASS="${ELASTICSEARCH_PASSWORD}"

# 인증 정보 확인
if [ -z "$ES_USER" ] || [ -z "$ES_PASS" ]; then
    echo "Error: Elasticsearch credentials are not set in environment variables."
    echo "Please set ELASTICSEARCH_USERNAME and ELASTICSEARCH_PASSWORD."
    exit 1
fi

# 템플릿, duration, 우선순위를 정의합니다
declare -A templates
templates=(
    ["congregate_failed"]="tiny:300"
    ["system-kubecomp"]="tiny:300"
    ["thirdparty"]="tiny:300"
    ["system-event"]="tiny:300"
    ["system-kubelet"]="tiny:300"
    ["jonathan-control-unmarked"]="short:500"
    ["jonathan-control"]="long:300"
    ["jonathan-usage"]="perma:300"
    ["jonathan-user"]="medium:300"
)

# curl 명령어 함수
es_curl() {
    curl -s -k -u "${ES_USER}:${ES_PASS}" "$@"
}

# 각 duration에 대한 설정을 정의하는 함수
get_policy_json() {
    local duration=$1
    local hot_max_age
    local hot_max_size
    local warm_min_age
    local cold_min_age
    local delete_min_age
    local delete_phase

    case $duration in
        tiny)
            hot_max_age="12h"
            hot_max_size="2gb"
            warm_min_age="3h"
            cold_min_age="12h"
            delete_min_age="1d"
            delete_phase=true
            ;;
        short)
            hot_max_age="2d"
            hot_max_size="5gb"
            warm_min_age="1d"
            cold_min_age="3d"
            delete_min_age="7d"
            delete_phase=true
            ;;
        medium)
            hot_max_age="7d"
            hot_max_size="10gb"
            warm_min_age="3d"
            cold_min_age="7d"
            delete_min_age="15d"
            delete_phase=true
            ;;
        long)
            hot_max_age="7d"
            hot_max_size="10gb"
            warm_min_age="7d"
            cold_min_age="15d"
            delete_min_age="30d"
            delete_phase=true
            ;;
        perma)
            hot_max_age="30d"
            hot_max_size="20gb"
            warm_min_age="30d"
            cold_min_age="90d"
            delete_phase=false
            ;;
    esac

    local policy_json='{
        "policy": {
            "phases": {
                "hot": {
                    "min_age": "0ms",
                    "actions": {
                        "rollover": {
                            "max_age": "'$hot_max_age'",
                            "max_primary_shard_size": "'$hot_max_size'"
                        },
                        "set_priority": {
                            "priority": 100
                        }
                    }
                },
                "warm": {
                    "min_age": "'$warm_min_age'",
                    "actions": {
                        "set_priority": {
                            "priority": 50
                        }
                    }
                },
                "cold": {
                    "min_age": "'$cold_min_age'",
                    "actions": {
                        "downsample": {
                            "fixed_interval": "1m",
                            "wait_timeout": "1d"
                        },
                        "set_priority": {
                            "priority": 0
                        }
                    }
                }'

    if [ "$delete_phase" = true ]; then
        policy_json+=',
                "delete": {
                    "min_age": "'$delete_min_age'",
                    "actions": {
                        "delete": {
                            "delete_searchable_snapshot": true
                        }
                    }
                }'
    fi

    policy_json+='
            }
        }
    }'

    echo "$policy_json"
}

# 각 패턴에 대한 ILP를 생성하는 함수
create_policy() {
    local pattern=$1
    local duration=$2
    local policy_name="ilp_${pattern}"
    
    local policy_json=$(get_policy_json "$duration")

    es_curl -X PUT "https://${ES_HOST}/_ilm/policy/jonathan-ilp-$policy_name" -H 'Content-Type: application/json' -d "$policy_json"
    echo "Created ILP: jonathan-ilp-$policy_name"
}

# 각 템플릿에 대한 Index Template을 생성하는 함수
create_template() {
    local pattern=$1
    local duration=$2
    local priority=$3
    local policy_name="ilp_${pattern}"

    local template_json='{
        "index_patterns": ["'$pattern'*"],
        "template": {
            "settings": {
                "index.lifecycle.name": "'jonathan-ilp-$policy_name'",
                "index.lifecycle.rollover_alias": "'$pattern'"
            },
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date_nanos"},
                    "time": {"type": "date_nanos"}
                }
            }
        },
        "priority": '$priority',
	    "data_stream": {}
    }'

    es_curl -X PUT "https://${ES_HOST}/_index_template/jonathan-template-$pattern" -H 'Content-Type: application/json' -d "$template_json"
    echo "Created Index Template: jonathan-template-$pattern"
}

create_pipeline(){
    local pipeline_json='{
    	"description": "Deduplicate logs",
  "processors": [
    {
      "fingerprint": {
        "fields": [
          "log",
          "lastTimestamp",
          "metadata.uid"
        ],
        "target_field": "_dedupe_hash",
        "method": "SHA-256"
      }
    },
    {
      "set": {
        "field": "_id",
        "value": "{{_dedupe_hash}}"
      }
    },
    {
      "script": {
        "source": "if (ctx._dedupe_hash != null) {\r\n    ctx._version_type = \"external\";\r\n    ctx._version = System.currentTimeMillis();\r\n}"
      }
    }
  ]
}'
    es_curl -X PUT "https://${ES_HOST}/_ingest/pipeline/deduplicate_logs" -H 'Content-Type: application/json' -d "$pipeline_json"
    echo "Create dedup pipeline"
}

# 메인 실행 부분
for pattern in "${!templates[@]}"; do
    IFS=':' read -r duration priority <<< "${templates[$pattern]}"
    create_policy "$pattern" "$duration"
    create_template "$pattern" "$duration" "$priority"
    create_pipeline
done

echo "All Elasticsearch ILPs and Index Templates have been created."
