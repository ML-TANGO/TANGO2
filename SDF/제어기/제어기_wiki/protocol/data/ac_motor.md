# AC 모터 제어 모듈 상태 데이터 전송

## :arrow_up: MQTT Upstream

- topic: {application}/{region_id}/_data/{gateway_id}

```json
{
  "ts": "<unsigned long>",
  "invalid": true,
  "probe_flag": true,
  "channel_1": {
    "state": 100
  },
  "channel_2": {
    "state": 255
  }
}
```

- state
  - 현재 동작 상태 표현
  - 0: 닫힘
  - 100: 열림
  - 255: 정지

![ac_motor 제어모듈 구성](uploads/c115970529f59763ebb8ef8aae87da7d/image.png)
