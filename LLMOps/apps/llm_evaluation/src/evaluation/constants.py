"""llm_evaluation 공용 상수."""

# lm-eval 채점 벤치마크 — 기본 채점기(manifest key "BENCHMARK" = evaluate-lmeval)가
# lm-evaluation-harness 로 실제 채점하는 집합(+ 런 데이터셋 생성 평가 custom).
# 2026-09-28 이전에는 evaluate-benchmark-mock 이 해시 점수를 내던 9 종이었다 — 기존 id 는
# 이력·비교표가 averages 의 키로 쓰므로 그대로 두고 lm-eval 태스크로 매핑했다
# (컨테이너 apps/evaluate_lmeval/registry.py 가 id ↔ 태스크 정본이다).
# ⚠️ humaneval 은 여기 없다 — 모델 생성 코드를 실행해 채점하므로 격리된 전용 채점기
#    (BENCHMARK_CODE)로 간다. 아래 REAL_BENCHMARK_MANIFEST_KEY 참고.
LMEVAL_BENCHMARK_IDS = (
    "arc", "kobest", "mmlu", "hellaswag", "winogrande",
    "gsm8k", "truthfulqa", "boolq",
    "arc_easy", "piqa", "openbookqa", "kmmlu", "kmmlu_direct", "haerae",
    "squadv2", "truthfulqa_gen", "drop",
    "custom",
)

# 실채점 벤치마크 → 전용 채점 컨테이너. 벤치마크마다 필요한 런타임이 달라(LogicKor 는
# 심판 LLM + transformers 5.5.4 핀) 한 컨테이너가 전부 채점할 수 없다. 한 런은 컨테이너
# 하나로 가므로 서로 다른 채점기의 벤치마크를 한 런에 섞을 수 없다(service 가 거부).
# 여기 없는 벤치마크(LMEVAL_BENCHMARK_IDS)는 기본 키 "BENCHMARK" 로 간다.
REAL_BENCHMARK_MANIFEST_KEY = {
    # 모델 생성 코드를 실행해 채점한다(pass@1). evaluate-lmeval 과 같은 이미지지만 코드 실행을
    # 켠 매니페스트(evaluate-lmeval-code)로 분리해 단독 런·격리 파드에서만 돈다.
    "humaneval": "BENCHMARK_CODE",
    "logickor": "LOGICKOR",
    # MixATIS 다중의도·슬롯. LogicKor 와 달리 심판 LLM 이 없고 정답(BIO 태그 + 의도 라벨)이
    # 데이터에 있어 지표가 결정론적이다 — 같은 체크포인트면 항상 같은 값이 나온다.
    "mixatis": "MIXATIS",
}

# 체크포인트가 **필수**인 채점기. LogicKor 는 체크포인트 없이 데이터셋의 기존 생성물을
# 채점하는 경로가 있어 optional 이지만, MixATIS 채점기는 평가할 가중치가 없으면 기동
# 직후 거부한다(evaluate_intent/app.py `_resolve_checkpoint`). BenchmarkRunBody 의
# commit_id 는 전 벤치마크 공통이라 optional 일 수밖에 없어, 필수 여부를 여기서 좁힌다.
# ⚠️ 2026-08-27 부터 **참조되지 않는다**. 벤치마크 생성이 언제나 배포 위임이 되면서
# (run_benchmark 이 inference_playground_id 를 필수로 요구) 컨테이너가 마운트할 체크포인트
# 자체가 필요 없어졌다 — 상수는 채점기 쪽 사실(evaluate_intent 는 가중치 없이는 못 뜬다)의
# 기록으로 남긴다. 체크포인트 경로를 되살리면 가드도 함께 복원해야 한다.
CHECKPOINT_REQUIRED_MANIFEST_KEYS = ("MIXATIS",)

# 형식(출력 규약) 학습을 **평가 전에 같은 잡에서** 돌릴 수 있는 채점기. UGEN 처럼 정답을
# 고정 형식으로 생성해야 채점되는 벤치마크는 형식을 배우지 않은 가중치로 재면 내용을 알아도
# 0 점이 나온다(MixATIS 실측: zero-shot 형식 준수 0/828 · joint_acc 0.0 → 발화 1500 을
# 1 에폭 태우면 0.4855). evaluate-intent 0.2.0+ 가 `train` 파라미터로 그 단계를 갖고 있다.
#
# ⚠️ 포맷 학습은 **배포 위임과 배타**다. 학습 산출물은 채점기가 로컬에 올린 모델에 얹는
#    LoRA 어댑터라 원격 배포에 붙일 통로가 없다 — 컨테이너도 `generate_base_url` 이 있으면
#    학습을 스스로 건너뛴다(evaluate_intent/app.py:376). 그래서 이 경로를 켜면 서비스가
#    generate_base_url 을 싣지 않고 checkpoint_name 을 대신 넘긴다(run_benchmark).
# ⚠️ 그 결과 이 경로는 위 CHECKPOINT_REQUIRED_MANIFEST_KEYS 를 **다시 살린다** — 체크포인트
#    없이는 학습할 대상이 없다. 다만 요청은 commit_id 를 받지 않으므로(dto tombstone) 이름은
#    고른 배포가 서빙 중인 커밋에서 역으로 푼다(_resolve_deployment_checkpoint).
FORMAT_TRAIN_MANIFEST_KEYS = ("MIXATIS",)

