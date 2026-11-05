"""MixATIS(UGEN 생성QA) 지표 집계 + 플랫폼 벤치마크 계약.

지표 **정의는 ETRI 원본**(`evaluate_qwen3_mixatis.py`)을 그대로 import 해서 쓴다.
그쪽 모듈은 최상위 부작용이 없어 안전하게 import 되고, 정의를 여기 다시 적으면
원본이 바뀔 때 조용히 갈라지기 때문이다. 이 파일이 하는 일은 그 결과를
llm_evaluation 벤치마크 계약(results/averages/benchmark_set/metric_map)으로 옮기는 것뿐이다.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

# ETRI 원본 지표 함수(UGEN utils/metric.py 재현). 정의 변경 금지 — 바꾸면 점수 비교가 깨진다.
from evaluate_qwen3_mixatis import intent_acc, micro_f1, overall_acc  # noqa: F401

# FE benchmarks.js / constants.py 와 일치해야 하는 id.
BENCHMARK_ID = "mixatis"

# 메트릭 = "대표 스칼라를 어느 축으로 잡느냐". 네 값은 항상 함께 산출되고
# metric 은 results[].score 에 실릴 축만 고른다(LogicKor judge_* 3종과 같은 규약).
METRIC_JOINT = "joint_acc"      # 의도집합 AND 슬롯집합 완전일치 — 태스크의 최종 난이도
METRIC_INTENT_ACC = "intent_acc"
METRIC_INTENT_F1 = "intent_f1"
METRIC_SLOT_F1 = "slot_f1"
SUPPORTED_METRICS = (METRIC_JOINT, METRIC_INTENT_ACC, METRIC_INTENT_F1, METRIC_SLOT_F1)
DEFAULT_METRIC = METRIC_JOINT


def aggregate(pred_intents: Sequence[List[str]], gold_intents: Sequence[List[str]],
              pred_slots: Sequence[List[Tuple[str, str]]],
              gold_slots: Sequence[List[Tuple[str, str]]]) -> Optional[Dict[str, Any]]:
    """네 지표를 한 번에 계산한다. 평가 발화가 없으면 None."""
    if not gold_intents:
        return None
    i_acc = intent_acc(pred_intents, gold_intents)
    i_p, i_r, i_f1 = micro_f1(pred_intents, gold_intents)
    s_p, s_r, s_f1 = micro_f1(pred_slots, gold_slots)
    j_acc = overall_acc(pred_slots, gold_slots, pred_intents, gold_intents)
    return {
        "count": len(gold_intents),
        "intent": {"acc": round(i_acc, 4), "precision": round(i_p, 4),
                   "recall": round(i_r, 4), "f1": round(i_f1, 4)},
        "slot": {"precision": round(s_p, 4), "recall": round(s_r, 4), "f1": round(s_f1, 4)},
        "joint_acc": round(j_acc, 4),
    }


def representative_score(agg: Dict[str, Any], metric: str) -> float:
    if metric == METRIC_INTENT_ACC:
        return float(agg["intent"]["acc"])
    if metric == METRIC_INTENT_F1:
        return float(agg["intent"]["f1"])
    if metric == METRIC_SLOT_F1:
        return float(agg["slot"]["f1"])
    return float(agg["joint_acc"])


def build_metrics(agg: Dict[str, Any], metric: str = DEFAULT_METRIC,
                  datasets: Optional[List[str]] = None) -> Dict[str, Any]:
    """집계 → 벤치마크 계약 metrics dict.

    키 구성은 evaluate-benchmark-mock / evaluate-logickor 와 동형으로 둬서 기존
    이력 flatten·FE 렌더 경로를 그대로 태운다. 네 지표 전체 격자는 계약 밖 추가
    정보라 'mixatis' 하위에만 둔다(자유형식 metrics JSON — 스키마 변경 없음).
    """
    if metric not in SUPPORTED_METRICS:
        metric = DEFAULT_METRIC
    score = representative_score(agg, metric)
    return {
        "mode": "benchmark",
        "mock": False,
        "results": [{"benchmark": BENCHMARK_ID, "metric": metric, "score": score}],
        "averages": {BENCHMARK_ID: score},
        "benchmark_set": [BENCHMARK_ID],
        "metric_map": {BENCHMARK_ID: metric},
        "datasets": datasets or [],
        BENCHMARK_ID: agg,
    }
