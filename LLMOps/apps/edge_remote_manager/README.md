# Edge remoteManager 에이전트

엣지 디바이스에서 실행되어, TANGO 플랫폼의 배포 지시(`/ops`)를 **실제 컨테이너 실행**으로 이행하고
상태/자원(`/metrics`)을 보고하며, 플랫폼으로 heartbeat를 보낸다. 향후 기관 배포용 실물 에이전트.

가상 디바이스 하네스(`apps/edge_virtual_device`)와 **동일 계약**을 구현한다(계약: `엣지 가상 디바이스 E2E 설계 문서(내부)` §4).

## 요구사항
- Docker 설치 + 실행 권한(에이전트 실행 사용자가 `docker` 사용 가능해야 함)
- Python 3.8+
- (GPU 사용 시) 데스크톱/서버: NVIDIA driver + nvidia-container-toolkit (`--gpus all`)
  · **Jetson(JetPack/L4T)**: nvidia-container-runtime (`--runtime nvidia`). `GPU=auto` 가
  Tegra 를 판별해 자동 선택하며 `GPU=runtime|gpus` 로 못박을 수 있다. 이미지는 arm64

## 실행
```bash
export MODEL_DIR=/opt/edge/models          # gguf 등 모델 파일 위치(컨테이너에 /models 로 마운트)
export GPU=auto                             # auto|on|off|runtime|gpus (Jetson 자동 판별)
export OPS_TOKEN="<플랫폼과 공유하는 /ops 인증 토큰>"   # 미설정 시 무인증(사설망 전용)
export OPS_TOKEN_PREV="<회전 중 직전 키>"               # 선택 — 둘 다 허용(무중단 회전)
# (선택) heartbeat 활성화 — 플랫폼에서 워커 등록 후 발급받은 토큰
export PLATFORM_HEARTBEAT_URL="http://<platform-host>/api/edge/devices/<device_id>/heartbeat"
export DEVICE_ID="edge-xxxxxxxx"
export DEVICE_TOKEN="<발급받은 raw token>"
./run.sh                                    # 기본 :8600
```

## 플랫폼 등록 (관리자)
1. Admin → 노드/엣지 등록: `remote_manager_url = http://<device-host>:8600` (**경로 없이**; 플랫폼 SSRF 가드가 `/ops`,`/metrics` 를 붙임).
2. 워커 토큰 발급 → raw token 을 위 `DEVICE_TOKEN` 에 넣고 에이전트 재기동(또는 heartbeat 설정).
3. 배포 실행 → 플랫폼이 `/ops` 로 `{op:deploy,image,model,version,gguf_path,model_url,params}` 전송 →
   에이전트가 `model_url` 에서 모델 파일을 받고(`DEVICE_TOKEN` 인증, Range 이어받기) pull+run.

## 계약
- `POST /ops` `{op:"deploy",image,model,version,gguf_path,model_url,params}` → (model_url 이 있으면) 모델 수신 + `docker pull` + `docker run`(교체).
  **`model_url` 이 있으면 `202 {"status":"deploying"}` 로 즉시 답하고 백그라운드로 진행**하며, 없으면 종전대로 동기 `{"status":"running"}`. 진행 중 재요청은 `409`. (실패 `{"status":"error","detail":...}`). `op:"stop"` → 컨테이너 제거 → `{"status":"stopped"}`. **실패는 반드시 `{"status":"error","detail":...}` 로 보고한다**(docker 부재 · `docker rm` 비0 종료 · 타임아웃). 이미 없는 컨테이너(`No such container`)는 목표 상태가 충족된 것이므로 성공으로 본다. 플랫폼이 이 응답으로 `deploy_state` 를 확정하므로, 실패를 `stopped` 로 보고하면 컨테이너가 살아 있는데 화면이 "중지됨" 이라 말하는 거짓이 된다.
  - `params` 옵션: `port`(호스트/컨테이너 포트), `env`(dict), `docker_args`(list, 추가 플래그), `cmd`(list, 컨테이너 실행 인자). 모델 파일은 `MODEL_DIR` 를 `/models` 로 마운트하고 `MODEL_PATH=/models/<gguf_path>` env 주입.
- `GET /metrics` → `{contract_version,deploy_in_progress,last_deploy_error,containers:[{name,image,state,model,version}],container_count,node_cpu_total,memory_total,gpu}`.
- `op:"stop"` 은 컨테이너 제거뿐 아니라 **진행 중 비동기 배포를 무효화**하고 `last_deploy_error` 를 해제한다(안 그러면 유령 재기동·상태 되돌림).
- 계약 명세 정본과 적합성 검사기는 `LLMOps/examples/edge-agent/` 에 있다(외부 배포용).

## ⚠️ 보안
- `/ops`·`/metrics` 는 `OPS_TOKEN` 이 설정되면 **Bearer 검증**한다(계약 1.1). 회전 중에는
  `OPS_TOKEN_PREV` 도 함께 허용해 아직 교체되지 않은 상태에서도 끊기지 않는다. 운영에서는 반드시 설정할 것.
  설정하지 않으면 무인증으로 열리며 그 상태는 **신뢰 사설망/방화벽 안 전용**이다. 공용 인터넷 금지.
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
