"""
lm-evaluation-harness 벤치마크 레지스트리.

각 벤치마크는 아래 정보를 가진다.
  key          : 내부 식별자 (웹 UI 체크박스 값)
  task         : lm-eval-harness task 이름 (없으면 커스텀 평가)
  label        : 화면 표시용 한국어/영어 이름
  group        : core_en | korean | generative | custom
  num_fewshot  : 권장 few-shot 개수 (None = 태스크 기본값 사용)
  primary      : 대표 지표 후보 (앞에 있을수록 우선). lm-eval 결과 dict 의
                 "<metric>,<filter>" 형태 키에서 <metric> 부분과 매칭한다.
  category     : 레이더 차트용 역량 카테고리
  higher_better: 값이 클수록 좋은가
"""

from __future__ import annotations

# ----------------------------------------------------------------------------
# 1. 대표(core) 영어 벤치마크
# ----------------------------------------------------------------------------
CORE_EN = [
    dict(key="arc_easy",       task="arc_easy",       label="ARC-Easy",
         primary=["acc_norm", "acc"], num_fewshot=0,  category="추론"),
    dict(key="arc_challenge",  task="arc_challenge",  label="ARC-Challenge",
         primary=["acc_norm", "acc"], num_fewshot=25, category="추론"),
    dict(key="hellaswag",      task="hellaswag",      label="HellaSwag",
         primary=["acc_norm", "acc"], num_fewshot=10, category="상식"),
    dict(key="mmlu",           task="mmlu",           label="MMLU",
         primary=["acc"],             num_fewshot=5,  category="지식"),
    dict(key="winogrande",     task="winogrande",     label="Winogrande",
         primary=["acc"],             num_fewshot=5,  category="추론"),
    dict(key="piqa",           task="piqa",           label="PIQA",
         primary=["acc_norm", "acc"], num_fewshot=0,  category="상식"),
    dict(key="boolq",          task="boolq",          label="BoolQ",
         primary=["acc"],             num_fewshot=0,  category="이해"),
    dict(key="openbookqa",     task="openbookqa",     label="OpenBookQA",
         primary=["acc_norm", "acc"], num_fewshot=0,  category="지식"),
    dict(key="gsm8k",          task="gsm8k",          label="GSM8K",
         primary=["exact_match"],     num_fewshot=5,  category="수학"),
    dict(key="truthfulqa_mc2", task="truthfulqa_mc2", label="TruthfulQA (MC2)",
         primary=["acc"],             num_fewshot=0,  category="진실성"),
]

# ----------------------------------------------------------------------------
# 2. 한국어 벤치마크
# ----------------------------------------------------------------------------
KOREAN = [
    dict(key="kobest_boolq",     task="kobest_boolq",     label="KoBEST BoolQ",
         primary=["acc"],             num_fewshot=5, category="한국어-이해"),
    dict(key="kobest_copa",      task="kobest_copa",      label="KoBEST COPA",
         primary=["acc"],             num_fewshot=5, category="한국어-추론"),
    dict(key="kobest_hellaswag", task="kobest_hellaswag", label="KoBEST HellaSwag",
         primary=["acc_norm", "acc"], num_fewshot=5, category="한국어-상식"),
    dict(key="kobest_sentineg",  task="kobest_sentineg",  label="KoBEST SentiNeg",
         primary=["acc"],             num_fewshot=5, category="한국어-감성"),
    dict(key="kobest_wic",       task="kobest_wic",       label="KoBEST WiC",
         primary=["acc"],             num_fewshot=5, category="한국어-어휘"),
    dict(key="kmmlu",            task="kmmlu",            label="KMMLU",
         primary=["acc"],             num_fewshot=5, category="한국어-지식"),
    dict(key="kmmlu_direct",     task="kmmlu_direct",     label="KMMLU (Direct)",
         primary=["exact_match", "acc"], num_fewshot=5, category="한국어-지식"),
    dict(key="haerae",           task="haerae",           label="HAE-RAE Bench",
         primary=["acc_norm", "acc"], num_fewshot=0, category="한국어-지식"),
]

# ----------------------------------------------------------------------------
# 3. 생성형 지표 벤치마크 (F1 / EM / BLEU / ROUGE)
# ----------------------------------------------------------------------------
GENERATIVE = [
    dict(key="squadv2", task="squadv2", label="SQuADv2 (F1/EM)",
         primary=["f1", "best_f1", "exact"], num_fewshot=0, category="독해-생성",
         metric_kind="f1",
         # squadv2 는 하네스가 이미 0~100 스케일로 보고한다
         pct={"f1", "exact", "best_f1", "best_exact", "HasAns_f1", "HasAns_exact",
              "NoAns_f1", "NoAns_exact"}),
    dict(key="truthfulqa_gen", task="truthfulqa_gen", label="TruthfulQA-gen (BLEU/ROUGE)",
         primary=["bleu_max", "rouge1_max", "rougeL_max"], num_fewshot=0,
         category="진실성-생성", metric_kind="bleu_rouge",
         # bleu_*/rouge*_max·diff 는 0~100, *_acc 는 0~1 스케일
         pct={"bleu_max", "bleu_diff", "rouge1_max", "rouge1_diff",
              "rouge2_max", "rouge2_diff", "rougeL_max", "rougeL_diff"}),
    dict(key="drop", task="drop", label="DROP (F1/EM)",
         primary=["f1", "em"], num_fewshot=3, category="독해-생성",
         metric_kind="f1", pct={"f1", "em"}),
]

