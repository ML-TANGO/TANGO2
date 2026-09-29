# 벤치마크 실채점기(evaluate-lmeval) 설계 — mock 교체

작성 2026-09-28 · 선행 실측 세션 기준 · 브랜치 `Acryl-LLMOps-dev`

## 1. 요구사항 재정의

정답 대조(reference) 벤치마크 런이 해시 mock(`evaluate-benchmark-mock` 0.2.0) 대신
**lm-evaluation-harness 로 실제 채점**하게 한다. 범위는 lm-eval 이 계산하는 17종 +
HumanEval(모델 생성 코드 실행 → **격리 파드**) + 커스텀 파일 평가(런 데이터셋으로 생성 후
F1/EM/BLEU/ROUGE). 채점 엔진은 ETRI 가 origin/main 에 올린 `LLMOps/Evaluation/lmeval`
(커밋 `5a973795e`)의 러너를 우리 외부 컨테이너 계약에 맞춰 이식한다.

확정된 결정(사용자, 2026-09-28):

| # | 결정 |
|---|---|
| D1 | 생성·채점 = **로컬 가중치**. 고른 배포가 서빙 중인 커밋을 역해석해 컨테이너가 GPU 1장에 올린다 |
| D2 | HumanEval 포함 — **격리 실행**(전용 매니페스트·egress 차단·SA 토큰 없음·RW 마운트 최소) |
| D3 | 커스텀 파일 평가를 벤치마크로 포함 |
| D4 | 범위 = lm-eval 이 계산 가능한 것 전부 |

## 2. 활성 토폴로지 확인 결과 (실측)

| 항목 | 실측값 |
|---|---|
| 인스턴스 | 개발 `tango-dev`(:31080) / 서빙 `jonathan-system` — 둘 다 BENCHMARK = `evaluate-benchmark-mock` 0.2.0 (settings 기본값, env 오버라이드 없음) |
| 소스 반영(dev) | `jfb-llm-evaluation`·`jfb-app-external-container`·`jfb-app-scheduler` = `/app`·`/fb_utils` src 마운트, `jfb-app-front` = `/front-data` src 마운트 → **rollout 만으로 반영** |
| GPU | 단일 노드 A100 80GB PCIe × 8 |
| HF 캐시 PVC | dev = 모델 3개(gemma-4-E4B-it·Llama-3.1-8B-Instruct·clip), 서빙 = 의료 QA 데이터셋 6종 — **lm-eval 벤치마크 데이터셋 전무** |
| 커밋 형식 | `models/<name>/commit_models/` 아래 커밋 디렉토리 + `source_model/`(전체 가중치). 어댑터 커밋은 서빙 파드가 `source_model` 위에 `merge_and_unload` (`deployment_llm/src/llm/playground.py:98-120`) |
| 등록 매니페스트 | dev: mock 0.2.0 / intent 0.1.0~0.2.4 / logickor-judge ~0.2.5 / selfmetric 1.0.0. 서빙: mock 0.1.0·0.2.0 / intent 0.2.4 / logickor-judge 0.2.5 |
| ETRI 러너 | `lm_eval 0.4.12`(HF 백엔드) + transformers `git main` + Flask 대시보드. 레지스트리 21종 |

### 2.1 왜 배포 위임으로는 못 하나 (D1 근거)

- 벤치마크의 현행 유일 생성 경로 = 배포 위임(`run_benchmark` `service.py:88-152`,
  `generate_base_url`). 그런데 shim 은 `/models` + 비스트리밍 `/chat/completions` 만 있고
  메시지를 문자열 하나로 합쳐 서빙 파드 `POST /` 의 `test_question` 으로만 넘긴다
  (`llm_playground service.py:3799`). temperature·max_tokens·stop 무시, **logprobs 없음**.
- 서빙 파드는 내장 vLLM 을 배포 시점 `SamplingParams` 하나로 돈다(`playground.py:130`).
- 우리 9종 중 **7종이 `multiple_choice`**(ARC·KoBEST·MMLU·HellaSwag·WinoGrande·
  TruthfulQA-MC2·BoolQ) — 보기별 loglikelihood 가 필요해 위 경로로는 구조적으로 불가.
- 선례: MixATIS 포맷 학습이 이미 "배포에서 커밋 이름을 역해석 → 컨테이너 로컬 GPU" 경로를
  쓴다(`_resolve_format_checkpoint` `service.py:1893`). 배포가 가중치의 정본이라는 불변식은
  그대로 유지된다(요청이 commit_id 를 고르지 않는다).

## 3. 닿는 표면

| 표면 | 경로 | 상태 | 변경 |
|---|---|---|---|
| 신규 채점 컨테이너 | `apps/evaluate_lmeval/` | 신설 | 러너·레지스트리·체크포인트·커스텀평가·코드실행, manifest 2종, Dockerfile, build.sh, 테스트 |
| 매니페스트 시드 | `apps/fb_external_container/manifests/` | 활성 | `evaluate-lmeval.yaml`, `evaluate-lmeval-code.yaml` 사본 |
| 매니페스트 스키마 | `apps/fb_external_container/src/manifest/schema.py`, `src/launch/lifecycle.py` | 활성 | `network.isolate: bool=False` opt-in 추가 → values 로 전달 |
| 잡 파드 차트 | `apps/fb_scheduler/helm_chart/external_container/` (+ `src/scheduler/dto.py`) | 활성 | `isolate` 시 NetworkPolicy 렌더, `automountServiceAccountToken: false`, `/model` RW 마운트 생략 |
| 평가 서비스 | `apps/llm_evaluation/src/evaluation/{constants,dto,service}.py` | 활성 | 벤치마크 id 확장, 로컬 가중치 라우팅, `sample_limit` 옵션, 기본 집합 정리 |
| 공용 설정/비교 | `apps/fb_utils/settings.py`, `apps/fb_utils/llm_db/db_model.py` | 활성 | 매니페스트 이름·버전, 비교 행에 `mock` 플래그 전파 |
| FE | `front/src/pages/llm/Evaluation/BenchmarkEvaluation/*`, `ProjectDetail.jsx`, `EvalCrossCompare/*`, i18n ko/en | 활성 | 벤치마크 카탈로그·메트릭·카테고리, lm-eval 상세 섹션, 샘플 제한 입력, mock 배지, 폴링 기한 |
| mock 컨테이너 | `apps/evaluate_benchmark_mock/` | 휴면화 | **삭제하지 않는다** — 롤백용 등록 유지 |
| ETRI 원본 | `LLMOps/Evaluation/lmeval` (origin/main) | 참조 | 우리 브랜치에 병합하지 않고 이식 대상 코드만 옮긴다 |

## 4. 기존 패턴 재사용

- **SP-1 컨테이너 골격** = `apps/evaluate_intent/app.py`(비동기 잡 레지스트리, `/run`·
  `/jobs/{id}`·cancel, `_resolve_checkpoint` 의 realpath 봉쇄·`config.json` 검사).
- **체크포인트 역해석** = `_resolve_format_checkpoint` 를 `_resolve_deployment_checkpoint`
  로 일반화(오류 문구만 호출 경로별 인자로). running 을 요구하지 않고, 서빙 모델 일치를
  거절 조건으로 보며, HF 직배포(커밋 없음)는 거절한다 — 기존 의미 그대로.
- **결과 출처** = 컨테이너가 `metrics.checkpoint.name` 을 채우면 `_eval_run_source`
  (`db_model.py:959`)가 `source_mode='checkpoint'` 로 읽는다. 추가 배선 없음.
- **이미지 스냅샷** = LogicKor 심판 이미지가 이 클러스터에서 검증한 `torch 2.10.0 /
  transformers 5.5.4 / vllm 0.19.1`(`Evaluation/Logickor/requirements/etri-infer.txt`,
  `--no-deps`). lm_eval 0.4.12 의 `[vllm]` extra 는 `vllm>=0.18` 이라 충족한다.
- **빌드** = `apps/evaluate_intent/build.sh` 패턴(buildctl → OCI tar → `ctr -n k8s.io
  images import` + `io.cri-containerd.image=managed` 라벨). 여기에 docker.io push 를 추가한다
  (신규 서버 ErrImagePull 교훈).
- **ETRI 러너에서 가져오는 것** — 태스크 루프(`run_eval.py:459-536`), 지표 추출
  (`extract_task_metrics`), tqdm 진행률 후킹, 커스텀 지표(`custom_metrics.py`, 한국어 글자
  단위). **버리는 것** — Flask 대시보드(무인증 0.0.0.0 + trust_remote_code 강제), 모델
  다운로드·카탈로그, `value > 1.0` 스케일 휴리스틱(DROP 100배 오표기 원인).

