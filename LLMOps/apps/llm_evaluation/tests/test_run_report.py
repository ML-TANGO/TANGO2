"""평가 실행 1건 리포트(Markdown) — 요약 + 샘플별 상세.

`utils`(fb_utils) 가 import 되는 환경(플랫폼 파드)에서 돈다:
  kubectl -n tango-dev exec deploy/jfb-llm-evaluation -- sh -c 'cd /app && python3 -m pytest tests -q'
"""
from __future__ import annotations

import asyncio
import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from evaluation import report as R  # noqa: E402
except Exception as exc:  # noqa: BLE001
    pytest.skip(f"evaluation.report import 불가: {exc}", allow_module_level=True)


# ── Markdown 안전 출력 ────────────────────────────────────────────────────────

def test_cell_escapes_pipes_and_newlines():
    assert R.md_cell("a|b\nc\r\nd") == "a\\|b c d"
    assert R.md_cell(None) == "-"


def test_cell_escapes_backslash_before_pipe():
    # `\|` 를 그대로 두면 `\\|` 가 되어 파이프가 열 구분자로 살아난다.
    assert R.md_cell("a\\|b") == "a\\\\\\|b"


def test_cell_is_capped():
    cell = R.md_cell("x" * (R.CELL_LIMIT + 50))
    assert len(cell) == R.CELL_LIMIT + 1 and cell.endswith("…")


def test_numbers_never_use_exponent_for_large_values():
    assert R._num(1729500000.5) == "1729500000.5"
    assert R._num(6.0) == "6"
    assert R._num(0.00001) == "1.00e-05"


def test_clip_is_idempotent():
    once = R._clip("가" * (R.TEXT_LIMIT + 10))
    assert R._clip(once) == once and once.count("생략") == 1


def test_db_times_are_shown_in_kst():
    assert R._kst("2026-10-20 10:00:00") == "2026-10-20 19:00"
    assert R._kst(None) == "-"


def test_fence_outlasts_backticks_in_content():
    text = "코드 ``` 블록 ```` 끝"
    fenced = R.md_fence(text)
    assert fenced.startswith("`````\n") and fenced.endswith("\n`````")
    assert text in fenced


def test_meta_values_hide_paths():
    rows = R.meta_rows({"csv": "/jf-data/local/main/SDS/jobs/x/output/a.csv", "batch_size": 8,
                        "nested": {"a": 1}})
    assert ("csv", "<path>") in rows
    assert ("batch_size", "8") in rows
    assert all(k != "nested" for k, _ in rows)


# ── 요약 ─────────────────────────────────────────────────────────────────────

def _reference_metrics(**extra):
    m = {
        "mode": "lmeval", "mock": False,
        "results": [{"benchmark": "arc", "metric": "acc_norm", "score": 0.5123}],
        "averages": {"arc": 0.5123},
        "failed_benchmarks": [{"benchmark": "gsm8k", "metric": "exact_match",
                               "error": "load failed at /tmp/lmeval-merged/x"}],
        "lmeval": {"engine": "vllm", "lm_eval_version": "0.4.8", "seed": 1234, "limit": None,
                   "benchmarks": {"arc": {
                       "metric": "acc_norm", "score": 0.5123, "num_fewshot": 25, "n": 1172,
                       "metrics": [{"metric": "acc_norm", "filter": "none", "score": 0.5123,
                                    "stderr": 0.0146}],
                       "subtasks": [{"task": "arc_challenge", "metric": "acc_norm",
                                     "filter": "none", "score": 0.5123, "stderr": 0.0146}]}}},
    }
    m.update(extra)
    return m


def test_reference_summary_lists_scores_failures_and_settings():
    md = R.render_benchmark_summary(_reference_metrics(), "reference")
    assert "| arc | acc_norm | 0.5123 |" in md
    assert "gsm8k" in md and "/tmp/lmeval-merged" not in md
    assert "arc_challenge" in md and "0.0146" in md
    assert "25" in md   # num_fewshot


def test_mock_scores_are_flagged():
    md = R.render_benchmark_summary(_reference_metrics(mock=True), "reference")
    assert "mock" in md


def test_judge_summary_lists_categories():
    metrics = {"results": [{"benchmark": "logickor", "metric": "judge_overall", "score": 6.2}],
               "logickor": {"categories": [{"category": "추론(Reasoning)", "single": 5.5,
                                            "multi": 6.0, "count": 6}],
                            "single_turn": 5.9, "multi_turn": 6.5, "overall": 6.2, "count": 42,
                            "scale_max": 10},
               "judge": {"model": "google/gemma", "judged": 42, "errors": 0}}
    md = R.render_benchmark_summary(metrics, "judge")
    assert "| 추론(Reasoning) | 5.5 | 6 | 6 |" in md
    assert "6.2" in md and "google/gemma" in md