# ----------------------------------------------------------------------------
# 4. 커스텀 파일 평가 (lm-eval 태스크가 아니라 custom_eval.py 로 직접 수행)
# ----------------------------------------------------------------------------
CUSTOM = [
    dict(key="custom_file", task=None, label="커스텀 파일 (F1/EM/BLEU/ROUGE)",
         primary=["f1", "em", "bleu", "rougeL"], num_fewshot=0,
         category="커스텀", metric_kind="custom"),
]

GROUPS = {
    "core_en":    dict(label="대표(core) 영어 벤치마크", items=CORE_EN),
    "korean":     dict(label="한국어 벤치마크",          items=KOREAN),
    "generative": dict(label="생성형 지표 벤치마크",     items=GENERATIVE),
    "custom":     dict(label="커스텀 파일 평가",         items=CUSTOM),
}

# 기본 선택(웹 UI 초기값): 사용자가 요청한 대표 항목들
DEFAULT_SELECTED = [
    # 영어 core 9종
    "arc_easy", "arc_challenge", "hellaswag", "mmlu", "winogrande",
    "piqa", "boolq", "openbookqa", "gsm8k", "truthfulqa_mc2",
    # 한국어
    "kobest_boolq", "kobest_copa", "kobest_hellaswag", "kobest_sentineg",
    "kobest_wic", "kmmlu",
    # 생성형
    "squadv2", "truthfulqa_gen",
]

# 지표 이름 → 화면 표기
METRIC_LABELS = {
    "acc": "Accuracy",
    "acc_norm": "Acc(norm)",
    "exact_match": "Exact Match",
    "exact": "Exact Match",
    "em": "Exact Match",
    "f1": "F1",
    "best_f1": "Best F1",
    "HasAns_f1": "F1 (HasAns)",
    "NoAns_f1": "F1 (NoAns)",
    "bleu": "BLEU",
    "bleu_max": "BLEU(max)",
    "bleu_acc": "BLEU(acc)",
    "bleu_diff": "BLEU(diff)",
    "rouge1": "ROUGE-1",
    "rouge2": "ROUGE-2",
    "rougeL": "ROUGE-L",
    "rouge1_max": "ROUGE-1(max)",
    "rouge2_max": "ROUGE-2(max)",
    "rougeL_max": "ROUGE-L(max)",
    "rouge1_acc": "ROUGE-1(acc)",
    "rougeL_acc": "ROUGE-L(acc)",
    "mc1": "MC1",
    "mc2": "MC2",
    "perplexity": "Perplexity",
}

# 스케일 규칙
#   1) 태스크 메타의 pct 집합에 있으면 이미 0~100 → 변환하지 않는다
#      (squadv2 의 f1/exact, truthfulqa_gen 의 bleu_*/rouge*_max 등)
#   2) UNBOUNDED 지표는 백분율이 아니므로 그대로 표시한다
#   3) 그 밖의 값이 1.0 을 넘으면 하네스가 이미 백분율로 보고한 것으로 본다
#      (accuracy·f1 류는 분수 스케일에서 1.0 을 넘을 수 없다)
#   4) 나머지(0~1)는 100 을 곱한다
#      — 같은 이름의 f1 이 squadv2 는 0~100, KoBEST 는 0~1 이므로
#        전역 목록이 아니라 태스크별 판정이 필요하다.
UNBOUNDED = {
    "perplexity", "word_perplexity", "byte_perplexity", "bits_per_byte",
    "sample_len",
}


def pct_metrics(item: dict) -> set[str]:
    """해당 벤치마크에서 이미 0~100 스케일로 보고되는 지표 이름 집합."""
    return set(item.get("pct") or ())


def all_items() -> list[dict]:
    out = []
    for g, meta in GROUPS.items():
        for it in meta["items"]:
            d = dict(it)
            d["group"] = g
            d.setdefault("higher_better", True)
            out.append(d)
    return out


def by_key() -> dict[str, dict]:
    return {it["key"]: it for it in all_items()}


def resolve(keys: list[str]) -> list[dict]:
    """선택된 key 목록 → 벤치마크 메타 목록 (레지스트리 순서 유지)."""
    ks = set(keys)
    return [it for it in all_items() if it["key"] in ks]


def lm_eval_tasks(keys: list[str]) -> list[str]:
    """선택 항목 중 lm-eval-harness 로 실행할 task 이름 목록."""
    return [it["task"] for it in resolve(keys) if it.get("task")]


def registry_json() -> dict:
    """웹 UI 로 내려줄 레지스트리 직렬화."""
    return {
        "groups": [
            {
                "key": g,
                "label": meta["label"],
                "items": [
                    {
                        "key": it["key"],
                        "label": it["label"],
                        "task": it.get("task"),
                        "num_fewshot": it.get("num_fewshot"),
                        "category": it.get("category"),
                        "primary": it.get("primary", []),
                    }
                    for it in meta["items"]
                ],
            }
            for g, meta in GROUPS.items()
        ],
        "default_selected": DEFAULT_SELECTED,
        "metric_labels": METRIC_LABELS,
    }