# 포맷 학습 레시피 — 값은 evaluate-intent 학습 파라미터로 params 에 그대로 실린다
# (train.py `train_examples`(0=train split 전체)·`train_epochs`, `use_4bit` 은 학습·평가 양쪽).
#   full  : ETRI Intent_web `run_experiment.sh full` 과 같은 학습량·정밀도 — 발화 13,162
#           (예제 26,324) × 3 에폭 × QLoRA 4bit. README 의 Joint 67.03% 가 이 조건의 값이다.
#   quick : 형식만 잡는 경량 점검 — 발화 1,500 × 1 에폭 × bf16(컨테이너 기본값, joint 0.4855 실측).
# 기본이 full 인 이유: 원 실험 수치와 비교할 수 있는 쪽이 기본이어야 한다 — quick 은 학습량이
# 약 26 배 적어(188 vs 4,936 스텝) 그 수치와 나란히 놓으면 성능 결함으로 오독된다.
# ⚠️ full 은 GPU 1장을 수 시간 잡는다 → 매니페스트 timeout 을 그에 맞춰 둔다(evaluate-intent 0.2.5).
# ⚠️ ETRI 와 같은 것은 학습량·정밀도까지다. 유효 배치는 16 으로 같지만 분할(컨테이너 8×2 /
#    ETRI 2×8)과 옵티마이저(adamw_torch / paged_adamw_8bit)는 다르다 — 수치가 완전히 같지는 않다.
FORMAT_TRAIN_RECIPES = {
    "full": {"train_examples": 0, "train_epochs": 3.0, "use_4bit": True},
    "quick": {"train_examples": 3000, "train_epochs": 1.0, "use_4bit": False},
}
DEFAULT_FORMAT_TRAIN_RECIPE = "full"

# 배포 위임이 **구조적으로 불가능한** 채점기 — 생성 경로를 로컬 가중치로 되돌린다.
# lm-eval 객관식 태스크는 보기별 로그확률로 채점하는데, 배포 shim(llm_playground
# openai_chat_completions)은 비스트리밍 chat/completions 만 있고 logprobs·stop·max_tokens 를
# 전달하지 못한다(서빙 파드는 배포 시점 SamplingParams 하나로 돈다). 그래서 이 채점기로 가는
# 런은 포맷 학습 경로와 같은 방식으로 **고른 배포가 서빙 중인 커밋 이름**을 풀어
# checkpoint_name 으로 넘기고, 컨테이너가 그 가중치를 GPU 한 장에 올린다
# (service._resolve_deployment_checkpoint). 배포가 가중치의 정본이라는 불변식은 그대로다.
LOCAL_WEIGHTS_MANIFEST_KEYS = ("BENCHMARK", "BENCHMARK_CODE")

# 런 데이터셋을 **읽지 않는** 벤치마크 — 문항이 채점 이미지에 구워져 있다(evaluate_lmeval
# prepare_tasks). 이것만으로 된 런은 데이터셋 없이 시작한다(마운트 없음, eval_result.dataset_id
# NULL). 데이터셋 선택을 요구하면 결과 머리에 채점에 쓰지 않은 데이터셋 이름이 찍힌다.
# custom 은 데이터셋이 곧 평가 문항이라 빠진다. MixATIS·LogicKor 는 이 판정 밖이라
# 종전대로 데이터셋을 요구한다(보수적 기본값 — 풀려면 채점기 쪽 사실을 먼저 확인한다).
DATASET_FREE_BENCHMARK_IDS = tuple(
    b for b in LMEVAL_BENCHMARK_IDS if b != "custom") + ("humaneval",)

# 벤치마크 정본(21) — id = FE benchmarks.js + 채점 컨테이너와 일치(tests/test_benchmark_catalog.py). 벤치마크
# = 표준 평가 태스크(ARC·MMLU…). "벤치마크 선택 → 벤치마크별 메트릭" 2단계의 1단계 후보다.
BENCHMARK_IDS = LMEVAL_BENCHMARK_IDS + tuple(REAL_BENCHMARK_MANIFEST_KEY)

# 벤치마크 → 평가 유형(EVAL_TYPES). 위의 mock/real 과는 **다른 축**이다: mock/real 은
# "어느 채점 컨테이너로 보내는가"(배선), 이건 "점수를 누가 매기는가"(사용자에게 보이는 축).
# 두 축이 교차한다 — mixatis 는 전용 컨테이너(real)로 가지만 정답이 데이터에 있어
# reference 고, logickor 는 같은 real 이면서 심판 LLM 이 점수를 낸다. 하나로 합치면 새
# 채점기가 붙을 때마다 사용자에게 보이는 유형이 흔들린다.
# ⚠️ FE benchmarks.js 의 벤치마크 목록과 같은 집합이어야 한다.
# ⚠️ MT-Bench 는 채점기가 없어 여기에도, FE 에도 없다(있으면 고를 수는 있는데 못 돌린다).
BENCHMARK_EVAL_TYPE = {
    "arc": "reference", "kobest": "reference", "mmlu": "reference",
    "hellaswag": "reference", "winogrande": "reference", "gsm8k": "reference",
    "truthfulqa": "reference", "boolq": "reference", "humaneval": "reference",
    "mixatis": "reference",
    "arc_easy": "reference", "piqa": "reference", "openbookqa": "reference",
    "kmmlu": "reference", "kmmlu_direct": "reference", "haerae": "reference",
    "squadv2": "reference", "truthfulqa_gen": "reference", "drop": "reference",
    # 런 데이터셋의 정답과 생성 결과를 대조한다(F1/EM/BLEU/ROUGE).
    "custom": "reference",
    # 정답이 없다(references=null) — 심판 LLM 점수가 유일한 채점 축이다.
    "logickor": "judge",
}

