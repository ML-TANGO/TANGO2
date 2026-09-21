# 엣지 에이전트 연동 규약 v1

엣지 디바이스에서 동작하며 플랫폼의 배포 지시를 실제 컨테이너 실행으로 옮기는
**에이전트**의 계약이다. 이 문서 하나와 옆의 `conformance.py` 만으로 구현·검증이
끝나도록 쓰여 있다. 플랫폼 접근 권한은 필요 없다.

- 참조 구현: `LLMOps/apps/edge_remote_manager/` (Python, 그대로 써도 되고 포팅해도 된다)
- 적합성 검사기: `conformance.py` (표준 라이브러리만, Python 3.8+)

---

## 1. 전체 그림

```
   ┌── 플랫폼 ──────────────┐            ┌── 엣지 디바이스 ─────────────┐
   │                        │  ① /ops    │                              │
   │  배포 지시 ────────────┼──────────► │  에이전트 (:8600)            │
   │                        │            │    └─ docker pull / run      │
   │  아티팩트 다운로드 ◄───┼────────────┼── ② model_url 로 모델 수신   │
   │                        │  ③ /metrics│                              │
   │  상태 폴링 ────────────┼──────────► │                              │
   │                        │ ◄──────────┼── ④ heartbeat (선택)         │
   └────────────────────────┘            └──────────────────────────────┘
```

방향이 둘이고 **자격증명도 둘**이다. 헷갈리면 안 된다.

| 방향 | 자격증명 | 설정 위치 |
|---|---|---|
| 플랫폼 → 디바이스 (`/ops`, `/metrics`) | `OPS_TOKEN` — 플랫폼이 자신을 증명 | 에이전트가 검증 |
| 디바이스 → 플랫폼 (heartbeat, 아티팩트 수신) | `DEVICE_TOKEN` — 디바이스가 자신을 증명 | 플랫폼이 발급·검증 |

두 토큰은 서로 대체할 수 없다.

## 2. 에이전트가 구현할 엔드포인트

### `POST /ops`

요청 헤더: `Authorization: Bearer <OPS_TOKEN>` (OPS_TOKEN 이 설정된 경우 필수)

**배포**
```json
{
  "op": "deploy",
  "image": "registry.example.com/edge-serve:1.0",
  "model": "qwen-7b",
  "version": "q4_k_m",
  "gguf_path": "model.q4.gguf",
  "model_url": "http://<플랫폼>/api/edge/devices/<device_id>/artifact",
  "params": { "port": 8000, "env": {}, "docker_args": [], "cmd": [] }
}
```
에이전트가 할 일:
1. `model_url` 이 있으면 **먼저 모델 파일을 받는다**(§3). 실패하면 배포를 진행하지 않고
   오류를 보고한다 — 모델 없이 컨테이너를 띄우면 화면은 정상인데 서빙이 안 된다.
2. 파일은 `MODEL_DIR` 아래 `gguf_path` 의 파일명으로 저장한다.
3. `docker pull` → 기존 컨테이너 교체(`rm -f`) → `docker run`.
   `MODEL_DIR` 을 컨테이너의 `/models` 로 마운트하고 `MODEL_PATH=/models/<파일명>` 을 주입한다.
   GPU 가 있으면 `--gpus all`.
4. 응답 — **`model_url` 이 있으면 비동기로 답한다.**

| 경우 | 응답 |
|---|---|
| `model_url` 있음 (모델 수신 필요) | `202` + `{"status":"deploying","contract_version":"1.0"}` 를 **즉시** 반환하고, 수신·기동은 백그라운드로 진행 |
| `model_url` 없음 (파일이 이미 있음) | `200` + `{"status":"running","contract_version":"1.0"}` |
| 이미 배포가 진행 중 | `409` + `{"status":"error","detail":"deploy already in progress"}` (동기·비동기 **모든** deploy에 적용) |

> 수 GB 파일을 받는 동안 응답을 붙들고 있으면 플랫폼의 호출(수 초 예산)이 타임아웃난다.
> 그래서 즉시 `202` 로 답하고, 진행·결과는 `/metrics` 의 `deploy_in_progress` 와
> `last_deploy_error` 로 알린다. 이 두 필드가 없으면 플랫폼은 '받는 중' 과 '실패' 와
> '중지됨' 을 구분하지 못해 다운로드 중인 디바이스를 중지됨으로 표시한다.

**중지**
```json
{ "op": "stop" }
```
컨테이너를 제거하고 `{"status":"stopped","contract_version":"1.0"}`.
**이미 없으면 성공이다**(목표 상태가 이미 충족됨). 멱등해야 한다.

`stop` 이 해야 할 일이 하나 더 있다:

