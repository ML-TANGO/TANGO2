# Few-Shot 프롬프트 최적화 모듈

## 1. 개요

few-shot 예시를 입력으로 받아, LLM을 사용자 도메인에 최적화시킬 수 있는 **시스템 프롬프트**(지시문 + 고른 예시)를 만들어 주는 Tango MSA 백엔드 서비스입니다. 

최적화는 아래 단계로 진행됩니다.

```
baseline  →  압축  →  [ 증강 → 재압축 ] × rounds
```

| 단계 | 단계별 설명 |
| --- | --- |
| baseline | 기본 지시문 + 주어진 예시 |
| 압축 | 주어진 예시의 하위 집합 중 점수가 높은 집합이 있는지 탐색합니다. |
| 증강 | 생성 모델이 합성 예시를 만들고, 점수를 올리는 예시들을 탐색합니다. |
| 재압축 | 늘어난 예시 집합에서 다시 압축합니다. |

## 2. 디렉토리 구성

```
fewshot_prompting/
├── main.py                    # FastAPI 앱: /health, /info, /run, /status
├── src/
│   ├── schemas.py             # 요청·응답 모델 (RunRequest / RunParams / RunResult)
│   ├── jobs.py                # 비동기 작업 저장소 (직렬 실행, 결과 보관 기간)
│   ├── service.py             # 요청 검증, 지표 결정, 최적화 실행, 시스템 프롬프트 렌더링
│   ├── fewshot_task.py        # 태스크 정의(프롬프트 형식, 이미지 입력)와 지표(SPICE / token F1 / BERTScore)
│   ├── spice.py               # SPICE 채점기: 상주 Java 서버와 통신
│   └── optimizer/
│       ├── pipeline.py        # 기준선 → 압축 → (증강 → 재압축) × rounds, history 기록
│       ├── task.py            # 예시 자료형, 예시 분할
│       ├── scoring.py         # 프롬프트 채점 (검증 예시 또는 leave-one-out)
│       ├── judge.py           # 변경을 받을지 판단
│       ├── likelihood.py      # 정답 문장 확률 계산 (실험용 판단 방식에서만 사용)
│       ├── mipro_step.py      # MIPROv2로 지시문·예시 고르기
│       ├── style.py           # 예시에서 문체 규칙(길이, 반올림) 측정
│       ├── generator.py       # 합성 예시 생성
│       ├── harvest.py         # 증강 루프 (생성 → 피드백 → 판단)
│       └── feedback.py        # 합성 예시 비평·수정
├── spice/                     # SPICE 서버 소스(SpiceServer.java)와 준비 스크립트(setup.sh)
├── tests/                     # 단위 테스트 (LLM 없이 실행)
├── Dockerfile
├── requirements.txt           # 서비스 의존성
├── requirements-bertscore.txt # 선택: BERTScore
└── requirements-dev.txt       # 테스트용
```

**모듈 구성.** 프롬프트 엔지니어링 블록의 다섯 모듈과 코드의 대응은 다음과 같습니다.

| 모듈 | 코드 |
| --- | --- |
| API 서비스 모듈 | `main.py`, `src/schemas.py`, `src/jobs.py`, `src/service.py` |
| 예시·태스크 관리 모듈 | `src/fewshot_task.py`, `src/optimizer/task.py`, `src/optimizer/scoring.py`, `src/optimizer/judge.py`, `src/spice.py` |
| 데이터 증강 모듈 | `src/optimizer/generator.py`, `src/optimizer/harvest.py`, `src/optimizer/feedback.py` |
| 데이터 압축 모듈 | `src/optimizer/mipro_step.py`, `src/optimizer/style.py` |
| 시스템 프롬프트 생성 모듈 | `service.render_system_prompt` (단계 조율은 `src/optimizer/pipeline.py`) |


## 3. 설치 방법

```bash
# 기본 이미지 (지표: SPICE, token F1)
docker build -t fewshot-prompt-optimizer:latest .

# BERTScore까지 포함 (CPU용 PyTorch)
docker build --build-arg WITH_BERTSCORE=true -t fewshot-prompt-optimizer:bertscore .
```

## 4. 실행 방법

### 4.1 서버 실행

아래 명령어를 통해 컨테이너를 실행합니다. 컨테이너가 시작되면 모델 파일(CoreNLP, BERTScore 모델)을 내려받습니다.
```bash
docker run -d -p 30000:30000 fewshot-prompt-optimizer:latest
```

컨테이너에서 호스트의 LLM을 쓸 때는 `llm_url`에 `localhost` 대신 호스트 IP(기본 브리지 네트워크면 `http://172.17.0.1:8000/v1`)를 씁니다. `vlm: true`로 이미지를 함께 쓰려면 `llm_url`이 비전 모델을 서빙해야 합니다.