# 유형별 벤치마크 집합 — run 이 프로젝트 유형과 같은 축의 벤치마크만 골랐는지 검증할 때,
# 그리고 거절 메시지의 '지정 가능' 목록으로 쓴다. BENCHMARK_IDS 를 돌며 만드는 이유는
# 정본(BENCHMARK_IDS)에 있는데 위 표에 빠진 벤치마크가 있으면 **import 시점에** KeyError
# 로 드러나게 하려는 것이다(런타임에 조용히 유형 없는 벤치마크가 생기는 것을 막는다).
REFERENCE_BENCHMARK_IDS = tuple(
    b for b in BENCHMARK_IDS if BENCHMARK_EVAL_TYPE[b] == "reference")
JUDGE_BENCHMARK_IDS = tuple(
    b for b in BENCHMARK_IDS if BENCHMARK_EVAL_TYPE[b] == "judge")

# 벤치마크 런(run_benchmark)을 시작할 수 있는 프로젝트 유형. reference 와 judge 는 런치
# 경로가 같고(같은 외부 컨테이너) 다른 것은 채점 주체뿐이라 한 함수를 공유한다 — 그래서
# 프로젝트 유형만으로는 무엇을 채점하는지가 정해지지 않고, 벤치마크 목록과 대조해야 한다.
# 표의 값에서 파생해 유형을 늘릴 때 두 곳을 고치지 않게 한다.
BENCHMARK_EVAL_TYPES = tuple(dict.fromkeys(BENCHMARK_EVAL_TYPE.values()))

# 요청에서 benchmarks 를 생략했을 때 채점할 기본 집합 — mock 시절의 기존 id 중 기본
# 채점기(BENCHMARK)로 가는 8 종. FE 는 언제나 벤치마크를 하나 골라 보내므로 이 기본값은
# 서비스 직접 호출 경로에서만 쓰인다.
# ⚠️ humaneval 을 넣으면 안 된다 — 다른 채점기(BENCHMARK_CODE)라 기본 집합 자체가 채점기
#    혼재 거부에 걸린다. custom 도 뺀다(데이터셋에 정답이 없으면 실패한다).
# ⚠️ 전부 reference 유형이다. judge 프로젝트가 벤치마크를 생략하면 기본값을 쓸 수 없고,
#    service 가 명시를 요구하며 거절한다 — 조용히 다른 축을 채점해 버리지 않도록.
DEFAULT_BENCHMARK_IDS = ("arc", "kobest", "mmlu", "hellaswag", "winogrande",
                         "gsm8k", "truthfulqa", "boolq")

# 메트릭 정본(11) — 벤치마크와 분리된 채점 방식. id = FE benchmarkMetrics.js + 채점기 일치.
# judge_* 3종은 LogicKor 전용 심판 점수(1~10). LogicKor 는 정답이 없어(references=null)
# accuracy/f1 계열을 계산할 수 없고 심판 LLM 점수가 유일한 채점 축이다. 셋의 차이는
# 대표 스칼라를 어느 축으로 잡느냐(전체/1턴/2턴)일 뿐이고 전체 결과는 항상 함께 산출된다.
METRIC_IDS = (
    "accuracy", "f1", "acc_norm", "bleu", "rouge", "meteor", "cider", "spice",
    "judge_overall", "judge_single", "judge_multi",
    # mixatis 전용 4종. 의도·슬롯이 서로 다른 단위(발화 / 항목 / 쌍)로 채점돼 기존
    # accuracy·f1 로는 어느 축인지 구분이 안 된다. 넷은 항상 함께 산출되고 metric 은
    # results[].score 에 실릴 대표 축만 고른다(judge_* 3종과 같은 규약).
    "intent_acc", "intent_f1", "slot_f1", "joint_acc",
    # lm-eval 생성형 태스크의 정확 일치(kmmlu_direct)와 코드 통과율(humaneval pass@1).
    # 둘 다 0~100 으로 싣는다.
    "exact_match", "pass_at_1",
)