> **진행 중인 비동기 배포를 반드시 무효화할 것.** 다운로드·pull 중에 `stop` 이 오면,
> 컨테이너만 지우고 응답해서는 안 된다. 그 백그라운드 작업이 그대로 완주해 컨테이너를
> **다시 만들어 버리기** 때문이다. 사용자는 껐는데 잠시 뒤 되살아나는 유령 재기동이 된다.
> 세대 카운터 같은 수단으로 진행 중 작업을 밀어내고, 컨테이너를 바꾸는 구간(`stop` 의
> 제거와 배포의 교체)을 **같은 락으로 직렬화**해 "무효화 확인 → 실행" 사이의 창을 닫아야 한다.
> 플랫폼 UI 는 `deploying` 상태에서도 중지 버튼을 열어 두므로 이것은 정상 사용 경로다.
>
> 또한 `stop` 성공 시 `last_deploy_error` 를 **`null` 로 되돌릴 것.** 남겨 두면 플랫폼이
> 확정한 `stopped` 를 다음 폴링이 `error` 로 되돌린다.

**오류 보고 규약 (가장 중요)**

실패는 반드시 이렇게 답한다:
```json
{ "status": "error", "detail": "사람이 읽을 수 있는 사유" }
```
플랫폼은 이 응답으로 배포 상태를 확정한다. 실패를 `stopped` 나 `running` 으로 보고하면
**컨테이너가 살아 있는데 화면은 중지됨이라 말하는** 조용한 거짓이 된다. docker 부재,
`docker rm` 비정상 종료, 타임아웃, 다운로드 실패 모두 `error` 다.

### `GET /metrics`

요청 헤더: `Authorization: Bearer <OPS_TOKEN>` (설정된 경우 필수)

```json
{
  "contract_version": "1.0",
  "deploy_in_progress": false,
  "last_deploy_error": null,
  "containers": [
    {"name":"edge-serve","image":"...","state":"running","model":"qwen-7b","version":"q4_k_m"}
  ],
  "container_count": 1,
  "node_cpu_total": 8,
  "memory_total": 16,
  "gpu": "NVIDIA Jetson Orin"
}
```
`state` 는 `running` 또는 `stopped`. 플랫폼은 이 값으로 실제 배포 상태를 확정하므로
**추측이 아니라 실제 컨테이너 상태**(예: `docker ps`)를 보고해야 한다.

> **`contract_version` 은 선택이 아닙니다.** 플랫폼은 배포 직전 `/metrics` 를 조회해 이
> 값이 없으면 **모델 수신이 필요한 배포를 거절**합니다. 구버전 에이전트는 모르는
> `model_url` 을 조용히 무시한 채 받은 적 없는 파일명으로 컨테이너를 띄우기 때문입니다
> (화면은 정상인데 모델이 없는 상태). 이 값을 반드시 보고하세요.

- `deploy_in_progress` — 비동기 배포(모델 수신·기동)가 진행 중이면 `true`.
- `last_deploy_error` — 직전 비동기 배포가 실패했으면 사유 문자열, 아니면 `null`.
  **성공한 배포는 이 값을 반드시 `null` 로 되돌린다**(옛 실패가 영구히 남으면 정상
  배포가 계속 실패로 보인다).

## 3. 모델 아티팩트 수신

`model_url` 은 플랫폼이 발급하는 1:1 다운로드 주소다. 무엇을 주는지는 플랫폼이 정하므로
경로를 바꿔 다른 파일을 요청할 수 없다.

```
GET <model_url>
Authorization: Bearer <DEVICE_TOKEN>
```

- 수 GB 파일이므로 **이어받기를 권장**한다. 서버는 `Accept-Ranges: bytes` 와
  `Range: bytes=<시작>-` (206 응답)을 지원한다.
- `HEAD` 로 `Content-Length` 를 먼저 확인하면 이미 받아 둔 파일을 건너뛸 수 있다.
- 부분 파일은 `.part` 같은 임시 이름에 쓰고 **완료 후에만** 제자리로 옮긴다. 중단된
  전송이 완성본처럼 보이면 다음 배포가 깨진 모델을 마운트한다.
- `HEAD` 도 같은 인증으로 지원한다(`Content-Length`, `Accept-Ranges`).
- 401 은 `DEVICE_TOKEN` 문제, 404 는 이 디바이스에 인가된 아티팩트가 없다는 뜻이다.
  **429** 는 디바이스별 전송량 한도(시간창 기준)에 걸린 것이므로 잠시 뒤 재시도한다.
