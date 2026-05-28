# DC 모터 제어 모듈 상태 데이터 전송

## :arrow_up: MQTT Upstream

- topic: {application}/{region_id}/_data/{gateway_id}

```json
{
  "ts": "<unsigned long>",
  "invalid": true,
  "probe_flag": true,
  "mode": "beymons_auto",
  "mode_switch": "beymons_remote",
  "relay": [0, 100, 0, 0, 0, 0, 0, 0],
  "relay_switch": [0, 100, 0, 0, 0, 0, 0, 0],
  "open_rate": [0, 50, 0, 0, 0, 0, 0, 0]
}
```
