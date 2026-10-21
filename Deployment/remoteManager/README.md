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
├── examples/
│   └── build.yaml         # 이미지 빌드 설정 예시
└── cmd/
    ├── cli/               # CLI 클라이언트
    │   ├── main.go
    │   └── build.go       # build 명령 (업로드, 상태, 로그, 목록)
    └── centralagent/      # Control Plane 서버
        ├── main.go
        ├── build_api.go   # 빌드 REST API
        ├── build_job.go   # 빌드 작업 실행 (ImageMaker → ImagePusher)
        ├── build_spec.go  # build.yaml 스키마, 검증, Dockerfile 생성
        └── build_spec_test.go
```

## 주요 구성 요소

### Control Plane (`cmd/centralagent/main.go`)
- 원격 노드의 Docker 데몬과 통신하는 REST API 서버
- 기본 포트: 8080
- 지원 작업: pull, create, start, stop, delete
- 이미지 빌드 API 포함 (아래 "이미지 빌드" 참고)

### CLI (`cmd/cli/main.go`)
- Control Plane과 통신하는 명령줄 클라이언트
- 원격 노드에 대한 컨테이너 관리 작업 수행
- `build` 명령으로 이미지 빌드 요청 (`cmd/cli/build.go`)

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

## 이미지 빌드 (ImageMaker / ImagePusher)

소스코드와 `build.yaml`을 업로드하면 Dockerfile을 자동 생성해 이미지를 빌드하고, Harbor에 Push한 뒤 (선택) 대상 노드에 배포합니다.

```
sdxr build --src app.tar.gz --config examples/build.yaml   # 작업 ID 출력
sdxr build status <id>
sdxr build logs <id> --follow
sdxr build list
```

| Method | Path | 설명 |
|---|---|---|
| POST | `/builds` | multipart(`source`=tar.gz, `config`=build.yaml) 업로드, 202 + 작업 ID |
| GET | `/builds` | 작업 목록 |
| GET | `/builds/:id` | 작업 상태 (queued → building → pushing → deploying → succeeded / failed) |
| GET | `/builds/:id/logs` | 빌드, Push, 배포 로그 |

`build.yaml` 스키마는 `examples/build.yaml`을 참고하세요. 알 수 없는 필드는 오류로 처리됩니다.

### 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `BUILD_TOKEN` | (없음) | 설정하면 `/builds`에 `Authorization: Bearer <token>` 필요 (CLI도 같은 환경변수 사용) |
| `BUILD_DATA_DIR` | `data/builds` | 작업 디렉토리 |
| `BUILD_PLUGIN_ROOT` | `data/plugins` | 플러그인 저장소 경로, `<name>/<version>` 구조 |
| `BUILD_BASE_PREFIX` | (없음) | 베이스 이미지 레지스트리 접두어 (예: Harbor 프록시 캐시) |
| `BUILD_MAX_CONCURRENT` | `2` | 동시 빌드 수 |
| `BUILD_TIMEOUT_MIN` | `30` | 작업당 제한 시간(분) |
| `BUILD_MAX_UPLOAD_MB` | `500` | 업로드 최대 크기 |
| `HARBOR_USER`, `HARBOR_PASSWORD` | (없음) | Harbor 자격증명 (설정 파일에 평문으로 두지 않음) |
| `DOCKER_HOST` | 로컬 소켓 | 빌드를 수행할 Docker 데몬 |

### 메트릭

- `sdx_build_jobs_total{status}`: 종료된 작업 수
- `sdx_build_duration_seconds`: 작업 소요 시간 histogram

### 참고

- 배포 시 같은 이름의 컨테이너가 노드에 있으면 제거한 뒤 새로 생성합니다 (재배포).
- 아카이브 안의 심볼릭 링크는 허용하지 않습니다.

### 향후 계획

- **배포 대상 선택 (`target_env`)**: 응용 배포 서버를 k8s-cluster(기존) 또는 독립 노드(SDx) 중에서 선택할 수 있도록 노드 타입 key를 추가합니다.
- **원격 노드 정보 DB 관리 (`resource_board`)**: 노드 정보를 DB에 저장하고 CRUD REST API로 관리합니다. `TARGET_ENV_CREATION`으로 노드를 등록합니다.
- **노드 검증**: `SUBMIT_START` 시 node type과 IP를 받아 노드 정보와 자원이 유효한지 확인합니다.
- **Workspace Checker 확장**: 기존 yaml 기반 K8s 클러스터 관리에 더해, docker API로 운영되는 독립 노드를 별도 DB로 관리합니다.
