"""run_benchmark 라우팅 — lm-eval 채점기는 로컬 가중치, 나머지는 배포 위임(회귀 없음).

DB·외부컨테이너·배포 조회는 전부 가짜로 바꿔 끼운다. `utils`(fb_utils) 가 import 되는
환경(플랫폼 파드)에서 돈다 — 로컬 호스트에서는 건너뛴다:
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
except Exception as exc:  # noqa: BLE001 — fb_utils 가 없거나 env 가 없어 settings 가 죽는 환경(로컬 호스트)
    pytest.skip(f"evaluation.service import 불가: {exc}", allow_module_level=True)


class _FakeClient:
    calls = []

    def __init__(self, base_url, client):
        pass

    async def start_job(self, **kw):
        _FakeClient.calls.append(kw)
        return {"job_id": "job-1"}


@pytest.fixture
def wired(monkeypatch):
    _FakeClient.calls = []
    seen = {"deploy_ckpt": [], "remote_gen": []}

    async def load_project(project_id, types):
        return {"eval_type": "reference"}

    async def run_model(project, model_id):
        return {"name": "llama"}, 2

    async def dataset(dataset_id):
        return {"workspace_id": 2, "name": "ds1", "access": "0"}

    async def deploy_ckpt(pid, model_id, workspace_id, purpose, off_hint):
        seen["deploy_ckpt"].append(purpose)
        return "source_model"

    async def remote_gen(pid, model_id, workspace_id):
        seen["remote_gen"].append(pid)
        return {"base_url": "http://shim/v1"}

    async def noop(*a, **k):
        return None

    monkeypatch.setattr(S, "_load_project_for_run", load_project)
    monkeypatch.setattr(S, "_resolve_run_model", run_model)
    monkeypatch.setattr(S.db_model, "get_dataset_model", dataset)
    monkeypatch.setattr(S, "_resolve_deployment_checkpoint", deploy_ckpt)
    monkeypatch.setattr(S, "_resolve_remote_generator", remote_gen)
    monkeypatch.setattr(S, "ExternalContainerClient", _FakeClient)
    monkeypatch.setattr(S.db_model, "insert_eval_result", noop)
    monkeypatch.setattr(S.db_model, "update_eval_project_status", noop)
    # 묶음 기록도 가짜로 — 빠뜨리면 파드 안 테스트가 실제 DB 에 묶음 행을 쓴다.
    monkeypatch.setattr(S.db_model, "insert_eval_run_batch", noop, raising=False)
    return seen


def _run(benchmarks, **kw):
    return asyncio.run(S.run_benchmark(project_id=1, model_id=7, dataset_ids=[3],
                                       benchmarks=benchmarks, inference_playground_id=11, **kw))


def test_lmeval_benchmark_uses_local_weights(wired):
    res = _run(["mmlu"], run_options={"sample_limit": 20})
    call = _FakeClient.calls[-1]
    assert call["manifest_name"] == S.settings.BENCHMARK_MANIFEST_NAME == "evaluate-lmeval"
    assert call["gpu_count"] is None                       # 매니페스트의 GPU 1장
    assert call["params"]["checkpoint_name"] == "source_model"
    assert call["params"]["limit"] == 20
    assert "generate_base_url" not in call["params"]
    assert wired["remote_gen"] == [] and wired["deploy_ckpt"] == ["lm-eval 벤치마크 채점"]
    assert res["used_deployment"] is False and res["checkpoint"] == "source_model"


def test_humaneval_goes_to_isolated_code_scorer(wired):
    _run(["humaneval"])
    assert _FakeClient.calls[-1]["manifest_name"] == S.settings.BENCHMARK_CODE_MANIFEST_NAME


def test_humaneval_cannot_share_a_run(wired):
    with pytest.raises(Exception, match="different scorers"):
        _run(["humaneval", "mmlu"])
    assert _FakeClient.calls == []


def test_sample_limit_rejected_for_other_scorers(wired):
    with pytest.raises(Exception, match="sample_limit"):
        _run(["mixatis"], run_options={"sample_limit": 5})
    assert _FakeClient.calls == []


def test_delegated_scorers_still_delegate(wired):
    res = _run(["mixatis"])
    call = _FakeClient.calls[-1]
    assert call["params"]["generate_base_url"] == "http://shim/v1"
    assert "checkpoint_name" not in call["params"]
    assert call["gpu_count"] == 0                           # 완전 위임
    assert res["used_deployment"] is True and wired["deploy_ckpt"] == []


# ── 데이터셋 선택화 — lm-eval 표준 벤치마크는 이미지에 구운 문항만 쓴다 ─────────────────

def _run_no_dataset(benchmarks, **kw):
    return asyncio.run(S.run_benchmark(project_id=1, model_id=7, dataset_ids=[],
                                       benchmarks=benchmarks, inference_playground_id=11, **kw))


def test_lmeval_run_without_dataset_mounts_nothing(wired, monkeypatch):
    inserted = []

    async def insert(**kw):
        inserted.append(kw)

    monkeypatch.setattr(S.db_model, "insert_eval_result", insert)
    res = _run_no_dataset(["arc"])
    params = _FakeClient.calls[-1]["params"]
    assert "_dataset" not in params and params["datasets"] == []
    assert inserted[-1]["dataset_id"] is None and inserted[-1]["dataset_name"] is None
    assert res["dataset_ids"] == [] and res["datasets"] == []


@pytest.mark.parametrize("benchmark", ["custom", "mixatis"])
def test_dataset_still_required_where_the_scorer_reads_it(wired, benchmark):
    with pytest.raises(Exception, match="데이터셋"):
        _run_no_dataset([benchmark])
    assert _FakeClient.calls == []


# ── 묶음 실행 — gpu_count 생략 = 벤치마크마다 런 하나(§12.2), 체크포인트는 한 번만 푼다 ──

@pytest.fixture
def gpu(monkeypatch):
    state = {"free": 4}

    async def free(workspace_id):
        return state["free"]

    monkeypatch.setattr(S, "_gpu_free_count", free)
    return state


def _batch(benchmarks, **kw):
    kw.setdefault("dataset_ids", [])
    return asyncio.run(S.run_benchmark_batch(project_id=1, model_id=7, benchmarks=benchmarks,
                                             inference_playground_id=11, **kw))


def test_batch_launches_one_run_per_benchmark_on_one_checkpoint(wired, gpu):
    res = _batch(["arc", "kmmlu", "humaneval"], run_options={"sample_limit": 20})
    calls = _FakeClient.calls
    assert [c["params"]["benchmark_set"] for c in calls] == [["arc"], ["kmmlu"], ["humaneval"]]
    assert [c["manifest_name"] for c in calls] == [
        S.settings.BENCHMARK_MANIFEST_NAME, S.settings.BENCHMARK_MANIFEST_NAME,
        S.settings.BENCHMARK_CODE_MANIFEST_NAME]
    assert {c["params"]["checkpoint_name"] for c in calls} == {"source_model"}
    assert all(c["params"]["limit"] == 20 for c in calls)
    # 체크포인트는 묶음에서 한 번만 푼다 — 런마다 풀면 중간에 배포가 커밋을 바꿨을 때
    # 한 묶음 안에서 서로 다른 가중치를 잰다.
    assert wired["deploy_ckpt"] == ["lm-eval 벤치마크 채점"]
    assert [(r["benchmarks"], r.get("job_id")) for r in res["runs"]] == [
        (["arc"], "job-1"), (["kmmlu"], "job-1"), (["humaneval"], "job-1")]
    assert res["checkpoint"] == "source_model" and res["failed"] == 0


@pytest.mark.parametrize("benchmarks", [["arc", "mixatis"], ["arc", "logickor"]])
def test_batch_rejects_scorers_without_local_weights_before_launch(wired, gpu, benchmarks):
    with pytest.raises(Exception, match="lm-eval"):
        _batch(benchmarks)
    assert _FakeClient.calls == [] and wired["deploy_ckpt"] == []


def test_batch_rejects_unknown_benchmark(wired, gpu):
    with pytest.raises(Exception, match="unknown"):
        _batch(["arc", "nope"])
    assert _FakeClient.calls == []


def test_batch_rejects_more_runs_than_free_gpus(wired, gpu):
    # 외부 잡은 빈 GPU 가 없으면 대기하지 않고 즉시 실패한다 — 넘치는 묶음은 런치 전에 거절.
    gpu["free"] = 1
    with pytest.raises(Exception, match="GPU"):
        _batch(["arc", "piqa"])
    assert _FakeClient.calls == []


def test_batch_unknown_gpu_pool_does_not_block(wired, gpu):
    # 조회 실패는 '모름' — 확인된 부족만 막는다(최종 판정은 스케줄러의 원자적 claim).
    gpu["free"] = None
    res = _batch(["arc", "piqa"])
    assert len(_FakeClient.calls) == 2 and res["failed"] == 0


def test_batch_requires_dataset_when_custom_is_included(wired, gpu):
    with pytest.raises(Exception, match="데이터셋"):
        _batch(["arc", "custom"])
    assert _FakeClient.calls == []
    res = _batch(["arc", "custom"], dataset_ids=[3])
    assert res["failed"] == 0 and len(_FakeClient.calls) == 2


def test_batch_reports_partial_launch_failure(wired, gpu, monkeypatch):
    real = _FakeClient.start_job

    async def flaky(self, **kw):
        if len(_FakeClient.calls) == 1:
            _FakeClient.calls.append(kw)
            raise RuntimeError("GPU allocation failed")
        return await real(self, **kw)

    monkeypatch.setattr(_FakeClient, "start_job", flaky)
    res = _batch(["arc", "piqa", "boolq"])
    assert [bool(r.get("job_id")) for r in res["runs"]] == [True, False, True]
    assert "GPU allocation failed" in res["runs"][1]["error"]
    assert res["failed"] == 1


# ── 요청 바디 경계 ────────────────────────────────────────────────────────────

def test_single_run_body_accepts_no_dataset():
    from evaluation import dto as D
    body = D.BenchmarkRunBody(project_id=1, model_id=7, benchmarks=["arc"],
                              inference_playground_id=11)
    assert body.dataset_ids == []


@pytest.mark.parametrize("extra", [
    {"format_train": True},                      # 묶음에 없는 설정 — 조용히 버리지 않는다
    {"judge_playground_id": 3},
    {"benchmarks": ["arc", "arc"]},              # 중복
    {"benchmarks": ["arc", "nope"]},             # 모르는 id
    {"benchmarks": []},                          # 빈 묶음
    {"dataset_ids": [1, 2]},                     # 데이터셋 상한 1
])
def test_batch_body_rejects(extra):
    from pydantic import ValidationError
    from evaluation import dto as D
    base = {"project_id": 1, "model_id": 7, "benchmarks": ["arc", "piqa"],
            "inference_playground_id": 11}
    with pytest.raises(ValidationError):
        D.BenchmarkBatchRunBody(**{**base, **extra})


def test_batch_gives_dataset_only_to_benchmarks_that_read_it(wired, gpu, monkeypatch):
    # custom + arc 묶음 — ARC 런에 custom 의 데이터셋을 실으면 결과가 "ARC 를 그 데이터셋으로
    # 쟀다"고 말한다(codex 리뷰). 데이터셋은 읽는 벤치마크에만 간다.
    inserted = []

    async def insert(**kw):
        inserted.append(kw)

    monkeypatch.setattr(S.db_model, "insert_eval_result", insert)
    _batch(["arc", "custom"], dataset_ids=[3])
    by_bench = {c["params"]["benchmark_set"][0]: c["params"] for c in _FakeClient.calls}
    assert "_dataset" not in by_bench["arc"] and by_bench["arc"]["datasets"] == []
    assert by_bench["custom"]["_dataset"]["name"] == "ds1"
    assert [(r["metric_set"].split(":")[0], r["dataset_id"]) for r in inserted] == [
        ("arc", None), ("custom", 3)]


def test_frozen_deployment_records_the_served_commit(monkeypatch):
    # 위임 런의 열은 "배포 × 그때 서빙하던 커밋" 이다 — 배포가 나중에 커밋을 바꿔도 옛 런이
    # 새 커밋 열로 옮겨 가지 않도록 완료 시점에 커밋을 굳힌다.
    async def source(pid):
        return {"name": "llama3.2", "model": "llama", "commit": "source_model",
                "workspace_id": 2}

    monkeypatch.setattr(S, "_deployment_source", source)
    frozen = asyncio.run(S._frozen_deployment(
        {"mode": "remote", "endpoint": "http://x/api/playgrounds/27/openai/v1"}, 2))
    assert frozen == {"deployment": "llama3.2", "model": "llama", "commit": "source_model"}


# ── 실행(묶음) 기록 — 결과 화면이 "한 번의 실행 = 카드 1장" 으로 읽는 단위 ─────────────

def test_batch_records_one_execution_with_launched_runs_only(wired, gpu, monkeypatch):
    real = _FakeClient.start_job
    job_ids = iter(["job-a", "job-b", "job-c"])

    async def launch(self, **kw):
        _FakeClient.calls.append(kw)
        if kw["params"]["benchmark_set"] == ["piqa"]:
            raise RuntimeError("GPU allocation failed")
        return {"job_id": next(job_ids)}

    recorded = []

    async def record(**kw):
        recorded.append(kw)
        return 42

    monkeypatch.setattr(_FakeClient, "start_job", launch)
    monkeypatch.setattr(S.db_model, "insert_eval_run_batch", record)
    res = _batch(["arc", "piqa", "boolq"], run_options={"sample_limit": 20})
    assert res["batch_id"] == 42
    # 런치에 실패한 벤치마크도 묶음에 남긴다 — 빼면 3개를 요청한 실행이 나중에 "2/2 완료"로 읽힌다.
    assert recorded == [{"eval_project_id": 1, "workspace_id": 2, "source_model_id": 7,
                         "checkpoint": "source_model", "sample_limit": 20,
                         "job_ids": ["job-a", "job-b"],
                         "job_benchmarks": {"job-a": ["arc"], "job-b": ["boolq"]},
                         "launch_failures": [{"benchmark": "piqa",
                                              "error": "GPU allocation failed"}]}]
    assert real is not None


def test_batch_record_failure_does_not_hide_launched_runs(wired, gpu, monkeypatch):
    async def broken(**kw):
        raise RuntimeError("db down")

    monkeypatch.setattr(S.db_model, "insert_eval_run_batch", broken)
    res = _batch(["arc", "piqa"])
    assert res["batch_id"] is None and res["launched"] == 2


def test_delete_run_batch_removes_members_of_that_project_only(monkeypatch):
    batch = {"id": 42, "eval_project_id": 1, "source_model_id": 7,
             "job_ids": ["job-a", "job-b"]}
    deleted, dropped = [], []

    async def get_batch(batch_id):
        return batch if batch_id == 42 else None

    async def delete_run(model_id, job_id):
        deleted.append((model_id, job_id))
        return {"job_id": job_id, "deleted": True}

    async def drop(batch_id):
        dropped.append(batch_id)

    cancelled = []

    async def row(job_str_id, source_model_id):
        return {"status": "running" if job_str_id == "job-a" else "completed"}

    async def cancel(model_id, job_id, status):
        cancelled.append((model_id, job_id, status))
        return {}

    monkeypatch.setattr(S.db_model, "get_eval_run_batch", get_batch)
    monkeypatch.setattr(S.db_model, "get_eval_result_by_job", row)
    monkeypatch.setattr(S, "mark_eval_status", cancel)
    monkeypatch.setattr(S, "delete_eval_run", delete_run)
    monkeypatch.setattr(S.db_model, "delete_eval_run_batch", drop)
    assert asyncio.run(S.delete_run_batch(project_id=9, batch_id=42))["deleted"] is False
    assert deleted == [] and dropped == [] and cancelled == []
    res = asyncio.run(S.delete_run_batch(project_id=1, batch_id=42))
    assert res == {"batch_id": 42, "deleted": True, "runs": 2}
    # 도는 멤버는 행을 지우기 전에 컨테이너까지 취소한다 — 행만 지우면 GPU 를 쥔 채 계속 돈다.
    assert cancelled == [(7, "job-a", "cancelled")]
    assert deleted == [(7, "job-a"), (7, "job-b")] and dropped == [42]


# ── GPU 수만큼 런으로 나누기(§14) — 분배(plan_benchmark_runs) + 묶음 실행 ─────────────────

def test_plan_balances_by_expected_time_not_by_count():
    # KMMLU(3884s) 하나가 나머지 합보다 무겁다 — 개수로 나누면 KMMLU 와 MMLU 가 한 런에 몰린다.
    runs = S.plan_benchmark_runs(["arc", "mmlu", "kmmlu", "hellaswag", "piqa"], 2)
    assert sorted(runs, key=len) == [["kmmlu"], ["arc", "mmlu", "hellaswag", "piqa"]]


def test_plan_keeps_request_order_inside_a_run_and_is_deterministic():
    ids = ["piqa", "boolq", "winogrande", "openbookqa", "arc_easy", "haerae"]
    first = S.plan_benchmark_runs(ids, 2)
    assert first == S.plan_benchmark_runs(ids, 2)
    order = {b: i for i, b in enumerate(ids)}
    for run in first:
        assert run == sorted(run, key=order.__getitem__)
    assert sorted(b for run in first for b in run) == sorted(ids)


def test_plan_isolates_code_and_dataset_benchmarks():
    runs = S.plan_benchmark_runs(["arc", "humaneval", "custom", "mmlu"], 3)
    assert sorted(runs) == [["arc", "mmlu"], ["custom"], ["humaneval"]]


def test_plan_rejects_fewer_gpus_than_unshareable_groups():
    with pytest.raises(Exception, match="최소 3장"):
        S.plan_benchmark_runs(["arc", "humaneval", "custom"], 2)


def test_plan_with_more_gpus_than_benchmarks_is_one_run_each():
    assert S.plan_benchmark_runs(["arc", "piqa"], 8) == [["arc"], ["piqa"]]


def test_plan_rejects_a_run_that_would_outlive_the_pod_timeout(monkeypatch):
    # 큰 모델(3B 추정 × 최악 배수)에서 한 런이 타임아웃을 넘으면 남은 벤치마크가 채점되지 않는다.
    # KMMLU+MMLU 한 런 ≈ (3884+1886+180)×3 ≈ 5.0h > 4h, 따로면 KMMLU ≈ 3.4h.
    monkeypatch.setattr(S, "LMEVAL_RUN_TIMEOUT_SECONDS", 4 * 3600)
    with pytest.raises(Exception, match="GPU 수를 늘리세요"):
        S.plan_benchmark_runs(["kmmlu", "mmlu"], 1)
    assert len(S.plan_benchmark_runs(["kmmlu", "mmlu"], 2)) == 2


def test_batch_with_gpu_count_packs_benchmarks_into_that_many_runs(wired, gpu, monkeypatch):
    job_ids = iter(["job-a", "job-b"])

    async def launch(self, **kw):
        _FakeClient.calls.append(kw)
        return {"job_id": next(job_ids)}

    recorded = []

    async def record(**kw):
        recorded.append(kw)
        return 7

    monkeypatch.setattr(_FakeClient, "start_job", launch)
    monkeypatch.setattr(S.db_model, "insert_eval_run_batch", record)
    gpu["free"] = 2
    res = _batch(["arc", "kmmlu", "piqa", "boolq"], gpu_count=2)
    sets = [c["params"]["benchmark_set"] for c in _FakeClient.calls]
    assert sorted(sets) == [["arc", "piqa", "boolq"], ["kmmlu"]]
    assert {c["params"]["checkpoint_name"] for c in _FakeClient.calls} == {"source_model"}
    assert wired["deploy_ckpt"] == ["lm-eval 벤치마크 채점"]
    # 런마다 담은 벤치마크가 기록에 남는다 — metric_set 은 255자에서 잘려 목록의 정본이 못 된다.
    assert recorded[0]["job_benchmarks"] == {r["job_id"]: r["benchmarks"] for r in res["runs"]}
    assert res["launched"] == 2 and res["failed"] == 0


def test_batch_gpu_check_counts_runs_not_benchmarks(wired, gpu):
    gpu["free"] = 2
    res = _batch(["arc", "piqa", "boolq", "winogrande", "openbookqa"], gpu_count=2)
    assert len(_FakeClient.calls) == 2 and res["failed"] == 0
    with pytest.raises(Exception, match="GPU 3장"):
        _batch(["arc", "piqa", "boolq"], gpu_count=3)


def test_batch_launch_failure_lists_every_benchmark_of_that_run(wired, gpu, monkeypatch):
    async def launch(self, **kw):
        _FakeClient.calls.append(kw)
        if "kmmlu" in kw["params"]["benchmark_set"]:
            return {"job_id": "job-k"}
        raise RuntimeError("GPU allocation failed")

    recorded = []

    async def record(**kw):
        recorded.append(kw)
        return 8

    monkeypatch.setattr(_FakeClient, "start_job", launch)
    monkeypatch.setattr(S.db_model, "insert_eval_run_batch", record)
    res = _batch(["arc", "kmmlu", "piqa"], gpu_count=2)
    assert res["launched"] == 1 and res["failed"] == 1
    assert sorted(f["benchmark"] for f in recorded[0]["launch_failures"]) == ["arc", "piqa"]


def test_batch_dataset_goes_only_to_the_run_that_reads_it(wired, gpu):
    _batch(["arc", "custom", "piqa"], dataset_ids=[3], gpu_count=2)
    by_set = {tuple(c["params"]["benchmark_set"]): c["params"] for c in _FakeClient.calls}
    assert "_dataset" not in by_set[("arc", "piqa")]
    assert by_set[("custom",)]["_dataset"]["name"] == "ds1"


def test_batch_body_gpu_count_bounds():
    from pydantic import ValidationError
    from evaluation import dto as D
    base = {"project_id": 1, "model_id": 7, "benchmarks": ["arc", "piqa"],
            "inference_playground_id": 11}
    assert D.BenchmarkBatchRunBody(**base, gpu_count=2).gpu_count == 2
    for bad in (0, 21):
        with pytest.raises(ValidationError):
            D.BenchmarkBatchRunBody(**base, gpu_count=bad)


# ── 채점기 진행 기록(progress.json) — 한 런에 여러 벤치마크가 들면 런 상태 하나로는 부족하다 ──

def test_read_progress_returns_per_benchmark_status_and_partial(tmp_path):
    import json
    (tmp_path / "progress.json").write_text(json.dumps({
        "benchmarks": [
            {"benchmark": "arc", "metric": "accuracy", "status": "done", "score": 41.5,
             "elapsed_sec": 240.1},
            {"benchmark": "mmlu", "status": "failed", "error": "RuntimeError: boom"},
            {"benchmark": "piqa", "status": "running"},
            {"benchmark": "x", "status": "weird"},        # 모르는 상태는 버린다
            "garbage",
        ],
        "partial": {"averages": {"arc": 41.5},
                    "checkpoint": {"name": "c1", "path": "/models/llama/commit_models/c1"}},
    }))
    prog = S._read_progress(str(tmp_path))
    assert [(b["benchmark"], b["status"], b["score"]) for b in prog["benchmarks"]] == [
        ("arc", "done", 41.5), ("mmlu", "failed", None), ("piqa", "running", None)]
    assert prog["benchmarks"][1]["error"] == "RuntimeError: boom"
    # 컨테이너 내부 경로는 응답 전에 지운다(metrics.json 과 같은 규약).
    assert "path" not in prog["partial_metrics"]["checkpoint"]


def test_read_progress_is_none_when_missing_or_broken(tmp_path):
    assert S._read_progress(str(tmp_path)) is None
    (tmp_path / "progress.json").write_text("{not json")
    assert S._read_progress(str(tmp_path)) is None


def test_project_view_attaches_progress_to_unfinished_runs_only(tmp_path, monkeypatch):
    # 카드 목록은 결과를 폴링하지 않는다 — 끝나지 않은 런 행에 벤치마크별 점수 요약을 싣는다.
    import json
    for job in ("jobcancel01", "jobdone0001"):
        (tmp_path / job / "output").mkdir(parents=True)
    (tmp_path / "jobcancel01" / "output" / "progress.json").write_text(json.dumps({
        "benchmarks": [{"benchmark": "arc_easy", "status": "done", "score": 70.0}],
        "partial": {"averages": {"arc_easy": 70.0}}}))
    (tmp_path / "jobdone0001" / "output" / "progress.json").write_text(json.dumps({
        "benchmarks": [{"benchmark": "arc", "status": "done", "score": 1.0}]}))
    lookups = []

    async def base(model_id):
        lookups.append(model_id)
        return str(tmp_path)

    monkeypatch.setattr(S, "_eval_jobs_base", base)
    runs = [{"job_id": "jobcancel01", "model_id": 2, "status": "cancelled", "metric_set": "arc_easy:acc_norm"},
            {"job_id": "jobdone0001", "model_id": 2, "status": "completed", "metric_set": "arc:accuracy"},
            {"job_id": "jobexpert01", "model_id": 2, "status": "running", "metric_set": "expert"}]
    asyncio.run(S._attach_run_progress(runs))
    assert runs[0]["progress"] == {"benchmarks": [
        {"benchmark": "arc_easy", "status": "done", "score": 70.0, "elapsed_sec": None, "error": None}]}
    assert "progress" not in runs[1] and "progress" not in runs[2]
    assert lookups == [2]          # 모델당 DB 조회 한 번


def test_metric_set_is_cut_on_whole_tokens(wired, monkeypatch):
    # 17개(272자)를 한 런에 담아도 metric_set(VARCHAR 255)에 반쪽 id("truthfulqa_ge")가 남지 않는다.
    inserted = []

    async def insert(**kw):
        inserted.append(kw)

    monkeypatch.setattr(S.db_model, "insert_eval_result", insert)
    ids = [b for b in S.DATASET_FREE_BENCHMARK_IDS if b != "humaneval"]
    asyncio.run(S.run_benchmark(project_id=1, model_id=7, dataset_ids=[], benchmarks=ids,
                                inference_playground_id=11))
    metric_set = inserted[0]["metric_set"]
    assert len(metric_set) <= 255
    tokens = [t.split(":")[0] for t in metric_set.split(",")]
    assert tokens == ids[:len(tokens)] and len(tokens) < len(ids)


def test_scorer_error_strings_do_not_leak_container_paths(tmp_path):
    import json
    (tmp_path / "progress.json").write_text(json.dumps({"benchmarks": [
        {"benchmark": "mmlu", "status": "failed",
         "error": "OSError: no such file /models/llama/commit_models/c1/config.json"}]}))
    assert S._read_progress(str(tmp_path))["benchmarks"][0]["error"] == \
        "OSError: no such file <path>"
    metrics = {"failed_benchmarks": [{"benchmark": "arc", "error": "cp /tmp/lmeval-merged failed"},
                                     {"benchmark": "piqa", "error": "CUDA OOM 2.00 GiB, N/A"}]}
    S._strip_internal_paths(metrics)
    assert [f["error"] for f in metrics["failed_benchmarks"]] == [
        "cp <path> failed", "CUDA OOM 2.00 GiB, N/A"]