def test_intent_summary_lists_intent_and_slot_scores():
    metrics = {"results": [{"benchmark": "mixatis", "metric": "joint_acc", "score": 0.47}],
               "mixatis": {"count": 828, "intent": {"acc": 0.9, "precision": 0.91, "recall": 0.92,
                                                    "f1": 0.915},
                           "slot": {"precision": 0.8, "recall": 0.81, "f1": 0.805},
                           "joint_acc": 0.47}}
    md = R.render_benchmark_summary(metrics, "intent")
    assert "0.915" in md and "0.805" in md and "0.47" in md and "828" in md


# ── 샘플별 상세 ──────────────────────────────────────────────────────────────

def test_reference_standard_benchmarks_say_no_per_sample_data(tmp_path):
    md = R.render_reference_samples(str(tmp_path), limit=100)
    assert "문항별" in md


def test_reference_custom_shows_lowest_f1_first(tmp_path):
    rows = [{"index": i, "input": f"질문{i}", "prediction": f"답{i}", "references": [f"정답{i}"],
             "f1": f, "em": 0} for i, f in enumerate([0.9, 0.1, 0.5])]
    (tmp_path / "custom_samples.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    md = R.render_reference_samples(str(tmp_path), limit=2)
    assert md.index("질문1") < md.index("질문2")
    assert "질문0" not in md
    assert "3건 중 2건" in md


def _write_judge(out, rows):
    d = out / "evaluated"
    d.mkdir()
    (d / "default.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8-sig")


def test_judge_samples_show_questions_answers_scores_and_reasons(tmp_path):
    _write_judge(tmp_path, [{
        "id": 1, "category": "추론(Reasoning)", "questions": ["Q1", "Q2"],
        "outputs": ["A1", "A2"], "references": [None, None],
        "query_single": {"judge_message": "근거가 부족함", "judge_score": 3.0},
        "query_multi": {"judge_message": "후속 답변 정확", "judge_score": 8.0}}])
    md = R.render_judge_samples(str(tmp_path), limit=100)
    for s in ("Q1", "A1", "Q2", "A2", "근거가 부족함", "후속 답변 정확", "3", "8"):
        assert s in md


def test_judge_samples_respect_limit(tmp_path):
    rows = [{"id": i, "category": "c", "questions": [f"질문{i}", ""], "outputs": ["", ""],
             "references": [None, None], "query_single": {"judge_message": "", "judge_score": 1},
             "query_multi": {"judge_message": "", "judge_score": 1}} for i in range(5)]
    _write_judge(tmp_path, rows)
    md = R.render_judge_samples(str(tmp_path), limit=2)
    assert "질문1" in md and "질문2" not in md
    assert "5건 중 2건" in md


def _write_mixatis(out, rows):
    with open(out / "mixatis_eval.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sentence", "gold_intents", "pred_intents",
                                          "gold_slots", "pred_slots", "intent_raw", "slot_raw"])
        w.writeheader()
        for r in rows:
            w.writerow({"intent_raw": "", "slot_raw": "", **r})


def test_intent_samples_list_only_wrong_predictions(tmp_path):
    _write_mixatis(tmp_path, [
        {"sentence": "맞은 문장", "gold_intents": "a;b", "pred_intents": "b;a",
         "gold_slots": "x=city", "pred_slots": "x=city"},
        {"sentence": "의도 틀림", "gold_intents": "a", "pred_intents": "c",
         "gold_slots": "", "pred_slots": ""},
        {"sentence": "슬롯 틀림", "gold_intents": "a", "pred_intents": "a",
         "gold_slots": "x=city", "pred_slots": "x=state"},
        # 채점기(overall_acc)는 정렬한 목록을 비교한다 — 중복 하나 차이도 오답이다.
        {"sentence": "중복 의도", "gold_intents": "a;a", "pred_intents": "a",
         "gold_slots": "", "pred_slots": ""},
    ])
    md = R.render_intent_samples(str(tmp_path), limit=100)
    assert "맞은 문장" not in md
    assert "의도 틀림" in md and "슬롯 틀림" in md and "중복 의도" in md
    assert "4건 중 3건" in md


