# Few-Shot Prompt Optimizer

`fewshot-prompt-optimizer`는 few-shot 예시들을 입력받아 최적화된 **시스템 프롬프트**를 생성하는 Tango MSA 백엔드 서비스입니다 (DSPy MIPROv2 + textual-gradient harvest 루프). 최적화에 수 분이 걸리므로, `POST /run`으로 작업을 등록하고 `GET /status`로 결과를 조회하는 **비동기 방식**으로 동작합니다.

## 기본 사용 흐름

```
1) POST /run           → job_id를 즉시 받음
2) GET  /status?job_id → 5~10초 간격으로 폴링
3) status가 "completed"가 되면 result.system_prompt 사용
```

---

## 1. `POST /run` — 최적화 작업 등록

작업을 등록하고 `job_id`를 즉시 반환합니다(1초 이내).

**Request**

```json
{
  "workspace_id": "ws-123",
  "project_id": "proj-456",
  "params": {
    "llm_url": "http://my-vllm-svc:8000/v1",
    "examples": [
      {"query": "사과는 무슨 색인가요?", "response": "사과는 빨간색입니다."},
      {"query": "바나나는 무슨 색인가요?", "response": "바나나는 노란색입니다."}
    ]
  }
}
```

**`params` 필드**

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `llm_url` | string | ✅ | OpenAI 호환 LLM 엔드포인트 (예: vLLM의 `http://host:8000/v1`) |
| `examples` | array | ✅ | few-shot 예시 목록. **최소 2개**. 각 항목은 `{"query": str, "response": str}` |
| `model` | string | | 모델 ID. 생략 시 `{llm_url}/models`에서 자동 감지 |
| `metric` | string | | 평가 지표: `"token_f1"`(기본) 또는 `"bert_score"` |
| `rounds` | int | | 최적화 라운드 수 (기본 1). `0`이면 빠른 모드(instruction·demo 선별만, 합성 예시 증강 생략, 소요 시간 절반) |
| `sync` | bool | | `true`면 동기 실행하여 결과를 즉시 반환 (기본 `false`). 수 분 걸리므로 디버깅용으로만 권장 |

**Response — 200 OK (등록 성공)**

```json
{
  "status": "success",
  "result": {
    "job_id": "job-a1b2c3d4e5f6",
    "job_status": "pending"
  }
}
```

**Response — 400 Bad Request (파라미터 오류)**

필수 값 누락 등은 작업을 등록하지 않고 즉시 반환합니다.

```json
{
  "status": "error",
  "code": "INVALID_PARAMS",
  "message": "llm_url is required (OpenAI-compatible base, e.g. http://host:8000/v1)."
}
```

---

## 2. `GET /status` — 작업 상태 / 결과 조회

```
GET /status?job_id=job-a1b2c3d4e5f6
```

**권장 폴링 주기: 5~10초.** 작업당 총 소요 시간은 모델·예시 수에 따라 약 2~10분입니다.

**Response — 진행 중**

```json
{
  "job_id": "job-a1b2c3d4e5f6",
  "status": "running",
  "progress": 15,
  "created_at": "2026-07-27T02:00:00+00:00",
  "started_at": "2026-07-27T02:00:01+00:00"
}
```

**Response — 완료 (`result.system_prompt`가 최종 산출물)**

```json
{
  "job_id": "job-a1b2c3d4e5f6",
  "status": "completed",
  "progress": 100,
  "created_at": "2026-07-27T02:00:00+00:00",
  "started_at": "2026-07-27T02:00:01+00:00",
  "finished_at": "2026-07-27T02:04:05+00:00",
  "result": {
    "system_prompt": "최적화된 시스템 프롬프트 텍스트 (instruction + 선별된 예시들)",
    "instruction": "...",
    "demos": [{"inputs": {"query": "..."}, "outputs": {"response": "..."}}],
    "n_examples": 5,
    "n_demos": 4,
    "base_score": 0.62,
    "final_score": 0.87,
    "model": "Qwen/Qwen3-4B-Instruct-2507",
    "metric": "token_f1"
  }
}
```

**Response — 실패**

```json
{
  "job_id": "job-a1b2c3d4e5f6",
  "status": "failed",
  "progress": 15,
  "finished_at": "2026-07-27T02:00:31+00:00",
  "code": "INTERNAL_ERROR",
  "message": "APIConnectionError: ..."
}
```

**Response — 404 Not Found (job_id 없음/만료)**

```json
{
  "status": "error",
  "code": "NOT_FOUND",
  "message": "unknown job_id: job-xxxx (never existed, or expired)"
}
```

**필드 설명**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `status` | string | `"pending"` \| `"running"` \| `"completed"` \| `"failed"` |
| `progress` | int | 진행률 0~100 (단계 기반 근사값: 10 모델 확인, 15 최적화 중, 95 최적화 완료) |
| `created_at` / `started_at` / `finished_at` | string (ISO 8601) | 등록 / 시작 / 종료 시각. 해당 없는 필드는 생략 |
| `result` | object | `completed`일 때만 포함. 핵심 값은 `result.system_prompt` |
| `code` / `message` | string | `failed` 또는 에러 응답일 때. 표준 에러 코드 사용 |

---

## 3. 그 외 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
| --- | --- | --- |
| `/health` | GET | 헬스 체크. `{"status": "healthy", "timestamp": ...}` |
| `/info` | GET | 서비스 메타정보. `capabilities`에 `"async_run"` 포함 |

## 4. 운영 참고 사항

- **결과 보관**: 완료/실패한 작업은 **1시간** 보관 후 삭제됩니다 (env `JOB_TTL_SECONDS`로 조정). 보관 기간이 지나거나 서버가 재시작되면 `/status`는 404를 반환하므로, 완료 확인 즉시 결과를 가져가 주세요.
- **동시 실행**: 작업은 한 번에 1개씩 직렬 처리됩니다 (LLM 엔드포인트 공유). 앞선 작업이 실행 중이면 새 작업은 `pending` 상태로 대기합니다.
- **호출 예시**:

```bash
# 1) 등록
JOB=$(curl -s -X POST http://<서비스>:30000/run -H "Content-Type: application/json" \
  -d @request.json | jq -r .result.job_id)

# 2) 폴링
curl -s "http://<서비스>:30000/status?job_id=$JOB" | jq .
```

---

## 5. 실행 방법

**로컬**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py          # :30000 (PORT env로 변경 가능)
```

**Docker**

```bash
docker build -t fewshot-prompt-optimizer:latest .
docker run -d -p 30000:30000 fewshot-prompt-optimizer:latest
```

컨테이너 안에서 호스트의 LLM을 쓰려면 `llm_url`에 `localhost` 대신 호스트 IP(기본 브리지 네트워크면 `http://172.17.0.1:8000/v1`)를 사용하세요.
