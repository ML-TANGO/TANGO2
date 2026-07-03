"""llm_evaluation 공용 상수."""

# ETRI BenchmarkEvaluationPage 정본 17 메트릭(evaluate-benchmark-mock 컨테이너와 id 일치).
BENCHMARK_METRICS = (
    "accuracy", "f1", "acc_norm", "arc", "kobest", "mmlu", "hellaswag",
    "winogrande", "gsm8k", "truthfulqa", "boolq", "humaneval", "meteor",
    "cider", "spice", "bleu", "rouge",
)

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
# 한 세션이 사람에게 보여줄 샘플 상한(손 채점이라 작게).
MAX_EXPERT_SAMPLES = 10

# ── 교차모델 비교 (④ 경량 뷰) ──────────────────────────────────────────────────
# 한 비교 뷰가 합칠 모델 상한(표 가독성 + 모델별 get_model/list_eval_results N쿼리 가드).
MAX_COMPARE_MODELS = 6

# ── 이력 관리 ────────────────────────────────────────────────────────────────
# 'running' 으로 방치된 벤치마크/judge 런을 실패로 간주하는 나이 임계(시간). 컨테이너
# 파드 크래시나 폴러 재시작으로 완료 콜백이 유실되면 런이 running 에 영구 고착되는데,
# eval_result 엔 updated_at 이 없어(create_datetime 만) 나이는 생성시각 기준으로 잰다.
# judge 는 자체 300s 타임아웃이 있고 벤치마크는 분 단위라 6h 면 정상 런엔 절대 안 걸린다.
# 사람이 시간에 걸쳐 채점하는 expert(metric_set='expert') 세션은 정당히 오래 running
# 이므로 스윕에서 제외한다.
STALE_RUNNING_MAX_HOURS = 6