# 벤치마크별 권장 메트릭(생략 시 채택) — FE 기본 선택·채점기 기본값과 공유(단일 소스).
BENCHMARK_RECOMMENDED_METRIC = {
    "arc": "accuracy", "kobest": "f1", "mmlu": "accuracy", "hellaswag": "acc_norm",
    "winogrande": "accuracy", "gsm8k": "accuracy", "truthfulqa": "accuracy",
    "boolq": "accuracy",
    # 코드 통과율은 정확도가 아니다 — mock 시절 accuracy 였던 것을 pass@1 로 바로잡는다.
    "humaneval": "pass_at_1",
    "arc_easy": "acc_norm", "piqa": "acc_norm", "openbookqa": "acc_norm",
    "kmmlu": "accuracy", "kmmlu_direct": "exact_match", "haerae": "acc_norm",
    "squadv2": "f1", "truthfulqa_gen": "bleu", "drop": "f1", "custom": "f1",
    "logickor": "judge_overall",
    # Joint = 의도집합 AND 슬롯집합 완전일치. 태스크의 최종 난이도 지표라 대표축으로 둔다.
    "mixatis": "joint_acc",
}

# 벤치마크별 산출 가능 메트릭 — 채점기가 그 벤치마크에서 계산할 수 있는 축의 집합.
# ⚠️ 2026-08-26 이후 이 표는 **입력 검증에 쓰이지 않는다**. 요청이 메트릭을 고르지 않게
# 바뀌었고(대표 스칼라는 항상 BENCHMARK_RECOMMENDED_METRIC), 채점기는 어차피 한 벤치마크의
# 전 지표를 함께 계산하므로 '허용 밖 조합'이라는 입력 자체가 존재하지 않는다.
# 남겨 두는 이유: 어떤 축이 실제로 산출되는지의 문서이자 FE 표시 목록(benchmarks.js 의
# 벤치마크별 metrics)의 정본 대조표다 — 결과 화면이 없는 축을 그리지 않도록.
BENCHMARK_ALLOWED_METRICS = {
    # lm-eval 이 실제로 내는 축(2026-09-28 교체 — mock 시절 표는 해시 채점기 기준이었다).
    "arc": ("accuracy", "acc_norm"),
    "kobest": ("f1", "accuracy"),
    "mmlu": ("accuracy",),
    "hellaswag": ("acc_norm", "accuracy"),
    "winogrande": ("accuracy",),
    "gsm8k": ("accuracy",),
    "truthfulqa": ("accuracy",),
    "boolq": ("accuracy",),
    "humaneval": ("pass_at_1",),
    "arc_easy": ("acc_norm", "accuracy"),
    "piqa": ("acc_norm", "accuracy"),
    "openbookqa": ("acc_norm", "accuracy"),
    "kmmlu": ("accuracy",),
    "kmmlu_direct": ("exact_match",),
    "haerae": ("acc_norm", "accuracy"),
    "squadv2": ("f1", "exact_match"),
    "truthfulqa_gen": ("bleu", "rouge"),
    "drop": ("f1", "exact_match"),
    "custom": ("f1", "exact_match", "bleu", "rouge"),
    "logickor": ("judge_overall", "judge_single", "judge_multi"),
    "mixatis": ("joint_acc", "intent_acc", "intent_f1", "slot_f1"),
}

# 한 벤치마크 런이 다룰 벤치마크 상한 — metric_set 요약 컬럼(VARCHAR 255) 초과·과도 태스크 방지.
MAX_BENCHMARK_ITEMS = 20

# ── 묶음 실행 분배(GPU 수만큼 런을 나눠 벤치마크를 담는다 — service.plan_benchmark_runs) ──
# 벤치마크별 예상 채점 시간(초) — P0 실측(3B, A100 80GB, 전체 문항, 설계 §11 #4). 절대값이 아니라
# **런끼리 짐을 고르게 나누는 무게**로 쓴다(한 런에 KMMLU 와 MMLU 가 같이 들면 벽시계가 길어진다).
# 표에 없는 벤치마크는 실측 80초 미만이었다(기본값). custom 은 데이터셋 크기에 달려 추정이 없다.
LMEVAL_EST_SECONDS = {
    "kmmlu": 3884, "mmlu": 1886, "hellaswag": 1632, "kmmlu_direct": 583, "drop": 493,
    "truthfulqa_gen": 459, "kobest": 244, "arc": 241, "squadv2": 196,
}
LMEVAL_EST_DEFAULT_SECONDS = 80
# 런 하나의 고정비 — 가중치 병합·vLLM 기동. evaluate-lmeval 매니페스트 estimated_startup_seconds 와
# 같다. 런 타임아웃도 그 매니페스트의 timeout_seconds 다(tests/test_benchmark_catalog.py 가 대조한다).
LMEVAL_STARTUP_SECONDS = 180
LMEVAL_RUN_TIMEOUT_SECONDS = 36000
# 위 추정은 3B 기준이다 — 8B 는 2~3 배(P0). 모델 크기를 알 수 없으므로 최악 배수를 곱한 추정이
# 타임아웃을 넘는 분배는 런치 전에 거절한다(넘치면 파드가 도중에 죽고 남은 벤치마크는 실패한다).
LMEVAL_WORST_SLOWDOWN = 3

# 로컬 가중치 채점기(LOCAL_WEIGHTS_MANIFEST_KEYS)의 태스크당 문항 상한(빠른 점검용). 비우면
# 전체. 준 점수는 분모가 달라 전체 측정과 나란히 비교하면 안 되므로 컨테이너가
# metrics.lmeval.limit 에 새기고 FE 가 구분해 보인다.
BENCHMARK_SAMPLE_LIMIT_MIN = 1
BENCHMARK_SAMPLE_LIMIT_MAX = 100000