주요 환경변수:

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `PORT` | `30000` | 서비스 포트 |
| `JOB_TTL_SECONDS` | `3600` | 끝난 작업을 `/status`로 조회할 수 있는 시간 |
| `MAX_FINISHED_JOBS` | `100` | 보관하는 끝난 작업 수 (넘으면 오래된 것부터 삭제) |
| `LLM_TIMEOUT_SECONDS` | `600` | LLM 호출 하나의 제한 시간 |
| `SPICE_XMX` / `SPICE_THREADS` | `3g` / `4` | SPICE JVM 힙과 파싱 스레드 수 (힙이 모자라면 문장이 조용히 빠져 점수가 흔들림) |
| `SPICE_PRELOAD` / `BERTSCORE_PRELOAD` | `true` | 서비스 시작 시 채점기를 미리 띄울지 |
| `BERTSCORE_MODEL` | `bert-base-multilingual-cased` | BERTScore 모델 |

### 4.2 빠른 시작

```bash
# 1) 작업 등록 → job_id를 바로 받음
curl -s -X POST http://localhost:30000/run -H "Content-Type: application/json" -d '{
  "workspace_id": "ws-1",
  "project_id": "proj-1",
  "params": {
    "llm_url": "http://my-vllm-svc:8000/v1",
    "examples": [
      {"query": "사과는 무슨 색인가요?", "response": "사과는 빨간색입니다."},
      {"query": "바나나는 무슨 색인가요?", "response": "바나나는 노란색입니다."},
      {"query": "레몬은 무슨 색인가요?", "response": "레몬은 노란색입니다."}
    ],
    "validation": [
      {"query": "포도는 무슨 색인가요?", "response": "포도는 보라색입니다."}
    ]
  }
}'
# → {"status": "success", "result": {"job_id": "job-a1b2c3d4e5f6", "job_status": "pending"}}

# 2) 5~10초 간격으로 조회 → status가 "completed"가 되면 result.system_prompt 사용
curl -s "http://localhost:30000/status?job_id=job-a1b2c3d4e5f6"
```

`validation`은 선택입니다. 검증 데이터가 따로 있으면 넣는 것을 권합니다. 예시가 적을 때는 leave-one-out 점수가 흔들려 좋은 변경과 나쁜 변경을 잘 가리지 못합니다.

### 4.3 API 명세

| 엔드포인트 | 메서드 | 설명 |
| --- | --- | --- |
| `/run` | POST | 최적화 작업 등록. `job_id`를 즉시 반환 (`params.sync=true`면 끝날 때까지 기다려 결과 반환) |
| `/status?job_id=...` | GET | 작업 상태와 결과 조회 |
| `/health` | GET | `{"status": "healthy", "timestamp": ...}` |
| `/info` | GET | 서비스 정보. `capabilities`에 `async_run`, 설치된 지표(`spice`, `bert_score`) 표시 |

**`POST /run` 요청.** Tango MSA 봉투(`workspace_id`, `project_id`, `params`)를 씁니다. `params` 없이 같은 필드를 최상위에 둬도 됩니다.

| `params` 필드 | 타입 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `llm_url` | string | (필수) | OpenAI 호환 엔드포인트, 예: `http://host:8000/v1` |
| `examples` | array | (필수) | 예시 목록 `{"query", "response", "image"?}`. 최적화하려면 2개 이상 |
| `validation` | array | `[]` | 검증 예시(형식은 `examples`와 같음). 주면 모든 판단을 이 예시로 채점하고 프롬프트에는 넣지 않음 |
| `model` | string | 자동 | 모델 ID. 생략하면 `{llm_url}/models`에서 확인 |
| `api_key` | string | `"EMPTY"` | LLM 엔드포인트 키 |
| `metric` | string | 자동 | `"spice"`, `"token_f1"`, `"bert_score"`. 생략하면 SPICE, 예시 답이 한국어이면 token F1 |
| `vlm` | bool | `false` | 예시의 `image`(data URI 또는 http(s) URL)를 모델에 함께 보여 줌 |
| `optimize` | bool | `true` | `false`면 최적화 없이 기본 지시문 + 예시 전부로 만든 프롬프트를 바로 반환 (LLM 호출 없음, 점수 없음) |
| `rounds` | int | `1` | 증강·재압축 반복 횟수. `0`이면 압축만 |
| `feedback` | bool | `true` | 합성 예시를 판단 전에 비평·수정할지 |
| `n_iterations` | int | `6` | 라운드당 증강 반복 수 |
| `n_per_iteration` | int | `3` | 한 번에 만드는 합성 예시 수 |
| `seeds_per_iteration` | int | `4` | 생성할 때 보여 주는 실제 예시 수 |
| `mipro_auto` | string | `"light"` | MIPROv2 탐색 강도 |
| `mipro_num_threads` | int | 자동 | MIPROv2 동시 평가 수 |
| `seed` | int | `0` | 난수 시드 |
| `sync` | bool | `false` | `true`면 동기 실행 (오래 걸리므로 디버깅용) |
| `holdout_fraction` | float | `0` | 예시 중 검증용으로 사용할 예시 비율(0 이상 1 미만). 검증용 예시는 채점에만 쓰고 프롬프트에는 넣지 않음. `0`이면 떼지 않고 예시 하나씩을 빼 가며 채점(leave-one-out). |