def test_intent_samples_survive_oversized_field(tmp_path):
    _write_mixatis(tmp_path, [
        {"sentence": "틀림", "gold_intents": "a", "pred_intents": "b", "gold_slots": "",
         "pred_slots": ""},
        {"sentence": "x" * 300, "gold_intents": "a", "pred_intents": "b", "gold_slots": "",
         "pred_slots": ""},
    ])
    old = csv.field_size_limit(100)
    try:
        md = R.render_intent_samples(str(tmp_path), limit=100)
    finally:
        csv.field_size_limit(old)
    assert "틀림" in md and "읽지 못해" in md


def test_jsonl_skips_oversized_lines(monkeypatch, tmp_path):
    monkeypatch.setattr(R, "_MAX_LINE", 50)
    path = tmp_path / "rows.jsonl"
    path.write_text(json.dumps({"a": "x" * 200}) + "\n" + json.dumps({"a": "ok"}) + "\n",
                    encoding="utf-8")
    assert list(R._iter_jsonl(str(path))) == [{"a": "ok"}]


def test_custom_rows_are_clipped_while_reading(tmp_path):
    big = "가" * (R.TEXT_LIMIT * 3)
    (tmp_path / "custom_samples.jsonl").write_text(
        json.dumps({"index": 0, "input": big, "prediction": "p", "references": ["r"], "f1": 0.1},
                   ensure_ascii=False), encoding="utf-8")
    md = R.render_reference_samples(str(tmp_path), limit=10)
    assert big not in md and md.count("생략") == 1


def test_expert_section_pairs_samples_with_ratings():
    samples = {"total": 2, "status": "running", "expert_prompt": "기준", "samples": [
        {"idx": 0, "input": "입력0", "output": "출력0", "reference": "참고0", "image": "img/a.png"},
        {"idx": 1, "input": "입력1", "output": "출력1", "reference": None}]}
    result = {"rated": 1, "avg_score": 3.0, "pass_rate": 0.0,
              "distribution": {"1": 0, "2": 0, "3": 1, "4": 0, "5": 0},
              "ratings": [{"sample_idx": 0, "score": 3, "verdict": "X", "comment": "근거 부족",
                           "rater_user": "rater1", "create_datetime": "2026-10-01 10:00"}]}
    md = R.render_expert(samples, result, limit=100)
    assert "1 / 2" in md and "3.0" in md
    assert "근거 부족" in md and "rater1" in md
    assert "a.png" in md and "img/a.png" not in md
    assert "미채점" in md


# ── 조립 ─────────────────────────────────────────────────────────────────────

def test_build_report_for_reference_run(monkeypatch, tmp_path):
    from evaluation import service as S

    async def by_job(job_str_id, source_model_id=None):
        return {"id": 7, "workspace_id": 2, "job_str_id": job_str_id, "dataset_name": "arc-ko",
                "metric_set": "arc:acc_norm", "status": "completed",
                "create_datetime": "2026-10-20 10:00"}

    async def by_ids(result_ids, workspace_id):
        return [{"id": 7, "eval_project_id": 3}]

    async def project(project_id):
        return {"id": 3, "name": "SDS 정답 대조", "eval_type": "reference"}

    async def model(model_id):
        return {"id": model_id, "name": "ETRI-SDS-VLM"}

    async def result(model_id, job_id):
        return {"job_id": job_id, "ready": True, "metrics": _reference_metrics()}

    async def output_dir(model_id, job_id, jobs_base=None):
        return str(tmp_path)

    monkeypatch.setattr(R.db_model, "get_eval_result_by_job", by_job)
    monkeypatch.setattr(R.db_model, "list_eval_results_by_ids", by_ids)
    monkeypatch.setattr(R.db_model, "get_eval_project", project)
    monkeypatch.setattr(R.db_model, "get_model", model)
    monkeypatch.setattr(S, "get_eval_result", result)
    monkeypatch.setattr(S, "_eval_output_dir", output_dir)

    out = asyncio.run(R.build_run_report(model_id=38, job_id="abcdef0123"))
    md = out["markdown"]
    assert out["filename"].endswith(".md") and "abcdef01" in out["filename"]
    assert "SDS 정답 대조" in md and "정답 대조" in md and "ETRI-SDS-VLM" in md
    assert "arc-ko" in md and "| arc | acc_norm | 0.5123 |" in md


