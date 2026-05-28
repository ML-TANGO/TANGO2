# 시간 동기화 명령

- Gateway의 시간 정보를 서버와 동기화
- 시간 정보를 최종적으로 사용하는 디바이스: Gateway

## :arrow_up: Upstream

### MQTT

- topic: {application}/{region_id}/_upstream/{gateway_id}
  - seq 필드는 Gateway의 uptime 혹은 현재 timestamp 값을 사용

```json
{
  "command": "get_time_req",
  "response_topic": "{application}/{site_id}/_downstream/{gateway_id}",
  "seq": "<unsigned long>"
}
```

## :arrow_down: Downstream

- topic: {application}/{region_id}/_downstream/{gateway_id}
  - 동기화 요청 메시지의 seq를 “seq” 필드에 반환
  - 서버의 timestamp를 “ts” 필드에 반환
  - Gateway는 해당 timestamp로 시간 동기화

### MQTT

```json
{
  "command": "get_time_resp",
  "seq": "<unsigned long>",
  "ts": "<unsigned long>"
}
```
