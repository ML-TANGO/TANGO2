# ~~MQTT 인증서 조회~~

- 아직 구체적인 설계 없음, 아직 구현되지 않음
- 생산 직후, 설정용 서버로 접속하여 해당 디바이스가 서비스를 위해 접속해야 하는 MQTT Broker 정보와 해당 broker에 접속하기 위한 인증서를 조회하는 명령

## :arrow_up: Upstream

- topic: {application}/{region_id}/_upstream/{gateway_id}

```json
{
  "command": "get_config_req",
  "response_topic": "{site_id}/_downstream/{gateway_id}",
  "seq": "<unsigned long>"
}
```

## :arrow_down: Downstream

- topic: {application}/{region_id}/_downstream/{gateway_id}

```json
{
  "command": "get_certificate_resp",
  "seq": unsigned long,
  "root_ca": string,
  "public_key": string,
  "cert": string
}
```