- 파일명은 플랫폼이 산출물마다 고유하게 정해 보낸다(`lineage-<id>-<이름>.gguf`). **받은
  파일을 이 이름 그대로 저장할 것.** "같은 이름 + 같은 크기면 이미 받은 것" 이라는 판단은
  이 규칙이 지켜질 때만 안전하다 — 같은 모델을 같은 방식으로 재양자화하면 원래 이름도
  크기도 같아지는 일이 흔해서, 이름을 임의로 줄이면 옛 가중치를 그대로 띄우게 된다.
- 이미 `.part` 가 전체 크기만큼 차 있으면 `Range` 로 더 요청하지 말고(서버가 416 을 준다)
  그대로 확정할 것. 그러지 않으면 운영자가 파일을 지울 때까지 재시도가 영구히 막힌다.

## 4. heartbeat (선택)

디바이스가 살아 있음을 주기적으로 알린다. 설정하지 않아도 배포는 동작하지만, 연결
상태가 폴링에만 의존하게 된다.

```
POST <플랫폼>/api/edge/devices/<device_id>/heartbeat
Authorization: Bearer <DEVICE_TOKEN>
{ "timestamp": "...", "cpu_pct": 12.3, "gpu_mem_gb": 8.0, "model_loaded": "qwen-7b" }
```
**30초 이상 간격**을 지킬 것. 더 자주 보내면 429 로 거절된다(35초 권장).

## 5. 계약 버전과 호환 정책

`contract_version` 은 `<major>.<minor>` 다.

- **minor 상승** = 필드 추가. 기존 구현은 그대로 동작해야 한다(모르는 필드는 무시할 것).
- **major 상승** = 필드 제거 또는 의미 변경. 구현 수정이 필요하다.

응답에 모르는 필드가 오더라도 실패하지 말 것. 현재 버전은 **1.0** 이다.

## 6. 설정(환경변수)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `AGENT_PORT` | 8600 | 수신 포트 |
| `MODEL_DIR` | `/opt/edge/models` | 모델 파일 위치(컨테이너에 `/models` 로 마운트) |
| `CONTAINER_NAME` | `edge-serve` | 관리 대상 컨테이너 이름 |
| `GPU` | `auto` | `auto` \| `on` \| `off` |
| `OPS_TOKEN` | (없음) | 플랫폼→디바이스 인증. **운영에서는 반드시 설정** |
| `DEVICE_TOKEN` | (없음) | 플랫폼이 발급. 아티팩트 수신·heartbeat 인증 |
| `DEVICE_ID` | (없음) | 플랫폼이 발급한 디바이스 식별자 |
| `PLATFORM_HEARTBEAT_URL` | (없음) | heartbeat 대상 주소 |
| `HEARTBEAT_INTERVAL` | 35 | 초. 31 미만 불가 |

> `OPS_TOKEN` 을 설정하지 않으면 `/ops`·`/metrics` 가 무인증으로 열린다. 그 상태는
> **신뢰 사설망 전용**이다. 이 엔드포인트는 호스트에서 컨테이너를 실행할 수 있으므로
> 공용 네트워크에 노출하면 안 된다. 에이전트는 호스트의 docker 를 제어하므로 컨테이너
> 안이 아니라 **호스트 프로세스**(systemd 등)로 실행한다.

## 7. 적합성 검사

구현이 끝나면 에이전트를 띄운 뒤 같은 장비에서 실행한다.

```bash
# 계약 검사만 (컨테이너를 띄우지 않음)
python3 conformance.py --url http://localhost:8600 --ops-token <OPS_TOKEN>

# 배포까지 검사 (모델 수신 → 기동 → 중지)
python3 conformance.py --url http://localhost:8600 \
    --ops-token <OPS_TOKEN> \
    --device-token <에이전트에 설정한 DEVICE_TOKEN> \
    --image <검사에 쓸 컨테이너 이미지>
```

배포 검사에서는 이 스크립트가 임시 HTTP 서버로 가짜 아티팩트를 제공하므로, **에이전트가
이 스크립트 쪽으로 접속할 수 있어야 한다**(다른 장비에서 돌린다면 `--callback-host` 로
에이전트가 볼 수 있는 주소를 지정).

전 항목 통과(종료코드 0)가 납품 기준이다.

```
결과: 17/17 통과
적합성 검사 통과 — 계약 v1 을 만족합니다.
```

## 8. 플랫폼 쪽 등록 절차(운영자)

1. 관리자 화면에서 엣지 워커 등록 — `remote_manager_url = http://<디바이스>:8600`
   (**경로 없이**. 플랫폼이 `/ops`, `/metrics` 를 붙인다)
2. 워커 토큰 발급 → 받은 값을 에이전트의 `DEVICE_TOKEN` 에 넣고 재기동
3. 배포 실행 → 플랫폼이 `/ops` 로 배포를 지시하고, 에이전트가 모델을 받아 컨테이너를 띄운다
