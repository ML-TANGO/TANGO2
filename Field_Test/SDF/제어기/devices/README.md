# Devices

devices 서비스는 BEYMONS 디바이스에 대한 메타데이터를 관리한다.
[API 문서](swagger.json)


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
| LOG_LEVLE              |   | 로그 레벨 (DEBUG, INFO, WARN, ERROR, default: INFO) |
| MQTT_CERT              |   | MQTT 브로커에 연결하기 위한 인증서 파일 (default: /cert/root-CA.crt) |
| REQUEST_TIMEOUT        |   | MQTT를 통한 명령에 대한 타임아웃 (default: 5m)|
| NATS_ENDPOINT          |   | NATS Endpoint (default: nats://nats:4222) |
| MQTT_ENDPOINT          | O | MQTT 브로커 Endpoint |
| MQTT_TOPIC             |   | 토픽 (default: +/_upstream/+_)
| MQTT_CLIENT_ID         |   | 사용할 Clinet ID (default: hostname)
| MQTT_CERT_FILE         |   | MQTT 연결에 사용하는 인증서 (default: /certs/server.cert.pem)
| MQTT_PRIVATE_KEY_FILE  |   | MQTT 연결에 사용하는 비공개키 (default: /certs/server.private.key)
| MQTT_ROOT_CA_FILE      |   | 루트 CA 인증서


## protobuf 컴파일
protoc 를 사용하여 컴파일해야 하므로 [protovalidate](https://github.com/bufbuild/protovalidate)를 서브모듈로 추가하였다.
따라서 컴파일하기 위해서는 레파지토리를 가져온 다음 다음의 추가 작업이 필요하다.

```
git submodule update --init --recursive
```

## Deployment

### Docker Compose 환경
Docker Compose 환경에서 배포하기 위해서는 먼저 `.env`파일에 COMPOSE_PROJECT_NAME으로 프로젝트 명을 설정해야 한다.
이후 다음 명령을 실행하면 서비스가 동작한다:
``` shell
docker compose up -d
```

### Kubernetes 환경
설치된 장치로부터 받은 요청이나 장치로 명령을 전달하기 위해 MQTT 브로커에 연결할 수 있는 인증서를 등록해야 한다.

인증서는 [AWS 콘솔](https://ap-northeast-2.console.aws.amazon.com/iot/home?region=ap-northeast-2#/certificate/641007e9517d0c7a7500c26d3617028674bd92f63a2fa427b2d183cbb6dcafad)에서 받을 수 있으며 다음 명령으로 등록할 수 있다:
```bash
kubectl create secret generic beymons-mqtt-certs \
    --from-file certs/root-CA.crt \
    --from-file certs/server.cert.pem \
    --from-file certs/server.private.key \
    -o yaml --dry-run=client | kubectl -n $NAMESPACE apply -f -
```

환경변수로 `NAMESPACE`를 설정한 뒤 설치를 진행하면 되며,
다음의 명령을 통해 `.env`파일의 환경설정이 Kubernetes의 Secret으로 등록된다:
``` shell
kubectl create secret generic devices-config --from-env-file .env -o yaml --dry-run=client |\
    kubectl -n $NAMESPACE apply -f -
```

다음 명령을 통해 프록시 파일이 Kubernetes의 ConfigMap으로 등록된다:
``` shell
kubectl create configmap devices-proxy \
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
``` shell
kubectl -n $NAMESPACE apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: devices-service
spec:
  hosts:
  - "*"
  gateways:
  - default
  http:
  - name: "devices"
    match:
    - uri:
        prefix: "/api/devices"
    rewrite:
      uri: "/devices"
    route:
    - destination:
        host: devices
  - name: "device-configs"
    match:
    - uri:
        prefix: "/api/device-configs"
    rewrite:
      uri: "/device-configs"
    route:
    - destination:
        host: devices
  - name: "sensor-types"
    match:
    - uri:
        prefix: "/api/sensor-types"
    rewrite:
      uri: "/sensor-types"
    route:
    - destination:
        host: devices
EOF
```

#### Autoscaling
HPA(HorizontalPodAutoscaler)를 이용하여 파드를 최소 1개에서 CPU 사용률이 75% 이상일 때,
최대 10개까지 확장하도록 설정하는 예는 다음과 같다:
```
kubectl -n $NAMESPACE autoscale deployment devices --cpu-percent=75 --min=1 --max=10
```

#### Uninstall
``` shell
kubectl -n $NAMESPACE delete virtualservice/devices-service
kubectl -n $NAMESPACE delete -f manifest.yaml
```
