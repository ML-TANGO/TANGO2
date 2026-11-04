"""REST contract: /health, /info, /run, /status (optimizer stubbed out)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

import main
from src.schemas import RunResult

client = TestClient(main.app)

EXAMPLES = [
    {"query": "사과는 무슨 색인가요?", "response": "사과는 빨간색입니다."},
    {"query": "바나나는 무슨 색인가요?", "response": "바나나는 노란색입니다."},
]
LLM_URL = "http://127.0.0.1:9/v1"  # never contacted: the optimizer is stubbed


def _fake_result(**overrides) -> RunResult:
    fields = dict(
        system_prompt="SP", instruction="I", demos=[], n_examples=2, n_seeds=1, n_holdout=1,
        n_demos=0, generated=0, accepted=0, base_score=0.1, final_score=0.2, model="m",
        metric="token_f1", history=[],
    )
    fields.update(overrides)
    return RunResult(**fields)


def _stub_optimizer(monkeypatch, fn=None):
    def fake(params, progress_cb=None):
        if progress_cb is not None:
            progress_cb(50)
        return fn(params) if fn else _fake_result()

    monkeypatch.setattr(main, "optimize_system_prompt", fake)


def _wait(job_id: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    body: dict = {}
    while time.time() < deadline:
        body = client.get("/status", params={"job_id": job_id}).json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish: {body}")


def _submit(body: dict) -> str:
    resp = client.post("/run", json=body)
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert result["job_status"] in ("pending", "running", "completed")  # a stub can finish instantly
    return result["job_id"]


def test_health():
    body = client.get("/health").json()
    assert body["status"] == "healthy"
    assert "timestamp" in body


def test_info_advertises_async_run():
    body = client.get("/info").json()
    assert body["name"] == "fewshot-prompt-optimizer"
    assert "async_run" in body["capabilities"]


@pytest.mark.parametrize(("capability", "probe"), [("spice", "spice_installed"), ("bert_score", "bert_score_installed")])
def test_info_reports_metric_capabilities_only_when_installed(monkeypatch, capability, probe):
    monkeypatch.setattr(main, probe, lambda: True)
    assert capability in client.get("/info").json()["capabilities"]
    monkeypatch.setattr(main, probe, lambda: False)
    assert capability not in client.get("/info").json()["capabilities"]


def test_startup_kicks_off_the_metric_preloads(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "preload_spice", lambda: calls.append("spice"))
    monkeypatch.setattr(main, "preload_bert_scorer", lambda: calls.append("bert_score"))
    with TestClient(main.app) as started:  # runs the lifespan
        assert started.get("/health").status_code == 200
    assert calls == ["spice", "bert_score"]


def test_run_requires_llm_url():
    resp = client.post("/run", json={"params": {"examples": EXAMPLES}})
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_PARAMS"
    assert "llm_url" in resp.json()["message"]


def test_run_requires_two_examples():
    resp = client.post("/run", json={"params": {"llm_url": LLM_URL, "examples": EXAMPLES[:1]}})
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_PARAMS"


def test_schema_errors_fold_into_400_invalid_params():
    resp = client.post("/run", json={"params": {"llm_url": LLM_URL, "examples": "not-a-list"}})
    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == "error" and body["code"] == "INVALID_PARAMS"
    assert "examples" in body["message"]


def test_run_rejects_unknown_metric(monkeypatch):
    _stub_optimizer(monkeypatch)
    resp = client.post(
        "/run", json={"params": {"llm_url": LLM_URL, "examples": EXAMPLES, "metric": "rouge"}}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_PARAMS"
    assert "token_f1, bert_score" in resp.json()["message"]


def test_vlm_rejects_local_image_paths(monkeypatch):
    _stub_optimizer(monkeypatch)
    examples = [{**EXAMPLES[0], "image": "/etc/passwd"}, EXAMPLES[1]]
    resp = client.post("/run", json={"params": {"llm_url": LLM_URL, "examples": examples, "vlm": True}})
    assert resp.status_code == 400
    assert "examples[0].image" in resp.json()["message"]


def test_text_path_ignores_images(monkeypatch):
    _stub_optimizer(monkeypatch)
    examples = [{**EXAMPLES[0], "image": "/etc/passwd"}, EXAMPLES[1]]
    assert _wait(_submit({"params": {"llm_url": LLM_URL, "examples": examples}}))["status"] == "completed"


def test_status_requires_job_id():
    resp = client.get("/status")
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_PARAMS"


def test_status_unknown_job_is_404():
    resp = client.get("/status", params={"job_id": "job-doesnotexist"})
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


def test_async_job_completes(monkeypatch):
    _stub_optimizer(monkeypatch)
    job_id = _submit({"workspace_id": "ws", "project_id": "p", "params": {"llm_url": LLM_URL, "examples": EXAMPLES}})
    body = _wait(job_id)
    assert body["status"] == "completed"
    assert body["progress"] == 100
    assert body["result"]["system_prompt"] == "SP"
    assert {"created_at", "started_at", "finished_at"} <= body.keys()


@pytest.mark.parametrize(
    ("exc", "code"),
    [(ValueError("bad input"), "INVALID_PARAMS"), (RuntimeError("boom"), "INTERNAL_ERROR")],
)
def test_async_job_failure_is_reported(monkeypatch, exc, code):
    def raise_(params):
        raise exc

    _stub_optimizer(monkeypatch, raise_)
    body = _wait(_submit({"params": {"llm_url": LLM_URL, "examples": EXAMPLES}}))
    assert body["status"] == "failed"
    assert body["code"] == code
    assert str(exc) in body["message"]
    assert "result" not in body


def test_baseline_mode_completes_without_llm_url():
    resp = client.post("/run", json={"params": {"optimize": False, "examples": EXAMPLES, "sync": True}})
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["final_score"] is None and result["n_demos"] == 2
    assert result["system_prompt"].endswith("Response: 바나나는 노란색입니다.")


def test_flat_body_is_accepted(monkeypatch):
    _stub_optimizer(monkeypatch)
    body = _wait(_submit({"llm_url": LLM_URL, "examples": EXAMPLES}))
    assert body["status"] == "completed"


def test_sync_mode_returns_result_inline(monkeypatch):
    _stub_optimizer(monkeypatch)
    resp = client.post("/run", json={"params": {"llm_url": LLM_URL, "examples": EXAMPLES, "sync": True}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["result"]["system_prompt"] == "SP"