def test_build_report_for_cancelled_run_says_no_result(monkeypatch):
    from evaluation import service as S

    async def by_job(job_str_id, source_model_id=None):
        return {"id": 7, "workspace_id": 2, "job_str_id": job_str_id, "dataset_name": "arc-ko",
                "metric_set": "arc:acc_norm", "status": "cancelled",
                "create_datetime": "2026-10-20 10:00:00"}

    async def nothing(*args, **kwargs):
        return None

    async def result(model_id, job_id):
        return {"job_id": job_id, "ready": False, "status": "cancelled", "metrics": None}

    monkeypatch.setattr(R.db_model, "get_eval_result_by_job", by_job)
    monkeypatch.setattr(R.db_model, "list_eval_results_by_ids", nothing)
    monkeypatch.setattr(R.db_model, "get_model", nothing)
    monkeypatch.setattr(S, "get_eval_result", result)

    md = asyncio.run(R.build_run_report(model_id=38, job_id="abcdef0123"))["markdown"]
    assert "취소되어 결과가 없습니다" in md and "다시 내보내세요" not in md
    assert "2026-10-20 19:00" in md


def test_build_report_unknown_run_raises(monkeypatch):
    async def by_job(job_str_id, source_model_id=None):
        return None

    monkeypatch.setattr(R.db_model, "get_eval_result_by_job", by_job)
    with pytest.raises(ValueError):
        asyncio.run(R.build_run_report(model_id=38, job_id="abcdef0123"))


# ── 프로젝트 리포트(실행 전체 요약) ───────────────────────────────────────────

def _run(run_id, job, status="completed", metrics=None, **extra):
    base = {"id": run_id, "job_id": job, "dataset_name": "ds-a", "metric_set": "arc:acc",
            "status": status, "create_datetime": "2026-10-20 01:00:00", "model_id": 21,
            "model_name": "model-a", "checkpoint": None, "source_mode": None,
            "source_model": "model-a", "source_deployment": None, "source_commit": None,
            "judge_model": None, "judge_deployment": None, "mock": False, "sample_limit": None,
            "metrics": metrics or {}}
    base.update(extra)
    return base


def _patch_project(monkeypatch, eval_type, runs, best, metric_keys, raw=None, name="P|1"):
    from evaluation import service as S

    async def get_project(project_id):
        return {"project": {"id": project_id, "workspace_id": 2, "name": name,
                            "description": "설명", "eval_type": eval_type, "status": "completed",
                            "creator": "acryl", "create_datetime": "2026-10-01 00:00:00"},
                "runs": {"metric_keys": metric_keys, "best": best, "runs": runs}, "batches": []}

    async def rows(result_ids, workspace_id):
        return [{"job_str_id": job, "metrics": json.dumps(m)} for job, m in (raw or {}).items()]

    monkeypatch.setattr(S, "get_project", get_project)
    monkeypatch.setattr(R.db_model, "list_eval_results_by_ids", rows)


def test_project_report_summarises_reference_runs(monkeypatch):
    runs = [
        _run(1, "job1", metrics={"arc": 0.5, "kmmlu": 0.4}, checkpoint="ckpt-1",
             source_mode="checkpoint"),
        _run(2, "job2", metrics={"arc": 0.6, "kmmlu": 0.3}, model_name="model-b",
             source_model="model-b", dataset_name="ds-b"),
        _run(3, "job3", metrics={"arc": 0.9}, mock=True),
        _run(4, "job4", metrics={"arc": 0.8}, sample_limit=20),
        _run(5, "job5", status="failed"),
        _run(6, "job6", metric_set="inference"),
    ]
    _patch_project(monkeypatch, "reference", runs, {"arc": 2, "kmmlu": 1}, ["arc", "kmmlu"])

    out = asyncio.run(R.build_project_report(project_id=3))
    md = out["markdown"]
    assert out["filename"].endswith(".md") and "P_1" in out["filename"]
    assert "P\\|1" in md and "정답 대조" in md and "2026-10-01 09:00" in md
    assert "| 0.6 ★ |" in md and "| 0.4 ★ |" in md            # 지표별 최고 표시
    assert "ckpt-1" in md and "model-b" in md
    assert "mock" in md and "빠른 확인" in md                  # 비교에서 뺀 런 안내
    assert "모델" in md and "데이터셋" in md and "섞여" in md   # 서로 다른 모델·데이터셋 경고
    assert "job6" not in md                                     # 추론 생성 런은 요약에서 제외
    assert "실패" in md


def test_project_report_pivots_judge_categories(monkeypatch):
    lk = lambda o, s, m: {"logickor": {"overall": o, "single_turn": s, "multi_turn": m,
                                        "categories": [{"category": "추론", "single": s,
                                                        "multi": m, "count": 7}]}}
    runs = [_run(1, "j1", metrics={"logickor": 4.3}, judge_model="gemma"),
            _run(2, "j2", metrics={"logickor": 5.1}, judge_model="gemma")]
    _patch_project(monkeypatch, "judge", runs, {"logickor": 2}, ["logickor"],
                   raw={"j1": lk(4.3, 5.0, 3.6), "j2": lk(5.1, 5.5, 4.7)})

    md = asyncio.run(R.build_project_report(project_id=3))["markdown"]
    assert "gemma" in md and "5.1 ★" in md
    assert "| 추론 | 5 / 3.6 | 5.5 / 4.7 |" in md


