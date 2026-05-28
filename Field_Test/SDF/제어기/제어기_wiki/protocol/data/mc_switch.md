# 마그네트 스위치 제어 모듈 상태 데이터 전송

## :arrow_up: MQTT Upstream

- topic: {application}/{region_id}/_data/{gateway_id}

```json
{
  "ts": "<unsigned long>",
  "invalid": true,
  "probe_flag": true,
  "state": [0, 1, 0, 1]
}
```

- state
  - 현재 동작 상태 표현
  - 0: off
  - 1: on

![mc_switch 제어모듈 구성](uploads/ebf054c8b04eb697a194b79733325d90/image.png)
