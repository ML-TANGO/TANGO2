# 엣지 에이전트 연동 규약 v1 (contract_version 1.2)

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
| 플랫폼 → 디바이스 (`/ops`, `/metrics`) | `OPS_TOKEN` (+회전 중 `OPS_TOKEN_PREV`) — 플랫폼이 자신을 증명 | 에이전트가 **둘 중 하나**와 맞으면 통과 |
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
   `mmproj_url` 이 있으면(1.2, 아래 VLM 패키지) 그 파일도 받는다. 둘 중 하나라도 실패하면 배포 실패다.
2. 파일은 `MODEL_DIR` 아래 `gguf_path`(·`mmproj_path`) 의 파일명으로 저장한다.
3. `docker pull` → 기존 컨테이너 교체(`rm -f`) → `docker run`.
   `MODEL_DIR` 을 컨테이너의 `/models` 로 마운트하고 `MODEL_PATH=/models/<파일명>` 을 주입한다.
   `mmproj_path` 가 있으면 `MMPROJ_PATH=/models/<mmproj 파일명>` 도 주입한다.
   GPU 가 있으면 GPU 인자를 붙인다 — 환경에 따라 `--gpus all` 또는 `--runtime nvidia` (§6-1).
4. 응답 — **`model_url` 이 있으면 비동기로 답한다.**

**VLM 패키지 (1.2)** — 이미지를 입력으로 받는 모델(예: SDS 해상 VLM)은 LLM GGUF 와 비전
인코더 GGUF(mmproj) 두 파일이 함께 있어야 동작한다. 이때 플랫폼은 아래 두 필드를 더 보낸다.
```json
{
  "mmproj_path": "lineage-14-mmproj-model.f16.gguf",
  "mmproj_url": "http://<플랫폼>/api/edge/devices/<device_id>/artifact/mmproj"
}
```
- 서빙 컨테이너는 `MMPROJ_PATH` 를 비전 파일로 써야 한다. llama.cpp `llama-server` 라면
  `--mmproj $MMPROJ_PATH`(또는 `LLAMA_ARG_MMPROJ`)로 띄우면 OpenAI 호환 `/v1/chat/completions`
  에서 `image_url`(base64 data URL) 입력을 받는다.
- 플랫폼은 VLM 패키지를 **contract_version 1.2 이상**을 보고하는 에이전트에만 보낸다. 이 필드를
  모르는 에이전트는 LLM 만 띄워 '이미지를 못 보는 모델' 이 정상처럼 보이기 때문이다.
  텍스트 모델 배포는 1.0/1.1 에이전트에도 그대로 간다.

| 경우 | 응답 |
|---|---|
| `model_url` 있음 (모델 수신 필요) | `202` + `{"status":"deploying","contract_version":"1.2"}` 를 **즉시** 반환하고, 수신·기동은 백그라운드로 진행 |
| `model_url` 없음 (파일이 이미 있음) | `200` + `{"status":"running","contract_version":"1.2"}` |

> `model_url` 이 없는 배포도 **기존 컨테이너를 먼저 내린 뒤** 새로 띄울 것. 내리지 않으면
> 이전 모델이 계속 돌아가는데 `/metrics` 는 새 배포를 보고해, 실제로 서빙 중인 모델과
> 화면이 어긋난다. 위 3번(`rm -f` → `run`)은 이 경로에도 그대로 적용된다.
| 이미 배포가 진행 중 | `409` + `{"status":"error","detail":"deploy already in progress"}` (동기·비동기 **모든** deploy에 적용) |

> 수 GB 파일을 받는 동안 응답을 붙들고 있으면 플랫폼의 호출(수 초 예산)이 타임아웃난다.
> 그래서 즉시 `202` 로 답하고, 진행·결과는 `/metrics` 의 `deploy_in_progress` 와
> `last_deploy_error` 로 알린다. 이 두 필드가 없으면 플랫폼은 '받는 중' 과 '실패' 와
> '중지됨' 을 구분하지 못해 다운로드 중인 디바이스를 중지됨으로 표시한다.

**중지**
```json
{ "op": "stop" }
```
컨테이너를 제거하고 `{"status":"stopped","contract_version":"1.2"}`.
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

**모르는 `op`**