## 5. 설계

### 5.1 채점기 2종과 라우팅

| 매니페스트 | 벤치마크 | 코드 실행 | 격리 |
|---|---|---|---|
| `evaluate-lmeval` 0.1.0 | lm-eval 17종 + `custom` | 불가(`HF_ALLOW_CODE_EVAL` 미설정 → 컨테이너가 거절) | `network.isolate: true` |
| `evaluate-lmeval-code` 0.1.0 | `humaneval` | 가능(`HF_ALLOW_CODE_EVAL=1`, `confirm_run_unsafe_code=True`) | `network.isolate: true` |

같은 이미지, 매니페스트만 둘이다. 코드 실행 허용을 **매니페스트 env 로만** 켜므로 params 를
어떻게 보내도 본 채점기에서는 코드가 실행되지 않는다. `constants.REAL_BENCHMARK_MANIFEST_KEY`
에 `humaneval → "BENCHMARK_CODE"` 를 추가하면 기존 "채점기 혼재 거부"
(`service.py:243-248`)가 HumanEval 을 자동으로 단독 런으로 만든다. 나머지는 기존 기본 키
`"BENCHMARK"` 로 가고, `settings.BENCHMARK_MANIFEST_NAME/VERSION` 을
`evaluate-lmeval/0.1.0` 으로 바꾼다(`BENCHMARK_CODE_MANIFEST_*` 신설).

⚠️ `DEFAULT_BENCHMARK_IDS`(생략 시 기본 집합)에 지금 `humaneval` 이 들어 있다. 채점기를
나누는 순간 기본 집합이 혼재 거부에 걸리므로 **기본 집합에서 humaneval 을 뺀다**. 또 기본
집합 전체를 한 런에 돌리면 수 시간이 걸리므로 기본값은 FE 가 쓰지 않는 서비스 직접 호출
경로에만 남긴다(FE 는 언제나 1개를 보낸다 — `BenchmarkRunConfig.jsx:78`).

### 5.2 벤치마크 id ↔ lm-eval 태스크

기존 id 8개는 **그대로 둔다**(이력·비교표가 `averages` 의 벤치마크 id 를 키로 쓴다).
few-shot 은 ETRI 레지스트리(리더보드 관례) 값을 따른다.

| id | lm-eval 태스크 | 유형 | few-shot | 대표 메트릭(id → lm-eval) | 카테고리 |
|---|---|---|---|---|---|
| arc | arc_challenge | MC | 25 | accuracy → acc | reasoning |
| arc_easy (신규) | arc_easy | MC | 0 | acc_norm → acc_norm | reasoning |
| kobest | kobest_boolq·copa·hellaswag·sentineg·wic | MC | 5 | f1 → 5개 f1 산술평균 | knowledge |
| mmlu | mmlu (그룹) | MC | 5 | accuracy → acc | knowledge |
| kmmlu (신규) | kmmlu (그룹) | MC | 5 | accuracy → acc | knowledge |
| kmmlu_direct (신규) | kmmlu_direct (그룹) | 생성 | 5 | exact_match → exact_match | knowledge |
| haerae (신규) | haerae (그룹) | MC | 0 | acc_norm → acc_norm | knowledge |
| hellaswag | hellaswag | MC | 10 | acc_norm → acc_norm | commonsense |
| winogrande | winogrande | MC | 5 | accuracy → acc | commonsense |
| piqa (신규) | piqa | MC | 0 | acc_norm → acc_norm | commonsense |
| openbookqa (신규) | openbookqa | MC | 0 | acc_norm → acc_norm | knowledge |
| gsm8k | gsm8k (strict-match) | 생성 | 5 | accuracy → exact_match | math |
| truthfulqa | truthfulqa_mc2 | MC | 0 | accuracy → acc | safety |
| truthfulqa_gen (신규) | truthfulqa_gen | 생성 | 0 | bleu → bleu_max | safety |
| boolq | boolq | MC | 0 | accuracy → acc | safety(기존 분류 유지) |
| squadv2 (신규) | squadv2 | 생성 | 0 | f1 → f1 | reading(신설) |
| drop (신규) | drop | 생성 | 3 | f1 → f1 | reading(신설) |
| humaneval | humaneval | 생성+실행 | 0 | pass_at_1 → pass@1 | code |
| custom (신규) | — (런 데이터셋) | 생성 | 0 | f1 → F1 | custom(신설) |

- 신규 메트릭 id: `exact_match`, `pass_at_1`(humaneval 의 대표를 accuracy 에서 교체 — 코드
  통과율은 정확도가 아니다). `em`·`rouge1/2/L` 은 상세에만 싣는다.
- `BENCHMARK_EVAL_TYPE` 은 신규 id 전부 `reference`. `BENCHMARK_ALLOWED_METRICS` 는 실제
  산출 축으로 갱신(문서 겸 FE 대조표 — `constants.py` 주석).
- `meteor`·`cider`·`spice` 는 이미지 캡셔닝 지표라 대응 벤치마크가 없다. 카탈로그에 남기되
  어느 벤치마크의 대표도 아니다(현행과 동일).

### 5.3 점수 스케일 — 휴리스틱 금지, 태스크별 명시표

화면은 accuracy 류를 0~100 으로 가정한다(`benchmarkMetrics.js:131-151`, mock 도 52~95).
컨테이너는 `{task: {metric: "fraction"|"percent"}}` 명시표로 환산한다. lm-eval 원본 실측:
`drop` = 0~1(`drop/utils.py` EM 1.0/0.0, F1 평균), `squadv2` = 0~100(HF `squad_v2`),
`truthfulqa_gen` 의 `bleu_*`·`rouge*_max/diff` = 0~100, `*_acc` = 0~1. 나머지 MC 는 0~1.
**표에 없는 (태스크, 메트릭)은 환산하지 않고 경고로 남긴다**(조용히 ×100 하지 않는다).
stderr 도 같은 규칙. P0 에서 17종 원시값 범위를 찍어 표를 확정한다.

### 5.4 컨테이너 실행 흐름

```
/run(params) → job(queued) → 서브프로세스(start_new_session, 취소=프로세스그룹 SIGTERM)
  1) checkpoint_name → /models/checkpoints/<name> (realpath 봉쇄, 단일 세그먼트)
       config.json 있음 → 그대로
       adapter_config.json 있음 → /models/checkpoints/source_model 위에 merge → /tmp/merged
       둘 다 없음 → 거절("merged HF 체크포인트 또는 LoRA 어댑터 필요")
  2) 엔진 = vLLM(기본) | HF(폴백, P0 결과로 확정). chat template OFF(리더보드 관례·
       Qwen3 사고모드 회피). trust_remote_code=False(기본값, 우리 커밋은 표준 아키텍처)
  3) 벤치마크별:
       lm-eval 태스크 → simple_evaluate(limit=sample_limit, seeds 고정) → 명시표 환산
       custom        → /dataset/<name> 행 파싱 → 생성 → F1/EM/BLEU/ROUGE
       humaneval     → HF_ALLOW_CODE_EVAL 확인 후 simple_evaluate(confirm_run_unsafe_code)
  4) /output/metrics.json(≤1MB) + /output/samples.jsonl(artifacts)
```

- 데이터: 17종 데이터셋 + `code_eval` 지표 스크립트를 **빌드 시 이미지에 적재**
  (`HF_DATASETS_CACHE=/opt/lmeval/datasets`, `HF_HUB_OFFLINE=1`, `HF_DATASETS_OFFLINE=1`).
  `/hf-cache` PVC 는 RO·인스턴스별 분리라 쓰지 않는다. 문항 버전이 이미지 태그에 묶인다.
- 커스텀 평가의 행 해석은 **플랫폼 규약을 따른다** — `llm_evaluation _row_to_sample`
  (`service.py:1495`)의 prompt/reference 키 우선순위·알파카 분할을 그대로 옮긴다(ETRI 목록과
  `apps/evaluate` 목록이 서로 달라 제3의 규약을 만들지 않기 위함). 생성은 토크나이저에 chat
  template 이 있으면 적용하고 `enable_thinking=False` 를 넘기며, 출력의 `<think>…</think>` 는
  제거한다. 한국어는 글자 단위 F1/ROUGE, BLEU 는 sacrebleu `char`. 데이터셋은 1개뿐이다
  (DTO `dataset_ids max_length=1`, 차트도 첫 데이터셋만 마운트).
