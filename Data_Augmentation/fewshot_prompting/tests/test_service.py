"""service.py: split, prompt rendering, model auto-detection (optimizer stubbed)."""

from __future__ import annotations

import http.server
import json
import threading

import pytest

from src import service
from src.optimizer import Example, OptimizeResult
from src.schemas import RunParams

EXAMPLES = [
    {"query": "사과는 무슨 색인가요?", "response": "사과는 빨간색입니다."},
    {"query": "바나나는 무슨 색인가요?", "response": "바나나는 노란색입니다."},
]


def test_every_example_reaches_the_optimizer(monkeypatch):
    """No seed/holdout split: every example is a demo candidate and a scoring example."""
    monkeypatch.setenv("LLM_API_BASE", "unset")
    monkeypatch.setenv("LLM_API_KEY", "unset")
    captured = {}

    def fake_run_optimization(task, examples, **kwargs):
        captured["examples"] = examples
        return OptimizeResult(
            program=None, instruction="I", final_demos=list(examples), seed_count=len(examples),
            holdout_count=len(examples), generated_count=0, accepted_count=0,
            base_score=0.1, final_score=0.2, history=[],
        )

    monkeypatch.setattr(service, "run_optimization", fake_run_optimization)
    params = RunParams(llm_url="http://127.0.0.1:9/v1", model="m", examples=EXAMPLES)
    result = service.optimize_system_prompt(params)
    assert [e.inputs["query"] for e in captured["examples"]] == [e["query"] for e in EXAMPLES]
    assert (result.n_seeds, result.n_holdout, result.n_demos) == (2, 2, 2)


FOUR = [{"query": f"q{i}", "response": f"r{i}"} for i in range(4)]


def _capture(monkeypatch):
    monkeypatch.setenv("LLM_API_BASE", "unset")
    monkeypatch.setenv("LLM_API_KEY", "unset")
    captured = {}

    def fake_run_optimization(task, examples, **kwargs):
        captured["examples"], captured["holdout"] = examples, kwargs["holdout"]
        return OptimizeResult(
            program=None, instruction="I", final_demos=list(examples), seed_count=len(examples),
            holdout_count=len(kwargs["holdout"] or examples), generated_count=0, accepted_count=0,
            base_score=0.1, final_score=0.2, history=[],
        )

    monkeypatch.setattr(service, "run_optimization", fake_run_optimization)
    return captured


def test_holdout_fraction_holds_examples_out_of_the_prompt(monkeypatch):
    captured = _capture(monkeypatch)
    service.optimize_system_prompt(RunParams(llm_url="http://127.0.0.1:9/v1", model="m", examples=FOUR, holdout_fraction=0.5))
    train = {e.inputs["query"] for e in captured["examples"]}
    held = {e.inputs["query"] for e in captured["holdout"]}
    assert len(train) == 2 and len(held) == 2 and not train & held and train | held == {e["query"] for e in FOUR}


def test_validation_wins_over_holdout_fraction(monkeypatch):
    captured = _capture(monkeypatch)
    validation = [{"query": "v", "response": "rv"}]
    service.optimize_system_prompt(RunParams(llm_url="http://127.0.0.1:9/v1", model="m", examples=FOUR,
                                             holdout_fraction=0.5, validation=validation))
    assert len(captured["examples"]) == 4 and [e.inputs["query"] for e in captured["holdout"]] == ["v"]


@pytest.mark.parametrize("fraction", [-0.1, 1.0, 1.5])
def test_holdout_fraction_must_be_below_one(fraction):
    with pytest.raises(ValueError, match="holdout_fraction"):
        service.validate_params(RunParams(llm_url="http://127.0.0.1:9/v1", model="m", examples=FOUR, holdout_fraction=fraction))


def test_validation_examples_are_scored_instead_of_leave_one_out(monkeypatch):
    """A caller-provided validation set becomes the holdout; the examples stay the demo candidates."""
    monkeypatch.setenv("LLM_API_BASE", "unset")
    monkeypatch.setenv("LLM_API_KEY", "unset")
    captured = {}

    def fake_run_optimization(task, examples, **kwargs):
        captured["examples"], captured["holdout"] = examples, kwargs["holdout"]
        return OptimizeResult(
            program=None, instruction="I", final_demos=list(examples), seed_count=len(examples),
            holdout_count=len(kwargs["holdout"]), generated_count=0, accepted_count=0,
            base_score=0.1, final_score=0.2, history=[],
        )

    monkeypatch.setattr(service, "run_optimization", fake_run_optimization)
    validation = [{"query": "포도는 무슨 색인가요?", "response": "포도는 보라색입니다."}]
    params = RunParams(llm_url="http://127.0.0.1:9/v1", model="m", examples=EXAMPLES, validation=validation)
    result = service.optimize_system_prompt(params)
    assert [e.inputs["query"] for e in captured["examples"]] == [e["query"] for e in EXAMPLES]
    assert [e.outputs["response"] for e in captured["holdout"]] == ["포도는 보라색입니다."]
    assert (result.n_demos, result.n_holdout) == (2, 1)


