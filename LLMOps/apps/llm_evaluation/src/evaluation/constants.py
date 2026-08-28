"""llm_evaluation 공용 상수."""

# mock 채점 벤치마크(9) — evaluate-benchmark-mock 컨테이너가 해시 점수로 채점하는 집합.
# ⚠️ 실채점이 아니다. 정식 채점기가 붙는 대로 이 집합에서 빠져 나간다.
MOCK_BENCHMARK_IDS = (
    "arc", "kobest", "mmlu", "hellaswag", "winogrande",
    "gsm8k", "truthfulqa", "boolq", "humaneval",
)

# 실채점 벤치마크 → 전용 채점 컨테이너. 벤치마크마다 필요한 런타임이 달라(LogicKor 는
# 심판 LLM + transformers 5.5.4 핀) 한 컨테이너가 전부 채점할 수 없다. 한 런은 컨테이너
# 하나로 가므로 서로 다른 채점기의 벤치마크를 한 런에 섞을 수 없다(service 가 거부).
REAL_BENCHMARK_MANIFEST_KEY = {
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

# 벤치마크 정본(10) — id = FE benchmarks.js + 채점 컨테이너와 일치. 벤치마크
# = 표준 평가 태스크(ARC·MMLU…). "벤치마크 선택 → 벤치마크별 메트릭" 2단계의 1단계 후보다.
BENCHMARK_IDS = MOCK_BENCHMARK_IDS + tuple(REAL_BENCHMARK_MANIFEST_KEY)

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

# 요청에서 benchmarks 를 생략했을 때 채점할 기본 집합. 전체(BENCHMARK_IDS)가 아니라
# mock 집합만 쓴다 — 실채점 벤치마크는 각자 다른 컨테이너로 가야 하므로 "전체 한 번에"가
# 성립하지 않는다. 실채점 벤치마크는 사용자가 명시적으로 골라야 한다.
# ⚠️ 이 집합은 전부 reference 유형이다(mock 9종). 그래서 judge 프로젝트가 벤치마크를
#    생략하면 기본값을 쓸 수 없고, service 가 명시를 요구하며 거절한다 — 조용히 다른
#    축을 채점해 버리지 않도록.
DEFAULT_BENCHMARK_IDS = MOCK_BENCHMARK_IDS

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
)

# 벤치마크별 권장 메트릭(생략 시 채택) — FE 기본 선택·채점기 기본값과 공유(단일 소스).
BENCHMARK_RECOMMENDED_METRIC = {
    "arc": "accuracy", "kobest": "f1", "mmlu": "accuracy", "hellaswag": "acc_norm",
    "winogrande": "accuracy", "gsm8k": "accuracy", "truthfulqa": "accuracy",
    "boolq": "accuracy", "humaneval": "accuracy",
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
    "arc": ("accuracy", "acc_norm", "f1"),
    "kobest": ("f1", "accuracy", "acc_norm"),
    "mmlu": ("accuracy", "acc_norm"),
    "hellaswag": ("acc_norm", "accuracy"),
    "winogrande": ("accuracy", "acc_norm"),
    "gsm8k": ("accuracy", "f1"),
    "truthfulqa": ("accuracy", "f1", "bleu", "rouge"),
    "boolq": ("accuracy", "f1"),
    "humaneval": ("accuracy",),
    "logickor": ("judge_overall", "judge_single", "judge_multi"),
    "mixatis": ("joint_acc", "intent_acc", "intent_f1", "slot_f1"),
}

# 한 벤치마크 런이 다룰 벤치마크 상한 — metric_set 요약 컬럼(VARCHAR 255) 초과·과도 태스크 방지.
MAX_BENCHMARK_ITEMS = 20

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
# 벤치마크 채점은 분 단위라 6h 면 정상 런엔 절대 안 걸린다.
# 사람이 시간에 걸쳐 채점하는 expert(metric_set='expert') 세션은 정당히 오래 running
# 이므로 스윕에서 제외한다.
STALE_RUNNING_MAX_HOURS = 6

# 한 화면 조회에서 컨테이너에 되물을 running 런 수 상한. 목록 렌더가 외부 호출 수에
# 비례해 느려지는 것을 막는다(running 런은 통상 0~1건이라 실제로 걸릴 일은 드물다).
MAX_RECONCILE_PER_VIEW = 8

# reconcile 조회 1건의 타임아웃. 이 값 x MAX_RECONCILE_PER_VIEW 가 목록 조회에 실릴 수
# 있는 최대 대기이므로 짧게 잡는다. 되묻기는 best-effort 라 놓쳐도 다음 폴링이 잡는다 —
# 반면 여기서 오래 붙들면 게이트웨이 타임아웃을 넘겨 목록 자체가 안 뜬다.
RECONCILE_TIMEOUT_SECONDS = 5.0
