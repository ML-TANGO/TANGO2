# 센서의 최근 데이터 조회

- ⚠️ 요청 메시지 포맷에 대한 논의 필요
- 센서 데이터를 요청하는 노드 하나 당 요청 메시지 하나 (다수의 노드가 요청해야 하는 경우 해당 노드 수 만큼 메시지 전송이 필요함)
- 대상 센서가 여러 개 존재하는 경우 address 를 지정

## :arrow_up: Upstream

- topic: {application}/{region_id}/_upstream/{gateway_id}

```json
{
    "command": "get_latest_value_req",
    "response_topic": "{application}/{site_id}/_upstream/{gateway_id}",
    "seq": "<unsigned long>",
    "node_id": "string",
    "address_4": true,
    "address_5": true
}
```

## :arrow_down: Downstream

- topic: {application}/{region_id}/_downstream/{gateway_id}

```json
{
  "command": "get_latest_value_resp",
  "seq": "<unsigned long>",
  "data": [
    {
      "node_id": "node_id_1",
      "address_4": {
        "sampling_rate": int,
        "bit_depth": int,
        "data": "base64 encoded string"
      },
      "address_5": {
        "channel_1": {
          "value": unknown type
        }
      }
    }
  ]
}
```