`deploy`·`stop` 이 아닌 `op` 는 오류로 답한다:
```json
{ "status": "error", "detail": "unknown op: <받은 값>" }
```
`running` 을 돌려주면 플랫폼이 오타 난 명령을 성공으로 기록한다. 적합성 검사기가
채점하는 항목이다(§7).

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
  "contract_version": "1.2",
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
  **`false` 로 내리는 시점은 컨테이너가 실제로 요청에 답할 수 있게 된 뒤다.** `docker run`
  이 반환했다거나 포트가 열렸다는 것만으로 내리면, 플랫폼이 "실행 중" 으로 표시하는 동안
  모델은 아직 로딩 중이고 그 사이 추론 요청은 실패한다. 서빙 컨테이너의 헬스 엔드포인트가
  200 을 준다고 곧바로 준비 완료는 아니다 — llama.cpp 계열은 HTTP 서버가 바인드되면
  `/health` 가 먼저 `200` 을 주고 모델 슬롯은 그 뒤에 준비된다(실측). 확실한 판정은
  **1토큰짜리 실제 추론 요청이 성공하는지** 보는 것이다.
- `last_deploy_error` — 직전 비동기 배포가 실패했으면 사유 문자열, 아니면 `null`.
  **성공한 배포는 이 값을 반드시 `null` 로 되돌린다**(옛 실패가 영구히 남으면 정상
  배포가 계속 실패로 보인다).

## 3. 모델 아티팩트 수신

`model_url` 은 플랫폼이 발급하는 1:1 다운로드 주소다. 무엇을 주는지는 플랫폼이 정하므로
경로를 바꿔 다른 파일을 요청할 수 없다.
**URL 은 받은 그대로(쿼리 포함) 쓸 것.** 플랫폼은 `?lineage=<id>` 를 붙여 보내고, 그 배포가
더 이상 인가된 배포가 아니면 404 를 준다 — 중지·재배포 직후 아직 돌던 옛 다운로드가 새 배포의
파일을 옛 이름으로 받아 가는 것을 막는 장치다.

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
- `mmproj_url`(1.2)도 같은 규칙이다 — 같은 `DEVICE_TOKEN`, 같은 Range·HEAD 지원, 같은 전송량 한도.
  파일명은 `mmproj_path` 그대로 저장하고, 옛 아티팩트를 정리할 때 이번 배포의 두 파일은 남긴다.
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

응답에 모르는 필드가 오더라도 실패하지 말 것. 현재 버전은 **1.2** 이다.

| 버전 | 추가된 것 |
|---|---|
| 1.0 | 최초 — heartbeat · artifact · /ops · /metrics · ops 토큰 |
| 1.1 | `OPS_TOKEN_PREV` 병행 허용(키 교체 구간 흡수, §6-2). 1.0 구현도 그대로 동작한다 |
| 1.2 | VLM 패키지 — `mmproj_url`·`mmproj_path` 수신, `MMPROJ_PATH` 주입(§2). VLM 배포는 1.2 이상에만 간다. 텍스트 모델은 1.0/1.1 도 그대로 |

## 6. 설정(환경변수)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `AGENT_PORT` | 8600 | 수신 포트 |
| `MODEL_DIR` | `/opt/edge/models` | 모델 파일 위치(컨테이너에 `/models` 로 마운트) |
| `CONTAINER_NAME` | `edge-serve` | 관리 대상 컨테이너 이름 |
| `GPU` | `auto` | `auto` \| `on` \| `off` \| `runtime` \| `gpus` (§6-1) |
| `OPS_TOKEN` | (없음) | 플랫폼→디바이스 인증. **운영에서는 반드시 설정** |
| `OPS_TOKEN_PREV` | (없음) | 회전 중 직전 키. 설정되면 이 값도 통과시킨다(§6-2) |
| `DEVICE_TOKEN` | (없음) | 플랫폼이 발급. 아티팩트 수신·heartbeat 인증 |
| `DEVICE_ID` | (없음) | 플랫폼이 발급한 디바이스 식별자 |
| `PLATFORM_HEARTBEAT_URL` | (없음) | heartbeat 대상 주소 |
| `HEARTBEAT_INTERVAL` | 35 | 초. 31 미만 불가 |

> `OPS_TOKEN` 을 설정하지 않으면 `/ops`·`/metrics` 가 무인증으로 열린다. 그 상태는
> **신뢰 사설망 전용**이다. 이 엔드포인트는 호스트에서 컨테이너를 실행할 수 있으므로
> 공용 네트워크에 노출하면 안 된다. 에이전트는 호스트의 docker 를 제어하므로 컨테이너
> 안이 아니라 **호스트 프로세스**(systemd 등)로 실행한다.