- 진행률: tqdm 후킹 → `GET /jobs/{id}` 의 `progress`. 플랫폼은 폴링만 하므로(파드→플랫폼
  통신 없음) egress 차단과 충돌하지 않는다.

### 5.5 metrics.json

mock 과 같은 최상위 계약을 유지하고 상세 키를 더한다.

```json
{
  "mode": "benchmark", "mock": false,
  "results":  [{"benchmark": "mmlu", "metric": "accuracy", "score": 68.12}],
  "averages": {"mmlu": 68.12},
  "benchmark_set": ["mmlu"], "metric_map": {"mmlu": "accuracy"},
  "datasets": ["..."],
  "checkpoint": {"name": "<commit>", "format": "merged|lora"},
  "lmeval": {
    "engine": "vllm", "vllm_version": "0.19.1", "lm_eval_version": "0.4.12",
    "chat_template": false, "seed": 42, "max_model_len": 4096, "limit": null,
    "benchmarks": {"mmlu": {
      "metric": "accuracy", "score": 68.12, "tasks": ["mmlu"], "num_fewshot": 5,
      "metrics": [{"metric": "acc", "filter": "none", "score": 68.12, "stderr": 0.37}],
      "subtasks": [{"task": "mmlu_anatomy", "metric": "acc", "score": 64.4, "stderr": 4.1}],
      "n": 14042, "elapsed_sec": 1234.5, "warnings": []}}
  },
  "_meta": {"name": "evaluate-lmeval", "version": "0.1.0", "item_id": "..."}
}
```

- 서브태스크는 `results[]` 에 넣지 않는다 — FE 행 키가 `${benchmark}:${metric}` 라
  중복된다(`BenchmarkResultView.jsx:216`). `lmeval.subtasks` 전용 섹션으로 그린다.
- `custom`/`humaneval` 런은 `lmeval` 대신 `custom`/`humaneval` 상세 키(건수·지표 전부).
- 샘플별 예측은 metrics.json 에 넣지 않는다(1MB 상한 `service.py:596` 초과 시 폴링이 에러로
  멈추고 런이 running 에 남는다) → `samples.jsonl` 아티팩트.

### 5.6 격리(`network.isolate`) — HumanEval 과 lm-eval 공통

런처 실측: NetworkPolicy 는 저장소 어디에도 없고 `egress_whitelist` 는 읽는 코드가 없다.
컨테이너 securityContext 는 이미 비루트·RO 루트FS·권한상승 금지·capability 전부 제거다
(`fb_scheduler dto.py:360-367`). 부족한 것은 셋이다.

| 항목 | 현행 | isolate=true |
|---|---|---|
| egress | 무제한 | **전면 차단**(DNS 포함). lm-eval 은 로컬 모드라 나갈 곳이 없다 |
| ingress | 무제한 | BFF(`jfb-app-external-container`, 인스턴스 네임스페이스)에서 `spec.port` 로만 |
| SA 토큰 | 기본 SA 토큰 자동 마운트 | `automountServiceAccountToken: false` |
| `/model` | `latest_checkpoint` **RW** 마운트(`pod.yaml:283-287`) | 생략 |
| 그 외 | `/models/checkpoints` RO, `/dataset` RO, `/hf-cache` RO, `/output`·`/logs` RW, `/tmp` emptyDir | 동일 |

- **opt-in 인 이유**: 기존 `egress_whitelist: []` 를 차단으로 해석하면 배포 위임 모드의
  intent·logickor 가 shim 을 못 불러 전부 깨진다.
- ingress 대상 네임스페이스는 인스턴스마다 다르다(`tango-dev` / `jonathan-system`) →
  fb_external_container 가 자기 네임스페이스를 values 로 넘긴다. kubelet 프로브는 Calico 기본
  정책상 호스트→로컬 파드 허용이지만 **P0 에서 실측**한다.
- 잔여 위험(수용): 실행 코드는 같은 모델의 커밋(RO)과 런 데이터셋(RO)을 읽을 수 있고
  `/output` 에 쓸 수 있다(자기 점수 변조). 네트워크·K8s API·다른 워크스페이스로는 나갈 수
  없다. `code_eval` 자체의 프로세스 분리·위험 함수 비활성·타임아웃이 한 겹 더 있다.

### 5.7 평가 서비스(llm_evaluation) 변경

- `run_benchmark`: `manifest_key in LOCAL_WEIGHTS_MANIFEST_KEYS("BENCHMARK","BENCHMARK_CODE")`
  이면 `_resolve_deployment_checkpoint` → `params.checkpoint_name`, `generate_base_url` 을
  싣지 않고 `gpu_count=None`(매니페스트 1장), 응답 `used_deployment=False`·`checkpoint`.
  포맷 학습 게이트·원격 심판 게이트는 그대로.
- 실행 옵션 `sample_limit`(태스크당 문항 상한, 1~N): DTO 필드로 열거(자유 passthrough 금지
  규약 `dto.py:204-207`), BENCHMARK/BENCHMARK_CODE 에서만 받고 다른 채점기에 주면 거절.
  `limit` 을 준 점수는 `metrics.lmeval.limit` 에 남고 FE 가 "빠른 점검" 배지로 구분한다.
- 비교표 mock 구분: `_attach_run_sources`/`build_eval_comparison` 행에 `mock` 을 싣는다.
  지금은 단건 결과 페이지에서만 보이고 비교표(`ProjectDetail`·`EvalCrossCompare`)에는 없다 →
  교체 후 같은 id 의 해시 점수와 실측 점수가 구분 없이 나란히 선다.
- 6시간 스윕(`fail_stale_eval_results`)은 컨테이너 확인 없이 나이만으로 failed 로 만들고 되돌릴
  수 없다. 불변식 **`STALE_RUNNING_MAX_HOURS × 3600 > max(manifest timeout_seconds) + 기동`**
  을 지킨다 — P0 실측 후 확정: `timeout_seconds` 36000(10h), `STALE_RUNNING_MAX_HOURS` 12
  (§11). 불변식은 tests/test_benchmark_catalog.py 가 매니페스트와 대조한다.

### 5.8 FE 변경

- `benchmarks.js`: 신규 9 id + `custom`, 카테고리 `reading`·`custom`, `real: true` 로 전환
  (실채점 배지 `BenchmarkResultView.jsx:156-158`). i18n `evaluation.bench.benchDesc.*` ko/en.
- `benchmarkMetrics.js`: `exact_match`·`pass_at_1`(0~100).
- 실행 화면: "배포가 서빙 중인 체크포인트를 평가기가 직접 올려 채점합니다(GPU 1장 사용)"
  안내, 샘플 제한 입력(비우면 전체), `custom` 선택 시 데이터셋이 평가 데이터라는 안내.
- 결과 화면: lm-eval 상세 섹션(설정 요약 + 서브태스크 표), custom/humaneval 상세.
- 비교 화면: mock 배지. 폴링 기한 `POLL_DEADLINE_MS` 를 매니페스트 timeout 과 맞춘다.

## 6. Cross-surface 계약 변경

| 짝 | 동기화 대상 |
|---|---|
| 벤치마크 id 정본 | `constants.BENCHMARK_IDS`·`BENCHMARK_EVAL_TYPE`·`RECOMMENDED`·`ALLOWED` ↔ 컨테이너 `registry.py` ↔ FE `benchmarks.js` ↔ i18n ko/en — **패리티 테스트 신설**(현재 BE↔FE id 패리티 테스트 없음) |
| 메트릭 id | `constants.METRIC_IDS` ↔ `benchmarkMetrics.js` ↔ 컨테이너 metric 매핑 |
| 매니페스트 | `apps/evaluate_lmeval/manifest*.yaml` ↔ `fb_external_container/manifests/` 사본 ↔ `settings.BENCHMARK(_CODE)_MANIFEST_NAME/VERSION` |
| 격리 플래그 | `schema.py` ↔ `lifecycle.py` values ↔ `fb_scheduler dto.py` ↔ 차트 `pod.yaml`/`networkpolicy.yaml` |
| 결과 계약 | 컨테이너 metrics.json ↔ `db_model._flatten_eval_metrics`(averages) ↔ `_eval_run_source`(checkpoint.name) ↔ FE 결과·비교 뷰 |
| 시간 상한 | 매니페스트 `timeout_seconds` ↔ `STALE_RUNNING_MAX_HOURS` ↔ FE `POLL_DEADLINE_MS` |
| monitoring pod_type | 변경 없음 — 기존 `job_type=evaluate`(intent 가 이미 GPU 1장 사용) |

