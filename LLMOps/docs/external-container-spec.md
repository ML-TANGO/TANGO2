# 외부 컨테이너 인터페이스 계약서 v1

협력기관 ML 컨테이너 → TANGO2 GenAI 플랫폼 통합 표준

| 항목 | 값 |
|---|---|
| spec API version | `tango.acryl.ai/v1` |
| 발효 | 2026-05 |
| 호환 약속 | 2026-05 ~ 2027-12 (2차년도 + 3차년도 시작) |
| spec 버전 | v1.1 (2026-04-29 코드 검증 후 회수 4건 반영: 다중 dataset / JF_HOME / Dockerfile framing / Secrets 환경변수 주입) |
| 대상 | SDx 컨소시엄 참여 협력기관 (고려대 / 서울대 / 슈어데이터랩 / 도메인 기관) |
| 관련 문서 | `docs/Tango MSA 탑재 가이드.md` (**기본 contract** — `/health`·`/info`·`/run`·helm chart 작성법) / `apps/fb_utils/errors.yaml` (에러 스키마) / `examples/openapi-template.yaml` (OpenAPI 출발점) / `docs/adr/0002-external-container-auth.md` (인증 ADR) |

---

## 1. 개요

TANGO2 GenAI 플랫폼이 **외부 협력기관**이 제공하는 ML 컨테이너를 K8s 클러스터에 launch + 결과 수집하는 표준.

### 1.1 대상 카테고리

| # | 카테고리 | 출처 | 입력 | 처리 | 출력 |
|---|---|---|---|---|---|
| A | 데이터 전처리/증강 | 학계/연구기관 | raw 데이터셋 | 멀티모달 임베딩 / 크로스모달 정렬 / 데이터 증강 / 프롬프트 기반 데이터 생성 | 학습용 데이터셋 |
| B | 평가 알고리즘 | 고려대 등 | 학습된 체크포인트 + eval 데이터셋 | Joint Accuracy / LLM-as-a-Judge / 메트릭 계산 | 메트릭 JSON |
| C | 학습 알고리즘 | 학계/협력기관 | 베이스 모델 + 학습 데이터 (LoRA/QLoRA/DoRA, Self-RAG, Knowledge Distillation, Diffusion) | 파인튜닝 | 학습된 모델 가중치 |
| D | 모델 변환 | 다양 | 학습된 모델 | 양자화 (AWQ, WSQ, GGUF), 가지치기, 추론엔진 변환 | 변환된 모델 + 실행 이미지 |
| E | 추론 서비스 | 학계/협력기관 | 학습된 체크포인트 + 요청 데이터 | 실시간 추론 (LLM, VLM, 멀티모달) | 추론 결과 (텍스트, 분류, 임베딩) |

> **Hybrid 컨테이너 (예: SDS-VLM)**: 한 코드베이스가 추론(E, sync) + 학습(C, async) 두 성격을 모두 가진 경우 → **두 manifest 로 분리해 등록** 권장 (같은 이미지, 다른 entrypoint). 예: `eva-vlm-infer.yaml` (execution_mode: sync, /run 영구 배포) + `eva-vlm-train.yaml` (execution_mode: async, 학습 시 launch). 자세한 사례는 `docs/superpowers/reviews/2026-05-12-ETRI-SDS-VLM-API-review.md` §E1 참고.

### 1.2 비대상 (v1 제외)

- **Webhook receiver / Platform API 호출 카테고리**: Platform API 인증/권한이 필요해서 v2에서 별도 정의
- **Edge device 자체 컨테이너**: 온디바이스 배포는 별도 spec
- **신규 자체 마이크로서비스**: 본 spec은 외부 협력기관 컨테이너 한정
- **인증/인가 (외부 컨테이너 보호)**: v1 은 Kong gateway 단의 인증 차단 + ClusterIP 만 노출 + NetworkPolicy 로 cluster 내부 cross-workspace 호출 차단 패턴 가정. 컨테이너 내부의 토큰 검증 미들웨어는 v1 미요구. v2 에서 K8s Secret 기반 API key / JWT 검증 미들웨어 표준화 예정.

### 1.3 `Tango MSA 탑재 가이드`와의 관계 — 두 layer contract

플랫폼은 외부 협력기관 서비스 탑재용으로 **두 layer 의 contract** 를 제공하며, 두 문서는 **충돌하지 않고 공존**한다.

| Layer | 문서 | 적용 범위 | 강제 강도 |
|---|---|---|---|
| **기본 contract** | `docs/Tango MSA 탑재 가이드.md` | 모든 외부 MSA 공통: `/health`, `/info`, `/run`, 공통 헤더, 표준 에러 코드, helm chart 작성법, `acryl.ai/appType: user` 어노테이션 | 항상 적용 |
| **도메인 contract** (본 spec) | `docs/external-container-spec.md` (SP-1 v2) | 학습·추론·배포 등 **GPU/PVC 자원이 필요하고 비동기 long-running job 형태**로 동작하는 도메인 | 해당 도메인 서비스에 한해 추가 적용 |