# ── 벤치마크 생성을 '빌린 배포'로 돌릴 때(inference_playground_id) ──────────────
# 예전에는 이 서비스가 HTTP 핸들러 안에서 인라인으로 생성한 뒤 params.samples 로 넘겼고,
# 그 예산 상수(BENCHMARK_INLINE_GEN_SECONDS=240 / BENCHMARK_GEN_CONCURRENCY=4)가 여기 있었다.
# 지금은 배포의 OpenAI shim base 를 params.generate_base_url 로 넘겨 **컨테이너가** 그 배포를
# 호출한다 — 핸들러가 아무것도 붙들지 않으므로 예산도, Kong 60s 와의 경쟁도 없어져 두 상수를
# 지웠다. 인라인으로 되돌릴 일이 생기면 run_benchmark docstring 의 '왜 위임인가'를 먼저 읽어라
# (프롬프트 조립이 컨테이너 소유라는 것이 핵심 제약이다).

# ── 실채점 컨테이너 실행 옵션(LogicKor) ──────────────────────────────────────
# 컨테이너가 실제로 읽는 파라미터만 노출한다(evaluate_logickor_judge app.py 의 params.get).
# ⚠️ seed 는 의도적으로 없다 — 생성(generate.py temperature=0)·심판(judge.py temperature=0.0)
#    둘 다 greedy 디코딩이라 시드가 바꿀 난수가 존재하지 않는다. 노브를 만들면 아무 것도
#    하지 않는 컨트롤이 된다. 런 간 변동을 보려면 컨테이너 샘플링부터 바꿔야 한다.
# ⚠️ hf_token 도 컨테이너가 받지만 시크릿이라 이 경로로 넘기지 않는다(secrets 계약 별도).
# ⚠️ use_latest_checkpoint 는 commit_id(체크포인트 선택)와 같은 것을 두 가지 방법으로
#    지정하게 만들어 노출하지 않는다.

# 프롬프트 전략 — ETRI 원본 templates.PROMPT_STRATEGY 키와 같은 집합이어야 한다.
LOGICKOR_STRATEGIES = ("default", "1-shot", "cot-1-shot")

# 컨텍스트 길이 — vLLM max_model_len 으로 그대로 들어간다. 너무 작으면 프롬프트가 잘리고
# 카드 메모리를 넘기면 컨테이너 기동 자체가 실패하므로 양쪽을 다 막는다.
LOGICKOR_MODEL_LEN_MIN = 512
LOGICKOR_MODEL_LEN_MAX = 32768

# 심판 1회 출력 상한(토큰). 너무 낮으면 평가문이 잘려 점수 파싱이 실패한다(metrics.judge
# 의 unscored 로 드러난다).
LOGICKOR_JUDGE_MAX_OUTPUT_MIN = 64
LOGICKOR_JUDGE_MAX_OUTPUT_MAX = 8192

# 심판 모델 화이트리스트 — 플랫폼이 고를 수 있는 심판의 정본. FE 는 이 표를
# /evaluations/benchmark/judge-models 로 받아 그리기만 한다(하드코딩 금지).
#
# 자유 입력을 받지 않는 이유: 채점 컨테이너는 HF_HUB_OFFLINE=1 로 뜨고 /hf-cache 는
# 읽기전용이다. 캐시에 없는 모델은 이름이 아무리 정확해도 GPU 를 잡고 수 분 뒤 기동
# 단계에서 죽는다. 고를 수 있는 것만 보여주는 게 유일하게 정직한 화면이다.
# allowlist 라서 경로 주입(절대경로·'..') 방어도 정규식이 아니라 멤버십으로 끝난다.
#
# 컨테이너에 넘기는 값은 id 가 아니라 **hf_id** 다 — judge.resolve_judge_model 이 모르는
# 값을 그대로 통과시키므로 컨테이너의 JUDGE_MODEL_PRESETS 에 없어도 로드된다. 덕분에
# 심판을 늘릴 때 이미지를 다시 빌드할 필요가 없다(캐시 적재 + 이 표에 한 줄).
#
# ⚠️ 여기 한 줄 늘리기 전에 반드시 캐시에 적재할 것. 그 순서를 강제하려고
#    Evaluation/serve/fetch_judge_models.py 가 **이 표를 읽어** 내려받는다.
# ⚠️ size_gb 는 대략적인 가중치 크기다. 채점 컨테이너 예산은 gpu_memory 64Gi(A100 80GB
#    한 장, gpu_memory_utilization 0.8)라 KV 캐시까지 감안하면 14B(~28GB)가 상한선이다.
#    32B bf16(~64GB)은 가중치만으로 예산을 다 먹으므로 넣지 않는다.
LOGICKOR_JUDGE_MODELS = (
    {"id": "gemma", "hf_id": "google/gemma-4-E4B-it",
     "label": "Gemma 4 E4B Instruct", "size_gb": 15},
    {"id": "qwen3-14b", "hf_id": "Qwen/Qwen3-14B",
     "label": "Qwen3 14B", "size_gb": 28},
    {"id": "qwen2.5-14b", "hf_id": "Qwen/Qwen2.5-14B-Instruct",
     "label": "Qwen2.5 14B Instruct", "size_gb": 28},
    {"id": "exaone3.5-7.8b", "hf_id": "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct",
     "label": "EXAONE 3.5 7.8B Instruct", "size_gb": 16},
)