## 7. 빌드/배포 시퀀스

| 단계 | 대상 | 반영 방법 |
|---|---|---|
| P0 | 스파이크(저장소 무변경) | 임시 이미지 + dev 워크스페이스 ad-hoc 파드로 호환성·시간·격리 실측 |
| P1 | `apps/evaluate_lmeval` | 단위 테스트 → `build.sh`(buildctl → containerd import) + docker.io push |
| P2 | 격리 플래그(schema·lifecycle·dto·차트) | dev src 마운트 → `rollout restart` external-container·scheduler |
| P3 | 매니페스트 2종 시드 | `manifests/` 추가 → external-container 재시작(부팅 시드, 새 (name,version)만 등록) |
| P4 | llm_evaluation + fb_utils | dev src 마운트 → `rollout restart` llm-evaluation |
| P5 | FE | `yarn build` + `/front-data` 반영 |
| P6 | dev e2e → 3-way 리뷰 → 커밋(사용자) | 서빙 인스턴스 반영은 **별도 승인** |

롤백: `BENCHMARK_MANIFEST_NAME/VERSION` 을 mock 0.2.0 으로 되돌리면 된다(mock 매니페스트는
양 인스턴스에 등록 유지). 단 되돌리면 신규 id 는 mock 이 필터링해 버리므로 FE 카탈로그도 함께
되돌려야 한다.

### 7.1 P0 스파이크 체크리스트 (구현 착수 전 게이트)

1. `lm_eval==0.4.12` + LogicKor 스냅샷(torch 2.10/transformers 5.5.4/vllm 0.19.1) + `datasets`·
   `evaluate` 핀 조합이 설치·임포트된다.
2. 17종 데이터셋 + `code_eval` 스크립트가 빌드 시 적재되고 **오프라인**(`HF_*_OFFLINE=1`)에서
   로드된다. 로딩 스크립트 의존 데이터셋(kobest·drop·haerae 후보)을 확인한다.
3. dev 커밋 1개로 19종 전부 `limit=20` 완주 → 원시값 범위로 §5.3 스케일표 확정.
4. 전체 측정 시간(vLLM vs HF): MMLU·KMMLU·HellaSwag·SQuADv2·DROP → timeout·stale 값 결정.
5. LoRA 커밋 merge 경로(실 파인튜닝 커밋이 없으면 합성 어댑터로).
6. 격리: deny-all egress + BFF ingress NetworkPolicy 하에서 startup/liveness 프로브 통과,
   파드 안에서 외부·클러스터 서비스 접속 실패, SA 토큰 부재, `/model` 부재.
7. 공개 수치 sanity: 같은 모델의 lm-eval 공개 MMLU·ARC-C·HellaSwag 와 수 점 이내.

## 8. 호환성 리스크

| 리스크 | 레벨 | 대응 |
|---|---|---|
| lm_eval 0.4.12 × vllm 0.19.1 × transformers 5.5.4 비호환 | MED | P0-1. 실패 시 HF 백엔드 + transformers 릴리스 핀 |
| 데이터셋 로딩 스크립트(datasets 버전) | MED | P0-2. parquet 리비전 고정 또는 datasets 핀 |
| 기본 집합에 humaneval → 혼재 거부 | HIGH(누락 시) | §5.1 기본 집합 수정 + 테스트 |
| 6h 스윕이 긴 런을 복구 불가 failed 로 | MED | §5.7 불변식 + 테스트 |
| 비교표에서 mock 과 실측 혼재 | MED | `mock` 플래그 전파 + 배지 |
| NetworkPolicy 로 프로브·폴링 차단 | MED | P0-6 실측, ingress 에 BFF 네임스페이스 명시 |
| vLLM 과 HF 수치 차(±1pt 내외) | LOW | `metrics.lmeval.engine` 기록, 엔진 고정 |
| 배포 + 평가 파드 GPU 이중 점유 | LOW | A100×8, 안내 문구. 워크스페이스 쿼터 확인 |
| 신규 서버 ErrImagePull(미push) | MED | build.sh 에 docker.io push |
| metrics.json 1MB 상한 | LOW | 샘플은 아티팩트, 서브태스크 수백 행 이내 |
| HumanEval 잔여 위험(RO 읽기·/output 쓰기) | LOW | §5.6 수용 사유 명시 |
| `metric_set` 255 절단 | LOW | FE 1개/런이라 도달 불가. 이번 범위 밖(기록만) |

## 9. 테스트 계획

- **컨테이너 단위(pytest)** — 레지스트리 19 id 매핑, 스케일표(drop 0~1·squadv2 0~100·
  표 밖 경고), `extract` 가 lm-eval 결과 dict(그룹·서브태스크·filter 키)를 올바로 읽음, 체크포인트
  해석(merged/lora/둘 다 없음/경로 탈출), 커스텀 행 파싱(플랫폼 규약 동일)·`<think>` 제거·한국어
  글자 단위, 코드 실행 env 미설정 시 humaneval 거절.
- **BE 단위** — 로컬 가중치 라우팅(generate_base_url 부재·checkpoint_name·gpu_count None),
  humaneval 단독 런 강제·기본 집합에 humaneval 없음, `sample_limit` 범위·타 채점기 거절,
  비교 행 `mock`, stale 불변식(`STALE_HOURS*3600 > 모든 매니페스트 timeout`).
- **패리티** — BE constants ↔ 컨테이너 registry ↔ FE benchmarks.js ↔ i18n 키.
- **클러스터 e2e(dev :31080)** — 커밋 모델 배포 → reference 프로젝트 → 19종 각각
  `sample_limit=20` 완주 → 결과·비교 화면. MMLU 1회 전체 측정. HumanEval 격리 검증(§7.1-6).
- **FE 브라우저 QA** — 카탈로그·카테고리·샘플 제한·상세 섹션·mock 배지·ko/en.

## 10. 목업 정합 (front_etri)

- 목업 `BenchmarkEvaluationPage.jsx` 는 벤치마크를 "메트릭"으로 다중 선택하고 데이터셋 ×
  메트릭 행렬 + 평균 열로 보여준다(점수는 `Math.random`). 우리 화면은 이미 "벤치마크 1개 선택
  → 서버 고정 대표 메트릭"으로 갈라져 있고(2026-08-26 결정), 이번 작업은 그 구조를 바꾸지 않는다.
- 목업 목록의 9 벤치마크(arc … humaneval)는 전부 실채점으로 전환된다. KMMLU·HAE-RAE·
  SQuADv2 등 신규 id 는 목업에 없다 — 사용자 결정(D4)으로 추가한다.
- 목업의 METEOR·CIDEr·SPICE(캡셔닝)와 객체탐지·세그멘테이션·OCR 데이터셋은 LLM
  벤치마크 채점기로 계산할 수 없다 — 이번 범위 밖(현행과 동일).

## 11. P0 실측 결과와 구현 확정 사항 (2026-09-28)

스파이크: tango-dev-2, GPU 7(A100 80GB) 임시 파드, 잡 파드와 같은 securityContext.
모델 = dev 커밋 Llama-3.2-3B(`source_model`). 스파이크 리소스는 검증 후 삭제했다.

| # | 항목 | 결과 |
|---|---|---|
| 1 | 호환성 | lm_eval 0.4.12 + torch 2.10.0+cu128 / transformers 5.5.4 / vllm 0.19.1 / datasets 5.0.1 / evaluate 0.4.6 / peft 0.21.0 — `pip check` 깨끗. 비루트·RO 루트FS 에서 vLLM 기동 |
| 2 | 오프라인 | 18종 전부 캐시만으로 로드(egress 차단 파드). 캐시 ≈ 0.9GB(datasets 756MB + hub 167MB). squad_v2·code_eval 지표 스크립트 포함 |
| 3 | 스케일 | 객관식·DROP·`*_acc` = 0~1, SQuADv2 `exact/f1`·TruthfulQA-gen `bleu/rouge*_max/diff` = 0~100 — §5.3 표 확정 |
| 4 | 시간(3B, 전체) | KMMLU 3884s · MMLU 1886s · HellaSwag 1632s · KMMLU-Direct 583s · DROP 493s · TruthfulQA-gen 459s · KoBEST 244s · ARC 241s · SQuADv2 196s, 나머지 < 80s. 객관식이 생성형보다 느리다(vLLM prompt_logprobs). → timeout 36000 · stale 12h |
| 5 | LoRA | 합성 어댑터 → `checkpoint.materialize`(서빙과 같은 merge_and_unload) 15s → vLLM 로드·채점 OK |
| 6 | 격리 | NetworkPolicy(egress `[]`, ingress = BFF ns + app 라벨 :8000) 하에서 프로브 통과, dev BFF 만 200, 다른 파드·서빙 BFF 차단, 파드→MariaDB·내부 svc·apiserver·DNS·인터넷·노드 NodePort/6443/10250 차단, SA 토큰 부재 |
| 7 | 수치 sanity | MMLU 5-shot 60.6(Meta 공개 3B-Instruct 63.4 — 로그확률·무템플릿 차), HellaSwag 73.3, WinoGrande 71.2, TruthfulQA-MC2 51.6, GSM8K strict 58.8, HumanEval 50.6 |

