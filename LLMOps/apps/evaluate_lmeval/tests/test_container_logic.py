"""체크포인트 해석·커스텀 평가·코드 실행 게이트 — GPU·vLLM 없이 도는 부분.

체크포인트는 경로가 아니라 커밋 이름 한 조각으로만 받고(마운트 밖 탈출 금지), LoRA 커밋은
기반 커밋 위에 병합한다. 커스텀 평가는 플랫폼 행 해석 규약(llm_evaluation _row_to_sample)과
같아야 하고, 코드 실행은 매니페스트 env 로만 켜진다.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

import checkpoint as CKPT  # noqa: E402
import custom_eval as CE  # noqa: E402
import registry as REG  # noqa: E402


# ── checkpoint ────────────────────────────────────────────────────────────────

def _commit(root: Path, name: str, files: dict) -> Path:
    d = root / name
    d.mkdir(parents=True)
    for fname, body in files.items():
        (d / fname).write_text(json.dumps(body) if isinstance(body, dict) else body)
    return d


def test_merged_commit(tmp_path):
    _commit(tmp_path, "c1", {"config.json": {}})
    ck = CKPT.resolve("c1", root=str(tmp_path))
    assert (ck.format, ck.base) == ("merged", None)


def test_lora_commit_uses_base_from_adapter_config(tmp_path):
    _commit(tmp_path, "source_model", {"config.json": {}})
    _commit(tmp_path, "ft1", {"config.json": {}})
    _commit(tmp_path, "lora2", {"adapter_config.json": {
        "base_model_name_or_path": "/models/llama/commit_models/ft1"}})
    ck = CKPT.resolve("lora2", root=str(tmp_path))
    assert (ck.format, ck.base) == ("lora", "ft1")


def test_lora_commit_falls_back_to_source_model(tmp_path):
    _commit(tmp_path, "source_model", {"config.json": {}})
    _commit(tmp_path, "lora1", {"adapter_config.json": {"base_model_name_or_path": "meta-llama/x"}})
    assert CKPT.resolve("lora1", root=str(tmp_path)).base == "source_model"


def test_lora_without_base_weights_is_rejected(tmp_path):
    _commit(tmp_path, "lora1", {"adapter_config.json": {}})
    with pytest.raises(ValueError, match="기반 가중치"):
        CKPT.resolve("lora1", root=str(tmp_path))


@pytest.mark.parametrize("name", ["../x", "a/b", "..", "", None])
def test_checkpoint_name_must_be_single_segment(tmp_path, name):
    with pytest.raises(ValueError):
        CKPT.resolve(name, root=str(tmp_path))


def test_symlink_escape_is_rejected(tmp_path):
    outside = tmp_path / "outside"
    _commit(outside, "evil", {"config.json": {}})
    root = tmp_path / "root"
    root.mkdir()
    (root / "link").symlink_to(outside / "evil")
    with pytest.raises(ValueError, match="escapes"):
        CKPT.resolve("link", root=str(root))


def test_commit_without_weights_is_rejected(tmp_path):
    _commit(tmp_path, "empty", {"README.md": "x"})
    with pytest.raises(ValueError, match="config.json"):
        CKPT.resolve("empty", root=str(tmp_path))


# ── custom_eval ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("row, expected", [
    ({"question": "수도는?", "answer": ["서울", "서울특별시"]}, ("수도는?", ["서울", "서울특별시"])),
    ({"instruction": "번역", "input": "", "output": "hello"}, ("번역", ["hello"])),     # 빈 input → instruction
    ({"instruction": "요약", "input": "본문", "output": "요약문"}, ("본문", ["요약문"])),  # 플랫폼 규약: input 우선
    ({"text": "### Instruction: 2+2?\n### Response: 4"}, ("2+2?", ["4"])),
    ({"text": "질문만", "output": "답"}, ("질문만", ["답"])),
    ({"prompt": "q"}, None),                                                           # 정답 없음 → 채점 불가
    ({"image": "a.png", "caption": "cat"}, None),                                      # 이미지 전용 → 제외
])
def test_row_to_pair_follows_platform_rules(row, expected):
    assert CE.row_to_pair(row) == expected


def test_load_pairs_reads_all_formats_and_counts_skips(tmp_path):
    (tmp_path / "a.jsonl").write_text(
        '{"question":"q1","answer":"a1"}\n{"question":"q2"}\nnot-json\n', encoding="utf-8")
    (tmp_path / "b.csv").write_text("prompt,reference\nq3,a3\n", encoding="utf-8")
    (tmp_path / "c.json").write_text(json.dumps({"data": [{"input": "q4", "output": "a4"}]}),
                                     encoding="utf-8")
    pairs, stats = CE.load_pairs(str(tmp_path))
    assert [p for p, _ in pairs] == ["q1", "q3", "q4"]
    assert stats == {"files": 3, "skipped_rows": 2}
    assert len(CE.load_pairs(str(tmp_path), limit=2)[0]) == 2


def test_strip_think():
    assert CE.strip_think("<think>음…</think>\n서울") == "서울"
    assert CE.strip_think("<think>끝나지 않은 사고") == ""      # 답 전에 잘린 생성
    assert CE.strip_think("서울") == "서울"


def test_build_prompt_disables_thinking():
    class Tok:
        chat_template = "x"

        def apply_chat_template(self, msgs, tokenize, add_generation_prompt, **kw):
            return f"{msgs[0]['content']}|think={kw.get('enable_thinking')}"

    assert CE.build_prompt(Tok(), "q") == "q|think=False"

    class Plain:
        chat_template = None
    assert CE.build_prompt(Plain(), "q") == "q"


class _CharTok:
    """글자 = 토큰인 가짜 토크나이저. 템플릿은 '<s>[U]' + 내용 + '[A]'."""

    def __init__(self, templated=True):
        self.chat_template = "x" if templated else None

    def apply_chat_template(self, msgs, tokenize, add_generation_prompt, **kw):
        return "<s>[U]" + msgs[0]["content"] + "[A]"

    def __call__(self, text, add_special_tokens=True):
        return {"input_ids": ([0] if add_special_tokens else []) + [ord(c) for c in text]}

    def decode(self, ids, skip_special_tokens=True):
        return "".join(chr(i) for i in ids)


def test_fit_prompt_keeps_template_header_when_truncating():
    tok = _CharTok()
    ids, cut = CE.fit_prompt(tok, "Q" * 100 + "END?", max_prompt=60)
    text = tok.decode(ids)
    assert cut and len(ids) <= 60
    assert text.startswith("<s>[U]") and text.endswith("END?[A]")   # 머리·생성 프롬프트 보존


def test_fit_prompt_untouched_when_short():
    tok = _CharTok(templated=False)
    ids, cut = CE.fit_prompt(tok, "hi", max_prompt=60)
    assert not cut and ids == [0, ord("h"), ord("i")]               # 무템플릿이면 BOS 를 붙인다


def test_korean_metrics_use_characters():
    pytest.importorskip("sacrebleu")      # 이미지에는 있다 — 로컬 호스트엔 없을 수 있다
    res = CE.evaluate_pairs(["서울특별시입니다"], [["서울특별시"]], lang="auto")
    assert res["korean"] is True
    assert 70 < res["metrics"]["f1"] < 100          # 공백 단위였다면 0 이다
    assert res["metrics"]["em"] == 0.0


def test_multiple_references_take_max():
    pytest.importorskip("sacrebleu")
    res = CE.evaluate_pairs(["Paris"], [["Lyon", "Paris"]], lang="en")
    assert res["metrics"]["em"] == 100.0 and res["metrics"]["f1"] == 100.0


# ── 코드 실행 게이트(app._plan) ─────────────────────────────────────────────────

@pytest.fixture
def app_module(monkeypatch, tmp_path):
    def load(allow_code: bool):
        monkeypatch.setenv("JF_OUTPUT_PATH", str(tmp_path))
        if allow_code:
            monkeypatch.setenv("LMEVAL_ALLOW_CODE_EXEC", "1")
        else:
            monkeypatch.delenv("LMEVAL_ALLOW_CODE_EXEC", raising=False)
        stdout, stderr = sys.stdout, sys.stderr
        try:
            sys.modules.pop("app", None)
            return importlib.import_module("app")
        finally:
            sys.stdout, sys.stderr = stdout, stderr     # app 이 표준 스트림을 Tee 로 바꾼다
    return load


def test_code_benchmark_rejected_without_env(app_module):
    app = app_module(False)
    with pytest.raises(ValueError, match="코드 실행"):
        app._plan({"benchmarks": [{"benchmark": "humaneval"}]})
    assert [b.id for b in app._plan({"benchmarks": ["mmlu", "custom"]})] == ["mmlu", "custom"]


def test_code_pod_accepts_only_code_benchmarks(app_module):
    app = app_module(True)
    assert [b.id for b in app._plan({"benchmarks": ["humaneval"]})] == ["humaneval"]
    with pytest.raises(ValueError, match="코드 벤치마크만"):
        app._plan({"benchmarks": ["humaneval", "mmlu"]})


def test_unknown_benchmark_is_rejected_not_dropped():
    with pytest.raises(ValueError, match="unknown benchmark"):
        REG.resolve(["mmlu", "nope"])
    with pytest.raises(ValueError):
        REG.resolve([])
    assert [b.id for b in REG.resolve(["mmlu", {"benchmark": "mmlu"}, "arc"])] == ["mmlu", "arc"]


@pytest.mark.parametrize("raw, ok", [(None, None), (20, 20), ("5", 5), (0, None)])
def test_int_param(app_module, raw, ok):
    app = app_module(False)
    assert app._int_param({"limit": raw}, "limit", None, 1, 100) == ok


def test_int_param_rejects_out_of_range(app_module):
    app = app_module(False)
    with pytest.raises(ValueError):
        app._int_param({"limit": 101}, "limit", None, 1, 100)
    with pytest.raises(ValueError):
        app._int_param({"limit": "x"}, "limit", None, 1, 100)


# ── 한 런 = 여러 벤치마크 직렬 채점 — 벤치마크 단위 실패 격리 + 진행 기록 ─────────────────

def _summary_of(bench_id: str, score: float) -> dict:
    return {"benchmark": bench_id, "metric": REG.BENCHMARKS[bench_id].metric, "score": score,
            "n": 10, "warnings": []}


def test_one_failing_benchmark_keeps_the_others(app_module, tmp_path):
    app = app_module(False)
    benches = REG.resolve(["arc", "mmlu", "piqa"])
    tracker = app._BenchTracker(benches, path=str(tmp_path / "progress.json"))
    tracker.build = lambda s, f: {"averages": {x["benchmark"]: x["score"] for x in s},
                                  "failed_benchmarks": f}

    def score_one(i, bench):
        if bench.id == "mmlu":
            raise RuntimeError("CUDA out of memory")
        return _summary_of(bench.id, 50.0 + i)

    summaries, failures = app._score_benchmarks(benches, score_one, tracker)
    assert [s["benchmark"] for s in summaries] == ["arc", "piqa"]
    assert failures == [{"benchmark": "mmlu", "metric": "accuracy",
                         "error": "RuntimeError: CUDA out of memory"}]
    prog = json.loads((tmp_path / "progress.json").read_text())
    assert [(r["benchmark"], r["status"]) for r in prog["benchmarks"]] == [
        ("arc", "done"), ("mmlu", "failed"), ("piqa", "done")]
    # 끝난 벤치마크 점수는 중간 결과로도 남는다 — 파드가 죽어도 그때까지의 점수가 보인다.
    assert prog["partial"]["averages"] == {"arc": 50.0, "piqa": 52.0}


def test_all_failing_benchmarks_fail_the_run(app_module, tmp_path):
    app = app_module(False)
    benches = REG.resolve(["arc", "piqa"])
    tracker = app._BenchTracker(benches, path=str(tmp_path / "progress.json"))

    def score_one(i, bench):
        raise ValueError(f"{bench.id} broke")

    with pytest.raises(RuntimeError, match="모든 벤치마크가 실패") as err:
        app._score_benchmarks(benches, score_one, tracker)
    assert "arc: ValueError: arc broke" in str(err.value)


def test_cancel_is_not_swallowed_as_a_benchmark_failure(app_module, tmp_path):
    # 취소는 BaseException(_Cancelled) — 벤치마크 실패로 삼켜 다음 벤치마크로 넘어가면 취소가 안 된다.
    app = app_module(False)
    benches = REG.resolve(["arc", "piqa"])
    tracker = app._BenchTracker(benches, path=str(tmp_path / "progress.json"))
    seen = []

    def score_one(i, bench):
        seen.append(bench.id)
        raise app._Cancelled

    with pytest.raises(app._Cancelled):
        app._score_benchmarks(benches, score_one, tracker)
    assert seen == ["arc"]
    prog = json.loads((tmp_path / "progress.json").read_text())
    assert [r["status"] for r in prog["benchmarks"]] == ["running", "pending"]


def test_progress_write_failure_does_not_stop_scoring(app_module, tmp_path):
    app = app_module(False)
    benches = REG.resolve(["arc"])
    blocker = tmp_path / "file"
    blocker.write_text("x")
    tracker = app._BenchTracker(benches, path=str(blocker / "progress.json"))   # 부모가 파일
    summaries, _ = app._score_benchmarks(benches, lambda i, b: _summary_of(b.id, 1.0), tracker)
    assert [s["benchmark"] for s in summaries] == ["arc"]


def test_vllm_requests_are_chunked_not_auto(app_module):
    # "auto" 면 lm-eval 이 요청 전체를 vLLM 에 한 번에 넘기고 전 토큰 logprob 을 다 모은다 —
    # KMMLU 전체가 파드 한도(GPU 번들 ≈ 40G)에서 OOMKilled 됐다. 정수 청크여야 메모리가 고정된다.
    app = app_module(False)
    assert isinstance(app.VLLM_BATCH_SIZE, int) and not isinstance(app.VLLM_BATCH_SIZE, bool)
    assert 1 <= app.VLLM_BATCH_SIZE <= 4096
