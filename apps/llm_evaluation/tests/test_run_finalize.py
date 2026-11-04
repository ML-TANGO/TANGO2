"""끝난 평가 런 마감 — 조회 시점(get_project) + 백그라운드 루프(finalize_finished_runs_once).

벤치마크 완료는 lazy(결과 조회가 metrics.json 을 보고 마감)라, 결과 화면을 열지 않으면 끝난 런이
running 에 남는다. 파드는 정리돼 사라지므로 화면에서는 죽은 것처럼 보였다(서빙 2026-09-29).
`utils`(fb_utils) 가 import 되는 환경(플랫폼 파드)에서 돈다:
  kubectl -n tango-dev exec deploy/jfb-llm-evaluation -- sh -c 'cd /app && python3 -m pytest tests -q'
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from evaluation import service as S  # noqa: E402
except Exception as exc:  # noqa: BLE001
    pytest.skip(f"evaluation.service import 불가: {exc}", allow_module_level=True)


@pytest.mark.parametrize("res, expected", [
    ({"ready": True, "metrics": {}}, "completed"),
    ({"ready": False, "status": "failed"}, "failed"),
    ({"ready": False, "status": "running"}, "running"),
    ({"ready": False}, "running"),
])
def test_settle_maps_result_lookup_to_status(monkeypatch, res, expected):
    async def lookup(model_id, job_id):
        return res

    monkeypatch.setattr(S, "get_eval_result", lookup)
    assert asyncio.run(S._settle_running_run(model_id=2, job_id="jobaaa0001")) == expected


def test_project_view_settles_running_runs_through_result_lookup(monkeypatch):
    # 종전엔 컨테이너 되묻기만 해서 completed 로 답한 런이 계속 running 이었다.
    rows = [{"id": 1, "job_str_id": "jobdone001", "source_model_id": 2, "status": "running",
             "metric_set": "logickor:judge_overall"},
            {"id": 2, "job_str_id": "jobinfer01", "source_model_id": 2, "status": "running",
             "metric_set": "inference"},
            {"id": 3, "job_str_id": "jobold0001", "source_model_id": 2, "status": "completed",
             "metric_set": "arc:accuracy"}]
    settled = []

    async def project(project_id):
        return {"id": 9, "workspace_id": 2, "dataset_ids": None}

    async def runs(eval_project_id):
        return rows

    async def settle(model_id, job_id):
        settled.append(job_id)
        return "completed"

    async def comparison(rows_, workspace_id):
        return {"runs": [{"job_id": r["job_str_id"], "status": r["status"]} for r in rows_]}

    async def noop(*a, **k):
        return None

    async def batches(project_id):
        return []

    monkeypatch.setattr(S.db_model, "get_eval_project", project)
    monkeypatch.setattr(S.db_model, "list_eval_results_by_project", runs)
    monkeypatch.setattr(S, "_settle_running_run", settle)
    monkeypatch.setattr(S, "_build_run_comparison", comparison)
    monkeypatch.setattr(S, "_attach_expert_run_view", noop)
    monkeypatch.setattr(S, "_attach_run_progress", noop)
    monkeypatch.setattr(S, "_project_batches", batches)
    res = asyncio.run(S.get_project(9))
    assert settled == ["jobdone001"]            # inference 생성 런·끝난 런은 건드리지 않는다
    assert res["runs"]["runs"][0]["status"] == "completed"


def test_background_pass_finalizes_only_runs_with_metrics(tmp_path, monkeypatch):
    for job in ("jobdone001", "jobrun0001"):
        (tmp_path / job / "output").mkdir(parents=True)
    (tmp_path / "jobdone001" / "output" / "metrics.json").write_text("{}")
    lookups, bases = [], []

    async def running(limit):
        return [{"job_str_id": "jobdone001", "source_model_id": 2, "metric_set": "arc:accuracy"},
                {"job_str_id": "jobrun0001", "source_model_id": 2, "metric_set": "arc:accuracy"}]

    async def base(model_id):
        bases.append(model_id)
        return str(tmp_path)

    async def lookup(model_id, job_id):
        lookups.append(job_id)
        return {"ready": True}

    monkeypatch.setattr(S.db_model, "list_running_eval_results", running)
    monkeypatch.setattr(S, "_eval_jobs_base", base)
    monkeypatch.setattr(S, "get_eval_result", lookup)
    assert asyncio.run(S.finalize_finished_runs_once()) == 1
    assert lookups == ["jobdone001"]            # 결과 파일이 없는 런은 조회(컨테이너 되묻기)하지 않는다
    assert bases == [2]                         # 모델당 jobs 경로 한 번


def test_background_pass_survives_a_bad_row(tmp_path, monkeypatch):
    (tmp_path / "jobdone001" / "output").mkdir(parents=True)
    (tmp_path / "jobdone001" / "output" / "metrics.json").write_text("{}")

    async def running(limit):
        return [{"job_str_id": "../escape", "source_model_id": 2, "metric_set": None},
                {"job_str_id": "jobdone001", "source_model_id": 2, "metric_set": None}]

    async def base(model_id):
        return str(tmp_path)

    async def lookup(model_id, job_id):
        return {"ready": True}

    monkeypatch.setattr(S.db_model, "list_running_eval_results", running)
    monkeypatch.setattr(S, "_eval_jobs_base", base)
    monkeypatch.setattr(S, "get_eval_result", lookup)
    assert asyncio.run(S.finalize_finished_runs_once()) == 1