# 컨테이너 기본 심판(judge.DEFAULT_JUDGE_MODEL)과 같아야 한다 — FE 가 초기 선택으로 쓴다.
LOGICKOR_DEFAULT_JUDGE_ID = "gemma"

LOGICKOR_JUDGE_MODEL_IDS = tuple(m["id"] for m in LOGICKOR_JUDGE_MODELS)
LOGICKOR_JUDGE_HF_ID = {m["id"]: m["hf_id"] for m in LOGICKOR_JUDGE_MODELS}


# 한 벤치마크 런이 다룰 데이터셋 상한 — dataset_name CSV 가 eval_result.dataset_name
# VARCHAR(255) 를 넘지 않도록(+ 과도한 멀티마운트 방지).
MAX_BENCHMARK_DATASETS = 10


# ── 외부 심판 제공자 — 지금은 **읽는 코드가 없다**(휴면 자산) ─────────────────
# 2026-08-27: 자유 샘플 + 기준 4종(정확·관련·유창·안전) LLM-as-a-Judge 는 제품에서
# 없앴다(JUDGE_CRITERIA / MAX_JUDGE_SAMPLES / MAX_JUDGE_RUN_SECONDS 도 함께 삭제).
# 'judge' 유형은 이제 **표준 심사 벤치마크**(LogicKor)를 뜻하고, 그 심판은 플랫폼 안
# (채점 컨테이너 또는 우리가 조립한 배포 URL)에서 돌아 상용 API 키를 쓰지 않는다.
#
# 그런데도 아래 세 표를 남기는 이유: 이건 "사용자 키를 상용 제공자에 들려 보낼 때
# **호스트를 우리가 고정한다**"는 방어의 정본이다. provider 이름만 받고 URL 은 절대 받지
# 않으므로, 키가 엉뚱한 호스트로 새거나 리다이렉트에 끌려가는 SSRF 경로가 애초에 생기지
# 않는다. 예정된 '외부 API 배포' 작업이 같은 문제를 그대로 다시 만나므로 그때 이 표를
# 배포 표면으로 옮긴다 — 지금 지우면 그 방어를 처음부터 다시 짜게 된다.
# ⚠️ 되살릴 때 함께 복원할 규약: 키는 헤더로만 전달(URL 쿼리 금지 — 예외/액세스로그 노출),
#    모델명은 URL 경로에 보간하기 전에 인코딩, local 은 service._validate_local_url 로 검증.
JUDGE_PROVIDERS = ("chatgpt", "claude", "gemini", "local")

# 상용 provider egress 화이트리스트(호스트 고정 — 사용자 입력은 키뿐, 호스트는 우리가 고정해
# 키 유출/리다이렉트 SSRF 방지).
JUDGE_PROVIDER_HOSTS = {
    "chatgpt": "api.openai.com",
    "claude": "api.anthropic.com",
    "gemini": "generativelanguage.googleapis.com",
}
JUDGE_DEFAULT_MODEL = {
    "chatgpt": "gpt-4o",
    "claude": "claude-opus-4-8",
    "gemini": "gemini-2.0-flash",
}

# ── 전문가 평가 (P3) ──────────────────────────────────────────────────────────
# 한 세션이 사람에게 보여줄 샘플 상한 = 데이터셋 전량 리뷰 의도(런어웨이 방지 안전 ceiling).
MAX_EXPERT_SAMPLES = 1000

# 전문가 평가 세트 — 공인시험은 평가자가 여러 명이라 각자 다른 100문항을 맡는다. 1k 데이터셋을
# 앞에서부터 100개씩 10구간으로 미리 나눠 두고(세트 N = [ (N-1)*100, N*100 )) 카드마다 하나를
# 고른다. 무작위가 아니라 고정 구간인 이유는 "누가 어느 문항을 봤는가"가 재현돼야 하기 때문.
# ⚠️ FE 상수(ExpertInferenceModal.SAMPLE_SET_*)와 같은 값이어야 한다 — 어긋나면 라벨의 구간과
#    실제 채점 구간이 달라진다.
EXPERT_SAMPLE_SET_SIZE = 100
EXPERT_SAMPLE_SET_COUNT = 10

# 점수 체계(D2) — 단일 1~5 별점. score_json 은 무스키마 확장 지점(다기준/구조화 피드백,
# 플라이휠 선호도쌍). 서비스에서 범위 검증(기존 O/X 화이트리스트 미러).
EXPERT_SCORE_MIN = 1
EXPERT_SCORE_MAX = 5
# score→verdict 파생 임계 — verdict VARCHAR(8) NOT NULL 을 보존하고 get_expert_result 의
# verdict=="O" 카운팅·레거시 pass_rate 경로가 계속 유효하도록 score 에서 파생 기록한다.
# ⚠️ 임계 4(=4·5 를 합격) 는 잠정값 — 검토 대상(도메인에 따라 3 이상으로 조정 가능).
EXPERT_VERDICT_PASS_THRESHOLD = 4
# score_json 직렬화 길이 상한(무스키마라 남용 방지 — 입력 경계 검증).
EXPERT_SCORE_JSON_MAX_LEN = 4096

