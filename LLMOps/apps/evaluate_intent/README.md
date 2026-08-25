# evaluate-intent

MixATIS 다중의도·슬롯 **실채점** 컨테이너. ETRI `Evaluation/Intent_web` 의 평가 단계를
플랫폼 외부컨테이너로 옮긴 것이다.

## 무엇을 하고, 무엇을 하지 않는가

원본 파이프라인은 `학습([1/2]) → 평가([2/2])` 두 단계이고, 웹 콘솔이 `docker run` 으로
컨테이너를 띄운 뒤 stdout 을 정규식으로 되읽어 지표 카드를 채웠다.

| 원본 | 이식 | 이유 |
|---|---|---|
| 학습([1/2]) | **넣음(0.2.0~, 기본 on)** | UGEN 은 정답을 고정 형식(`"값 is one 슬롯명"`)으로 생성해야 채점되는 벤치마크다. 형식을 배우지 않은 모델은 내용을 알아도 0 점이 나온다 — Qwen3-8B 실측으로 zero-shot 은 형식 준수 0/828 · joint_acc 0.0, 같은 가중치에 1500 발화 1 에폭을 태우면 joint_acc 0.4855. ETRI README 의 95.89%/98.10% 도 학습 후 수치다 |
| 평가([2/2]) | **이 컨테이너** | |

⚠️ 그래서 점수의 의미는 "체크포인트 단독"이 아니라 **"체크포인트 + 이 레시피"** 다.
어떤 레시피였는지는 `metrics.json` 의 `train` 절에 새긴다. `train: false` 로 부르면
0.1.0 과 같은 zero-shot 경로이며, 형식 미학습을 진단할 때 쓴다.
체크포인트는 **필수**다(`checkpoint_name` 없으면 기동 직후 거부) — BE 도
`CHECKPOINT_REQUIRED_MANIFEST_KEYS` 로 파드를 띄우기 전에 막는다.
| 웹 콘솔 + `docker run` | **뺌** | 클러스터는 containerd 라 도커 소켓이 없다. 이미지를 K8s Job 으로 직접 돌린다 |
| stdout 정규식 파싱 | **뺌** | `/output/metrics.json` 으로 대체 |

## 지표 정의는 재구현하지 않았다

`ugen_data.py` 와 `evaluate_qwen3_mixatis.py` 는 **ETRI 원본을 그대로 복사**해 쓴다
(build.sh 가 `Evaluation/Intent_web` 에서 스테이징). 두 모듈 모두 최상위 부작용이 없어
import 가 안전하다. `scoring.py` 는 그 지표 함수를 import 만 하고, 하는 일은 결과를
플랫폼 벤치마크 계약으로 옮기는 것뿐이다 — 정의를 다시 적으면 원본이 바뀔 때 조용히 갈라진다.

## 지표 4종

네 값은 **항상 함께** 산출되고, `metric` 은 `results[].score` 에 실릴 대표 축만 고른다
(LogicKor 의 `judge_*` 3종과 같은 규약).

| id | 정의 | 단위 |
|---|---|---|
| `joint_acc` (기본) | 의도집합 **AND** 슬롯집합이 모두 완전일치한 발화 비율 | 발화 |
| `intent_acc` | 의도 집합이 정확히 일치한 발화 비율 | 발화 |
| `intent_f1` | 의도 항목 단위 micro F1(부분 정답 인정) | 의도 항목 |
| `slot_f1` | `(값, 슬롯명)` 쌍 단위 micro F1(둘 다 맞아야 정답) | 슬롯 쌍 |

`joint_acc` 가 유독 낮은 건 결함이 아니라 정의다 — 슬롯이 5개면 5개 전부 값·이름이
맞아야 하고 거기에 의도 집합까지 정확해야 1점이다. ETRI README 의 full 기준도
Intent F1 98.10 / Slot F1 90.77 인데 Joint 는 67.03 이다.

## LogicKor 채점기와의 차이

**심판 LLM 이 없다.** 정답(BIO 태그 + 의도 라벨)이 데이터에 있어 지표가 결정론적이고,
같은 체크포인트면 몇 번을 돌려도 같은 값이 나온다. LogicKor 는 심판이 바뀌면 절대 점수를
비교할 수 없지만 이쪽은 원본과 이식본의 숫자를 **직접 대조해 검증**할 수 있다.