구현 중 확정·변경(위 절보다 우선):

- **엔진 = vLLM 고정**(사용자 지시 — HF 비교·폴백 없음).
- **DROP 은 upstream 태스크를 그대로 쓸 수 없다** — `doc_to_target: "{{ answer|join(',')}}"` 가 원본
  `answer` dict 의 키 이름을 정답으로 렌더해 few-shot 정답이 `number,date,spans,worker_id,hit_id`
  가 되고 모델이 그걸 베낀다(EM·F1 0). 빌드 시 `drop_tango` 수정본을 만든다(정답 `answers[0]`,
  정지 시퀀스 `"."` → 줄바꿈 — 소수 절단·다음 지문 생성 방지). 100문항 F1 0.004 → 0.211.
  수정본이라 **공개 lm-eval DROP 수치와 비교 불가**.
- `metrics.json` 상세는 벤치마크별 `lmeval.benchmarks[<id>]`(한 런에 여러 벤치마크 가능).
- 비교 행에 `mock` 을 싣고 **`best` 후보에서 mock 런을 뺀다**(해시 점수가 실측을 제친다).
- vLLM 0.19 `SamplingParams` 에 `truncate_prompt_tokens` 가 없어 custom 은 직접 토큰화해 앞을 자른다.
- 곁가지 발견: dev·서빙 두 인스턴스의 GPU 할당기는 서로의 할당을 모른다(dev 는 서빙의 GPU 0 을
  빈 것으로 본다) — 기존 리스크, 이번 범위 밖.

### 11.1 P1 구현·검증에서 드러난 것 (2026-09-28)

- **스케줄러 RBAC** — 격리 잡 차트가 NetworkPolicy 를 렌더하는데 `<ns>-clusteradmin-cluster-role-scheduler`
  에 `networking.k8s.io/networkpolicies` 권한이 없어 helm install 이 forbidden 으로 실패했다(dev 플랫폼 e2e,
  job fa838cc2). 차트 정본 `devops/fb_scheduler/helm/templates/rbac.yaml` 에 추가했고, **라이브 ClusterRole
  반영(dev·서빙)은 운영자 승인 대상**이다 — 반영 전에는 lm-eval 런이 전부 launch 단계에서 실패한다.
- **적재물 권한** — build 중 evaluate 가 받은 지표 스크립트가 root 600 이라 비루트 잡 파드가 복사하지 못했다
  → Dockerfile 에 읽기 권한 보정 레이어.
- **custom 잘라내기** — 템플릿을 입힌 토큰열의 앞을 자르면 BOS·역할 마커가 날아간다(리뷰 지적) →
  `custom_eval.fit_prompt` 가 템플릿 전 내용을 잘라 다시 입힌다.
- **컨테이너 직접 e2e**(dev GPU 파드, 차트와 같은 마운트·securityContext, API /run→/jobs→metrics.json):
  arc 40.0 · drop(수정본) 15.0 · custom F1 48.6/EM 37.5(ETRI sample_ko 8문항, 한국어 글자 단위) ·
  humaneval pass@1 90.0(코드 채점기) — 모두 limit=20. 코드 실행 게이트 양방향 400 확인.
- 이미지 안 테스트 50/50, BE 라우팅 테스트 5/5(dev 파드), 카탈로그 패리티 11/11.

### 11.2 브라우저 QA 에서 드러난 것 (2026-09-28)

- **FE 가 dev 에 빌드되지 않았다** — dev front 는 워크트리 `front/build` 를 그대로 서빙하는데 빌드가
  09-22 것이었다. dev 워크트리 `yarn build` 로 반영. front 는 index.html·i18n JSON 을
  `Cache-Control` 없이(Last-Modified 만) 내보내 배포 직후 브라우저가 옛 번들·옛 번역(키 문자열 노출)을
  쓸 수 있다 — 기존 동작, 서빙 반영 시 강력 새로고침 안내 필요.
- **빠른 확인 런이 Best 를 다퉜다** — 비교 행에 `mock` 만 있고 `limit` 이 없어 20문항 점수가 목록·비교에서
  아무 표시 없이 Best 가 됐다. → 비교 행에 `sample_limit`(`metrics.lmeval.limit`, 1 이상 정수만)을 싣고
  `best` 후보에서 뺀다(`build_eval_comparison`). FE 는 `compareMatrix.isUnranked`(mock ∨ 빠른 확인)
  하나로 순위를 판정하고 목록·런 비교·모델 비교·프로젝트 비교에 "빠른 확인" 배지를 단다.
  테스트 `apps/llm_evaluation/tests/test_eval_comparison.py`(dev 파드 9/9).
- 남은 것: lm-eval 표준 벤치마크도 데이터셋이 필수라(`_run_dataset_ids`) 결과 머리에 쓰지 않은
  데이터셋이 찍힌다 — §12.2 에서 함께 푼다. 샘플 수 입력은 숫자만 남겨 `1.5` 가 경고 없이 `15` 가 된다(LOW).

## 12. 확장 계획 — 여러 벤치마크 한 번에 실행 + 모델 요약 (2026-09-28, 미착수)

배경: ETRI 대시보드(`Evaluation/lmeval`, 5a973795e)는 한 프로세스에서 선택한 태스크를 **직렬로** 돌리고
요약 카드 4장(영어 core·한국어·생성형 평균 + "종합"), 카테고리 레이더, 생성형 지표 표, 전체 상세 표를
보여준다. 목업(`front_etri` `BenchmarkEvaluationPage`)도 다중 선택 + 평균 열이다(§10). 우리 화면은
"런 하나 = 벤치마크 하나"라 여러 벤치마크를 재려면 런을 하나씩 만들어야 하고, 모델 단위로 한눈에 보는
요약이 없다.

### 12.1 실행 단위는 바꾸지 않는다 — 벤치마크 1개 = eval_result 1행 = 잡 1개

