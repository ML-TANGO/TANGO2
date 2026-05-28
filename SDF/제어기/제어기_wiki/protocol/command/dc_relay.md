# DC 개폐기 제어 모듈

## 동작 명령

### :arrow_down: MQTT Downstream

- topic: {application}/{region_id}/_downstream/{gateway_id}

```json
{
  "command": "set_agsmotor_operation_req",
  "response_topic": "{application}/{site_id}/_upstream/{gateway_id}",
  "seq": unsigned long,
  "node_id": "node_id_1",
  "command_from": "(beymons_auto|beymons_remote)",
  "address_1": {
    "channel_1":    10,
    "channel_2":    50,
    "channel_4":    100,
    "channel_5":    50,
    "channel_6":    0,
    "channel_8":    25
  }
}
```

### :arrow_up: MQTT Upstream

- topic: {application}/{region_id}/_upstream/{gateway_id}

```json
{
  "command": "set_agsmotor_operation_resp",
  "seq": unsigned long,
  "node_id": "node_id_1"
}
```

### (TODO) :arrow_down: LoRa Downstream
### (TODO) :arrow_down: Modbus Downstream
### (TODO) :arrow_up: Modbus Upstream
### (TODO) :arrow_up: LoRa Upstream

## 모터 동작 완료 보고

### (TODO) :arrow_down: Modbus Downstream

- 모터 동작 완료 확인

### (TODO) :arrow_up: Modbus Upstream

- 모터 동작 응답

### (TODO) :arrow_up: LoRa Upstream
### (TODO) :arrow_down: Lora Downstream
### (TODO) :arrow_up: MQTT Upstream
### (TODO) :arrow_up: MQTT Downstream


## 모터 동작 에러 보고

### (TODO) :arrow_down: Modbus Downstream

- 모터 동작 완료 확인

### (TODO) :arrow_up: Modbus Upstream

- 모터 동작 응답 (에러 포함 응답)

### (TODO) :arrow_up: LoRa Upstream
### (TODO) :arrow_down: Lora Downstream
### (TODO) :arrow_up: MQTT Upstream
### (TODO) :arrow_up: MQTT Downstream

## DC모터 Calibration

### :arrow_down: MQTT Downstream
### :arrow_up: MQTT Upstream

### :arrow_down: LoRa Downstream
### :arrow_down: Modbus Downstream
### :arrow_up: Modbus Upstream
### :arrow_up: LoRa Upstream
