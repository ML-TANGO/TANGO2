# SDx Remote

Software Defined Infrastructure (SDx) 기반 원격 노드 컨테이너 관리 시스템

## 개요

여러 원격 노드에서 Docker 컨테이너를 중앙에서 일괄 관리할 수 있는 시스템입니다. Control Plane 서버와 CLI 클라이언트를 통해 container pull, create, start, stop, delete 등의 작업을 수행할 수 있습니다.

### 특징
클라우드 서버 단위로 장애 예측 및 서비스 운영을 위해 **원격으로 도커 컨테이너를 자동 배포**하고, 실시간 상태를 중앙에서 모니터링할 수 있는 관리 프로그램입니다.

### 판매 구분
- □ 상업용  
- ■ 비상업용



## 프로젝트 구조

```
sdx_remote/
├── README
├── go.mod                  # Go 모듈 정의
├── go.sum                  # Go 의존성 체크섬
├── inventory.yaml          # 원격 노드 설정 (호스트, 타임아웃 등)
├── nodes.txt              # 노드 목록 (텍스트 형식)
├── cert/                  # TLS 인증서 디렉토리
└── cmd/
    ├── cli/               # CLI 클라이언트
    │   └── main.go
    └── controlplane/      # Control Plane 서버
        └── main.go
```

## 주요 구성 요소

### Control Plane (`cmd/controlplane/main.go`)
- 원격 노드의 Docker 데몬과 통신하는 REST API 서버
- 기본 포트: 8080
- 지원 작업: pull, create, start, stop, delete

### CLI (`cmd/cli/main.go`)
- Control Plane과 통신하는 명령줄 클라이언트
- 원격 노드에 대한 컨테이너 관리 작업 수행

## 준비 사항

### 필수 요구사항
- **Go 1.19+** (Control Plane, CLI 빌드용)
- **원격 노드**: Docker daemon 실행 중 (포트 2380)
- **네트워크**: Control Plane과 원격 노드 간 통신 가능

### 원격 노드 설정

각 원격 노드에서 Docker daemon을 원격 접근 가능하도록 설정해야 합니다:

```bash
# Docker daemon을 TCP 포트로 노출 (2380)
# /etc/docker/daemon.json 설정 후
sudo systemctl restart docker
```

## 빠른 시작

### 1. inventory.yaml 설정

제어 대상 노드 정보를 `inventory.yaml`에 입력합니다:

```yaml
nodes:
  node-52:
    host: tcp://10.0.2.52:2380
    timeoutSec: 30

  node-53:
    host: tcp://10.0.2.53:2380
    timeoutSec: 30
```

### 2. Control Plane 실행

메인 서버에서 Control Plane을 시작합니다:

```bash
go run cmd/controlplane/main.go
```

### 3. CLI 환경 설정

```bash
# Control Plane 주소 설정
export CP_ADDR=http://<메인_서버_IP>:8080

# (선택) 명령 단축어 설정
alias sdxr='go run cmd/cli/main.go'
```

## 사용 예시

### 이미지 pull

```bash
sdxr pull --image nginx --tag latest --nodes node-52
```

### 컨테이너 생성

```bash
sdxr create --image nginx --tag latest --name webserver --publish 8080:80 --nodes node-52
```

### 컨테이너 시작

```bash
sdxr start --name webserver --nodes node-52
```

### 컨테이너 중지

```bash
sdxr stop --name webserver --nodes node-52
```

### 컨테이너 삭제

```bash
sdxr delete --name webserver --nodes node-52
```

### 여러 노드에 한 번에 배포

```bash
sdxr create --image nginx --tag latest --name web01 --nodes node-52 node-53
```

## 모니터링 (선택사항)

Prometheus와 Grafana를 사용하여 배포된 컨테이너의 상태와 자원 사용량을 모니터링할 수 있습니다.

- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000`

자세한 설정은 모니터링 가이드를 참고하세요.