**원칙 (이 spec 의 핵심 가정)**:

- **내부 자체 개발 모델** (아크릴 internal LLM 등) → 본 spec 미적용. apps/llm_model 의 모듈 코드 패턴 유지 (`/fine-tuning/sse-status/{model_id}` SSE 기반).
- **외부 협력기관 학습/추론/배포 서비스** → 본 spec 표준 적용. **URL 과 스키마는 manifest 기반 자유 정의**, response shape (`status` enum, `job_id`, `progress`, `result`, `error` 필드 구조) 와 lifecycle 만 strict.
- **사용자 facing 통합 UI** (모델 > 학습/추론/변환/배포) → 플랫폼 BFF (`apps/llm_model`) 가 internal/external 양쪽 normalize 책임. 협력기관의 URL 변경 강제 없음.

→ 새 협력기관 onboarding 시 권장 순서: ① 탑재 가이드 1~4장 (helm chart + /health/info/run 구현) → ② 도메인이 학습/추론/배포면 본 spec 추가 적용 + manifest 작성 → ③ 플랫폼 담당자 사전 협의.

---

## 2. 컨테이너 Lifecycle

```
1. 협력기관: 컨테이너 + manifest.yaml 작성 → 자체 registry push (registry.jonathan.acryl.ai/external/...)
2. 플랫폼 운영자: manifest 검토 + 승인 → 플랫폼 DB에 등록
3. 사용자: 자기 workspace에서 외부 컨테이너 작업 트리거 (UI / API)
4. 플랫폼 fb_scheduler: manifest 기반 Helm 템플릿 instance 생성 → K8s pod launch (외부 컨테이너 전용 mitigation 정책 자동 적용)
5. 컨테이너: 실행 (sync / async / batch)
6. 플랫폼: 결과 회수 (stdout 실시간 파싱 + 종료 후 /output 파일 스캔)
7. 플랫폼: cleanup (pod 삭제, /output 파일은 workspace로 이전 또는 후속 작업 입력으로)
```

---

## 3. 입력 Contract

### 3.1 PVC Mount 경로

| 경로 | RO/RW | 용도 | 카테고리 |
|---|---|---|---|
| `/dataset/{DATASET_NAME}` | RO | 입력 데이터셋 (단일) | A, B, C |
| `/model` | RW | 입력/출력 모델 (학습 컨테이너 lifecycle) | B, C, D |
| `/built_in_checkpoint` | RO | 베이스 체크포인트 (있을 때) | C |
| `/tmp_model` | RW | 학습 중간 산출물 | C |
| `/logs` | RW | TensorBoard events | B, C |
| **`/input`** | **RO** | scheduler가 launch 직전 작성하는 launch input (params.json 등) | A, B, C, D |
| **`/output`** | RW (write-only artifact) | 컨테이너 산출물 (dataset/metrics/model/logs/artifacts) | A, B, D |

> **`/input` (RO) vs `/output` (RW) 분리 이유**: provenance 보존 + 컨테이너가 자기 입력 덮어쓰기 방지. 실패 후 재시도 시 플랫폼이 원본 입력 식별 가능.

> **단일 dataset 가정**: 1차년도 코드 패턴 일관 (`apps/fb_scheduler/helm_chart/fine_tuning/templates/pod.yaml:148` 단일 mount, `dto.py` `dataset_name: str` 단일 필드). 협력기관이 다중 데이터(예: train + eval)가 필요하면 **단일 dataset 디렉토리 안에 multi-split 파일로 포함** 권장:
>
> ```
> /dataset/my_eval_set/
>   ├── train.parquet
>   ├── eval.parquet
>   ├── test.parquet
>   └── manifest.json
> ```
>
> 컨테이너 코드가 split 파일별로 읽기 (`pd.read_parquet(f"{dataset_path}/eval.parquet")`). 진짜 다중 mount가 필요한 케이스는 v2에서 별도 spec.
>
> **외부 자격증명 (OPENAI_API_KEY 등)**: K8s Secret 파일 mount 메커니즘 v1 미사용. 1차년도 HF 토큰 패턴(`--set spec.containers.env.JF_HUGGINGFACE_TOKEN={...}`)과 일관되게 **환경변수 주입**. 자세한 흐름은 Section 6 `secrets.required` 참조.

### 3.2 환경변수 주입

플랫폼이 컨테이너에 자동 주입:

```bash
# === Platform metadata (정적 값, 환경변수 안전) ===
JF_HOME=/root/project         # 1차년도 ENV 클래스 패턴 일관 (apps/fb_scheduler/src/scheduler/dto.py:94 PATH.JF_PROJECT_BASE_HOME_POD_PATH)
JF_HOST=<owner_name>          # workspace owner
JF_ITEM_ID=<job_id>           # job id (UUID)
JF_POD_NAME=<unique_pod_name>
JF_TOTAL_GPU=<count>

# === 모델/데이터셋 (1차년도 컨벤션 + 외부 컨테이너용 신규 변수) ===
JF_MODEL_PATH=/model
JF_MODEL_NAME=<model_name>     # 신규 (SP-3에서 dto.py 보강 시 추가): /model 에 mount된 모델의 식별 이름 (예: "llama-3-8b")
JF_DATASET_PATH=/dataset
JF_DATASET_NAME=<name>         # 신규 (SP-3에서 dto.py 보강 시 추가): /dataset/{name} 의 단일 dataset 식별
JF_HUGGINGFACE_TOKEN=<token>   # HF 모델 다운로드 필요 시 (1차년도 호환성 위해 환경변수 유지)
JF_BUILT_IN_CHECKPOINT_PATH=/built_in_checkpoint

# === 외부 컨테이너 신규 (SP-3에서 launch 인프라 작성 시 추가) ===
JF_INPUT_PATH=/input
JF_OUTPUT_PATH=/output
JF_JOB_TYPE=train|evaluate|preprocess|convert|infer
JF_EXECUTION_MODE=sync|async|batch    # 컨테이너가 자기 mode 자기 인식 (manifest와 자동 일관)
JF_PARAMS_PATH=/input/params.json
JF_PORT=8000                  # HTTP 서버 listen port (sync/async 컨테이너만, batch는 무시). manifest.spec.port에서 결정, default 8000

# === 외부 자격증명 (manifest secrets.required 기반, 환경변수 주입) ===
# 협력기관이 manifest에 신고한 자격증명을 운영자가 helm `--set spec.containers.env.{NAME}={VALUE}` 으로 주입
# 예: OPENAI_API_KEY, WANDB_API_KEY 등 — 1차년도 HF 토큰 패턴과 동일
```

#### 컨테이너 코드 예시 — 환경변수 사용

```python
import os, json

# Platform metadata
job_id = os.environ["JF_ITEM_ID"]
job_type = os.environ["JF_JOB_TYPE"]                # "evaluate" | "train" | "infer" 등
execution_mode = os.environ.get("JF_EXECUTION_MODE", "batch")  # "sync" | "async" | "batch"

# 입력
params = json.load(open(os.environ["JF_PARAMS_PATH"]))   # /input/params.json
dataset_name = os.environ["JF_DATASET_NAME"]             # "my_eval_set"
dataset_path = f"{os.environ['JF_DATASET_PATH']}/{dataset_name}"  # /dataset/my_eval_set
model_path = os.environ["JF_MODEL_PATH"]                 # /model
model_name = os.environ.get("JF_MODEL_NAME")             # "llama-3-8b"

# 외부 자격증명 (manifest secrets.required 신고 후 운영자가 환경변수로 주입 — 1차년도 HF 패턴 일관)
openai_key = os.environ.get("OPENAI_API_KEY")            # None일 수 있음 (선택 자격증명)
hf_token = os.environ.get("JF_HUGGINGFACE_TOKEN")        # 1차년도 자체 패턴 그대로

# 출력
output_dir = os.environ["JF_OUTPUT_PATH"]                # /output
metrics_path = f"{output_dir}/metrics.json"

# HTTP 컨테이너만 (sync/async)
port = int(os.environ.get("JF_PORT", "8000"))

# 다중 split이 필요한 경우 (학습 컨테이너가 train + eval 동시에 사용)
# → 단일 dataset 안에 multi-split 파일로 포함
train_data = f"{dataset_path}/train.parquet"
eval_data = f"{dataset_path}/eval.parquet"
```

### 3.3 입력 파라미터 전달

> **⚠️ 보안 결정**: 환경변수를 dynamic params transport로 사용 금지. **dynamic 사용자 파라미터는 반드시 `/input/params.json` 파일로 전달**. 환경변수는 platform fixed metadata 전용.

플랫폼 fb_scheduler가 launch 직전 `/input/params.json`에 작성. 컨테이너는 RO mount로 읽기:

```json
{
  "learning_rate": 1e-5,
  "batch_size": 8,
  "lora_config": {"r": 8, "alpha": 16, "target_modules": ["q_proj", "v_proj"]},
  "eval_dataset_split": "validation"
}
```

manifest의 `inputs.params: required` (params.json 사용) 또는 `inputs.params: none` (params 자체 미사용).

---

## 4. 출력 Contract

### 4.1 파일 기반 (`/output/`)

```
/output/
├── model/                          # 카테고리 D (변환): 양자화/포팅 결과
│   ├── adapter_model.safetensors   # LoRA 출력
│   ├── adapter_config.json
│   ├── model.gguf                  # 양자화 결과
│   ├── inference.py                # 추론 스크립트
│   ├── run.sh                      # 실행 환경
│   └── config.json
├── dataset/                        # 카테고리 A (전처리): 변환된 데이터셋
│   ├── train.parquet
│   ├── eval.parquet
│   └── manifest.json
├── metrics.json                    # 카테고리 B (평가): 최종 메트릭
├── logs/                           # 추가 텍스트 로그
└── artifacts/                      # 기타 산출물
```

> 학습 카테고리 (C): 기존 패턴 그대로 `/model` (학습 결과) + `/logs` (TensorBoard) 사용.

### 4.2 stdout JSON Lines (실시간)