# 시나리오 결속 고정 프롬프트(D3) — 사용자 입력 없음. SDS(선박 도메인)는 전용 프롬프트,
# 그 외 데이터셋은 일반 기본값. 세션에 결속(빌더가 샘플 shape 로 시나리오 판별).
EXPERT_PROMPT_SDS = (
    "아래는 선박 운항 상황 이미지와 계측 데이터(표)를 바탕으로 모델이 생성한 조언입니다. "
    "조언이 상황에 비추어 정확하고 안전하며 실무에 유용한지 1~5점으로 평가해 주세요. "
    "(1 = 매우 부적절, 5 = 매우 우수)"
)
EXPERT_PROMPT_DEFAULT = (
    "아래 입력에 대한 모델 출력의 품질(정확성·적절성·유용성)을 1~5점으로 평가해 주세요. "
    "(1 = 매우 미흡, 5 = 매우 우수)"
)

# 생성 시스템 프롬프트(헤더 고정 박스) 표시원 — SDS external eva-vlm 폴백. eva-vlm(external)은
# 내부 vLLM 처럼 조회 가능한 prompt.system_message 가 없고 /info 는 output_type 이름만 노출한다.
# 그래서 SDS 전문가 세션은 eva-vlm 이 custom_prompt 미전달 시 실제 쓰는 프롬프트(PROMPT_MAP
# '한글 항해조력메시지', 실측 yvvyee/eva-vlm-backend:1.1.0 model_manager.py:34)를 미러한다 →
# 표시=실사용 일치. (custom_prompt 를 넘기면 그게 우선하고 이 상수는 미사용.)
SDS_GEN_SYSTEM_PROMPT = (
    "제공된 카메라 이미지와 AIS 데이터를 기반으로 COLREG 규칙에 따른 "
    "자선의 항해 조력 메시지를 제공하시오."
)

# SDS 데이터셋 레이아웃 규약(실측) — 샘플당 서브디렉토리 tango_sds-*/ 에
# input_data.csv(표) + input_image.png(멀티모달) + output_*.txt(참조 출력)를 담는다.
# 디렉토리-워크 빌더가 이 규약으로 디렉토리 1개=샘플 1개를 만든다.
SDS_SAMPLE_DIR_GLOB = "tango_sds-*"
EXPERT_CSV_FILENAME = "input_data.csv"
EXPERT_IMAGE_FILENAME = "input_image.png"
EXPERT_OUTPUT_GLOB = "output_*.txt"
# reference 로 우선 채택할 output 파일(없으면 정렬상 첫 output_*.txt).
EXPERT_REFERENCE_FILENAME = "output_advice_kor.txt"

# ── 평가 추론 러너 (generate phase) ──────────────────────────────────────────
# 한 평가 추론 런이 생성할 최대 샘플 수(전량 batch 상한 — 장시간/타임아웃·metrics JSON 비대 방지).
# judge/expert 의 20/1000 캡과 달리 러너는 데이터셋 전량 지향이라 크게 잡되 상한은 둔다. 초과분 truncate.
MAX_EVAL_SAMPLES = 200

# 전용 배포 할당 시 status-sync running 대기 폴링 상한(2s 간격 → ~10분, pipeline 동형).
EVAL_DEPLOY_MAX_POLLS = 300

# 러너 generate 전체 wall-clock 상한(초) — hung/느린 배포가 GPU(전용 할당)를 무한 점유하지
# 않도록. expert(_EXPERT_INFER_BUDGET 90)와 동일 취지이나 전량 batch(≤MAX_EVAL_SAMPLES)
# 라 크게 잡는다. 초과 시 런=failed + (할당형) teardown.
EVAL_INFER_RUN_SECONDS = 3600

# ── 교차모델 비교 (④ 경량 뷰) ──────────────────────────────────────────────────
# 한 비교 뷰가 합칠 모델 상한(표 가독성 + 모델별 get_model/list_eval_results N쿼리 가드).
MAX_COMPARE_MODELS = 6

# ── 런 단위 비교 (모델 축 → 런 축) ──────────────────────────────────────────────
# 한 비교 뷰가 합칠 **런** 상한. 모델 축(MAX_COMPARE_MODELS 6)보다 크게 잡는 이유는 한
# 모델이 체크포인트마다 런을 남겨 후보 자체가 모델보다 훨씬 촘촘하기 때문(ckpt1..ckptN 을
# 나란히 보는 게 이 축의 목적). 다만 선택 런은 한 번의 IN 조회로 읽으므로 모델 축과 달리
# 상한이 쿼리 수가 아니라 표의 열 수와 IN 절 크기를 제한한다.
MAX_COMPARE_RUNS = 20

