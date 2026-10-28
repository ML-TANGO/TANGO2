# evaluate-logickor

LogicKor 벤치마크 **채점 집계** 컨테이너. 해시 mock 이 아닌 실채점이다.

## 무엇을 하고, 무엇을 하지 않는가

LogicKor 파이프라인은 `clean → train → generate → evaluate → score` 5단계다.
이 컨테이너는 **마지막 score 단계만** 한다.

| 단계 | 담당 | 이유 |
|---|---|---|
| train / generate / evaluate(심판) | **이 컨테이너 밖** | GPU + `transformers 5.5.4` / `vllm` 핀 필요. 플랫폼 기본(`transformers>=4.52.4,<5.0.0`)과 충돌해 전용 이미지가 따로 있어야 한다 |
| score(집계) | 이 컨테이너 | 순수 파이썬 + CPU. 위 충돌과 무관 |

그래서 GPU·모델·학습데이터가 없어도 **평가 탭에 실점수를 띄우는 것까지** 이 컨테이너로 완결된다.

⚠️ 점수는 입력 jsonl 에 **이미 들어있는 심판 점수**다. 어떤 심판 모델이 매겼는지는 이
단계에서 알 수 없다(생성·심판 단계의 책임).

## 입력

플랫폼이 마운트한 데이터셋(`/dataset/<JF_DATASET_NAME>`) 하위의 `*.jsonl` 전부를 재귀
탐색한다. ETRI `evaluator.py` 산출물 형식이며 utf-8-sig(BOM):

```json
{"id": 1, "category": "추론(Reasoning)",
 "questions": ["<질문1>", "<후속질문>"], "outputs": ["<답변1>", "<답변2>"],
 "references": [null, null],
 "query_single": {"judge_message": "<평가문>", "judge_score": 9},
 "query_multi":  {"judge_message": "<평가문>", "judge_score": 8}}
```

- `judge_score` = 1~10. 구형 산출물의 평면 키(`judge_single_score`/`judge_multi_score`)도 받는다.
- 채점 필드가 없는 행(= `generator` 원본 산출물)은 건너뛴다. 전부 미채점이면 잡이 실패한다.

### params (선택)

| 키 | 뜻 |
|---|---|
| `benchmarks` | `[{"benchmark":"logickor","metric":"judge_overall"}]` — 대표 스칼라 축 |
| `evaluated_subdir` | 데이터셋 안에서 더 좁힐 하위 경로. `..`·절대경로는 거부하고 realpath 로 탈출도 막는다 |
| `datasets` | 맥락용 데이터셋 이름 목록 |

`metric` 은 **어느 축을 대표값으로 쓸지**만 고른다(`judge_overall` / `judge_single` /
`judge_multi`). 무엇을 골라도 영역별·턴별 전체 점수는 함께 산출된다.

## 출력 — `/output/metrics.json`

```json
{
  "mode": "benchmark",
  "mock": false,
  "results": [{"benchmark": "logickor", "metric": "judge_overall", "score": 8.10}],
  "averages": {"logickor": 8.10},
  "benchmark_set": ["logickor"],
  "metric_map": {"logickor": "judge_overall"},
  "logickor": {
    "categories": [{"category": "추론(Reasoning)", "single": 7.86, "multi": 8.14, "count": 7}],
    "single_turn": 8.00, "multi_turn": 8.19, "overall": 8.10,
    "count": 42, "scale_max": 10.0
  }
}
```

`results[]` 는 기존 벤치마크 계약 그대로여서 이력·교차비교표가 손대지 않고 동작하고,
영역×턴 격자는 `logickor` 키 하위에만 있어 **다른 벤치마크 결과 표시에 영향이 없다**.

## 검증

집계 로직은 ETRI 가 커밋한 실측 점수표와 소수점까지 대조해 검증한다:

```bash
python3 -m pytest apps/evaluate_logickor/tests/test_scoring.py -q
```

기준값 = `Evaluation/Logickor/evaluated/Gemma4-e4b-it/sft/test_result.md` (전략 3종 ×
버전 5개 = 15 케이스). GPU·모델 없이 돈다.

⚠️ **버전 라벨 오프셋**: `test_result.md` 는 1부터, 디렉토리는 0부터 센다
(md `v1` = dir `v0`, dir `v5` 는 없음). 같은 이름끼리 비교하면 집계기가 틀린 것처럼 보인다.

## 플랫폼 배선

- `llm_evaluation` `constants.REAL_BENCHMARK_MANIFEST_KEY['logickor'] = 'LOGICKOR'`
  → `settings.LOGICKOR_MANIFEST_NAME` 으로 라우팅
- 한 런 = 컨테이너 하나이므로 **mock 벤치마크(arc·mmlu…)와 같은 런에 섞을 수 없다**.
  섞으면 `service.run_benchmark` 가 거부한다(조용히 반쪽 채점되는 것 방지)
