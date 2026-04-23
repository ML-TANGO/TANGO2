# fb_log_middleware

Flightbase 시스템 앱들이 EFK 스택(Elasticsearch / Fluentd / Kibana)에 저장된 로그를 직접 쿼리하지 않도록 중간에 두는 **로그 쿼리 미들웨어**입니다. gRPC 와 REST API 두 가지 인터페이스를 제공합니다.

## 현재 구조

현재 시점에서 본 서비스의 구현은 `go-poc/` 디렉터리 안의 Go PoC 가 정식 코드로 사용되고 있습니다. 따라서 빌드/실행/배포 등 **상세 가이드는 [`go-poc/README.md`](./go-poc/README.md)** 를 참조해 주세요.

```
apps/fb_log_middleware/
├── Dockerfile        # go-poc/Dockerfile 와 동일한 이미지 정의(빌드 컨텍스트는 go-poc/)
├── README.md         # 이 문서
└── go-poc/           # 실제 Go 구현체(server.go, proto, handler 등)
```

## 어떤 문서를 봐야 하는가

| 목적 | 참조할 문서 |
|---|---|
| 미들웨어가 무엇을 하는지, EFK 와의 관계 | [`go-poc/README.md`](./go-poc/README.md) "개요" 섹션 |
| Go 환경 준비, proto 빌드 | [`go-poc/README.md`](./go-poc/README.md) "개발" 섹션 |
| 로컬 실행(`ELASTICSEARCH_ADDRESS` 환경변수) | [`go-poc/README.md`](./go-poc/README.md) "로컬에서 실행" |
| 이미지 빌드 / 레지스트리 푸시 | [`go-poc/image_build_push.sh`](./go-poc/image_build_push.sh) |
| 쿠버네티스 배포 (PoC manifest) | [`go-poc/test.yaml`](./go-poc/test.yaml) |
| EFK 스택 자체 설치/구성 | [`../../devops/gaip_efk/README.md`](../../devops/gaip_efk/README.md) |

## 정식 devops 차트 작성 예정

PoC 단계라 현재는 `go-poc/test.yaml` 같은 단일 manifest 로 배포합니다. 향후 다른 앱들과 동일한 형태의 `devops/fb_log_middleware/helm` 차트로 정리할 예정입니다.
