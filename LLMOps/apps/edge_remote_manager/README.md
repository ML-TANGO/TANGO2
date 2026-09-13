# Edge remoteManager 에이전트

엣지 디바이스에서 실행되어, TANGO 플랫폼의 배포 지시(`/ops`)를 **실제 컨테이너 실행**으로 이행하고
상태/자원(`/metrics`)을 보고하며, 플랫폼으로 heartbeat를 보낸다. 향후 기관 배포용 실물 에이전트.

가상 디바이스 하네스(`apps/edge_virtual_device`)와 **동일 계약**을 구현한다(계약: `docs/superpowers/specs/2026-07-21-edge-virtual-device-e2e-design.md` §4).

## 요구사항
- Docker 설치 + 실행 권한(에이전트 실행 사용자가 `docker` 사용 가능해야 함)
- Python 3.8+
- (GPU 사용 시) NVIDIA driver + nvidia-container-toolkit (`--gpus all`)

## 실행
```bash
export MODEL_DIR=/opt/edge/models          # gguf 등 모델 파일 위치(컨테이너에 /models 로 마운트)
export GPU=auto                             # auto|on|off
# (선택) heartbeat 활성화 — 플랫폼에서 워커 등록 후 발급받은 토큰
export PLATFORM_HEARTBEAT_URL="http://<platform-host>/api/edge/devices/<device_id>/heartbeat"
export DEVICE_ID="edge-xxxxxxxx"
export DEVICE_TOKEN="<발급받은 raw token>"
./run.sh                                    # 기본 :8600
```

## 플랫폼 등록 (관리자)
1. Admin → 노드/엣지 등록: `remote_manager_url = http://<device-host>:8600` (**경로 없이**; 플랫폼 SSRF 가드가 `/ops`,`/metrics` 를 붙임).
2. 워커 토큰 발급 → raw token 을 위 `DEVICE_TOKEN` 에 넣고 에이전트 재기동(또는 heartbeat 설정).
3. 배포 실행 → 플랫폼이 `/ops` 로 `{op:deploy,image,model,version,gguf_path,params}` 전송 → 에이전트가 pull+run.

## 계약
- `POST /ops` `{op:"deploy",image,model,version,gguf_path,params}` → `docker pull` + `docker run`(교체) → `{"status":"running"}` (실패 `{"status":"error","detail":...}`). `op:"stop"` → 컨테이너 제거 → `{"status":"stopped"}`. **실패는 반드시 `{"status":"error","detail":...}` 로 보고한다**(docker 부재 · `docker rm` 비0 종료 · 타임아웃). 이미 없는 컨테이너(`No such container`)는 목표 상태가 충족된 것이므로 성공으로 본다. 플랫폼이 이 응답으로 `deploy_state` 를 확정하므로, 실패를 `stopped` 로 보고하면 컨테이너가 살아 있는데 화면이 "중지됨" 이라 말하는 거짓이 된다.
  - `params` 옵션: `port`(호스트/컨테이너 포트), `env`(dict), `docker_args`(list, 추가 플래그), `cmd`(list, 컨테이너 실행 인자). 모델 파일은 `MODEL_DIR` 를 `/models` 로 마운트하고 `MODEL_PATH=/models/<gguf_path>` env 주입.
- `GET /metrics` → `{containers:[{name,image,state,model,version}],container_count,node_cpu_total,memory_total,gpu}`.

## ⚠️ 보안
- `/ops`·`/metrics` 는 **무인증**(플랫폼↔remoteManager 계약). **신뢰 사설망/방화벽 안**에서만 노출. 공용 인터넷 금지.
- heartbeat 는 Bearer 토큰(sha256 해시 대조, 90일 TTL). 토큰은 발급 1회만 노출되니 안전 보관.
- 호스트 docker 를 제어하므로 컨테이너 안이 아니라 **호스트 프로세스(systemd/nohup)** 로 실행.

## 로컬 계약 검증(디바이스 없이)
`DOCKER_BIN` 을 가짜 스크립트로 지정하면 실제 docker 없이 `/ops`·`/metrics` 계약을 점검할 수 있다.
플랫폼측 e2e 는 동일 계약을 mock 하는 `apps/edge_virtual_device` + `edge_e2e_driver.py` 로 이미 통과.
```bash
DOCKER_BIN=/path/to/fake-docker python3 -m uvicorn remote_manager_agent:app --port 8600
```

## 이미지별 실행 인자
서빙 이미지(llama.cpp/vLLM 등)마다 필요한 실행 인자가 다르므로, 이미지 고유 플래그는 `params.docker_args`/`params.cmd`/`params.env` 로 전달한다(에이전트는 이미지-불문 실행기). 예: llama.cpp GGUF 서빙은 `MODEL_PATH` env + 포트로 기동.
