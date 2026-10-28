# evaluate-selfmetric — 플랫폼 소유 자동평가 컨테이너 (SP-5 / v0.4 3.8)

학습 완료 모델을 **자체 메트릭**(BLEU / ROUGE-1/2/L / perplexity)으로 채점한다.
외부 SaaS judge(gpt-4.1 등)에 의존하지 않으며(PROGRESS 7/15 결정), 동시에 ⑪ 고려대
평가 plugin 슬롯의 **참조 구현** 역할을 한다(같은 `job_type=evaluate` 계약).

`apps/convert`(SP-4)와 동형 — 플랫폼이 소유·구현하고, 배포는 external_container
launch 메커니즘을 재사용한다(`fb_evaluate` 신규 서비스 회피). SP-1 외부 컨테이너 계약을
그대로 따르므로 플랫폼/FE/eval_result 영속화 와이어링은 변경 없이 동작한다.

## 입력 (params, /input/params.json)
| 키 | 기본값 | 설명 |
|---|---|---|
| `metric_set` | `["bleu","rouge","perplexity"]` | 계산할 메트릭(csv 또는 list) |
| `max_samples` | 50 | 평가 샘플 수 cap (1~1000) |
| `max_new_tokens` | 64 | 생성 길이 cap (BLEU/ROUGE 용, 1~512) |
| `prompt_field` / `reference_field` / `text_field` | 자동감지 | 데이터셋 컬럼 override |

- `/model` = 평가 대상 모델(예약키 `_base_model`). `/dataset/<name>` = 평가셋(예약키 `_dataset`).
- 데이터셋: jsonl/json/csv/tsv/txt 자동탐색. prompt+reference → BLEU/ROUGE, text(또는 reference) → perplexity.

## 출력
- `/output/metrics.json` — `{bleu, rouge1, rouge2, rougeL, perplexity, ...}` (플랫폼이 NFS 산출물로 lazy 영속화).
- `result.metrics` — 동일 dict.

## 빌드 / 배포 (cluster, buildkitd 없음)
```bash
cd apps/evaluate
docker build -t docker.io/acrylaaai/evaluate-selfmetric:1.0.0 .
docker save docker.io/acrylaaai/evaluate-selfmetric:1.0.0 | nerdctl --namespace=k8s.io load
# manifest 등록: POST /api/v1/manifests (또는 fb_external_container manifest_router)
```

## 주의
- 토크나이저는 공백분리+소문자(데모용 단순화). 정밀 평가는 고려대 plugin(⑪)으로 수용.
- 소형 모델은 CPU 로 충분(manifest gpu:0). 대형 모델은 manifest `resources.gpu: 1` 로 상향.
- `CONVERT_MANIFEST_NAME` 과 동형으로 `EVALUATE_MANIFEST_NAME` env 로 mock↔real 전환.