# ── 평가 프로젝트 관리 (2026-07-07) ────────────────────────────────────────────
# 프로젝트 = 관리 단위(모델·데이터셋·유형·이름 잠금, 1:N run). 유형은 생성 시 확정·불변
# 이며 run-start 시 프로젝트 유형과 일치해야 한다(교차유형 run 생성 차단).
#
# 2026-08-27: 구 'benchmark' 를 **채점 주체** 기준으로 둘로 쪼갰다. 한 유형 안에 정답이
# 데이터에 있어 결정론적으로 채점되는 것과 심판 LLM 이 점수를 매기는 것이 섞여 있었고,
# 결과 화면에서는 둘 다 그냥 숫자라 "이 점수가 무엇으로 나왔나"를 사후에 구분할 방법이
# 없었다(비교표에서 그대로 나란히 놓였다).
#   reference = 정답 대조 평가(구 benchmark) — REFERENCE_BENCHMARK_IDS
#   judge     = LLM 심사(표준 심사 벤치마크 전용) — JUDGE_BENCHMARK_IDS
#   expert    = 전문가 평가(사람이 채점, 변경 없음)
# ⚠️ 옛 값 'benchmark' 로 오는 요청은 dto 가 안내와 함께 422 로 거절한다(pydantic 기본
#    extra=ignore 로 조용히 무시되면 사용자가 고른 적 없는 유형의 프로젝트가 생긴다).
EVAL_TYPES = ("reference", "judge", "expert")

# 프로젝트 설명 상한 — eval_project.description 의 VARCHAR(5000) 과 **같은 값**이어야
# 한다. 상수로 뽑는 이유는 dto(경계 422)와 service(방어 검증) 두 곳이 같은 숫자를 봐야
# 하기 때문이다. 크게 잡으면 초과분이 거절 대신 DB 에서 조용히 잘려 사용자가 쓴 글이
# 사라진다. 길이 자체는 배포(playground.description)와 맞췄다 — 같은 카드 본문 값이다.
EVAL_PROJECT_DESCRIPTION_MAX = 5000

# 프로젝트 상태(created=구성만 확정·run 0 / running=run 존재 / completed=집계 마감).
PROJECT_STATUS_CREATED = "created"
PROJECT_STATUS_RUNNING = "running"
PROJECT_STATUS_COMPLETED = "completed"

# ── 이력 관리 ────────────────────────────────────────────────────────────────
# 'running' 으로 방치된 벤치마크 런을 실패로 간주하는 나이 임계(시간). 컨테이너
# 파드 크래시나 폴러 재시작으로 완료 콜백이 유실되면 런이 running 에 영구 고착되는데,
# eval_result 엔 updated_at 이 없어(create_datetime 만) 나이는 생성시각 기준으로 잰다.
# ⚠️ 이 값(시간) × 3600 은 벤치마크 채점기 매니페스트의 최대 timeout_seconds + 기동보다
#    커야 한다 — 스윕은 컨테이너에 묻지 않고 나이만으로 failed 로 만들고 되돌릴 수 없다.
#    evaluate-lmeval 은 KMMLU 전체가 8B 에서 3 시간 가까이 걸려 timeout 이 10 시간이다
#    (tests/test_benchmark_catalog.py 가 이 불변식을 매니페스트와 대조한다).
# 사람이 시간에 걸쳐 채점하는 expert(metric_set='expert') 세션은 정당히 오래 running
# 이므로 스윕에서 제외한다.
STALE_RUNNING_MAX_HOURS = 12

# 한 화면 조회에서 컨테이너에 되물을 running 런 수 상한. 목록 렌더가 외부 호출 수에
# 비례해 느려지는 것을 막는다(running 런은 통상 0~1건이라 실제로 걸릴 일은 드물다).
MAX_RECONCILE_PER_VIEW = 8

# 한 화면 조회에서 채점기 진행 기록(progress.json)을 읽어 실을 끝나지 않은 런 수 상한(최신순).
# NFS 파일 읽기라 외부 호출보다 싸지만 목록 렌더가 런 수에 비례해 느려지지 않게 둔다.
MAX_PROGRESS_PER_VIEW = 20

# 백그라운드 마감 루프(service.finalize_finished_runs_loop) — 결과 화면을 아무도 열지 않아도 끝난 런
# (metrics.json 이 생긴 running 런)을 completed 로 마감한다. 간격마다 최신순 EVAL_FINALIZE_BATCH 건만
# 파일 존재를 본다(컨테이너 호출 없음 — NFS stat 뿐). 레플리카가 여럿이어도 마감은 WHERE status='running'
# 가드라 중복 실행이 무해하다.
EVAL_FINALIZE_INTERVAL_SECONDS = 60
EVAL_FINALIZE_BATCH = 50

# reconcile 조회 1건의 타임아웃. 이 값 x MAX_RECONCILE_PER_VIEW 가 목록 조회에 실릴 수
# 있는 최대 대기이므로 짧게 잡는다. 되묻기는 best-effort 라 놓쳐도 다음 폴링이 잡는다 —
# 반면 여기서 오래 붙들면 게이트웨이 타임아웃을 넘겨 목록 자체가 안 뜬다.
RECONCILE_TIMEOUT_SECONDS = 5.0
