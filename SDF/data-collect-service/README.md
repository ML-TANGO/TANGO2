# Collects

- [API 문서](swagger.json)
- collects 서비스는 MQTT broker에 전송되는 메시지를 subscribe 하여 메시지를 처리한다.
- 처리해야 하는 메시지의 Topic 구조 및 메시지 포맷은 [여기](https://gitlab.suredatalab.kr/beymons)를 참조한다.
- 실행 시 MQTT broker에 접속하기 위한 인증서 파일을 마운트 해야 한다.
- MQTT 접속 정보는 AWS console의 IoT Core 서비스에 설정된 내용을 참조하여 설정한다.
- MQTT 메시지 처리
  - client 초기화 및 subscribe 등록: mqtt_client.go, subscribe.go
  - message 수신 후 topic 파싱: topic_distribute.go
  - topic에 대해 처리 분기: subscribe.go[messageHandler()]
    - 온습도 데이터 관련: data_temp_humi.go
    - 시간 동기화 명령 관련: cmd_timesync.go
    - 인증서 조회 관련: cmd_certificates.go
  - 데이터 처리 중, site_id 및 device_id, sensor_type을 통해 DB에서 관리하고 있는 device_id 정보 갱신: topic_distribute.go[getSensorIdMap()]

## Configuration

서비스를 실행하기 위한 설정으로 환경변수나 .env 파일을 통해 설정 가능하다.

이 서비스에서 지원하는 환경변수는 다음과 같다:

| 변수                   |필수| 설명 |
| ---------------------- |---| ----- |
| ALLOW_FEDERATED_ISSUER |   | 다른 토큰 발급자 허용 여부 (default: no) |
| SECURE_MODE            |   | 인증 모드 [enforce: 인증, 권한 (default), enable: 인증, disable: 미적용] |
| ZIPKIN_ENDPOINT        |   | API 모니터링을 위한 Zipkin URL (default: http://zipkin:9411/api/v2/spans) |
| DB_HOST                | O | DB에 연결하기 위한 주소 |
| DB_PORT                |   | DB에 연결하기 위한 포트 번호 (default: 5432) |
| DB_NAME                | O | 서비스에서 사용하는 DB |
| DB_USER                | O | DB 접속 Username |
| DB_PASSWD              | O | DB 접속 Password |
| LOG_LEVEL              |   | 로그 레벨 (DEBUG, INFO, WARN, ERROR, default: INFO) |
| NATS_ENDPOINT          |   | NATS Broker URL (default: nats://nats:4222) |
| MQTT_ENDPOINT          |   | MQTT Broker URL (default: mqtt://localhost:1883) |
| MQTT_TOPIC             |   | 모니터링 대상 Topic (default: +/_data/+) |
| MQTT_CLIENT_ID         |   | MQTT Broker에 접속하기 위해 사용하는 client ID (default: beymons-server) |
| MQTT_CERT_FILE         |   | 인증서 CERTIFICATE file (default: server.cert.pem) |
| MQTT_PRIVATE_KEY_FILE  |   | 인증서 PRIVATE KEY file (default: server.private.key) |
| MQTT_ROOT_CA_FILE      |   | 인증서 root-CA file (default: root-CA.crt) |


## Deployment

### Docker Compose 환경
Docker Compose 환경에서 배포하기 위해서는 먼저 `.env`파일에 COMPOSE_PROJECT_NAME으로 프로젝트 명을 설정해야 한다.
이후 다음 명령을 실행하면 서비스가 동작한다:
``` shell
docker compose up -d
```


### Kubernetes 환경

MQTT subscribe를 위한 설정이 필요하다.
환경변수를 통한 MQTT 관련 설정과 MQTT 연결을 위한 인증서 mount가 필요하다.

- 인증서 secret 생성

```bash
kubectl create secret generic beymons-mqtt-certs \
    --from-file certs/root-CA.crt \
    --from-file certs/server.cert.pem \
    --from-file certs/server.private.key \
    -o yaml --dry-run=client | kubectl -n $NAMESPACE apply -f -
```


Kubernetes 환경에 배포하기 위해 환경설정과 트랜스코딩을 위한 proxy 파일을 등록해야 한다.
환경변수로 `NAMESPACE`를 설정한 뒤 설치를 진행하면 되며,
다음의 명령을 통해 `.env`파일의 환경설정이 Kubernetes의 Secret으로 등록된다:
``` shell
kubectl create secret generic collects-config --from-env-file .env -o yaml --dry-run=client |\
    kubectl -n $NAMESPACE apply -f -
```

다음 명령을 통해 프록시 파일이 Kubernetes의 ConfigMap으로 등록된다:
``` shell
kubectl create configmap collects-proxy \
    --from-file envoy-proxy/envoy.yaml \
    --from-file envoy-proxy/proto.pb \
    -o yaml --dry-run=client | kubectl -n $NAMESPACE apply -f -
```


#### Install
서비스를 설치하는 방법은 다음과 같다:
``` shell
kubectl -n $NAMESPACE apply -f manifest.yaml
```

외부에서 호출 가능하도록 Istio의 Ingress Gateway를 통해 라우팅 설정을 해야 한다.
환경변수로 `GATEWAY_NAME`을 추가로 설정한 후에 다음을 실행하면 된다:
``` shell
kubectl -n $NAMESPACE apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: collects-service
spec:
  hosts:
  - "*"
  gateways:
  - beymons-gateway
  http:
  - name: "collects"
    match:
    - uri:
        prefix: "/api/collects"
    rewrite:
      uri: "/collects"
    route:
    - destination:
        host: collects
  - name: "collects"
    match:
    - uri:
        exact: "/api/statistics/collects"
    rewrite:
      uri: "/statistics/collects"
    route:
    - destination:
        host: collects
EOF
```

#### Autoscaling
HPA(HorizontalPodAutoscaler)를 이용하여 파드를 최소 1개에서 CPU 사용률이 75% 이상일 때,
최대 10개까지 확장하도록 설정하는 예는 다음과 같다:
```
kubectl -n $NAMESPACE autoscale deployment collects --cpu-percent=75 --min=1 --max=10
```

#### Uninstall
``` shell
kubectl -n $NAMESPACE delete virtualservice/collects-service
kubectl -n $NAMESPACE delete -f manifest.yaml
```

## AWS IoT Core 정책 설정

- 다음 내용이 test-device 를 위한 정책으로 설정된 상태
- site_id `sdl` 로 시작하는 topic에만 publish/subscribe 할 수 있도록 설정
- client ID는 모두 허용
  - 제한해야 하는 경우 다음과 같이 설정
  - "arn:aws:iot:<region>:<account-id>:client/<client-id>"

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iot:Publish",
        "iot:Receive",
        "iot:PublishRetain"
      ],
      "Resource": "arn:aws:iot:ap-northeast-2:637423230966:topic/sdl/*"
    },
    {
      "Effect": "Allow",
      "Action": "iot:Subscribe",
      "Resource": "arn:aws:iot:ap-northeast-2:637423230966:topicfilter/sdl/*"
    },
    {
      "Effect": "Allow",
      "Action": "iot:Connect",
      "Resource": "*"
    }
  ]
}
```
