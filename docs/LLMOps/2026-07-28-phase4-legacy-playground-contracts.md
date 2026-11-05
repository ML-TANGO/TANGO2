# Phase 4 legacy playground compatibility contracts

`apps/llm_playground`에는 기존 `tests/`, `conftest.py`, `pytest.ini` 또는 playground 테스트
모듈이 없다. 다른 마이크로서비스의 격리된 harness를 복제해 새 의존·부트스트랩을 만들지 않고,
Phase 4에서 보존해야 할 현재 계약을 아래처럼 기록한다.

## 보존 계약

1. `POST /playgrounds/dual-session`
   - 인증 사용자와 요청의 workspace/model/commit/resource 값을 기존
     `create_dual_session` one-shot co-provision에 그대로 전달한다.
   - 성공 envelope의 `result`는
     `{session_playground_id, prompt_gen_playground_id}`이고, 실패는 기존처럼 HTTP
     route를 제거하지 않은 채 `status=0`, `message`, `result=null` envelope로 반환한다.

2. `POST /playgrounds/dual-batch`
   - 동기 호환 경로이며 `batch_stream`을 끝까지 소비한다.
   - `result` shape는
     `{samples, summary, sample_count, has_reference, metric_set}`을 유지한다.
   - 저장된 dual 링크가 있으면 그 LLM1을 사용한다. 요청 LLM1이 저장 링크와 다르면 명시적
     오류로 거부한다. 링크가 없으면 요청 LLM1을 계속 허용하고, 요청 LLM1도 없으면 기존
     단일 배치 모드로 동작한다.

3. `GET /playgrounds/dual-batch/sse`
   - `GET /playgrounds/batch/sse`와 같은 handler의 호환 alias다.
   - query 계약은 `playground_id`, `test_dataset_id`, `test_dataset_filename`,
     `sample_count`, `metrics`, `output_type`이며 session은 URL이 아니라 `jf-session`
     header에서 읽는다.
   - SSE event shape는 `start`, 반복 `sample`, 마지막 `summary`이고 장시간 추론 중 빈
     keepalive event를 보낼 수 있다. 저장 링크가 있으면 자동으로 LLM1→LLM2를 수행한다.

4. `GET /playgrounds/status-sync/{playground_id}?skip_dual=true`
   - dual parent 자신의 LLM2 상태만 기존 `{status, init_deployment}` result로 반환한다.
   - aggregate `components`는 포함하지 않는다. `skip_dual`이 없거나 false인 새 기본 계약은
     aggregate status와 components를 함께 반환한다.

5. `PromptCom` manual unlinked chaining
   - 단일 playground에서 사용자가 수동 dual toggle을 켜고 같은 workspace의 다른
     playground를 LLM1으로 선택하면 `POST /playgrounds/test`에
     `prompt_gen_playground_id`를 보낸다.
   - 대상 playground에 저장 dual 링크가 **없을 때만** 요청 LLM1을 그대로 허용한다.
     저장 링크가 있으면 요청 생략 또는 동일 ID는 저장 LLM1으로 실행하고, 다른 ID는 한국어
     충돌 오류로 거부한다.
   - 성공 응답은 기존 `result[0].output`을 유지하며 dual 실행이면
     `result[0].optimized_prompt`도 유지한다.

## 제거 전 관측

각 legacy 호출은 `event=deprecated_api_call path=... caller=...` 형식의 warning 한 줄을
남긴다. `/playgrounds/test`는 실제로 unlinked manual LLM1이 요청된 호출만 기록한다.
이 telemetry는 응답 코드, envelope, SSE event 또는 실행 순서를 바꾸지 않는다.
