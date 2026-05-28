설비 관리 서비스
==========
제품 및 설비를 관리하는 서비스로 다음의 서비스를 의존한다:
- services/metadata
- beymons/sites
- beymons/devices

[API 문서](swagger.json)


Configuration
----------
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


Deployment
----------
### Docker Compose 환경
Docker Compose 환경에서 배포하기 위해서는 먼저 `.env`파일에 COMPOSE_PROJECT_NAME으로 프로젝트 명을 설정해야 한다.
이후 다음 명령을 실행하면 서비스가 동작한다:
``` shell
docker compose up -d
```


### Kubernetes 환경
Kubernetes 환경에 배포하기 위한 방법으로 환경변수 `NAMESPACE`를 설정한 뒤 설치를 진행해야 한다.

1. [환경설정 파일 생성](#configuration)
2. 서비스에서 사용하는 [환경변수 등록](#환경변수-등록)
3. gRPC 트랜스코딩을 위한 [설정 파일](#envoy-설정) 등록
4. [서비스 배포](#서비스-배포)
5. [VirtualService 등록](#virtualservice-등록)
6. [Autoscaling 설정](#autoscaling-설정)


#### 환경변수 등록
다음의 명령을 통해 `.env`파일의 환경설정이 Kubernetes의 Secret으로 등록된다:
``` shell
kubectl create secret generic facilities-config --from-env-file .env -o yaml --dry-run=client |\
    kubectl -n $NAMESPACE apply -f -
```


#### Envoy 설정
HTTP 프로토콜을 gRPC 프로토콜로 트랜스코딩하기 위해 Envoy에 설정에 필요한 파일을 등록해야 한다.
설정 파일은 `make envoy` 명령을 통해 생성되며, API나 모델이 변경되지 않으면 다시 올릴 필요는 없다.

다음 명령을 통해 설정 파일을 Kubernetes의 ConfigMap으로 등록할 수 있다:
``` shell
kubectl create configmap facilities-proxy \
    --from-file envoy-proxy/envoy.yaml \
    --from-file envoy-proxy/proto.pb \
    -o yaml --dry-run=client | kubectl -n $NAMESPACE apply -f -
```


#### 서비스 배포
서비스를 배포하는 방법은 다음과 같다:
``` shell
kubectl -n $NAMESPACE apply -f manifest.yaml
```


#### VirtualService 등록
외부에서 호출 가능하도록 Istio의 Ingress Gateway를 통해 라우팅 설정을 해야 한다:
``` shell
kubectl -n $NAMESPACE apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: facilities-service
spec:
  hosts:
  - "*"
  gateways:
  - default
  http:
  - name: facilities
    match:
    - uri:
        prefix: "/api/facilities"
    rewrite:
      uri: "/facilities"
    route:
    - destination:
        host: facilities
EOF
```


#### Autoscaling 설정
HPA(HorizontalPodAutoscaler)를 이용하여 파드를 최소 1개에서 CPU 사용률이 75% 이상일 때,
최대 10개까지 확장하도록 설정하는 예는 다음과 같다:
```
kubectl -n $NAMESPACE autoscale deployment facilities --cpu-percent=75 --min=1 --max=10
```


#### Uninstall
``` shell
kubectl -n $NAMESPACE delete virtualservice/facilities-service
kubectl -n $NAMESPACE delete -f manifest.yaml
```
