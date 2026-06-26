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
