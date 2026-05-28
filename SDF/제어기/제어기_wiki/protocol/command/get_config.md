# 디바이스 설정 값 조회 (수정필요)

- 서버에 설정되어 있는 디바이스 별 config 조회

## :arrow_up: Upstream

- topic: {application}/{region_id}/_upstream/{gateway_id}

```json
{
  "command": "get_config_req",
  "response_topic": "{site_id}/_downstream/{gateway_id}",
  "seq": "<unsigned long>",
  "node_id": "string"
}
```

## :arrow_down: Downstream

- topic: {application}/{region_id}/_downstream/{gateway_id}

```json
{
  "command": "get_config_resp",
  "seq": "<unsigned long>",
  "gateway": json_object,
  "nodes": {
    "node_id_1": json_object
  }
}
```