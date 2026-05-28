# 마그네트 스위치를 사용한 AC 모터 제어 모듈

![ac_motor 제어모듈 구성](uploads/c115970529f59763ebb8ef8aae87da7d/image.png)

## 동작 명령

### :arrow_down: MQTT Downstream

- topic: {application}/{region_id}/_downstream/{gateway_id}

```json
{
  "command": "set_agsacmotor_req",
  "response_topic": "{application}/{site_id}/_upstream/{gateway_id}",
  "seq": unsigned long,
  "node_id": "node_id_1",
  "command_from": "(beymons_auto|beymons_remote)",
  "address_1": {
    "channel_1": 100,
    "channel_2": 255
  }
}
```

- 각 채널에 해당하는 마그네트 스위치의 동작 명시, 현재 상태를 유지하는 채널은 해당 메시지에서 표현하지 않음
  - 0: 닫기, 100: 열기, 255: 정지
- 8ch 릴레이 모듈을 사용하는 경우 제어 모터는 최대 2채널

### :arrow_up: MQTT Upstream

- topic: {application}/{region_id}/_upstream/{gateway_id}

```json
{
  "command": "set_agsacmotor_resp",
  "seq": unsigned long,
  "node_id": "node_id_1"
}
```

### (TODO) :arrow_down: LoRa Downstream
### (TODO) :arrow_down: Modbus Downstream
### (TODO) :arrow_up: Modbus Upstream
### (TODO) :arrow_up: LoRa Upstream


## 동작 에러 보고

### (TODO) :arrow_down: Modbus Downstream
### (TODO) :arrow_up: Modbus Upstream
### (TODO) :arrow_up: LoRa Upstream
### (TODO) :arrow_up: MQTT Upstream
### (TODO) :arrow_down: MQTT Downstream