추론 엔진도 vLLM 이 아니라 transformers `generate()`(greedy) 다 — 원본이 그것으로 쟀고
지표 정의가 거기 묶여 있다. 엔진을 바꾸면 패딩·샘플링 처리가 달라져 점수가 갈린다.

## 입력

- **모델**: `checkpoint_name` 으로 커밋 이름 한 조각을 받아 `/models/checkpoints/<name>` 으로
  해석한다. **경로를 받지 않는다** — params 로 마운트 밖을 열 수 있고 NFS 실경로가 로그·응답에
  샌다. BE 가 `commit_id` 를 이름으로 풀어 넘긴다.
- **문항**: MixATIS test 828 발화가 **이미지에 baked** 되어 있다. 벤치마크 정의 자체라
  런마다 같아야 점수가 비교된다. 데이터셋 업로드 대상이 아니다.

### params (선택)

| 키 | 기본 | 뜻 |
|---|---|---|
| `checkpoint_name` | — | 평가할 커밋 이름(필수에 준함) |
| `use_latest_checkpoint` | false | `checkpoint_name` 대신 `/model` 사용 |
| `benchmarks` | — | `[{benchmark: mixatis, metric: ...}]` — 대표 스칼라 축 |
| `limit` | 0(전체) | 앞 N 발화만(디버그). **분모가 달라지므로 full 값과 비교 금지** |
| `batch_size` | 16 | 생성 배치 (원본 `run_experiment.sh` 기본값) |
| `max_new_tokens` | 128 | 생성 상한 (원본 동일) |
| `use_4bit` | false | QLoRA 4bit 로드. 기본은 bf16 — 잡이 80GB 한 장을 받으므로 더 빠르다 |
| `split` | test | 평가 split |

## 출력

- `/output/metrics.json` — 벤치마크 계약(`results`/`averages`/`benchmark_set`/`metric_map`)
  + `mixatis` 하위에 네 지표 격자 + `evaluate`(발화수·빈 예측 수 등) + `checkpoint`
- `/output/mixatis_eval.csv` — 발화별 `gold/pred` 와 **모델 원문**(`intent_raw`/`slot_raw`)

CSV 에 원문을 남기는 이유: 슬롯 형식(`값 is one 슬롯명`)을 어기면 파싱이 조용히 빈 예측을
만들어 F1 만 떨어진다. 사후 진단 수단이 이 파일뿐이라 `empty_intent_predictions` /
`empty_slot_predictions` 개수도 metrics 에 함께 싣는다.

## 데이터 — seq.out 복원

저장소의 `Evaluation/Intent_Detection/data/MixATIS_clean` 에는 **`seq.out`(BIO 태그)이 없다**.
루트 `.gitignore` 4번째 줄 `*.out` 이 train·dev·test 전부를 삼켰다. `ugen_data.read_split()`
은 이 파일이 필수라 그대로는 못 돈다.

`rebuild_seq_out.py` 가 같은 디렉토리의 `<split>.txt`(CoNLL)에서 복원한다. 복원본의 토큰과
의도가 기존 `seq.in`·`label` 과 **전부 일치하는지 대조**하고 하나라도 어긋나면 실패한다 —
태그가 문장과 어긋난 채 평가에 들어가면 점수만 조용히 낮아진다.

실측: train 13162 / dev 759 / test 828 행 전부 일치(2026-08-25).

## 빌드

```bash
bash apps/evaluate_intent/build.sh
```

buildkit → OCI tar → `ctr -n k8s.io images import` + `io.cri-containerd.image=managed` 라벨.
라벨이 없으면 `IfNotPresent` 인데도 kubelet 이 pull 을 시도해 ErrImagePull 이 난다.

## 플랫폼 배선

| 표면 | 항목 |
|---|---|
| `constants.py` | `REAL_BENCHMARK_MANIFEST_KEY["mixatis"] = "MIXATIS"`, `METRIC_IDS` 4종, 권장·허용 메트릭 |
| `fb_utils/settings.py` | `MIXATIS_MANIFEST_NAME` / `_VERSION` |
| FE | `benchmarks.js` (mixatis 항목), `benchmarkMetrics.js` (4종) |

⚠️ `BENCHMARK_ALLOWED_METRICS` 와 FE `benchmarks.js` 의 `metrics` 는 **정확히 같은 집합**이어야
한다. FE 가 제시하는데 BE 에 없으면 사용자가 고른 메트릭이 아무 신호 없이 권장값으로 교정된다.