플랫폼이 stdout을 실시간 파싱 → SSE로 UI 노출.

#### Event Types

| event | 의무 | 의미 | 예시 |
|---|---|---|---|
| `progress` | 권장 | 진행률 | `{"event":"progress","step":100,"total":1000,"percent":10.0,"timestamp":"..."}` |
| `metric` | 권장 | 학습/평가 메트릭 | `{"event":"metric","name":"train/loss","value":2.34,"step":100,"timestamp":"..."}` |
| `log` | 선택 | 일반 로그 | `{"event":"log","level":"info","message":"...","timestamp":"..."}` |
| `error` | 의무 (실패 시) | 에러 발생 | `{"event":"error","code":"E_OOM","message":"...","fatal":true}` |
| `artifact` | 권장 | 새 파일 생성 | `{"event":"artifact","path":"output/model/adapter_model.safetensors","type":"model","size_bytes":123456}` |
| `phase` | 선택 | 단계 전환 | `{"event":"phase","name":"data_loading|training|evaluation|saving"}` |

> **메트릭 `name` 컨벤션**: TensorBoard 태그 형식 권장 (`train/loss`, `eval/loss`, `train/learning_rate`) → 플랫폼 UI 코드 일관성.

비-JSON 라인 (print, traceback)은 플랫폼이 raw 로그로 보관. 컨테이너가 둘 섞어 출력해도 됨.

### 4.3 종료 코드

| 코드 | 의미 | UI 표시 |
|---|---|---|
| `0` | 성공 | ✅ 완료 |
| `1` | 사용자 에러 (잘못된 입력/파라미터) | ❌ 입력 점검 안내 |
| `2` | 인프라 에러 (OOM/타임아웃/GPU 실패) | ⚠️ 시스템 측 재시도 안내 |
| `3` | 의존성 에러 (외부 API 실패, 네트워크 단절) | 🔧 화이트리스트/네트워크 점검 안내 |
| `130` | 사용자 cancel (SIGINT) | ⏹️ 취소됨 |
| 그 외 | 알 수 없는 에러 | ❓ 로그 확인 안내 |

---

## 5. HTTP 엔드포인트 (HTTP 컨테이너만)

> **batch 모드 예외**: 카테고리 A/B/D 중 일부는 HTTP 서버 필요 없음. manifest에 `endpoints: none` 명시. 입력 = 환경변수 + `/input/params.json`, 출력 = stdout + `/output/` 파일.

### 5.1 `/info` (필수, GET)

manifest의 `metadata` + `capabilities` 정보를 그대로 반영. 플랫폼이 launch 후 컨테이너에서 다시 한 번 introspection 검증.

```json
{
  "name": "korea-eval-joint-acc",
  "version": "1.0.0",
  "execution_mode": "async",
  "job_type": "evaluate",
  "supported_models": ["llama", "qwen"],
  "min_gpu_memory_gb": 16,
  "estimated_duration_seconds": 600,
  "estimated_startup_seconds": 600,
  "spec_api_version": "tango.acryl.ai/v1"
}
```

> 컨테이너는 `/info` 응답을 manifest 값과 일관되게 유지. 불일치 시 fb_scheduler가 launch 실패 처리.

### 5.2 `/health` (readiness 전용) + Probe semantics

> **⚠️ 운영 결정**: `/health`를 readiness + liveness 둘 다 사용 시 ML 모델 cold-start (5-30분) 동안 K8s가 정상 startup을 liveness 실패로 오인 → restart loop. **probe semantics 분리 의무**.

#### `/health` 동작 (readiness 전용)

- `200 OK` + `{"status":"ready"}` → pod 준비 완료
- `503` + `{"status":"loading","reason":"..."}` → 아직 준비 안 됨

#### K8s probe 적용 (플랫폼이 자동 생성)

```yaml
startupProbe:                          # cold-start 보호 (~30분 허용)
  httpGet: { path: /health, port: <port> }
  failureThreshold: 360                # 30분 = 360 * 5초
  periodSeconds: 5

readinessProbe:                        # 트래픽 게이팅
  httpGet: { path: /health, port: <port> }
  failureThreshold: 3
  periodSeconds: 10

livenessProbe:                         # 진짜 deadlock/crash만 검출
  httpGet: { path: /live, port: <port> }   # 별도 엔드포인트 (선택)
  failureThreshold: 3
  periodSeconds: 30
  initialDelaySeconds: 1800            # 30분 후부터 검증
```

#### `/live` (선택, async 컨테이너 권장)

자체 deadlock/leak 검출 가능 시 구현. 미구현 시 livenessProbe = K8s container exit code 기반.

### 5.3 `/run` (필수, POST)

#### Sync 컨테이너 (`execution_mode: sync`)
- **입력**: JSON body
- **출력**: 200 OK + result JSON (timeout 5분 권장)

#### Async 컨테이너 (`execution_mode: async`)
- **입력**: JSON body
- **출력**: `202 Accepted` + `{"job_id": "abc123"}`

### 5.4 `/jobs/{job_id}` (async만, GET)

