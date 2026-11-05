"""lm-eval 결과 dict → 플랫폼 metrics.json.

최상위 계약은 evaluate-benchmark-mock 과 같다(llm_evaluation `_flatten_eval_metrics` 가
averages 를, FE 결과 뷰가 results[] 를 읽는다). 서브태스크·설정 같은 상세는
`lmeval.benchmarks[<id>]` 에 싣는다 — results[] 에 넣으면 FE 행 키
(`${benchmark}:${metric}`)가 겹친다.

이 모듈은 lm_eval·torch 를 임포트하지 않는다 — GPU 없이 단위 테스트가 돈다.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

import registry as REG

_NON_SCORE_KEYS = {"alias", "samples", "sample_len", " "}


def _num(v) -> Optional[float]:
    """숫자로 쓸 수 있는 값만 float 로. 'N/A'·NaN·bool 은 None(metrics.json 은 allow_nan=False)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return None if math.isnan(f) or math.isinf(f) else f


def scale(bench: REG.Benchmark, metric: str, value: float) -> Tuple[float, Optional[str]]:
    """(환산값, 경고). 명시표에 없는 지표는 원값 그대로 + 경고."""
    kind = bench.scale.get(metric)
    if kind == REG.FRACTION:
        return value * 100.0, None
    if kind == REG.PERCENT:
        return value, None
    return value, f"{bench.id}: 스케일 미지정 지표 {metric!r} — 환산하지 않고 원값을 싣는다"


def _metrics_of(bench: REG.Benchmark, src: dict, warnings: List[str]) -> List[dict]:
    """한 태스크(또는 그룹) 결과 dict → [{metric, filter, score, stderr}] (스케일 환산)."""
    rows = []
    for key, raw in (src or {}).items():
        name, _, filt = str(key).partition(",")
        if name in _NON_SCORE_KEYS or name.endswith("_stderr"):
            continue
        val = _num(raw)
        if val is None:
            continue
        score, warn = scale(bench, name, val)
        if warn and warn not in warnings:
            warnings.append(warn)
        se = _num(src.get(f"{name}_stderr,{filt}" if filt else f"{name}_stderr"))
        if se is not None and bench.scale.get(name) == REG.FRACTION:
            se *= 100.0
        rows.append({"metric": name, "filter": filt or "none",
                     "score": round(score, 4),
                     "stderr": None if se is None else round(se, 4)})
    return rows


def _pick(rows: List[dict], metric: str, filt: str) -> Optional[float]:
    for r in rows:
        if r["metric"] == metric and r["filter"] == filt:
            return r["score"]
    return None


def _n_effective(n_samples: dict, names) -> Optional[int]:
    total, seen = 0, False
    for name in names:
        eff = ((n_samples or {}).get(name) or {}).get("effective")
        if isinstance(eff, int):
            total += eff
            seen = True
    return total if seen else None


def summarize_lmeval(bench: REG.Benchmark, raw: dict) -> dict:
    """simple_evaluate 반환값 → 벤치마크 요약(대표값·지표·서브태스크·건수·경고)."""
    results = raw.get("results") or {}
    groups = raw.get("groups") or {}
    warnings: List[str] = []

    if bench.mean_of_tasks:
        per_task = {t: _metrics_of(bench, results.get(t), warnings) for t in bench.tasks}
        vals = [_pick(per_task[t], bench.lm_metric, bench.lm_filter) for t in bench.tasks]
        if any(v is None for v in vals):
            missing = [t for t, v in zip(bench.tasks, vals) if v is None]
            raise ValueError(f"{bench.id}: 대표 지표 {bench.lm_metric} 가 없는 태스크 {missing}")
        primary = sum(vals) / len(vals)
        # 전 태스크에 공통인 지표만 평균해 상세에 싣는다.
        common = set.intersection(*[{(r["metric"], r["filter"]) for r in rows}
                                    for rows in per_task.values()])
        metrics = [{"metric": m, "filter": f, "stderr": None,
                    "score": round(sum(_pick(per_task[t], m, f) for t in bench.tasks)
                                   / len(bench.tasks), 4)}
                   for m, f in sorted(common)]
        subtasks = [{"task": t, **row} for t in bench.tasks for row in per_task[t]
                    if row["metric"] == bench.lm_metric and row["filter"] == bench.lm_filter]
        leaves = list(bench.tasks)
    else:
        task = bench.tasks[0]
        src = groups.get(task) or results.get(task)
        if src is None:
            raise ValueError(f"{bench.id}: lm-eval 결과에 {task!r} 가 없다")
        metrics = _metrics_of(bench, src, warnings)
        primary = _pick(metrics, bench.lm_metric, bench.lm_filter)
        if primary is None:
            raise ValueError(f"{bench.id}: 대표 지표 {bench.lm_metric},{bench.lm_filter} 가 "
                             f"결과에 없다 (있는 키: {sorted(src)})")
        # 서브태스크 = 그룹 아래의 말단 태스크. 단일 태스크면 비어 있다.
        leaves = [name for name in results if name not in groups and name != task]
        subtasks = []
        for name in sorted(leaves):
            rows = _metrics_of(bench, results[name], warnings)
            row = next((r for r in rows if r["metric"] == bench.lm_metric), None)
            if row:
                subtasks.append({"task": name, **row})
        leaves = leaves or [task]

    return {
        "benchmark": bench.id,
        "metric": bench.metric,
        "score": round(primary, 4),
        "tasks": list(bench.tasks),
        "num_fewshot": bench.num_fewshot,
        "lm_metric": bench.lm_metric,
        "lm_filter": bench.lm_filter,
        "metrics": metrics,
        "subtasks": subtasks,
        "n": _n_effective(raw.get("n-samples"), leaves),
        "warnings": warnings,
    }


def build_metrics(summaries: List[dict], *, datasets: List[str], checkpoint: dict,
                  engine: dict, limit: Optional[int], meta: dict,
                  failures: Optional[List[dict]] = None) -> dict:
    """벤치마크 요약 목록 → metrics.json(dict).

    failures = 채점하다 실패한 벤치마크 [{benchmark, metric, error}] — results·averages 에는 넣지
    않는다(점수가 없다). 따로 싣는 이유: 빼 버리면 5개를 요청한 런이 "4개 채점 완료"로만 읽혀
    하나가 빠진 사실이 결과 어디에도 남지 않는다."""
    results = [{"benchmark": s["benchmark"], "metric": s["metric"], "score": s["score"]}
               for s in summaries]
    return {
        "mode": "benchmark",
        "mock": False,
        "results": results,
        "averages": {r["benchmark"]: r["score"] for r in results},
        "benchmark_set": [r["benchmark"] for r in results],
        "metric_map": {r["benchmark"]: r["metric"] for r in results},
        "failed_benchmarks": [dict(f) for f in failures or []],
        "datasets": list(datasets or []),
        "checkpoint": checkpoint,
        "lmeval": {
            **engine,
            # limit 을 준 점수는 분모가 달라 전체 측정과 나란히 비교하면 안 된다.
            "limit": limit,
            "benchmarks": {s["benchmark"]: {k: v for k, v in s.items() if k != "benchmark"}
                           for s in summaries},
        },
        "_meta": meta,
    }
