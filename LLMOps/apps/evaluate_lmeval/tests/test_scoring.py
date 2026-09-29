"""lm-eval 결과 해석·스케일 환산 골든 검증.

픽스처는 P0 스파이크(lm_eval 0.4.12 + vLLM 0.19.1, Llama-3.2-3B, limit=20 — drop 만
drop_tango limit=5)가 실제로 반환한 dict 의 results/groups/n-samples 다. 기댓값은 그
원시값을 손으로 환산한 것이라, 해석 규칙(그룹·필터·평균·스케일)이 바뀌면 여기서 잡힌다.
GPU·lm_eval 없이 돈다.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

import registry as REG  # noqa: E402
import scoring  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _raw(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _summary(bid: str, fixture: str = None) -> dict:
    return scoring.summarize_lmeval(REG.BENCHMARKS[bid], _raw(fixture or bid))


@pytest.mark.parametrize("bid, expected", [
    ("arc", 40.0),              # acc 0.4 → 40 (acc_norm 이 아니라 대표 = acc)
    ("mmlu", 61.6667),          # 그룹 가중 평균 acc 0.61667
    ("haerae", 51.0),           # 그룹 acc_norm 0.51
    ("kmmlu_direct", 30.0),     # 생성형 exact_match 0.3
    ("gsm8k", 50.0),            # strict-match 0.5 (flexible-extract 0.55 가 아니다)
    ("humaneval", 90.0),        # pass@1,create_test 0.9
    ("drop", 40.0),             # drop_tango f1 0.4 — 0~1 스케일(ETRI 원본은 여기서 100배 작게 표기)
    ("squadv2", 27.99),         # 이미 0~100 — 환산하지 않는다
    ("truthfulqa_gen", 35.42),  # bleu_max 이미 0~100
])
def test_primary_score(bid, expected):
    # 기댓값은 원시값 유효숫자 4 자리 기준 — 스케일(×100 여부)을 가르기엔 0.01 이면 충분하다.
    assert _summary(bid)["score"] == pytest.approx(expected, abs=0.01)


def test_kobest_is_mean_of_five_subtask_f1():
    s = _summary("kobest")
    assert s["score"] == pytest.approx((0.7 + 0.7494 + 0.3951 + 0.52 + 0.4357) / 5 * 100, abs=0.01)
    assert [r["task"] for r in s["subtasks"]] == list(REG.BENCHMARKS["kobest"].tasks)
    assert all(r["metric"] == "f1" for r in s["subtasks"])
    assert s["n"] == 100


def test_group_lists_leaf_subtasks_only():
    s = _summary("mmlu")
    names = {r["task"] for r in s["subtasks"]}
    assert len(names) == 57
    assert "mmlu" not in names and "mmlu_humanities" not in names   # 그룹은 말단이 아니다
    assert s["n"] == 57 * 20


def test_single_task_has_no_subtasks():
    s = _summary("arc")
    assert s["subtasks"] == []
    assert s["n"] == 20


def test_mixed_scale_truthfulqa_gen():
    rows = {r["metric"]: r["score"] for r in _summary("truthfulqa_gen")["metrics"]}
    assert rows["bleu_max"] == pytest.approx(35.42, abs=0.01)   # percent 그대로
    assert rows["bleu_acc"] == pytest.approx(70.0, abs=0.01)    # fraction ×100
    assert rows["rougeL_acc"] == pytest.approx(60.0, abs=0.01)


def test_stderr_follows_value_scale_and_never_nan():
    for bid in ("arc", "mmlu", "kobest", "squadv2", "humaneval"):
        for r in _summary(bid)["metrics"] + _summary(bid)["subtasks"]:
            se = r["stderr"]
            assert se is None or (isinstance(se, float) and not math.isnan(se))
    arc_acc = next(r for r in _summary("arc")["metrics"] if r["metric"] == "acc")
    assert 1.0 < arc_acc["stderr"] < 20.0          # 0.11 → 11 (값과 같은 ×100)


def test_unknown_metric_is_reported_not_scaled():
    bench = REG.BENCHMARKS["arc"]
    raw = {"results": {"arc_challenge": {"acc,none": 0.5, "weird,none": 0.25}}}
    s = scoring.summarize_lmeval(bench, raw)
    weird = next(r for r in s["metrics"] if r["metric"] == "weird")
    assert weird["score"] == 0.25
    assert any("weird" in w for w in s["warnings"])


def test_missing_primary_metric_fails_loudly():
    bench = REG.BENCHMARKS["gsm8k"]
    raw = {"results": {"gsm8k": {"exact_match,flexible-extract": 0.5}}}
    with pytest.raises(ValueError, match="strict-match"):
        scoring.summarize_lmeval(bench, raw)


def test_build_metrics_keeps_mock_contract():
    s = _summary("mmlu")
    m = scoring.build_metrics([s], datasets=["ds"], checkpoint={"name": "c1", "format": "merged"},
                              engine={"engine": "vllm"}, limit=20,
                              meta={"name": "evaluate-lmeval", "version": "0.1.0"})
    assert m["mock"] is False and m["mode"] == "benchmark"
    assert m["results"] == [{"benchmark": "mmlu", "metric": "accuracy", "score": s["score"]}]
    assert m["averages"] == {"mmlu": s["score"]}
    assert m["metric_map"] == {"mmlu": "accuracy"} and m["benchmark_set"] == ["mmlu"]
    assert m["lmeval"]["limit"] == 20 and "mmlu" in m["lmeval"]["benchmarks"]
    json.dumps(m, allow_nan=False)        # metrics.json 은 allow_nan=False 로 쓴다
    assert len(json.dumps(m)) < 1_000_000  # llm_evaluation 이 1MB 초과를 거부한다


def test_build_metrics_lists_failed_benchmarks_without_scores():
    s = _summary("mmlu")
    fail = {"benchmark": "arc", "metric": "accuracy", "error": "RuntimeError: boom"}
    m = scoring.build_metrics([s], datasets=[], checkpoint={"name": "c1", "format": "merged"},
                              engine={"engine": "vllm"}, limit=None,
                              meta={"name": "evaluate-lmeval", "version": "0.1.1"},
                              failures=[fail])
    assert m["failed_benchmarks"] == [fail]
    assert "arc" not in m["averages"] and m["benchmark_set"] == ["mmlu"]
    # 실패 없는 런도 키는 있다(빈 목록) — 소비자가 존재 여부로 분기하지 않게.
    ok = scoring.build_metrics([s], datasets=[], checkpoint={}, engine={}, limit=None, meta={})
    assert ok["failed_benchmarks"] == []