```json
{
  "job_id": "abc123",
  "status": "running|completed|failed|cancelled",
  "progress": 0.5,
  "result": {...},
  "error": {...}
}
```

> **URL 정책 (2026-05-13 명확화)**: `/jobs/{job_id}` 는 **권장 default 패턴**.
> 협력기관이 자체 URL 컨벤션 (예: `/train/status?job_id=X`) 을 쓰시려면
> `manifest.yaml` 의 `spec.endpoints.jobs` 에 URL 템플릿 명시 (예:
> `jobs: /train/status?job_id={id}`). 플랫폼 측 interface layer 가
> 컨테이너별 URL 호출 + dto normalize 를 담당하므로 협력기관 구현 자유.
> Default 따르면 manifest endpoints 필드 생략 가능 + 플랫폼 측 작업 최소.

### 5.5 `/jobs/{job_id}/cancel` (async, POST, 선택)

- 200 OK → 정상 종료 (SIGINT 송신)
- URL 정책: §5.4 와 동일 — `/jobs/{job_id}/cancel` 권장, manifest 의
  cancel 필드로 자체 URL 명시 가능.

---

## 6. `manifest.yaml`

협력기관이 컨테이너 등록 시 함께 제출.

```yaml
apiVersion: tango.acryl.ai/v1
kind: ExternalContainer
metadata:
  name: korea-eval-joint-acc
  version: "1.0.0"
  vendor: "Korea University NLP Lab"
  contact: "researcher@korea.ac.kr"

spec:
  image: "registry.jonathan.acryl.ai/external/korea-eval:1.0.0"

  job_type: evaluate                # train | evaluate | preprocess | convert | infer
  execution_mode: async             # sync | async | batch (batch = HTTP 없음)
  port: 8000                        # HTTP 서버 listen port. sync/async만 의미. batch는 무시. default 8000.

  resources:
    cpu: "4"
    memory: "16Gi"
    gpu: 1
    gpu_memory: "16Gi"
    accelerator: nvidia             # nvidia (default) | hailo | rocm. v1은 nvidia만 enforce

  inputs:
    dataset:                        # 단일 dataset (다중은 v2 forward, 다중 split은 dataset 내부 파일로)
      required: true                # required | none. mount: /dataset/{name}, JF_DATASET_NAME 으로 식별
    base_model:
      required: false               # /model 로 mount, JF_MODEL_NAME 으로 식별
    params:
      required: true                # /input/params.json 사용 (required | none)

  outputs:
    metrics: true                   # /output/metrics.json 작성 여부
    model: false                    # /output/model/ 작성 여부
    dataset: false
    artifacts: false

  secrets:                          # 외부 자격증명 신고 (환경변수 주입 — 1차년도 HF 토큰 패턴 일관)
    required:                       # 협력기관이 자기 컨테이너 필요한 자격증명 list로 신고
      - OPENAI_API_KEY              # 예: LLM-as-a-Judge용
      - WANDB_API_KEY               # 선택
    # 운영자: 협력기관이 별도 암호화 채널로 자격증명 값 제출 →
    # launch 시 helm `--set spec.containers.env.{NAME}={VALUE}` 으로 환경변수 주입
    # v2 (보안 강화 시): K8s Secret object + 파일 mount로 일괄 마이그레이션 (HF 토큰 포함)

  network:
    egress_whitelist:               # v1 advisory (신고 목적)
      - "huggingface.co"
      - "hf.co"
      - "api.openai.com"            # OPENAI_API_KEY 사용 시
      # 빈 배열 = 외부 통신 없음 신고

  endpoints:                        # HTTP 컨테이너만, batch는 생략
    info: "/info"
    health: "/health"               # readiness 전용
    live: "/live"                   # 선택 — async 컨테이너 권장
    run: "/run"
    jobs: "/jobs/{id}"              # async만, {id}는 placeholder

  capabilities:
    supported_models: ["llama", "qwen"]
    min_gpu_memory_gb: 16
    estimated_duration_seconds: 600
    estimated_startup_seconds: 600  # startupProbe 산정 기준
    timeout_seconds: 7200           # 선택 — hard timeout. 미명시 시 estimated_duration_seconds * 3 default
```

#### manifest 필드 reference