**`POST /run` 응답.**

```json
{"status": "success", "result": {"job_id": "job-a1b2c3d4e5f6", "job_status": "pending"}}
```

**`GET /status` 응답.**

```json
{
  "job_id": "job-a1b2c3d4e5f6",
  "status": "completed",
  "progress": 100,
  "created_at": "2026-10-25T02:00:00+00:00",
  "started_at": "2026-10-25T02:00:01+00:00",
  "finished_at": "2026-10-25T02:40:05+00:00",
  "result": {
    "system_prompt": "지시문\n\nHere are some examples:\n\nQuery: ...\nResponse: ...",
    "instruction": "...",
    "demos": [{"inputs": {"query": "..."}, "outputs": {"response": "..."}}],
    "n_examples": 12, "n_seeds": 12, "n_holdout": 50, "n_demos": 15,
    "generated": 36, "accepted": 3,
    "base_score": 0.4596, "final_score": 0.4790,
    "model": "google/gemma-4-E4B-it",
    "metric": "spice",
    "history": [{"step": "baseline", "holdout": 0.4596, "n_demos": 12, "n_synthetic": 0, "instruction": "...", "system_prompt": "..."}],
    "warnings": []
  }
}
```

| 필드 | 설명 |
| --- | --- |
| `status` | `pending` · `running` · `completed` · `failed` |
| `progress` | 단계 기반 근사값 (10 모델 확인, 15 최적화 시작, 95 최적화 완료, 100 끝) |
| `result.system_prompt` | 최종 산출물. 이 문자열을 시스템 메시지로 씀 |
| `result.n_holdout` | 채점에 쓴 예시 수 (`validation`이 있으면 그 개수) |
| `result.base_score` / `final_score` | 기준선과 최종 프롬프트의 점수. `optimize=false`면 `null` |
| `result.metric` | 실제로 쓴 지표 (요청한 지표를 쓸 수 없으면 대체한 지표) |
| `result.history` | 단계별 기록. `step`(`baseline`, `compress`, `round1`, …), `holdout`(그 단계 점수), `n_demos`, `n_synthetic`, `instruction`, `system_prompt`. 압축 단계에는 `chosen`(고른 후보), 라운드에는 `generated`·`accepted`(합성 예시 수)가 더 붙음 |
| `result.warnings` | 지표 대체 등 알림 |
| `code` / `message` | 실패 시 오류 코드(`INVALID_PARAMS`, `INTERNAL_ERROR`)와 내용 |

**오류 응답.** 요청 오류는 등록하지 않고 400으로, 없는(또는 만료된) `job_id`는 404로 돌려줍니다.

```json
{"status": "error", "code": "INVALID_PARAMS", "message": "llm_url is required (OpenAI-compatible base, e.g. http://host:8000/v1)."}
{"status": "error", "code": "NOT_FOUND", "message": "unknown job_id: job-xxxx (never existed, or expired)"}
```

### 4.4 운영 참고

- **작업 처리.** 작업은 한 번에 하나씩 처리하고, 실행 중에 들어온 작업은 `pending`으로 기다립니다. 끝난 작업은 `JOB_TTL_SECONDS`(기본 1시간) 동안 보관합니다. 서버가 재시작되면 보관된 결과도 사라집니다.
- **소요 시간.** 후보 프롬프트 하나를 평가할 때마다 채점 예시 수만큼 LLM 답변을 생성하고, 한 라운드에 후보를 20~30개 평가합니다. 그래서 시간은 채점 예시 수(검증 예시 수, 없으면 주어진 예시 수)와 `rounds`에 거의 비례합니다. 4B 모델, 검증 예시 50개, `rounds=1`이면 수십 분이 걸릴 수 있습니다.
- **LLM 서버 부하.** 채점할 때 동시에 여러 요청을 보냅니다. 여러 작업이 한 LLM 서버를 같이 쓰면 응답이 느려지거나 멈출 수 있습니다. 호출 하나가 `LLM_TIMEOUT_SECONDS` 안에 끝나지 않으면 재시도하고, 끝내 실패한 답은 빈 답으로 채점합니다.
- **SPICE를 통한 평가.** 한국어 예시 사용시 `metric: "spice"`를 지정하지 않으면 token-f1으로 측정됩니다(`warnings`에 표시).
- **이전 버전에서 바뀐 동작.** 엔드포인트와 기존 요청 필드는 그대로입니다.
  - `metric`을 생략하면 예전에는 token F1이었고, 지금은 SPICE(한국어 예시면 token F1)입니다.
  - 선택 필드 `optimize`, `feedback`, `validation`과 응답의 `warnings`가 추가됐습니다.