| 근거 | 실측·코드 |
|---|---|
| 시간 | 3B 전체 합 ≈ 2.8h(§11 #4, KMMLU 65분이 최장). 8B 면 잡 timeout 10h 에 근접 — 한 잡이면 하나만 죽어도 전부 재실행 |
| 병렬 | 벤치마크별 잡이면 GPU N장에 동시 배치 → 벽시계 ≈ 최장 벤치마크. 한 잡은 1장에서 직렬 |
| HumanEval | 코드 실행 격리 매니페스트라 다른 벤치마크와 한 잡에 못 싣는다(`service.py:250` 채점기 혼합 거절) |
| 기존 단위 | Best·재실행·삭제·결과 페이지가 런 단위다 |

같은 채점기끼리 한 잡에 싣는 기존 API 경로(metric_set CSV)는 하위호환으로 남기되 화면은 쓰지 않는다.

### 12.2 여러 벤치마크 선택 → 벤치마크별 런으로 펼치기

- **FE** `BenchmarkRunConfig`: 라디오 → 체크박스. 카테고리 칩에 "이 카테고리 전부" 선택, 선택 수와 필요한
  GPU 수를 가용량(이미 표시 중인 `GPU n available`) 옆에 보인다. 샘플 수 제한은 묶음 전체에 적용.
- **BE** 묶음 실행 한 요청(`run_benchmark_batch` 류) — 모델·배포·**체크포인트 해석을 한 번만** 하고
  (묶음 안 런이 같은 가중치를 재는 것을 보장 — 중간에 배포가 커밋을 바꿔도) 벤치마크마다 기존 런치
  경로를 탄다. HumanEval 은 자동으로 코드 매니페스트로 간다. 응답은 벤치마크별 `{job_id | error}`.
  FE 가 N번 POST 하는 방식은 검증이 N번 돌고 부분 실패가 화면에서 흩어져 채택하지 않는다.
- **GPU 부족은 대기가 아니라 즉시 실패다** — 외부 잡 런치는 빈 GPU 가 없으면 `GpuAllocationError` 로
  바로 실패한다(`fb_scheduler external_run.py:196-202`, 대기열 없음). 1차는 **선택 수 ≤ 가용 GPU** 로
  막는다(BE 가 최종 판정, FE 는 사전 안내). 가용량보다 큰 묶음을 순차로 흘리는 대기열(eval_result 를
  `pending` 으로 두고 리콘사일러가 GPU 가 비면 런치)은 2차.
- **데이터셋 필수 해제** — lm-eval 표준 벤치마크는 이미지에 구운 데이터만 쓴다. `_run_dataset_ids`
  (`service.py:1135`) 필수를 데이터셋을 실제로 읽는 채점기(custom·MixATIS·LogicKor 등)로 한정.
  `eval_result.dataset_id` 는 이미 NULL 허용(`fb_utils/llm_db/schema.sql:153`). 결과 머리의
  "데이터셋 -" 표시 확인 필요.

### 12.3 모델 요약(스코어카드)

- **위치**: 모델 비교(`EvalCrossCompare` 모델별 탭) 상단 — 새 페이지를 만들지 않는다. 데이터는 지금
  비교 응답 그대로(행 = 벤치마크, 셀 = 모델별 대표 런) → **스키마 변경·묶음 id 불필요**. 묶음으로
  실행했든 하나씩 실행했든 같은 요약이 나온다.
- **카테고리 평균**: `benchmarks.js` 의 `category` 로 묶고 **0~100 정답률 계열 지표만** 평균한다
  (accuracy·acc_norm·f1·exact_match·pass_at_1). BLEU/ROUGE·perplexity·심판 점수(0~10)·MixATIS 는
  평균에서 빼고 개별로 보인다. 순위 제외 런(mock·빠른 확인)은 평균에서도 뺀다(`isUnranked`).
- **모델 간 공정성**: 모델마다 잰 벤치마크가 다르면 평균이 서로 다른 문항 집합을 잰다 → 카드에
  커버리지(`k/n 벤치마크`)를 싣고, 비교 모드에서는 **선택한 모델이 모두 잰 벤치마크만으로** 평균한다.
- **ETRI "종합"(전체 대표지표 평균)은 채택하지 않는다** — 정답률·F1·BLEU 를 한 평균에 섞는다.
- 레이더는 평균 가능한 카테고리가 3개 이상일 때만.
- 열린 질문: 같은 모델의 서로 다른 체크포인트를 한 셀로 합칠지(지금 행렬은 모델 단위 최고 런) —
  체크포인트별 열로 가를지 사용자 결정.

### 12.4 순서

| 단계 | 내용 | 검증 |
|---|---|---|
| P0 | 가용 GPU 판정 소스 확정(FE 가 쓰는 GPU 가용량 read-model 재사용) · 데이터셋 NULL 런이 결과/목록/비교에서 깨지지 않는지 | dev 에서 데이터셋 없는 런 1건 |
| P1 BE | 묶음 실행 엔드포인트 + 데이터셋 선택화 + GPU 상한 | 파드 테스트(부분 실패·상한·HumanEval 라우팅·같은 체크포인트) |
| P2 FE | 다중 선택 + 모델 요약 카드·레이더 | 브라우저 QA |
| P3 | dev e2e — 한국어 묶음(KoBEST·KMMLU·HAE-RAE·KMMLU-Direct) GPU 4장 병렬, 3-way 리뷰 | 벽시계 ≈ KMMLU 단독 |

### 12.5 구현·검증 결과 (2026-09-29)

사용자 결정: **같은 모델이라도 체크포인트가 다르면 따로 본다**(비교·요약 모두).

- **BE** `POST /evaluations/benchmark/batch`(`BenchmarkBatchRunBody`, `extra=forbid`) → `run_benchmark_batch`.
  런치 전 거절: 모르는 id·위임 채점기·데이터셋 누락·프로젝트 유형·가용 GPU 부족(`_gpu_free_count` =
  `gpu_pool.snapshot` 의 클러스터·워크스페이스 중 작은 값, 조회 실패는 막지 않음). 체크포인트는 한 번 풀어
  `run_benchmark(pinned_checkpoint=…)` 로 넘긴다(라우트는 받지 않음). 데이터셋 선택화 =
  `DATASET_FREE_BENCHMARK_IDS`(BE·FE·컨테이너 레지스트리 3자 대조 테스트).
- **FE** lm-eval 벤치마크 체크박스 다중 선택 + "보이는 항목 모두 선택"(카테고리 필터와 함께 쓰면 묶음 프리셋),
  2개 이상이면 묶음 API. 모델 비교 열 = **모델 × 출처**(`ckpt:<이름>` / `dep:<배포>` / 출처 미상 —
  위임 런은 서빙 커밋 기록이 없어 체크포인트 열과 합치지 않는다), 같은 모델의 두 번째 이후 열은 점선.
  요약 카드(공통 벤치마크 평균·카테고리 평균·커버리지) + 카테고리 3개 이상이면 SVG 레이더.
- **테스트** dev 파드 32/32(라우팅·묶음·DTO 경계·비교), 호스트 카탈로그 12/12, compareMatrix 순수 로직
  esbuild+node 하네스 12/12.
- **dev e2e**(프로젝트 15, llama `source_model`, 전체 문항): 묶음 4개 한 요청 → 잡 4개가 GPU 1~4 에 동시
  기동(서빙 GPU0 회피), 전부 completed — ARC-Easy acc_norm 71.09 · PIQA acc_norm 76.77 · OpenBookQA
  acc_norm 39.20 · BoolQ acc 78.59, `dataset_name` NULL. 요약 카드 평균 66.41(공통 4개)·레이더 4축,
  빠른 점검 런(76~78)은 Best·평균 제외 확인.
- ⚠️ **dev 에서는 배포를 띄우지 않는다** — dev 배포 할당기가 GPU 예약 키를 무시해 서빙 GPU0 에 붙었다(즉시
  중지, 서빙 무영향). e2e 는 멈춘 배포 id 로 체크포인트를 풀어(원래 running 을 보지 않는다) API 로 돌렸다 —
  그래서 **실행 모달의 최종 제출 클릭은 dev 에서 검증하지 못했다**(모달의 선택·검증·레일은 브라우저 확인).
- 리뷰 반영(BE·FE·보안·codex 4-way): Redis 클라이언트 획득까지 스레드로(`_gpu_free_count`, 루프 블로킹
  방지) · 격자 항목 전부 `role=checkbox`(radio 는 radiogroup 조상 필요) · 모델 id 문자열 비교 · import 순서 ·
  (codex) 묶음의 데이터셋은 **읽는 벤치마크에만**(custom+ARC 묶음에서 ARC 런에 데이터셋이 기록되던 것) ·
  (codex) 순위 제외 점수만 있는 대상도 **카드로 남김**(`unrankedOnly` — 빼면 "비교할 전체 측정이 없다"가
  가려진다) · (codex) 순위 제외 셀은 차이값·막대를 그리지 않음 · (codex) 위임 런 열 = **배포 × 완료 시점
  서빙 커밋**(`_platform_source.commit` → 비교 행 `source_commit`; 굳히기 이전 옛 런은 배포만).
  남긴 것: 묶음 라우트 요청 빈도 제한 없음(플랫폼 전역 공백, 묶음은 GPU 수로 상한) · BFF 오류 본문이
  벤치마크별 error 로 노출(기존 동작) · 순차 런치 — 실측 간격 ≈1.3초/개(4개 4초, 런 79~82 생성 시각)라
  상한 20개여도 ≈26초로 Kong 60s 안이다.

## 13. 정답 대조 = 실행 카드 + ETRI 결과 화면 (2026-09-29)

사용자 요청: 벤치마크 평가 목록을 **run 단위 카드**(전문가 평가와 같은 모양)로 바꾸고, 카드 안 세부 화면은
**ETRI 가 준 결과 화면**(`Evaluation/lmeval` 대시보드)을 따르며, 각 지표를 누르면 종전 실행 목록 행을 눌렀을 때의
세부 화면(`BenchmarkResultPage`, `/run/:jobId`)으로 간다.

결정(사용자): ① **한 번의 실행 = 카드 1장**(묶음 기록 신설) ② 요약 카드 4장은 ETRI 구성, **종합은 정답률 계열만**
(모델 비교 요약과 같은 규칙 — `compareMatrix.AVERAGE_METRIC_IDS` 공유) ③ LLM 심사는 표 유지(정답 대조만 변경).

- **실행 기록**: `eval_run_batch` + `eval_run_batch_member`(job_str_id FK CASCADE·UNIQUE) 신규 2테이블(ALTER 없음,
  schema.sql·mariadb-init 반영). `run_benchmark_batch` 가 뜬 런만 기록(기록 실패는 런치를 무르지 않는다 → 단건 카드로
  보임). `get_project` 응답에 `batches`(조회 실패 시 [] — 테이블 없는 DB 에서도 화면이 뜬다). 삭제
  `DELETE /evaluations/projects/{pid}/batches/{bid}`(다른 프로젝트 것은 not-found, 멤버는 단건 삭제 경로).
  정답 대조의 lm-eval 실행은 **벤치마크 1개여도 묶음 API** 로 — 모든 실행이 카드 1장으로 남는다. MixATIS 단건·
  기록 이전 런은 카드 1장씩(`r-<jobId>`).
- **카드**(`ProjectDetail`): 벤치마크 이름들 · 모델·체크포인트·벤치마크 수 · 종합 · 빠른 점검/mock · 상태(진행 중
  n/N, 일부 실패 = partial) · 중지(도는 멤버 전부)·삭제(묶음째). 표가 없어졌으므로 **'실행 비교' 탭이 정답 대조에도
  다시 보인다**(`RUN_TABLE_TYPES = ['judge']`).
- **결과 요약**(`BenchmarkBatchPage`, `/project/:id/batch/:key`): ETRI 순서 — 진행 상황(완료/전체 + 벤치마크별 칩) →
  요약 카드 4장(영어 core·한국어·생성형 평균 + 종합) → 벤치마크별 점수(그룹 색 막대) + 카테고리 레이더 → 생성형
  지표(F1/EM/BLEU/ROUGE-1/2/L, lm-eval 원 지표 이름으로 선택) → 전체 지표 상세(태스크·few-shot·원 지표·표준오차·n·
  소요·상태). ETRI 의 실행 로그는 벤치마크마다 잡이 따로라 각 런 세부 화면(Run log)에 둔다. 멤버마다
  `getEvalResult` 를 폴링(공용 `resultPolling.js`) — 결과 JSON 의 `lmeval.benchmarks[id]` 에서 상세를 읽고, 폴링이
  곧 런 마감 트리거다. 벤치마크·지표 행 → 세부 화면, 세부 화면의 뒤로가기 = 요약(`location.state.from`).
- **그룹**(`benchmarks.js` `group`): ETRI 묶음 그대로 — 영어 core / 한국어(KoBEST·KMMLU·KMMLU-Direct·HAE-RAE·LogicKor) /
  생성형(SQuADv2·TruthfulQA-gen·DROP, 목록에 없는 HumanEval 도 여기) / 커스텀(custom·MixATIS). 레이더 축은 기존
  `category`(지식·추론·상식…).
- 검증: 파드 테스트 38/38(묶음 기록·기록 실패·묶음 삭제 경계), 호스트 12/12, batchSummary 하네스 12/12, dev e2e —
  4개 빠른 점검 묶음(ARC-Easy 70.00·KoBEST F1 56.01·SQuADv2 F1 26.40·TruthfulQA-gen BLEU 35.51, GPU1~4) → 카드 1장 →
  요약(영어 70.00·한국어 56.01·생성형 30.95·종합 50.80) → SQuADv2 세부 → 요약 복귀.
- ⚠️ 서빙 반영 전 서빙 DB 에 두 CREATE 를 수동 적용(승인 대상). 적용 전이면 모든 런이 카드 1장씩으로 보인다(기능 저하,
  오류 아님).
- 리뷰 반영(BE/보안·FE·codex): 묶음 삭제가 **도는 멤버를 서버에서 먼저 취소**(`mark_eval_status`, API 직접 호출도
  GPU 잡을 남기지 않게) · 멤버 삽입 실패 시 묶음 행 삭제(고아 방지) · 단건 조회는 LEFT JOIN(멤버 0 인 묶음도 지울 수
  있게) · **런치 실패도 기록**(`eval_run_batch.launch_failures` — 요청 3개 중 2개만 뜬 실행이 "2/2 완료"로 읽히지 않게,
  요약에 '시작 못 함' 항목) · 여러 벤치마크를 담은 옛 런은 토큰마다 항목 · 폴링 effect 별 상태·묶음 바뀌면 결과 초기화·
  tick 예외 방어 · 표의 이름 칸은 버튼(키보드) · 카드는 role 없는 div + 진짜 '열기' 버튼(중첩 상호작용 제거).
  남긴 것: 묶음 id 열거로 다른 워크스페이스 기록 삭제 가능(플랫폼 authZ 비활성 posture — 단건 삭제보다 경계는 강함),
  정답 대조에서 안 쓰이게 된 표 계산(`benchRows` 등) 정리는 후속.

## 14. 묶음 실행 = GPU 수만큼의 런 (2026-09-29, §12.1 번복)

사용자 요청: 벤치마크마다 런을 두지 않고 **GPU 개수를 골라 런을 나눠** 띄운다. §12.1 은 "벤치마크 1개 = 런 1개"를
유지했는데, 그 규칙이면 20개를 고른 실행이 빈 GPU 20장을 요구해 거절된다(외부 잡은 대기열 없이 즉시 실패). 한 런에
여러 벤치마크를 담을 때의 약점 — 하나만 죽어도 전부 버린다 — 을 채점기가 벤치마크 단위로 막도록 바꾸고 번복한다.

- **채점기(evaluate-lmeval 0.1.1)**: 한 런이 벤치마크를 직렬로 채점한다(모델은 한 번 로드). `_score_benchmarks` 가
  벤치마크 하나의 예외를 그 벤치마크의 실패로 기록하고 다음으로 간다(취소 `_Cancelled` 는 BaseException 이라 통과,
  전부 실패하면 런 실패). 결과는 `metrics.json` 에 `failed_benchmarks: [{benchmark, metric, error}]` 로 함께 싣는다.
  진행은 `/output/progress.json`(`{benchmarks:[{benchmark, status: pending|running|done|failed, score, elapsed_sec,
  error}], partial: <끝난 벤치마크의 metrics shape>}`, tmp+rename 원자 교체, best-effort). ⚠️ 이름을 나눈 이유 —
  `get_eval_result` 는 `metrics.json` 이 생기면 곧바로 런을 completed 로 마감한다. 매니페스트 2종·settings 기본값
  0.1.1(부팅 시드가 새 (name, version) 을 등록).
- **분배**(`service.plan_benchmark_runs`): 런 수 = `gpu_count`(런마다 GPU 1장). HumanEval(코드 실행 격리 채점기)과
  데이터셋을 읽는 벤치마크(custom — 데이터셋은 읽는 런에만)는 각각 따로 런, 나머지는 남은 GPU 수만큼 **예상 시간 LPT**
  (`LMEVAL_EST_SECONDS` = §11 #4 실측, 표 밖은 80초)로 고르게. 런 안 순서는 요청 순서, 같은 요청이면 같은 분배(안정
  정렬). 최소 GPU(묶음 수) 미달·**런 제한 시간 가드**(`(180 + Σ추정) × 3 > 36000` — 3B 추정 × 8B 최악 배수, 모델
  크기를 모르므로 보수적) 는 런치 전 거절. `gpu_count` 생략 = 벤치마크마다 런 하나(종전). GPU 가용 검사는 런 수 기준.
- **기록**: `eval_run_batch_member.benchmarks JSON`(런이 담은 벤치마크) — `eval_result.metric_set` 은 VARCHAR(255)라
  17개를 담으면 272자로 잘려 목록의 정본이 못 된다. `get_project.batches[].job_benchmarks`. 런치 실패는 그 런의
  벤치마크마다 `launch_failures` 에 남긴다. dev DB 는 ALTER 적용완(서빙은 테이블째 미생성 — §13 의 CREATE 에 컬럼 포함).
- **진행 노출**: `get_eval_result` 가 metrics.json 이 없을 때 `progress`(`_read_progress`: commonpath·1MB·상태
  화이트리스트·내부 경로 제거)를 싣고, `get_project` 가 끝나지 않은 런 행에 `progress`(점수 요약만, 최신 20개,
  모델당 jobs 경로 1회 조회)를 싣는다 — 카드 목록은 폴링하지 않으므로 이것이 없으면 도중에 멈춘 런이 카드에서만
  "실패"로 보인다. partial 은 영속하지 않는다(비교·Best 는 끝까지 채점한 런만).
- **FE**: 실행 설정에 **GPU 수 스테퍼**(최소 = `minRunCount` — BE 분배와 같은 규칙, 최대 = min(벤치마크 수, 빈 GPU),
  기본 = 최대). 카드·요약의 진행·상태는 **벤치마크 단위**(`entryProgressOf` — 대기 / 채점 중 / 완료 / 실패 / 취소를
  구분, 점수가 있으면 런이 도중에 멈췄어도 완료). 요약의 벤치마크 → `/run/:jobId?benchmark=<id>` — 세부 화면은 그
  벤치마크만(`focusMetrics`, "런 전체 보기"로 풀기), 도는 런·멈춘 런이면 끝난 결과를 중간 결과로 먼저 보이고, 채점기가
  실패로 적은 벤치마크는 사유를 보인다. 취소 배지 라벨 정정('생성됨' → '취소됨').
- 검증: 채점기 53 passed(+격리·전부실패·취소 통과·진행 기록 실패 무시), 파드 55/55(분배 LPT·격리·최소 GPU·시간 가드·
  GPU 검사 = 런 수·런치 실패 벤치마크 전개·데이터셋 격리·진행 읽기·카드 진행), 카탈로그 13/13(시간 상수 ↔ 매니페스트),
  FE 하네스 28/28. dev e2e — 5개(빠른 점검) GPU 2장 → 런 2개(ARC·PIQA·OBQA / KoBEST·BoolQ = LPT 예측과 같음, GPU0
  회피) → ARC 40.0·PIQA 85.0·OBQA 30.0·KoBEST 56.0051(종전 단독 런과 같은 값)·BoolQ 70.0, 요약 영어 56.25·종합 56.20.
  취소 경로 — 3개 GPU 1장, ARC-Easy 완료 직후 취소 → 런 cancelled + ARC-Easy 70.0 이 중간 결과로 남음(카드 종합 70·
  일부 실패, 세부 화면 "도중에 멈춤"). 모달 GPU 스테퍼(HumanEval 포함 5개: 기본 3 = 빈 GPU, 최소 2) 브라우저 확인.
- 3-way 리뷰(codex·기능·보안) 반영: ① 모델 비교 `compareMatrix.metricIdOf` 가 여러 토큰 metric_set 에서 제 벤치마크
  토큰을 고른다(종전엔 첫 콜론 뒤 전체를 지표로 읽어 묶음 런이 스코어카드에서 빠졌다, codex HIGH) ② 초안 테이블을
  가진 DB 용 **멱등 migration `apps/llm_evaluation/migrations/005_eval_run_batch.sql`**(두 테이블 CREATE IF NOT EXISTS +
  launch_failures·benchmarks 없으면 ADD — 서빙 반영도 이 파일, dev 무변화 적용 확인, codex HIGH) ③ metric_set 은 **토큰
  단위로** 자른다(반쪽 id 방지) ④ 세부 화면 폴링 상태를 effect 마다(런 전환 시 이전 응답이 새 화면을 덮지 않게) ⑤ 누른
  벤치마크가 아직 점수가 없으면 같은 런의 다른 결과로 채우지 않고 "채점 전 / 멈춰 채점 못 함" 을 말한다 ⑥ 채점기 오류
  문자열의 컨테이너 절대 경로를 BE 경계에서 `<path>` 로 가린다(`_redact_paths` — progress 행·failed_benchmarks, 보안 LOW).
  기능·보안 리뷰 추가 결함 없음.
- 실사용 관찰(사용자 브라우저, batch 4): 17개(전체 문항)를 GPU 3장 → 런 3개. KMMLU 가 혼자 한 런(LPT), 나머지 8+8 은
  완료(예: MMLU 72.65·GSM8K 85.44·DROP 43.96). ⚠️ GPU 가용 검사는 통과해도 **워크스페이스 네임스페이스 ResourceQuota
  (dev tango-dev-2: limits.cpu 8 · memory 160G, 잡 1개 = 1.9 CPU·39.9G)** 에 막히면 스케줄러 helm install 이 거절되고
  런은 failed 로 마감된다 — 런치 전 검사가 쿼터를 보지 않는다(기존 제약, 이번 범위 밖).

### 14.1 KMMLU 전체 OOMKilled → vLLM 요청 청크(0.1.2, 2026-09-29)

- 증상: batch 4(모델 6, 전체 문항)의 KMMLU 단독 런 파드가 채점 62분째 `OOMKilled`(exit 137, CUDA OOM 아님). 직전
  /health·/live 프로브 타임아웃. 같은 실행의 다른 두 런(MMLU 포함 8개씩)은 완료.
- 원인 ① 채점기가 `VLLM(batch_size="auto")` — lm-eval 이 로그확률 요청 **전체를 한 덩어리로** vLLM 에 넘기고
  (`vllm_causallms._loglikelihood_tokens` `get_batched(n=0)`), vLLM `generate` 는 모든 요청의 **프롬프트 전 토큰 logprob**
  (`prompt_logprobs=1`)을 다 모은 뒤에야 돌려준다 → 호스트 메모리가 벤치마크 크기에 비례(KMMLU ≈ 3.5만 문항 × 보기 4 ×
  5-shot 한국어 문맥이 최대). ② 파드 한도는 매니페스트(64Gi)가 아니라 스케줄러의 **GPU 인스턴스 번들**(GPU 1장 = 2 CPU /
  40G − 0.1 여유 → 1.9 / 39.9G, `fb_scheduler external_run._apply_instance_resource_bundle`, 쿼터 회계용 의도된 정책).
  P0 스파이크(§11)는 임시 파드라 이 한도를 밟지 않았다.
- 수정: `VLLM_BATCH_SIZE = 1024`(정수 청크) — 청크마다 파싱하고 버려 메모리가 청크 크기로 고정된다. 한도(정책)는 건드리지
  않는다. 부수효과: 정수면 lm-eval 이 vLLM 'Processed prompts' 막대를 끈다 → 진행률·취소가 lm-eval 'Running …' 막대(청크
  단위)로 거칠어진다. 이미지·매니페스트 2종·settings 0.1.2.
- 검증: 빠른 점검 5개 점수 0.1.1 과 동일(단일 청크), **여러 청크** BoolQ 전체(6,540 요청 = 7청크)·PIQA 전체가 batch 4
  (0.1.1 auto) 와 동일(84.7401 · 76.0609). KMMLU 전체(모델 2·모델 6) 파드 메모리 3.5~4.7G 에서 분당 ≈20MB — 결과는 아래.
- 곁가지(사용자 보고): 세부 화면 서브태스크 표(KMMLU 45행)가 스크롤 없이 도중에 잘림 — react-data-table-component 6.11.8 은
  fixedHeader 면 본문(.rdt_TableBody)에 max-height + overflow-y: auto 를 거는데, 공용 BorderTable 스타일
  `.bordertable .rdt_Table .rdt_TableBody { overflow: visible !important }` 가 끄고 바깥 `.result-table { overflow: hidden }` 가
  넘친 행을 자른다. 결과 화면 모듈 스타일에서만 본문 스크롤을 되살렸다(공용 규칙은 다른 화면 드롭다운 셀 때문에 유지).
  브라우저 확인: 본문 2160px 을 360px 창에서 스크롤, 머리 행 유지, 45번째 행 도달.
- §14.1 결과: KMMLU 전체 **모델 2 = 35.2241**(35,030문항, 3,978초, 컨테이너 메모리 최고 7.67G) · **모델 6(OOM 난 그 모델) =
  49.9372**(35,030문항, 5,096초, 최고 9.17G) — 둘 다 한도 39.9G 의 1/4 이하로 완주. 청크 비용은 3B 실측(청크 없음 3,884초) 대비
  ≈2%. batch 8(모델 6: KMMLU + BoolQ·PIQA)이 batch 4 의 빠진 KMMLU 를 채운다.
- 결과 화면 머리 정리(사용자 요청): 실행 요약 머리 줄 = 모델·체크포인트·생성 일시만(벤치마크 수·런 수·빠른 점검 문구·엔진·설명
  줄 제거 — 진행 카드·빠른 점검 배지·세부 화면 채점 구성에 이미 있다). 실채점·mock 배지는 실행 요약(머리·벤치마크 행)과 세부 화면
  머리에서 제거. 카드 목록·비교 화면의 mock 배지는 이력 속 해시 점수 구분용으로 유지.
