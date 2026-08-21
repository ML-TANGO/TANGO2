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
}

# 벤치마크 정본(10) — id = FE benchmarks.js + 채점 컨테이너와 일치. 벤치마크
# = 표준 평가 태스크(ARC·MMLU…). "벤치마크 선택 → 벤치마크별 메트릭" 2단계의 1단계 후보다.
BENCHMARK_IDS = MOCK_BENCHMARK_IDS + tuple(REAL_BENCHMARK_MANIFEST_KEY)

# 요청에서 benchmarks 를 생략했을 때 채점할 기본 집합. 전체(BENCHMARK_IDS)가 아니라
# mock 집합만 쓴다 — 실채점 벤치마크는 각자 다른 컨테이너로 가야 하므로 "전체 한 번에"가
# 성립하지 않는다. 실채점 벤치마크는 사용자가 명시적으로 골라야 한다.
DEFAULT_BENCHMARK_IDS = MOCK_BENCHMARK_IDS

# 메트릭 정본(11) — 벤치마크와 분리된 채점 방식. id = FE benchmarkMetrics.js + 채점기 일치.
# judge_* 3종은 LogicKor 전용 심판 점수(1~10). LogicKor 는 정답이 없어(references=null)
# accuracy/f1 계열을 계산할 수 없고 심판 LLM 점수가 유일한 채점 축이다. 셋의 차이는
# 대표 스칼라를 어느 축으로 잡느냐(전체/1턴/2턴)일 뿐이고 전체 결과는 항상 함께 산출된다.
METRIC_IDS = (
    "accuracy", "f1", "acc_norm", "bleu", "rouge", "meteor", "cider", "spice",
    "judge_overall", "judge_single", "judge_multi",
)

# 벤치마크별 권장 메트릭(생략 시 채택) — FE 기본 선택·채점기 기본값과 공유(단일 소스).
BENCHMARK_RECOMMENDED_METRIC = {
    "arc": "accuracy", "kobest": "f1", "mmlu": "accuracy", "hellaswag": "acc_norm",
    "winogrande": "accuracy", "gsm8k": "accuracy", "truthfulqa": "accuracy",
    "boolq": "accuracy", "humaneval": "accuracy",
    "logickor": "judge_overall",
}

# 벤치마크별 허용 메트릭 — FE benchmarks.js 의 벤치마크별 metrics 목록과 동일 집합.
# 지금까지 이 제약은 FE 에만 있어서 API 를 직접 치면 'logickor × cider' 처럼 계산 자체가
# 불가능한 조합이 통과했다(서버는 벤치마크·메트릭을 각각만 검사). 여기 두고 서버에서
# 강제해 허용 밖 조합은 권장 메트릭으로 교정한다.
# ⚠️ 이 표는 FE benchmarks.js 의 벤치마크별 metrics 와 **정확히 같은 집합**이어야 한다.
# FE 가 제시하는데 여기 없으면, 사용자가 고른 메트릭이 아무 신호 없이 권장값으로 교정돼
# "F1 을 골랐는데 accuracy 로 채점된" 상태가 된다(실제로 gsm8k·truthfulqa 에서 발생).
# 둘 중 하나를 줄이려면 FE 와 함께 줄여야 한다.
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
}

# 한 벤치마크 런이 다룰 벤치마크 상한 — metric_set 요약 컬럼(VARCHAR 255) 초과·과도 태스크 방지.
MAX_BENCHMARK_ITEMS = 20

# 한 벤치마크 런이 다룰 데이터셋 상한 — dataset_name CSV 가 eval_result.dataset_name
# VARCHAR(255) 를 넘지 않도록(+ 과도한 멀티마운트 방지).
MAX_BENCHMARK_DATASETS = 10


# ── LLM-as-a-Judge (P2) ──────────────────────────────────────────────────────
# 채점 기준 4종(정확/관련/유창/안전). eval_result.metrics 에는 벤치마크 'accuracy' 와
# 충돌하지 않도록 'judge_' 접두로 저장(모델 이력 비교표에서 별도 컬럼).
JUDGE_CRITERIA = ("accuracy", "relevance", "fluency", "safety")

# 심판 provider. 상용 3종 = API 키 사용자 입력(transient). local = 호출 URL 사용자 입력.
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

# 한 judge 런이 채점할 샘플 상한(비용·시간·레이트리밋 가드).
MAX_JUDGE_SAMPLES = 20

# judge 백그라운드 태스크 전역 wall-clock 상한 — 병적 행(hung provider) 시 running 행이
# 무한정 남지 않도록 초과 시 failed 처리(FE 는 timeout 후 '이력에서 확인' 안내).
MAX_JUDGE_RUN_SECONDS = 300

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
# 않도록. judge(MAX_JUDGE_RUN_SECONDS 300)·expert(_EXPERT_INFER_BUDGET 90)와 동일 취지이나
# 전량 batch(≤MAX_EVAL_SAMPLES) 라 크게 잡는다. 초과 시 런=failed + (할당형) teardown.
EVAL_INFER_RUN_SECONDS = 3600

# ── 교차모델 비교 (④ 경량 뷰) ──────────────────────────────────────────────────
# 한 비교 뷰가 합칠 모델 상한(표 가독성 + 모델별 get_model/list_eval_results N쿼리 가드).
MAX_COMPARE_MODELS = 6

# ── 평가 프로젝트 관리 (2026-07-07) ────────────────────────────────────────────
# 프로젝트 = 관리 단위(모델·데이터셋·유형·이름 잠금, 1:N run). 유형은 생성 시 확정·불변
# 이며 run-start 시 프로젝트 유형과 일치해야 한다(교차유형 run 생성 차단).
EVAL_TYPES = ("benchmark", "judge", "expert")

# 프로젝트 상태(created=구성만 확정·run 0 / running=run 존재 / completed=집계 마감).
PROJECT_STATUS_CREATED = "created"
PROJECT_STATUS_RUNNING = "running"
PROJECT_STATUS_COMPLETED = "completed"

# ── 이력 관리 ────────────────────────────────────────────────────────────────
# 'running' 으로 방치된 벤치마크/judge 런을 실패로 간주하는 나이 임계(시간). 컨테이너
# 파드 크래시나 폴러 재시작으로 완료 콜백이 유실되면 런이 running 에 영구 고착되는데,
# eval_result 엔 updated_at 이 없어(create_datetime 만) 나이는 생성시각 기준으로 잰다.
# judge 는 자체 300s 타임아웃이 있고 벤치마크는 분 단위라 6h 면 정상 런엔 절대 안 걸린다.
# 사람이 시간에 걸쳐 채점하는 expert(metric_set='expert') 세션은 정당히 오래 running
# 이므로 스윕에서 제외한다.
STALE_RUNNING_MAX_HOURS = 6
