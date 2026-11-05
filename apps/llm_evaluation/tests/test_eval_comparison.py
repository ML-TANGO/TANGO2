"""비교표 빌더(build_eval_comparison) — 순위에 들지 않는 런(mock·빠른 확인) 규칙.

빠른 확인(sample_limit) 런은 태스크당 앞 N문항만 채점해 분모가 다르다 — 전체 측정과 같은
줄에서 Best 를 다투면 20문항 점수가 전체 점수를 이긴다. mock 과 같은 규칙으로 뺀다.
`utils`(fb_utils) 가 import 되는 환경(플랫폼 파드)에서 돈다 — 로컬 호스트에서는 건너뛴다:
  kubectl -n tango-dev exec deploy/jfb-llm-evaluation -- sh -c 'cd /app && python3 -m pytest tests -q'
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from utils.llm_db import db_model  # noqa: E402
except Exception as exc:  # noqa: BLE001 — fb_utils 가 없거나 env 가 없어 settings 가 죽는 환경(로컬 호스트)
    pytest.skip(f"utils.llm_db.db_model import 불가: {exc}", allow_module_level=True)


def _row(run_id, score, *, limit=None, mock=False, status="completed"):
    metrics = {"averages": {"arc": score}, "mock": mock}
    if limit is not None or not mock:
        metrics["lmeval"] = {"limit": limit, "benchmarks": {}}
    return {"id": run_id, "status": status, "metrics": metrics, "metric_set": "arc:accuracy"}


def _run(result, run_id):
    return next(r for r in result["runs"] if r["id"] == run_id)


def test_quick_check_run_carries_sample_limit():
    result = db_model.build_eval_comparison([_row(1, 40.0, limit=20), _row(2, 35.0)])
    assert _run(result, 1)["sample_limit"] == 20
    assert _run(result, 2)["sample_limit"] is None


def test_quick_check_run_is_not_best_even_with_higher_score():
    result = db_model.build_eval_comparison([_row(1, 90.0, limit=20), _row(2, 35.0)])
    assert result["best"]["arc"] == 2


def test_no_best_when_only_quick_or_mock_runs():
    result = db_model.build_eval_comparison(
        [_row(1, 40.0, limit=20), _row(2, 88.0, mock=True)])
    assert "arc" not in result["best"]
    # 점수 자체는 그대로 보인다 — 순위에서만 빠진다.
    assert _run(result, 1)["metrics"]["arc"] == 40.0


@pytest.mark.parametrize("bad", [0, -3, True, "20", 1.5])
def test_malformed_limit_is_ignored(bad):
    rows = [{"id": 1, "status": "completed", "metric_set": "arc:accuracy",
             "metrics": {"averages": {"arc": 40.0}, "lmeval": {"limit": bad}}}]
    assert _run(db_model.build_eval_comparison(rows), 1)["sample_limit"] is None


def test_non_lmeval_runs_have_no_sample_limit():
    rows = [{"id": 1, "status": "completed", "metric_set": "bleu",
             "metrics": {"bleu": 12.3}}]
    assert _run(db_model.build_eval_comparison(rows), 1)["sample_limit"] is None


def test_delegated_run_carries_the_frozen_serving_commit():
    rows = [{"id": 1, "status": "completed", "metric_set": "logickor:judge_overall",
             "metrics": {"averages": {"logickor": 7.1},
                         "generate": {"mode": "remote", "endpoint": "x"},
                         "_platform_source": {"deployment": "llama3.2", "model": "llama",
                                              "commit": "ckpt-3"}}},
            {"id": 2, "status": "completed", "metric_set": "logickor:judge_overall",
             "metrics": {"averages": {"logickor": 6.0},
                         "generate": {"mode": "remote", "endpoint": "x"},
                         "_platform_source": {"deployment": "llama3.2"}}}]
    result = db_model.build_eval_comparison(rows)
    assert _run(result, 1)["source_commit"] == "ckpt-3"
    assert _run(result, 2)["source_commit"] is None       # 굳히기 이전 런 — 추측하지 않는다
    assert _run(result, 1)["source_deployment"] == "llama3.2"


def test_batch_row_is_removed_when_member_insert_fails(monkeypatch):
    # 두 번의 커밋이라 원자적이지 않다 — 멤버 삽입이 실패하면 멤버 0 인 묶음 행을 지운다.
    import asyncio
    calls = []

    async def commit(query, params=None, execute="one"):
        calls.append((" ".join(query.split())[:40], execute))
        if "eval_run_batch_member" in query:
            raise RuntimeError("fk violation")
        return 42

    monkeypatch.setattr(db_model, "commit_query", commit)
    with pytest.raises(RuntimeError):
        asyncio.run(db_model.insert_eval_run_batch(
            eval_project_id=1, workspace_id=2, source_model_id=7, job_ids=["job-a"]))
    assert [c[0].split()[0] for c in calls] == ["INSERT", "INSERT", "DELETE"]


def test_batch_rows_carry_per_run_benchmark_lists():
    # 한 런이 여러 벤치마크를 담는다 — 목록은 멤버 행의 benchmarks(JSON)에서 온다(metric_set 은 잘린다).
    base = {"id": 5, "eval_project_id": 1, "workspace_id": 2, "source_model_id": 7,
            "checkpoint": "c1", "sample_limit": None, "create_datetime": "t",
            "launch_failures": None}
    rows = [{**base, "job_str_id": "job-a", "benchmarks": '["arc", "mmlu"]'},
            {**base, "job_str_id": "job-b", "benchmarks": None},          # 기록 이전 멤버
            {**base, "job_str_id": "job-c", "benchmarks": "{broken"}]
    [batch] = db_model._batch_rows_to_dicts(rows)
    assert batch["job_ids"] == ["job-a", "job-b", "job-c"]
    assert batch["job_benchmarks"] == {"job-a": ["arc", "mmlu"]}


def test_batch_member_insert_stores_benchmarks(monkeypatch):
    import asyncio
    import json
    calls = []

    async def commit(query, params=None, execute=None, **kw):
        calls.append((query, params))
        return 11

    monkeypatch.setattr(db_model, "commit_query", commit)
    asyncio.run(db_model.insert_eval_run_batch(
        eval_project_id=1, workspace_id=2, source_model_id=7, job_ids=["job-a", "job-b"],
        job_benchmarks={"job-a": ["arc", "mmlu"]}))
    member_params = calls[1][1]
    assert member_params == [(11, "job-a", 0, json.dumps(["arc", "mmlu"])), (11, "job-b", 1, None)]
