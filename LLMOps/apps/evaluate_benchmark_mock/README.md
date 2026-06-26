# evaluate-benchmark-mock

벤치마크 평가 **mock** 컨테이너 (llm_evaluation P1a).

## 목적
정식 벤치마크 평가 컨테이너(고려대 plugin / 실측)가 탑재되기 전, 평가 서비스
오케스트레이션 + FE 를 **end-to-end 로 테스트**하기 위한 mock. 모델을 실제로 돌리지
않고, ETRI 벤치마크 화면이 요구하는 **17개 메트릭**에 대해 결정적(hash 기반) 점수를 반환한다.

⚠️ **MOCK — 실제 평가 아님.** 정식 메트릭은 `apps/evaluate`(실측 기본 BLEU/ROUGE/PPL) /
고려대 plugin(정밀)로 라우팅하며, manifest 교체로 대체한다.

## 계약
SP-1 외부 컨테이너 계약(`apps/evaluate` 동형). `job_type=evaluate`, `execution_mode=async`,
port 8000. 표준 endpoint: `/health` `/live` `/info` `/run` `/jobs/{id}` `/jobs/{id}/cancel`.

### 입력 (params, `/run` body 또는 `/input/params.json`)
- `metric_set`: 17 메트릭 중 부분집합 (생략 시 전체 17).
  `accuracy f1 acc_norm arc kobest mmlu hellaswag winogrande gsm8k truthfulqa boolq humaneval meteor cider spice bleu rouge`
- `datasets`: 데이터셋 이름 리스트 (생략 시 `JF_DATASET_NAME` 또는 `["default"]`).

### 출력 (`/output/metrics.json`)
```json
{
  "mode": "benchmark", "mock": true,
  "scores":   { "<dataset>": { "<metric>": 0.0, ... }, ... },
  "averages": { "<metric>": 0.0, ... },
  "datasets": [...], "metric_set": [...],
  "_meta": { "name": "...", "version": "...", "item_id": "..." }
}
```

## 로컬 실행/테스트
```bash
pip install -r requirements.txt
python3 app.py                                  # :8000
curl -s localhost:8000/info | jq
curl -s -XPOST localhost:8000/run -H 'content-type: application/json' \
  -d '{"params":{"datasets":["mmlu_ko","logickor"],"metric_set":["mmlu","bleu","rouge"]}}'
# → {status: running, job_id}
curl -s localhost:8000/jobs/<job_id> | jq      # poll → completed + result.metrics
```