def test_project_report_lists_intent_scores(monkeypatch):
    mx = {"mixatis": {"joint_acc": 0.49, "intent": {"acc": 0.93, "f1": 0.97},
                      "slot": {"f1": 0.86}}}
    _patch_project(monkeypatch, "intent", [_run(1, "j1", metrics={"mixatis": 0.49})],
                   {"mixatis": 1}, ["mixatis"], raw={"j1": mx})

    md = asyncio.run(R.build_project_report(project_id=3))["markdown"]
    assert "0.49 ★" in md and "0.93" in md and "0.97" in md and "0.86" in md


def test_project_report_shows_expert_progress(monkeypatch):
    runs = [_run(1, "e1", metric_set="expert",
                 metrics={"expert_avg_score": 4.2, "expert_pass_rate": 80.0}, run_name="세트 1"),
            _run(2, "e2", metric_set="expert", status="running", run_name="세트 2",
                 expert_progress={"rated": 30, "total": 100, "avg_score": 3.5})]
    _patch_project(monkeypatch, "expert", runs, {"expert_avg_score": 1},
                   ["expert_avg_score", "expert_pass_rate"],
                   raw={"e1": {"expert_avg_score": 4.2, "expert_pass_rate": 80.0,
                               "_rated": 100, "_total": 100}})

    md = asyncio.run(R.build_project_report(project_id=3))["markdown"]
    assert "세트 1" in md and "100 / 100" in md and "4.2 ★" in md and "80" in md
    assert "세트 2" in md and "30 / 100" in md and "3.5" in md


def test_project_report_unknown_project_raises(monkeypatch):
    from evaluation import service as S

    async def get_project(project_id):
        raise Exception(f"eval project {project_id} not found")

    monkeypatch.setattr(S, "get_project", get_project)
    with pytest.raises(Exception):
        asyncio.run(R.build_project_report(project_id=999))


def test_project_judge_main_score_uses_logickor_key(monkeypatch):
    runs = [_run(1, "j1", metrics={"logickor": 4.3}), _run(2, "j2", metrics={"logickor": 5.1},
                                                         judge_model="a|b%")]
    _patch_project(monkeypatch, "judge", runs, {"logickor": 2}, ["a_first", "logickor"])

    md = asyncio.run(R.build_project_report(project_id=3))["markdown"]
    assert "5.1 ★" in md and "| 4.3 |" in md
    assert "a\\|b%" in md                      # 문자열 셀은 늘 이스케이프


def test_project_warns_when_deployments_differ(monkeypatch):
    runs = [_run(1, "d1", metrics={"arc": 0.5}, source_mode="deployment", source_deployment="dep-a"),
            _run(2, "d2", metrics={"arc": 0.6}, source_mode="deployment", source_deployment="dep-b")]
    _patch_project(monkeypatch, "reference", runs, {"arc": 2}, ["arc"])

    md = asyncio.run(R.build_project_report(project_id=3))["markdown"]
    assert "섞여" in md


def test_project_reference_table_caps_metric_columns(monkeypatch):
    keys = [f"b{i:02d}" for i in range(10)]
    runs = [_run(1, "r1", metrics={k: 0.5 for k in keys})]
    _patch_project(monkeypatch, "reference", runs, {k: 1 for k in keys}, keys,
                   name="**P** #1")

    md = asyncio.run(R.build_project_report(project_id=3))["markdown"]
    header_row = next(line for line in md.splitlines() if line.startswith("| # |"))
    assert "b07" in header_row and "b08" not in header_row
    assert "앞 8개" in md and "b09" in md     # 숨긴 지표는 안내 + 최고 기록 표에 남는다
    assert md.startswith("# 평가 프로젝트 리포트 — P 1")


def test_project_hidden_metric_without_best_still_listed(monkeypatch):
    keys = [f"b{i:02d}" for i in range(9)]
    runs = [_run(1, "r1", status="failed", metrics={"b08": 0.7})]   # 실패 런에만 있는 9번째 지표
    _patch_project(monkeypatch, "reference", runs, {}, keys)

    md = asyncio.run(R.build_project_report(project_id=3))["markdown"]
    assert "## 나머지 지표" in md and "| #1 | b08 | 0.7 |" in md
