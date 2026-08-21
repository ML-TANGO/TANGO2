"""LogicKor 집계기 골든 검증 — ETRI 가 커밋한 실측 점수표와 소수점까지 대조한다.

기준값은 `Evaluation/Logickor/evaluated/Gemma4-e4b-it/sft/test_result.md`. ETRI 가 자기
파이프라인으로 뽑아 커밋한 표라, 우리 집계기가 같은 입력에서 같은 표를 내는지가
"채점 로직이 원본과 동일한가"의 유일한 객관적 검증이다. GPU·모델·학습데이터 없이 돈다.

⚠️ 버전 라벨 오프셋: md 는 1부터, 디렉토리는 0부터 센다. md `v1` = 디렉토리 `v0` 이고
md 최종 `v5` 에 대응하는 디렉토리는 `v4`(디렉토리 `v5` 는 없음). 15개 케이스가 전부
일관되게 +1 이므로 데이터 오류가 아니라 표기 규칙 차이다. 이걸 모르고 같은 이름끼리
비교하면 "집계기가 틀렸다"고 오진한다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

import scoring  # noqa: E402  (sys.path 주입 후 임포트)

LLMOPS_ROOT = Path(__file__).resolve().parents[3]
SFT_DIR = LLMOPS_ROOT / "Evaluation" / "Logickor" / "evaluated" / "Gemma4-e4b-it" / "sft"
RESULT_MD = SFT_DIR / "test_result.md"

# md 의 "## <전략>" 섹션명 = 생성 전략(templates.py PROMPT_STRATEGY 키)이자 jsonl 파일명.
STRATEGIES = ("default", "1-shot", "cot-1-shot")

# md 버전 → 디렉토리 버전 오프셋(위 주석 참조).
MD_TO_DIR_VERSION_OFFSET = -1

_SUMMARY_RE = re.compile(r"\|\s*(Single turn|Multi turn|Overall)\s*\|\s*([\d.]+)\s*\|")


def _parse_result_md(text: str):
    """test_result.md → [(전략, md버전번호, {Single turn/Multi turn/Overall: 값})].

    카테고리별 표의 헤더(`| Category | Single turn | Multi turn |`)는 라벨 뒤에 숫자가
    오지 않으므로 _SUMMARY_RE 에 걸리지 않는다 → 종합표만 잡힌다.
    """
    cases = []
    for block in re.split(r"\n## ", text):
        strategy = block.split("\n", 1)[0].strip()
        if strategy not in STRATEGIES:
            continue  # 문서 머리말(# SFT) 등
        for match in re.finditer(r"### v(\d+)(.*?)(?=### v|\Z)", block, re.S):
            version = int(match.group(1))
            summary = {k: float(v) for k, v in _SUMMARY_RE.findall(match.group(2))}
            if len(summary) == 3:
                cases.append((strategy, version, summary))
    return cases


def _golden_cases():
    if not RESULT_MD.exists():
        return []
    return _parse_result_md(RESULT_MD.read_text(encoding="utf-8"))


GOLDEN_CASES = _golden_cases()

pytestmark = pytest.mark.skipif(
    not GOLDEN_CASES,
    reason=f"골든 데이터 없음: {RESULT_MD} (ETRI 평가 산출물이 필요)",
)


def test_golden_case_count():
    """전략 3종 × 버전 5개 = 15케이스가 모두 파싱돼야 한다(파서 회귀 방지)."""
    assert len(GOLDEN_CASES) == 15, [(s, v) for s, v, _ in GOLDEN_CASES]


@pytest.mark.parametrize(
    "strategy,md_version,expected",
    GOLDEN_CASES,
    ids=[f"{s}-md_v{v}" for s, v, _ in GOLDEN_CASES],
)
def test_aggregate_matches_etri_score_table(strategy, md_version, expected):
    """우리 집계기가 ETRI 커밋 점수표와 소수점 2자리까지 일치하는가."""
    dir_version = md_version + MD_TO_DIR_VERSION_OFFSET
    path = SFT_DIR / f"v{dir_version}" / f"{strategy}.jsonl"
    assert path.exists(), f"골든 입력 없음: {path}"

    agg = scoring.aggregate(scoring.iter_records([str(path)]))
    assert agg is not None

    assert agg["single_turn"] == expected["Single turn"]
    assert agg["multi_turn"] == expected["Multi turn"]
    assert agg["overall"] == expected["Overall"]


def test_aggregate_shape_and_category_order():
    """카테고리 6종 × 7문항 = 42, 표 순서는 정본 순서로 고정."""
    path = SFT_DIR / "v0" / "default.jsonl"
    agg = scoring.aggregate(scoring.iter_records([str(path)]))

    assert agg["count"] == 42
    assert agg["scale_max"] == 10.0
    names = [c["category"] for c in agg["categories"]]
    assert names == list(scoring.CATEGORY_ORDER)
    assert all(c["count"] == 7 for c in agg["categories"])
    # 심판 점수는 1~10 척도 안에 있어야 한다.
    for c in agg["categories"]:
        assert 0.0 <= c["single"] <= 10.0
        assert 0.0 <= c["multi"] <= 10.0


def test_build_metrics_contract():
    """벤치마크 계약(results/averages/metric_map)과 벤치마크별 상세가 함께 실리는가."""
    path = SFT_DIR / "v0" / "default.jsonl"
    agg = scoring.aggregate(scoring.iter_records([str(path)]))
    metrics = scoring.build_metrics(agg)

    assert metrics["mode"] == "benchmark"
    assert metrics["mock"] is False
    assert metrics["results"] == [
        {"benchmark": "logickor", "metric": "judge_overall", "score": agg["overall"]}
    ]
    assert metrics["averages"] == {"logickor": agg["overall"]}
    assert metrics["metric_map"] == {"logickor": "judge_overall"}
    assert metrics["benchmark_set"] == ["logickor"]
    # 카테고리×턴 격자는 벤치마크 키 하위에만(계약 밖 추가 정보).
    assert metrics["logickor"]["categories"] == agg["categories"]


@pytest.mark.parametrize(
    "metric,key",
    [("judge_overall", "overall"), ("judge_single", "single_turn"),
     ("judge_multi", "multi_turn")],
)
def test_metric_selects_representative_scalar(metric, key):
    """지표 선택이 results[].score 대표값을 바꾼다(전체 결과는 항상 동일)."""
    path = SFT_DIR / "v0" / "default.jsonl"
    agg = scoring.aggregate(scoring.iter_records([str(path)]))
    metrics = scoring.build_metrics(agg, metric)

    assert metrics["results"][0]["metric"] == metric
    assert metrics["results"][0]["score"] == agg[key]


def test_unknown_metric_falls_back_to_default():
    agg = {"single_turn": 1.0, "multi_turn": 2.0, "overall": 1.5, "categories": [],
           "count": 1, "scale_max": 10.0}
    metrics = scoring.build_metrics(agg, "cider")  # LogicKor 로 계산 불가한 지표
    assert metrics["results"][0]["metric"] == scoring.DEFAULT_METRIC
    assert metrics["results"][0]["score"] == 1.5


def test_extract_scores_accepts_legacy_flat_keys():
    """구형 산출물(judge_single_score/judge_multi_score)도 받는다."""
    assert scoring.extract_scores(
        {"query_single": {"judge_score": 9}, "query_multi": {"judge_score": 8}}) == (9.0, 8.0)
    assert scoring.extract_scores(
        {"judge_single_score": 7, "judge_multi_score": 6}) == (7.0, 6.0)
    # 미채점 행(generator 원본 산출물)은 None → 집계에서 제외된다.
    assert scoring.extract_scores({"id": 1, "outputs": ["a", "b"]}) is None


def test_aggregate_returns_none_when_nothing_judged():
    """채점 행이 없으면 0 점짜리 표를 만들지 않고 None(호출부가 실패로 판단)."""
    assert scoring.aggregate([{"id": 1, "category": "추론(Reasoning)"}]) is None


def test_score_files_over_directory():
    """디렉토리를 주면 하위 jsonl 을 모두 합산한다(전략 3종 = 126문항)."""
    metrics = scoring.score_files(str(SFT_DIR / "v0"))
    assert metrics is not None
    assert metrics["logickor"]["count"] == 42 * len(STRATEGIES)
    assert sorted(metrics["source_files"]) == sorted(f"{s}.jsonl" for s in STRATEGIES)


def test_score_files_missing_path_returns_none():
    assert scoring.score_files(str(SFT_DIR / "v99" / "*.jsonl")) is None
