"""LogicKor 채점 집계 — evaluator 산출 jsonl → 벤치마크 계약 metrics.

LogicKor 파이프라인의 마지막 단계(clean→train→generate→evaluate→**score**)만 담당한다.
모델을 로드하지 않으므로 torch/vllm/transformers 의존이 0이고 CPU 로만 돈다. 생성·심판
(GPU 필요, transformers 5.5.4 핀)은 이 모듈 밖의 별도 단계다 — 그래서 플랫폼 기본 의존성
(transformers>=4.52.4,<5.0.0)과 충돌하지 않는다.

입력: ETRI evaluator.py 가 쓴 jsonl 1개 이상. 한 줄 = LogicKor 문항 1개.
  {id, category, questions[2], outputs[2], references[2],
   query_single:{judge_message, judge_score}, query_multi:{...}}
  judge_score 는 1~10(심판 LLM 이 매김). 구형 산출물은 judge_single_score /
  judge_multi_score 평면 키를 쓰므로 둘 다 받는다(ETRI score.py 와 동일한 수용 범위).

출력: llm_evaluation 벤치마크 계약. results[] 가 이력·교차비교용 대표 스칼라 1개,
  같은 dict 의 'logickor' 키에 카테고리×턴 전체 격자를 싣는다. FE 는 results[] 가 있으면
  그걸 렌더하고 없으면 averages 로 폴백하므로 기존 9벤치마크 표시에 영향이 없다.
"""
from __future__ import annotations

import glob
import json
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

BENCHMARK_ID = "logickor"

# 대표 스칼라로 고를 수 있는 지표 — llm_evaluation constants.METRIC_IDS 및 FE
# benchmarkMetrics.js 와 id 가 일치해야 한다. LogicKor 는 정답이 없어(references=null)
# accuracy/f1 계열을 계산할 수 없고, 심판 점수(1~10)가 유일한 채점 축이다.
METRIC_OVERALL = "judge_overall"
METRIC_SINGLE = "judge_single"
METRIC_MULTI = "judge_multi"
SUPPORTED_METRICS = (METRIC_OVERALL, METRIC_SINGLE, METRIC_MULTI)
DEFAULT_METRIC = METRIC_OVERALL

# 카테고리 표 순서 고정용. ETRI score.py 는 파일 등장 순서를 쓰는데, 그러면 실행마다
# 표의 행 순서가 바뀌어 화면·비교표가 흔들린다. LogicKor 원본 문항 순서(id 1~42 가
# 카테고리별 7개씩)를 정본으로 삼아 고정하고, 목록에 없는 카테고리는 뒤에 덧붙인다.
CATEGORY_ORDER = (
    "추론(Reasoning)",
    "수학(Math)",
    "글쓰기(Writing)",
    "코딩(Coding)",
    "이해(Understanding)",
    "문법(Grammar)",
)

_SCORE_SCALE_MAX = 10.0


