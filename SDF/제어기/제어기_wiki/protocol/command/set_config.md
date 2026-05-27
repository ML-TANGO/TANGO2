# 센서의 config 변경 명령

## :arrow_down: Downstream

- topic: {application}/{region_id}/_downstream/{gateway_id}

```json
{
  "command": "set_config_req",
  "response_topic": "{site_id}/_upstream/{gateway_id}",
  "seq": "<unsigned long>",
  "gateway": "json_object",
  "nodes": {
    "node_id_1": json_object,
    "node_id_2": json_object
  }
}
```

## :arrow_up: Upstream

- topic: {application}/{region_id}/_upstream/{gateway_id}

```json
{
  "command": "set_config_resp",
  "seq": "<unsigned long>",
  "gateway": int,
  "nodes": {
    "node_id_1": int,
    "node_id_2": int
  }
}
```