### 6-1. GPU 접근 방식 (Jetson 주의)

컨테이너에 GPU 를 붙이는 방법이 플랫폼마다 다릅니다.

| 환경 | 인자 |
|---|---|
| 데스크톱/서버 NVIDIA + nvidia-container-toolkit | `--gpus all` |
| Jetson(JetPack/L4T) + nvidia-container-runtime | `--runtime nvidia` |
| Jetson + 최신 toolkit(JetPack 6 계열) | `--gpus all` 도 동작 |

참조 구현은 `GPU=auto` 에서 이를 **런타임에 판별**합니다 — Jetson 여부를
`/etc/nv_tegra_release` 또는 `/proc/device-tree/model` 로 보고, Jetson 이면 docker 에
`nvidia` 런타임이 등록돼 있는지에 따라 위 둘 중 하나를 고릅니다.

> ⚠️ **`nvidia-smi` 유무로 GPU 를 판단하지 마세요.** Jetson 은 그 도구를 기본 제공하지
> 않습니다(`tegrastats` 를 씁니다). 그걸 기준으로 삼으면 Orin 이 'GPU 없음' 으로 잡혀
> **오류 없이 CPU 로 서빙**하게 됩니다 — 가장 발견하기 어려운 실패입니다.

대상 JetPack 버전이 확정됐다면 자동 판별에 맡기지 말고 `GPU=runtime` 또는 `GPU=gpus`
로 못박는 편이 안전합니다. 서빙 이미지도 **arm64(L4T) 빌드**여야 합니다.

받은 아티팩트는 `lineage-<id>-…` 이름으로 저장되며, 새 배포가 성공하면 참조 구현이
이전 `lineage-*` 파일을 정리합니다(저장공간이 제한적인 장비 대비). 운영자가 직접 넣어
둔 모델 파일은 건드리지 않습니다.

### 6-2. 키 교체

플랫폼 관리자 화면(노드 관리 → Edge)에서 키를 조회·재발급할 수 있다.

**재발급은 하드 컷오버다.** 플랫폼은 항상 현재 키만 보내고, 401 을 받아도 옛 키로
재시도하지 않는다(유출된 키가 계속 통하는 상태를 만들지 않기 위해서다). 따라서 교체
작업 창을 잡고 디바이스를 차례로 바꿔야 한다.

```
① 플랫폼에서 [재발급]      이 시점부터 플랫폼은 새 키만 보낸다
                            → 아직 옛 키인 디바이스는 /ops·/metrics 가 401
                            → heartbeat 와 실행 중인 컨테이너는 영향 없음
② 디바이스를 하나씩 교체     OPS_TOKEN=<새 키> 로 바꾸고 에이전트 재기동
③ 플랫폼에서 [옛 키 폐기]    보관 중이던 직전 키 삭제(인증 동작에는 영향 없음)
```

`OPS_TOKEN_PREV` 는 이 중단을 없애 주지 않는다. ②에서 디바이스를 새 키로 바꾼 직후
플랫폼이 잠시 옛 키를 보낼 수 있는 구간(서버측 캐시)을 덮기 위한 것이다.

에이전트 구현 요구사항은 하나다 — **`OPS_TOKEN` 또는 `OPS_TOKEN_PREV` 중 하나와 맞으면
통과**시킬 것(둘 다 상수시간 비교). 지원하지 않아도 계약 위반은 아니지만(1.0 호환),
그 경우 회전할 때 그 디바이스는 교체 전까지 연결이 끊긴다.

> ⚠️ ②는 **사람이 해야 한다.** 플랫폼이 디바이스에 키를 밀어 넣을 채널이 곧 인증
> 대상이라(순환), 첫 주입과 교체는 대역 외로 전달한다. 화면이 하는 일은 조회·재발급·
> 창 관리까지다.

## 7. 적합성 검사

구현이 끝나면 에이전트를 띄운 뒤 같은 장비에서 실행한다.

```bash
# 계약 검사만 (컨테이너를 띄우지 않음)
python3 conformance.py --url http://localhost:8600 --ops-token <OPS_TOKEN> \
    --ops-token-prev <OPS_TOKEN_PREV>   # 회전 창 검사(선택)

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