| 필드 | 의무 | 설명 |
|---|---|---|
| `apiVersion` | ✅ | `tango.acryl.ai/v1` 고정 (v1 호환) |
| `metadata.{name,version,vendor,contact}` | ✅ | 협력기관 식별 + 검토 통보 채널 |
| `spec.image` | ✅ | 자체 registry 강제 (`registry.jonathan.acryl.ai/external/...`) |
| `spec.port` | sync/async만 | HTTP listen port, default 8000 |
| `spec.resources.accelerator` | 선택 | nvidia (default). v1은 nvidia만. hailo/rocm은 v2 |
| `spec.inputs.dataset` | 선택 | 단일 dataset (다중 split은 dataset 내부 파일로). 다중 mount는 v2 forward |
| `spec.secrets.required` | 선택 | 환경변수로 주입할 자격증명 list (1차년도 HF 토큰 패턴 일관) |
| `spec.network.egress_whitelist` | 선택 | v1 advisory. 운영자 검토 게이트 |
| `spec.endpoints.{info,health,run,jobs,live}` | sync/async만 | HTTP 엔드포인트 path. async 컨테이너의 `jobs` 는 `/jobs/{id}` **권장 (default 패턴)**. 협력기관이 다른 URL 사용 시 manifest 에 명시 (예: `jobs: /train/status?job_id={id}`). 플랫폼 측 interface layer (`apps/llm_model/external_vlm/clients/*`) 가 각 컨테이너별 URL 호출 + dto normalize 책임. `/jobs/{id}/cancel` 도 동일하게 권장 + 자유. |
| `spec.capabilities.estimated_startup_seconds` | ✅ (HTTP) | startupProbe failureThreshold 산정 |
| `spec.capabilities.timeout_seconds` | 선택 | hard timeout. 미명시 시 default 적용 |
| `spec.workspace_scope` | 선택 | `per-workspace` (default, 워크스페이스마다 별도 helm install) \| `shared` (cluster 전체 단일 인스턴스). user-pod 컨테이너는 `per-workspace`. |

> `apiVersion: tango.acryl.ai/v1`은 plain YAML 메타. v1 시점 K8s CRD 등록 미사용. 향후 v2/v3 CRD 도입 시 호환 표기.

#### Hybrid 컨테이너 가이드 (추론 + 학습 동시 제공)

한 코드베이스가 sync 추론 (E 카테고리) + async 학습 (C 카테고리) 두 lifecycle 을 모두 가진 경우, 단일 manifest 로 표현하지 말고 **두 manifest 로 분리**해 등록한다.

- `*-infer.yaml`: `execution_mode: sync`, `job_type: infer`, 워크스페이스마다 영구 배포 (1 pod 상주, GPU 점유). endpoints: `info`, `health`, `live`, `run`.
- `*-train.yaml`: `execution_mode: async`, `job_type: train`, 학습 launch 시마다 새 pod 생성 후 종료 (job lifecycle). endpoints: `info`, `health`, `run` (POST → 202 + job_id), `jobs` (GET + /jobs/{id}/cancel).
- 두 manifest 가 같은 Docker 이미지 참조 가능 (entrypoint 만 다르게: uvicorn 추론 vs 학습 launcher).
- 학습 결과 reload: train pod 의 `/output` 가 commit_model 테이블에 commit 되면 infer pod 이 reload 신호 수신 (POST `/reload-model` 또는 commit_model watch).

레퍼런스 사례: ETRI SDS-VLM 통합 (`docs/superpowers/reviews/2026-05-12-ETRI-SDS-VLM-API-review.md` §E1).

---

## 7. v1 방어적 mitigation 표준 (best-effort)

> **⚠️ Trust boundary 한계 frank하게**: 본 절은 "isolation standard"가 아니라 **"v1 best-effort mitigation"**. 다음 한계를 운영자/협력기관 모두 명확히 인지해야 함:
>
> 1. **NetworkPolicy enforce 안 함** → 외부 컨테이너가 cluster 외부와 무제한 egress 가능. mount된 데이터셋/모델/토큰을 임의 outbound으로 exfiltrate 가능
> 2. **데이터셋/모델 mount 자체는 차단 X** (ML 컨테이너 본질) → buggy/compromised 컨테이너가 mount된 워크스페이스 데이터 전체 읽기 가능
> 3. **HF 토큰 등 secret이 환경변수로 주입** → 컨테이너 process 메모리/`/proc/self/environ` 통해 접근 가능
>
> **v1 운영 모델**: 협력기관 = "공식 SDx 컨소시엄 참여 기관"으로 한정. 임의 third-party 컨테이너 받지 않음. v2 enforce 도입 후에야 broader ecosystem 개방.

플랫폼이 외부 컨테이너 launch 시 **자동으로** 적용되는 mitigation:

### 7.1 securityContext

```yaml
spec:
  containers:
  - securityContext:
      runAsNonRoot: true
      runAsUser: 1000
      runAsGroup: 1000
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true     # /input, /output, /model, /logs, /tmp_model, /secrets 제외 RW
      capabilities:
        drop: [ALL]                    # ML 워크로드는 capability 거의 안 씀
```

#### 협력기관 Dockerfile 작성 가이드

> **⚠️ 외부 컨테이너 전용 신규 표준**: 본 가이드는 SP-1 v1 발효(2026-05) 시점에 외부 협력기관이 따라야 할 표준입니다. **1차년도 자체 컨테이너(`apps/fb_*/Dockerfile`)에는 적용되지 않음** — 1차년도는 root 실행 + securityContext 미적용 패턴을 그대로 유지 (cluster 내부 신뢰 모델). 외부 컨테이너만 securityContext가 자동 강제되며, 협력기관 Dockerfile이 이 가이드를 따라야 launch 가능.

위 securityContext 제약을 만족하기 위한 Dockerfile 권장 패턴:

```dockerfile
# 권장 베이스 이미지: NVIDIA CUDA + Python (Ubuntu 22.04)
FROM nvidia/cuda:12.1.0-devel-ubuntu22.04

# Non-root user 생성 (UID 1000 = securityContext 표준과 일치)
RUN groupadd -g 1000 tango && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash tango

# Python + 의존성 설치 (root 권한 필요한 작업은 USER 1000 전에)
RUN apt-get update && apt-get install -y python3.11 python3-pip && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 컨테이너 코드 복사
COPY --chown=1000:1000 ./app /app

# Non-root 전환
USER 1000

# WORKDIR은 mount된 RW 영역만. 컨테이너 자체 디스크 = readOnlyRootFilesystem
# `/tmp` 는 K8s에서 emptyDir로 자동 mount되므로 사용 가능
WORKDIR /tmp

# stdout 버퍼링 비활성화 (실시간 JSON Lines 출력)
ENV PYTHONUNBUFFERED=1

# ENTRYPOINT
ENTRYPOINT ["python", "-u", "/app/run.py"]
```

#### Dockerfile 체크리스트

- [ ] `USER 1000` 명시 (root 권한 X)
- [ ] `pip install` 등 root 권한 필요한 작업은 `USER 1000` 전에 완료
- [ ] write 디렉토리 = mount된 영역(`/output`, `/tmp_model`, `/logs`, `/tmp`)만 사용. 컨테이너 자체 디스크에 쓰지 않음
- [ ] `PYTHONUNBUFFERED=1` 또는 `python -u` (stdout 실시간)
- [ ] `ping`, raw socket, `iptables` 등 `CAP_NET_RAW`/`CAP_NET_ADMIN` 필요 작업 없음 (capabilities drop ALL 호환)
- [ ] 베이스 이미지는 `registry.jonathan.acryl.ai/external/...` 로 push (Docker Hub 등 외부 X)
- [ ] HTTP 컨테이너면 `JF_PORT` 환경변수에서 listen 포트 읽기

#### 자주 막히는 곳

| 증상 | 원인 | 해결 |
|---|---|---|
| pod이 `CreateContainerConfigError` | UID 1000 사용자가 컨테이너 안에 없음 | Dockerfile에 `useradd --uid 1000` 추가 |
| pod이 `Error: failed to create init process: Permission denied` | readOnlyRootFilesystem인데 `/var`, `/root` 등에 쓰려고 함 | `WORKDIR /tmp` 또는 mount된 영역만 사용 |
| stdout JSON Lines가 SSE에 실시간 안 뜸 | Python stdout 버퍼링 | `PYTHONUNBUFFERED=1` 또는 `python -u` |
| `ConnectionError: 'huggingface.co'` | egress 신고 누락 (v2 enforce 시) | manifest `network.egress_whitelist` 에 추가 |

### 7.2 PVC subPath 격리

```yaml
volumeMounts:
- name: jf-data
  mountPath: /dataset/{DATASET_NAME}
  subPath: data/{ACCESS}/{DATASET_NAME}
  readOnly: true
- name: jf-main
  mountPath: /model
  subPath: models/{MODEL_NAME}/latest_checkpoint
- name: jf-main
  mountPath: /input
  subPath: jobs/{JOB_ID}/input
  readOnly: true
- name: jf-main
  mountPath: /output
  subPath: jobs/{JOB_ID}/output
```

### 7.3 NetworkPolicy egress (v1: advisory only)

manifest의 `network.egress_whitelist`는 v1에서 **신고 목적**. K8s NetworkPolicy 자동 enforce X.

**근거**: 클러스터 CNI가 도메인 기반 egress 화이트리스트 직접 지원 X. HuggingFace 같은 CDN은 IP 동적 → CIDR 화이트리스트 비현실적. 자체 학습 컨테이너도 NetworkPolicy 없이 정상 동작하는 모델과 일관.

**v1 mitigation**:

| 통제 | 방법 |
|---|---|
| 이미지 출처 통제 | `registry.jonathan.acryl.ai/external/...` 만 허용. Docker Hub 등 외부 registry pull 차단 |
| Manifest 검토 게이트 | 운영자가 협력기관 manifest의 `egress_whitelist` 도메인 검토 후 승인 |
| 신고 의무 | 협력기관은 자기 컨테이너의 외부 도메인을 manifest에 모두 명시 |

**v2 마이그레이션**: 3차년도 또는 이후 Cilium/Calico FQDN policy 도입 시 enforce 활성화. manifest 필드 그대로 유지 → 외부 컨테이너 spec 변경 0.

### 7.4 Resource Limits

manifest의 `resources` 기반 K8s `requests` + `limits` 자동 설정.

---

## 8. 에러 메시지 표준

표준 스키마는 `apps/fb_utils/errors.yaml` 참조. 4-튜플 (problem / cause / fix / docs_url) 형식.

### 외부 컨테이너 에러 출력

협력기관 컨테이너가 stdout에 발행:

```json
{"event":"error","code":"E_OOM_DURING_QUANTIZATION","message":"GPU memory exhausted","fatal":true,"timestamp":"..."}
```

