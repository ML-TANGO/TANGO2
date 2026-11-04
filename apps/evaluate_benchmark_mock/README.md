# evaluate-benchmark-mock

벤치마크 평가 **mock** 컨테이너 (llm_evaluation P1a).

## 목적
정식 벤치마크 평가 컨테이너(고려대 plugin / 실측)가 탑재되기 전, 평가 서비스
오케스트레이션 + FE 를 **end-to-end 로 테스트**하기 위한 mock. 모델을 실제로 돌리지
않고, **9개 벤치마크(ARC·KoBEST·MMLU…)** 를 **벤치마크별 지정 메트릭**(Accuracy/F1/…)으로
결정적(hash 기반) 채점해 점수를 반환한다. (FE 는 "벤치마크 선택 → 벤치마크별 메트릭" 2단계.)

⚠️ **MOCK — 실제 평가 아님.** 정식 메트릭은 `apps/evaluate`(실측 기본 BLEU/ROUGE/PPL) /
고려대 plugin(정밀)로 라우팅하며, manifest 교체로 대체한다.

## 계약
SP-1 외부 컨테이너 계약(`apps/evaluate` 동형). `job_type=evaluate`, `execution_mode=async`,
port 8000. 표준 endpoint: `/health` `/live` `/info` `/run` `/jobs/{id}` `/jobs/{id}/cancel`.

벤치마크(9)·메트릭(8)·권장 매핑 id 는 llm_evaluation `constants.py`(BENCHMARK_IDS·METRIC_IDS·
BENCHMARK_RECOMMENDED_METRIC) + FE `benchmarks.js`/`benchmarkMetrics.js` 와 **id 일치**.
- 벤치마크(9): `arc kobest mmlu hellaswag winogrande gsm8k truthfulqa boolq humaneval`
- 메트릭(8): `accuracy f1 acc_norm bleu rouge meteor cider spice`

### 입력 (params, `/run` body 또는 `/input/params.json`)
- `benchmarks`: `[{ "benchmark": "<id>", "metric": "<id>" }, ...]` 벤치마크→메트릭 매핑
  (생략/빈값 시 전체 9벤치마크를 권장 메트릭으로 채점). unknown id·벤치마크 중복은 무시.
- `datasets`: 데이터셋 이름 리스트 (선택 — 맥락용, 점수엔 미반영). 생략 시 `JF_DATASET_NAME`/`["default"]`.

### 출력 (`/output/metrics.json`)
```json
{
  "mode": "benchmark", "mock": true,
  "results":  [ { "benchmark": "arc", "metric": "accuracy", "score": 0.0 }, ... ],
  "averages": { "<benchmark>": 0.0, ... },
  "benchmark_set": [ "<benchmark>", ... ],
  "metric_map":    { "<benchmark>": "<metric>", ... },
  "datasets": [...],
  "_meta": { "name": "...", "version": "...", "item_id": "..." }
}
```
`averages` 를 **벤치마크키**로 두어 llm_evaluation 이력 비교표(`_flatten_eval_metrics`)가 벤치마크별
비교로 그대로 동작한다.

## 로컬 실행/테스트
```bash
pip install -r requirements.txt
python3 app.py                                  # :8000
curl -s localhost:8000/info | jq               # benchmarks/metrics 분리 노출
curl -s -XPOST localhost:8000/run -H 'content-type: application/json' \
  -d '{"params":{"benchmarks":[{"benchmark":"arc","metric":"accuracy"},{"benchmark":"kobest","metric":"f1"}]}}'
# → {status: running, job_id}
curl -s localhost:8000/jobs/<job_id> | jq      # poll → completed + result.metrics
```

## 빌드/등록 (배포)
baked 이미지(`COPY app.py /srv`)라 코드 변경은 **이미지 재빌드 필요**(src-mount 아님).
버전 bump 시 이미지 태그 + `manifest.yaml` version + `settings.BENCHMARK_MANIFEST_VERSION` 동기.
```bash
# 이미지 빌드 후 노드 containerd k8s.io ns 로 적재(단일노드 + imagePullPolicy=IfNotPresent → push 불필요)
docker build -t docker.io/acrylaaai/evaluate-benchmark-mock:<ver> .
docker save docker.io/acrylaaai/evaluate-benchmark-mock:<ver> | ctr -n k8s.io images import -
# manifest 등록(레지스트리)
curl -XPOST <external-container-svc>/api/v1/manifests \
  -H 'content-type: application/json' -d "{\"manifest_yaml\": \"$(sed 's/\"/\\\"/g' manifest.yaml)\"}"
```
