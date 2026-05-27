# 디바이스 에러 알림

- Node 혹은 Gateway에서 발생한 에러를 서버로 전송
- TODO: 커맨드 이름 변경 필요 (set_status -> set_device_error)

## :arrow_up: Upstream

### LoRa (정의 필요)

### MQTT

- topic: {application}/{region_id}/_upstream/{gateway_id}
  - 서버는 수신된 에러 내용을 DB에 저장함

```json
{
  "command": "set_status_req",
  "response_topic": "{site_id}/_downstream/{gateway_id}",
  "seq": "<unsigned long>",
  "nodes": {
    "node_id_1": {
      "address_1": int,
      "address_2": int
    }
  }
}
```

- 에러 코드에 대한 내용은 [에러코드](/error_code) 문서 참조

## :arrow_down: Downstream

### MQTT

- topic: {application}/{region_id}/_downstream/{gateway_id}
  - 서버 확인 응답

```json
{
  "command": "set_status_resp",
  "seq": "<unsigned long>"
}
```