def test_render_system_prompt():
    demos = [Example(inputs={"query": " q1 "}, outputs={"response": "r1"})]
    assert service.render_system_prompt("Be brief.", demos) == (
        "Be brief.\n\nHere are some examples:\n\nQuery: q1\nResponse: r1"
    )
    assert service.render_system_prompt(None, demos).startswith("Here are some examples:")
    assert service.render_system_prompt("  Be brief.  ", []) == "Be brief."


class _ModelsHandler(http.server.BaseHTTPRequestHandler):
    """Fake OpenAI-compatible ``/v1/models``; enforces a bearer token like
    ``vllm serve --api-key`` when ``required_token`` is set."""

    required_token: str | None = None

    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/") != "/v1/models":
            self.send_response(404)
            self.end_headers()
            return
        if self.required_token and self.headers.get("Authorization") != f"Bearer {self.required_token}":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error": "Unauthorized"}')
            return
        body = json.dumps({"object": "list", "data": [{"id": "served-model"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def models_server():
    servers = []

    def start(token: str | None = None) -> str:
        handler = type("Handler", (_ModelsHandler,), {"required_token": token})
        srv = http.server.HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return f"http://127.0.0.1:{srv.server_port}/v1"

    yield start
    for srv in servers:
        srv.shutdown()
        srv.server_close()


@pytest.fixture
def stub_optimizer(monkeypatch):
    """Replace the real optimization with a canned result; keep env changes local."""
    monkeypatch.setenv("LLM_API_BASE", "unset")
    monkeypatch.setenv("LLM_API_KEY", "unset")

    def fake_run_optimization(task, examples, **kwargs):
        demo = Example(inputs={"query": "q"}, outputs={"response": "r"})
        return OptimizeResult(
            program=None, instruction="Do it.", final_demos=[demo], seed_count=len(examples),
            holdout_count=len(examples), generated_count=0, accepted_count=0,
            base_score=0.1, final_score=0.2, history=[],
        )

    monkeypatch.setattr(service, "run_optimization", fake_run_optimization)


def test_model_autodetect_without_auth(models_server, stub_optimizer):
    url = models_server()
    result = service.optimize_system_prompt(RunParams(llm_url=url, examples=EXAMPLES))
    assert result.model == "served-model"
    assert result.system_prompt == "Do it.\n\nHere are some examples:\n\nQuery: q\nResponse: r"


def test_model_autodetect_sends_api_key(models_server, stub_optimizer):
    url = models_server(token="secret")
    result = service.optimize_system_prompt(RunParams(llm_url=url, api_key="secret", examples=EXAMPLES))
    assert result.model == "served-model"


def test_model_autodetect_with_wrong_key_points_at_api_key(models_server, stub_optimizer):
    url = models_server(token="secret")
    with pytest.raises(ValueError, match="api_key"):
        service.optimize_system_prompt(RunParams(llm_url=url, api_key="wrong", examples=EXAMPLES))


def test_augmentation_switches_reach_the_optimizer(monkeypatch):
    monkeypatch.setenv("LLM_API_BASE", "unset")
    monkeypatch.setenv("LLM_API_KEY", "unset")
    captured = {}

    def fake_run_optimization(task, examples, **kwargs):
        captured["config"] = kwargs["config"]
        return OptimizeResult(
            program=None, instruction="I", final_demos=list(examples), seed_count=len(examples),
            holdout_count=len(examples), generated_count=0, accepted_count=0,
            base_score=0.1, final_score=0.2, history=[],
        )

    monkeypatch.setattr(service, "run_optimization", fake_run_optimization)
    params = RunParams(llm_url="http://127.0.0.1:9/v1", model="m", examples=EXAMPLES, feedback=False)
    service.optimize_system_prompt(params)
    assert captured["config"].feedback is False
    assert captured["config"].instruction == "Respond to the user's query, following the style and format of the examples."


def test_task_lm_output_is_capped_from_the_example_lengths(monkeypatch):
    monkeypatch.setenv("LLM_API_BASE", "unset")
    monkeypatch.setenv("LLM_API_KEY", "unset")
    captured = {}

    def fake_run_optimization(task, examples, **kwargs):
        captured["task_lm"] = kwargs["task_lm"]
        return OptimizeResult(
            program=None, instruction="I", final_demos=list(examples), seed_count=len(examples),
            holdout_count=len(examples), generated_count=0, accepted_count=0,
            base_score=0.1, final_score=0.2, history=[],
        )

    monkeypatch.setattr(service, "run_optimization", fake_run_optimization)
    long_answers = [{"query": "q1", "response": "x" * 600}, {"query": "q2", "response": "y"}]
    service.optimize_system_prompt(RunParams(llm_url="http://127.0.0.1:9/v1", model="m", examples=long_answers))
    assert captured["task_lm"].kwargs["max_tokens"] == 1200
    service.optimize_system_prompt(RunParams(llm_url="http://127.0.0.1:9/v1", model="m", examples=EXAMPLES))
    assert captured["task_lm"].kwargs["max_tokens"] == 512


def test_explicit_model_skips_autodetect(stub_optimizer):
    params = RunParams(llm_url="http://127.0.0.1:9/v1", model="given-model", examples=EXAMPLES)
    assert service.optimize_system_prompt(params).model == "given-model"


def test_llm_calls_get_a_timeout_without_touching_dspy_cache_keys(monkeypatch, stub_optimizer):
    import litellm

    monkeypatch.setattr(litellm, "request_timeout", litellm.request_timeout)  # restored afterwards
    service.optimize_system_prompt(RunParams(llm_url="http://127.0.0.1:9/v1", model="m", examples=EXAMPLES))
    assert litellm.request_timeout == service.LLM_TIMEOUT_SECONDS
    assert service._OpenAIChatLM("m", "http://127.0.0.1:9/v1", "EMPTY")._client.timeout == service.LLM_TIMEOUT_SECONDS


KO = [Example(inputs={"query": "q"}, outputs={"response": "맑은 날씨이다."})] * 2
EN = [Example(inputs={"query": "q"}, outputs={"response": "Clear skies."})] * 2


def test_default_metric_is_spice_for_english_and_token_f1_for_korean():
    assert service.resolve_metric(None, EN) == ("spice", [])
    metric, notes = service.resolve_metric(None, KO)
    assert metric == "token_f1" and "SPICE is English-only" in notes[0]


def test_an_explicit_metric_is_always_honored():
    metric, notes = service.resolve_metric("spice", KO)
    assert metric == "spice" and "identical words" in notes[0]
    assert service.resolve_metric("token_f1", EN) == ("token_f1", [])
    assert service.resolve_metric("bert_score", KO) == ("bert_score", [])


def test_korean_job_reports_the_metric_switch(stub_optimizer):
    result = service.optimize_system_prompt(RunParams(llm_url="http://127.0.0.1:9/v1", model="m", examples=EXAMPLES))
    assert result.metric == "token_f1"
    assert result.warnings[0].startswith("examples are Korean")


def test_baseline_mode_returns_the_given_examples_without_any_llm():
    params = RunParams(optimize=False, examples=EXAMPLES)  # no llm_url needed
    result = service.optimize_system_prompt(params)
    assert result.instruction == "Respond to the user's query, following the style and format of the examples."
    assert result.system_prompt == (
        f"{result.instruction}\n\nHere are some examples:\n\n"
        "Query: 사과는 무슨 색인가요?\nResponse: 사과는 빨간색입니다.\n\n"
        "Query: 바나나는 무슨 색인가요?\nResponse: 바나나는 노란색입니다."
    )
    assert (result.n_demos, result.n_holdout, result.base_score, result.final_score) == (2, 0, None, None)
    assert result.history == []


def test_baseline_mode_needs_one_example_and_uses_the_vlm_instruction():
    with pytest.raises(ValueError, match="at least 1 example"):
        service.optimize_system_prompt(RunParams(optimize=False, examples=[]))
    result = service.optimize_system_prompt(RunParams(optimize=False, vlm=True, examples=EXAMPLES[:1]))
    assert "image" in result.instruction and result.n_demos == 1


def test_bert_score_fallback_is_reported_in_result(monkeypatch, stub_optimizer):
    from src import fewshot_task

    def unavailable():
        raise OSError("offline")

    monkeypatch.setattr(fewshot_task, "_load_bert_scorer", unavailable)
    params = RunParams(llm_url="http://127.0.0.1:9/v1", model="m", metric="bert_score", examples=EXAMPLES)
    result = service.optimize_system_prompt(params)
    assert result.metric == "token_f1"
    assert result.warnings and result.warnings[0].startswith("bert_score unavailable")