플랫폼이 `errors.yaml`에서 코드 매칭 → 사용자에게 4-튜플 메시지 표시.

### 네이밍 컨벤션

`E_` prefix + `SCREAMING_SNAKE_CASE`. 예: `E_OOM_DURING_QUANTIZATION`, `E_DATASET_NOT_FOUND`, `E_MODEL_INCOMPATIBLE`.

---

## 9. 버전 / 호환성 정책

### 9.1 spec 버전

- `tango.acryl.ai/v1` (본 문서)
- `manifest.apiVersion`으로 식별

### 9.2 호환성 약속

- **v1 호환 lifecycle**: 2026-05 ~ 2027-12 (2차년도 + 3차년도 시작)
- 이 기간 동안 v1 컨테이너는 플랫폼 업그레이드되어도 호환 보장
- breaking change는 v2로 별도 발표

### 9.3 Deprecation

- v2 발표 시 **6개월 이전 deprecation 알림** + migration 가이드 제공
- 알림 채널: GitHub release notes + 운영자 메일링리스트

### 9.4 v1 호환 layer

플랫폼이 manifest.apiVersion 식별 후 호환 layer 제공 가능 (v1 manifest를 v2 내부 형식으로 자동 변환).

---

## 10. 인증 (Future — v1 비대상)

PDF 4종 카테고리 (전처리/평가/학습/변환) 모두 **closed-loop pattern** — Platform API 호출 없음. 따라서 v1에는 외부 컨테이너용 platform API 인증 메커니즘 부재.

상세 의사결정 + v2 도입 계획은 `docs/adr/0002-external-container-auth.md` 참조.

---

## 11. OpenAPI 템플릿

협력기관이 자기 컨테이너 OpenAPI spec 작성 시 출발점: `examples/openapi-template.yaml`.

FastAPI + Pydantic 기반 권장 (1차년도 플랫폼 패턴과 일관, OpenAPI 자동 생성).

---

## 12. 외부 협력기관 5단계 통합 가이드

```
1. 인터페이스 spec 확인     → docs/external-container-spec.md (본 문서)
2. 이미지 빌드             → examples/hello-plugin/Dockerfile + run.sh 샘플 (SP-12, 별도 작성 예정)
3. registry push           → registry.jonathan.acryl.ai/external/{name}:{version}
4. 플랫폼 plugin 등록      → manifest.yaml 작성 + 플랫폼 운영자에게 제출
5. 헬스체크 + 샘플 호출    → curl /health → curl /run < sample.json
```

**Time-to-First-Integration 목표**: 5분 (`hello-plugin/` 기준).

---

## 13. 문의 / 협력기관 onboarding

### 13.1 contact

- **플랫폼 측 contact**: `external-containers@acryl.ai` (가칭 — 5월 첫 주 발표 시 확정)
- **GitHub issue**: `acryl-ai/tango2-platform` 저장소의 `external-container` 라벨 (가칭)

### 13.2 v1 발표 일정

| 일정 | 항목 |
|---|---|
| 2026-05-01주 | 본 spec v1.0 + `examples/hello-plugin/` 동시 공개 (협력기관 onboarding 자산) |
| 2026-05-말 | v1.1 보강 (협력기관 첫 통합 피드백 반영) |
| 2026-07 | SP-3 LLaVA 첫 적용 (실제 spec 검증) |
| 2026-08 | 고려대 평가 도커 통합 (외부 두 번째 컨테이너) |

### 13.3 manifest 제출 흐름

```
1. 협력기관: manifest.yaml 작성 (본 spec Section 6 참조)
2. 협력기관: external-containers@acryl.ai 메일 또는 GitHub issue로 제출
   → 첨부: manifest.yaml + 컨테이너 이미지 README + (선택) K8s Secret 자료(별도 암호화 채널)
3. 운영자: 영업일 5일 내 검토
   → 승인: 플랫폼 DB 등록 + 협력기관에 사용 가능 통보
   → 거부: 사유 + 재제출 가이드 회신 (예: egress_whitelist 누락 도메인 추가 등)
4. 협력기관: 승인 받은 후 사용자가 워크스페이스에서 호출 가능
```

### 13.4 검토 SLA

| 단계 | SLA |
|---|---|
| 첫 회신 | 영업일 2일 내 |
| 검토 완료 | 영업일 5일 내 |
| 거부 시 재제출 | 영업일 3일 내 |
| 긴급 (단계평가 직전 등) | 운영자와 직접 협의 |

### 13.5 알려진 한계 frank하게 (협력기관 onboarding 시 고지)

- v1은 closed-loop pattern만 지원 (Platform API 호출 X). webhook receiver 등은 v2에서 별도 협의
- v1은 NVIDIA GPU 가속기만 enforce. Hailo NPU / AMD ROCm은 v2
- v1은 NetworkPolicy egress advisory only. 운영자 manifest 검토 + 자체 registry 강제로 mitigation
- v1은 단일 컨테이너 pod 가정. multi-container (sidecar) 필요 시 별도 협의