def extract_scores(record: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """레코드에서 (single, multi) 심판 점수를 뽑는다. 채점 필드가 없으면 None.

    None 을 예외 대신 돌려주는 이유: 한 파일에 미채점 행이 섞여 있어도 나머지로 집계를
    끝내야 한다(전량 실패보다 부분 집계가 유용). 채점 행이 0건이면 aggregate 가 판단한다.
    """
    single = record.get("query_single")
    multi = record.get("query_multi")
    if isinstance(single, dict) and isinstance(multi, dict):
        s = single.get("judge_score")
        m = multi.get("judge_score")
        if s is not None and m is not None:
            return float(s), float(m)

    # 구형 평면 키
    s = record.get("judge_single_score")
    m = record.get("judge_multi_score")
    if s is not None and m is not None:
        return float(s), float(m)

    return None


def iter_records(paths: Iterable[str]) -> Iterable[Dict[str, Any]]:
    """jsonl 들을 순회한다. evaluator 는 utf-8-sig(BOM) 로 쓰므로 그 인코딩으로 읽는다."""
    for path in paths:
        with open(path, "r", encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    # 잘린 마지막 줄(중단된 실행) 등은 건너뛴다.
                    continue


def _within(path: str, root: str) -> bool:
    """path 의 실경로가 root 실경로 안에 있는지. 심볼릭 링크 탈출을 잡는다."""
    real_root = os.path.realpath(root)
    try:
        return os.path.commonpath([os.path.realpath(path), real_root]) == real_root
    except ValueError:
        # 서로 다른 드라이브/앵커 → 같은 트리가 아니다.
        return False


def resolve_paths(pattern_or_dir: str) -> List[str]:
    """glob 패턴 또는 디렉토리를 jsonl 경로 목록으로. 디렉토리는 재귀 탐색한다.

    ⚠️ 심볼릭 링크는 따라가지 않는다. 데이터셋 내용은 사용자가 올린 tar/zip 이라
    신뢰할 수 없고, glob(recursive=True) 는 링크 디렉토리를 그대로 따라 들어가서
    마운트 밖 파일(예: 다른 잡의 산출물)을 채점 입력으로 끌어온다(실측 확인).
    호출부의 루트 검증(_resolve_input_root)은 루트 자체만 보므로 여기서 파일 단위로
    다시 막아야 한다. os.walk(followlinks=False) + islink 거부 + realpath 재검증 3중.
    """
    if os.path.isdir(pattern_or_dir):
        found: List[str] = []
        for dirpath, dirnames, filenames in os.walk(pattern_or_dir, followlinks=False):
            # 링크 디렉토리는 하위 순회 대상에서 제거(followlinks=False 로도 진입하지
            # 않지만, 목록에 남기면 아래 파일 검사가 무의미하게 돌아간다).
            dirnames[:] = [d for d in dirnames
                           if not os.path.islink(os.path.join(dirpath, d))]
            for name in filenames:
                if not name.endswith(".jsonl"):
                    continue
                full = os.path.join(dirpath, name)
                if os.path.islink(full) or not _within(full, pattern_or_dir):
                    continue
                found.append(full)
        return sorted(found)

    # glob 패턴 경로 — 패턴의 부모를 루트로 삼아 같은 규칙을 적용한다.
    root = os.path.dirname(pattern_or_dir) or "."
    return sorted(p for p in glob.glob(pattern_or_dir, recursive=True)
                  if not os.path.islink(p) and _within(p, root))


def aggregate(records: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """레코드들 → 카테고리별 Single/Multi 평균 + 전체 Single/Multi/Overall.

    Overall 은 (전체 single 평균 + 전체 multi 평균) / 2 — ETRI score.py 와 동일 정의다.
    카테고리 평균의 평균이 아니므로 카테고리별 문항 수가 다르면 값이 달라진다(현재는
    카테고리마다 7문항으로 같다).
    채점 행이 하나도 없으면 None.
    """
    per_category: Dict[str, Dict[str, List[float]]] = {}
    all_single: List[float] = []
    all_multi: List[float] = []

    for record in records:
        scores = extract_scores(record)
        if scores is None:
            continue
        single, multi = scores
        category = str(record.get("category") or "기타")
        bucket = per_category.setdefault(category, {"single": [], "multi": []})
        bucket["single"].append(single)
        bucket["multi"].append(multi)
        all_single.append(single)
        all_multi.append(multi)

    if not all_single:
        return None

    def _order(name: str) -> Tuple[int, str]:
        # 정본 순서에 있으면 그 위치, 없으면 뒤로 밀고 이름순.
        return (CATEGORY_ORDER.index(name), "") if name in CATEGORY_ORDER \
            else (len(CATEGORY_ORDER), name)

    categories = [
        {
            "category": name,
            "single": round(sum(b["single"]) / len(b["single"]), 2),
            "multi": round(sum(b["multi"]) / len(b["multi"]), 2),
            "count": len(b["single"]),
        }
        for name, b in sorted(per_category.items(), key=lambda kv: _order(kv[0]))
    ]

    single_turn = sum(all_single) / len(all_single)
    multi_turn = sum(all_multi) / len(all_multi)
    return {
        "categories": categories,
        "single_turn": round(single_turn, 2),
        "multi_turn": round(multi_turn, 2),
        "overall": round((single_turn + multi_turn) / 2, 2),
        "count": len(all_single),
        "scale_max": _SCORE_SCALE_MAX,
    }


def representative_score(agg: Dict[str, Any], metric: str) -> float:
    """선택한 지표를 results[].score 로 쓸 대표 스칼라 1개로 환산."""
    if metric == METRIC_SINGLE:
        return agg["single_turn"]
    if metric == METRIC_MULTI:
        return agg["multi_turn"]
    return agg["overall"]


def build_metrics(agg: Dict[str, Any], metric: str = DEFAULT_METRIC,
                  datasets: Optional[List[str]] = None) -> Dict[str, Any]:
    """집계 결과 → llm_evaluation 벤치마크 계약 metrics dict.

    키 구성은 evaluate-benchmark-mock 과 동형(results/averages/benchmark_set/metric_map)
    으로 두어 기존 이력 flatten·FE 렌더 경로를 그대로 태운다. 카테고리×턴 격자는 계약에
    없는 추가 정보라 'logickor' 하위에만 둔다(자유형식 metrics JSON 이라 스키마 변경 없음).
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


def score_files(pattern_or_dir: str, metric: str = DEFAULT_METRIC,
                datasets: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """경로 패턴 → metrics dict. 매칭 파일이 없거나 채점 행이 없으면 None."""
    paths = resolve_paths(pattern_or_dir)
    if not paths:
        return None
    agg = aggregate(iter_records(paths))
    if agg is None:
        return None
    metrics = build_metrics(agg, metric, datasets)
    metrics["source_files"] = [os.path.basename(p) for p in paths]
    return metrics
