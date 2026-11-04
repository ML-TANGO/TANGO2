"""fewshot_task.py: metrics and the VLM (image) path."""

from __future__ import annotations

import sys
import threading
import types
from types import SimpleNamespace

import dspy
import pytest

from conftest import png_data_uri
from src import fewshot_task
from src.fewshot_task import FewShotTask, token_f1
from src.optimizer.mipro_step import _extract_demos, _to_dspy
from src.optimizer.scoring import build_program, score_demos_per_example
from src.optimizer.task import Example

RED, BLUE, GREEN = png_data_uri((255, 0, 0)), png_data_uri((0, 0, 255)), png_data_uri((0, 255, 0))


class RecordingLM(dspy.BaseLM):
    """Returns a fixed reply and records the exact messages it was sent."""

    def __init__(self, reply: str):
        super().__init__(model="recording")
        self.reply = reply
        self.calls: list[list[dict]] = []

    def __call__(self, prompt=None, messages=None, **kwargs):
        self.calls.append(messages)
        return [self.reply]


# --------------------------------------------------------------------- #
# scoring format == deployed format
# --------------------------------------------------------------------- #

DEMOS = [
    Example(inputs={"query": "사과는?"}, outputs={"response": "빨강"}),
    Example(inputs={"query": "바나나는?"}, outputs={"response": "노랑"}),
]


def test_candidates_are_scored_with_the_returned_system_prompt():
    task = FewShotTask()
    lm = RecordingLM("  초록  ")
    with dspy.context(lm=lm):
        prediction = build_program(task, DEMOS, "Answer with a color.")(query="수박은?")
    assert prediction.response == "초록"  # the whole reply, no field markers to parse
    assert lm.calls == [[
        {"role": "system", "content": task.render_system_prompt("Answer with a color.", DEMOS)},
        {"role": "user", "content": "수박은?"},
    ]]
    assert task.render_system_prompt("Answer with a color.", DEMOS) == (
        "Answer with a color.\n\nHere are some examples:\n\nQuery: 사과는?\nResponse: 빨강\n\n"
        "Query: 바나나는?\nResponse: 노랑"
    )


def test_no_chain_of_thought_in_the_scored_program():
    program = FewShotTask().build_dspy_program(DEMOS)
    [(_, predictor)] = program.named_predictors()
    assert type(predictor) is dspy.Predict
    assert list(predictor.signature.output_fields) == ["response"]


def test_vlm_scoring_sends_only_the_query_image():
    task = FewShotTask(supports_image=True)
    demos = [Example(inputs={"query": "색은?", "image": BLUE}, outputs={"response": "파랑"})]
    lm = RecordingLM("빨강")
    with dspy.context(lm=lm):
        build_program(task, demos, None)(**task.prepare_inputs({"query": "색은?", "image": RED}))
    system, user = lm.calls[0]
    assert system["content"] == task.render_system_prompt(fewshot_task.default_instruction(True), demos)
    assert "base64" not in system["content"]  # demo images never enter the text system prompt
    assert user["content"] == [{"type": "image_url", "image_url": {"url": RED}}, {"type": "text", "text": "색은?"}]


def test_default_instructions():
    assert fewshot_task.default_instruction(False).startswith("Respond to the user's query, following")
    assert "image" in fewshot_task.default_instruction(True)


# --------------------------------------------------------------------- #
# token_f1
# --------------------------------------------------------------------- #


def test_token_f1_bounds():
    assert token_f1("a b c", "a b c") == 1.0
    assert token_f1("", "") == 1.0
    assert token_f1("a", "") == 0.0
    assert token_f1("a b", "c d") == 0.0


def test_token_f1_english_partial_overlap():
    assert token_f1("the cat sat", "the cat ran") == pytest.approx(2 / 3)


def test_token_f1_ignores_case_and_punctuation():
    assert token_f1("사과는 빨간색입니다.", "사과는 빨간색입니다") == 1.0
    assert token_f1("Hello, World!", "hello world") == 1.0


def test_token_f1_credits_korean_stems():
    # 사과/빨간/간색 shared out of 7 syllable bigrams on each side
    assert token_f1("사과는 빨간색입니다", "사과가 빨간색이에요") == pytest.approx(3 / 7)


def test_tokens_split_hangul_from_digits_and_latin():
    # digits become their own token, as in English ("Rule 14" -> rule, 14)
    assert fewshot_task._tokens("COLREG 제14조(마주치는 상태)") == [
        "colreg", "제", "14", "조", "마주", "주치", "치는", "상태",
    ]


# --------------------------------------------------------------------- #
# metric selection
# --------------------------------------------------------------------- #

ANSWER = Example(inputs={"query": "사과는?"}, outputs={"response": "사과는 빨갛다"})


def test_unknown_metric_is_rejected():
    with pytest.raises(ValueError, match="token_f1, bert_score"):
        FewShotTask(metric_name="rouge")


class _FakeF1:
    def item(self) -> float:
        return 0.9


def _fake_bert(monkeypatch) -> dict:
    """Install a stub ``bert_score`` module (the real package is optional);
    returns the kwargs its BERTScorer gets constructed with."""
    captured: dict = {}

    class FakeScorer:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def score(self, cands, refs, verbose=False):
            return None, None, _FakeF1()

    stub = types.ModuleType("bert_score")
    stub.BERTScorer = FakeScorer
    monkeypatch.setitem(sys.modules, "bert_score", stub)
    monkeypatch.setattr(fewshot_task, "_bert_scorer", None)
    return captured


def test_bert_score_uses_a_multilingual_model(monkeypatch):
    captured = _fake_bert(monkeypatch)
    assert fewshot_task._bert_f1("사과는 빨갛다", "사과가 빨갛다") == pytest.approx(0.9)
    assert captured.get("lang") != "en"
    assert captured["model_type"] == "bert-base-multilingual-cased"


def test_bert_score_model_is_configurable(monkeypatch):
    captured = _fake_bert(monkeypatch)
    monkeypatch.setattr(fewshot_task, "BERTSCORE_MODEL", "klue/roberta-large")
    fewshot_task._bert_f1("a", "b")
    assert captured["model_type"] == "klue/roberta-large"


def test_unavailable_bert_score_falls_back_for_the_whole_run(monkeypatch):
    def unavailable():
        raise OSError("offline")

    monkeypatch.setattr(fewshot_task, "_load_bert_scorer", unavailable)
    task = FewShotTask(metric_name="bert_score")
    assert task.metric_name == "token_f1"
    assert "bert_score unavailable (OSError: offline)" in task.warnings[0]
    assert task.metric(ANSWER, {"response": "사과는 빨갛다"}) == 1.0


def test_single_bert_score_failures_are_counted(monkeypatch):
    _fake_bert(monkeypatch)
    task = FewShotTask(metric_name="bert_score")
    assert task.metric(ANSWER, {"response": "x"}) == pytest.approx(0.9)

    def failing(gold, pred):
        raise RuntimeError("CUDA OOM")

    monkeypatch.setattr(fewshot_task, "_bert_f1", failing)
    assert task.metric(ANSWER, {"response": "사과는 빨갛다"}) == 1.0  # token_f1 for this pair
    assert task.metric_name == "bert_score"
    assert task.warnings == [
        "bert_score failed on 1 prediction(s) (first: RuntimeError('CUDA OOM')); token_f1 was used for those"
    ]


def test_preload_is_skipped_without_the_package(monkeypatch):
    monkeypatch.setattr(fewshot_task, "bert_score_installed", lambda: False)
    monkeypatch.setenv("BERTSCORE_PRELOAD", "true")
    assert fewshot_task.preload_bert_scorer() is None


def test_preload_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(fewshot_task, "bert_score_installed", lambda: True)
    monkeypatch.setenv("BERTSCORE_PRELOAD", "false")
    assert fewshot_task.preload_bert_scorer() is None


def test_preload_runs_in_the_background_and_survives_failures(monkeypatch):
    monkeypatch.setattr(fewshot_task, "bert_score_installed", lambda: True)
    monkeypatch.setenv("BERTSCORE_PRELOAD", "true")
    calls = []

    def offline_load():
        calls.append(threading.current_thread().name)
        raise OSError("offline")

    monkeypatch.setattr(fewshot_task, "_load_bert_scorer", offline_load)
    thread = fewshot_task.preload_bert_scorer()
    thread.join(5)
    assert calls == ["bertscore-preload"]


# --------------------------------------------------------------------- #
# VLM path (vlm=true)
# --------------------------------------------------------------------- #


def test_data_uri_and_url_become_dspy_images():
    assert fewshot_task._to_dspy_image(RED).url == RED
    assert fewshot_task._to_dspy_image("https://example.com/a.png").url == "https://example.com/a.png"


def test_local_image_paths_are_refused():
    # images are forwarded to the caller's llm_url; reading server files would leak them
    assert not fewshot_task.is_image_ref("/etc/hostname")
    assert not fewshot_task.is_image_ref("file:///etc/hostname")
    assert fewshot_task._to_dspy_image("/etc/hostname") is None


def test_text_task_ignores_images():
    task = FewShotTask()
    assert task.input_keys == ("query",)
    assert task.prepare_inputs({"query": "q", "image": RED}) == {"query": "q"}


def test_vlm_scoring_passes_image_to_program(monkeypatch):
    task = FewShotTask(supports_image=True)
    seen: list[dict] = []

    class FakeProgram:
        def __call__(self, **kwargs):
            seen.append(kwargs)
            return SimpleNamespace(response="빨강")

    monkeypatch.setattr(task, "build_dspy_program", lambda demos: FakeProgram())
    holdout = [Example(inputs={"query": "이 그림의 색은?", "image": RED}, outputs={"response": "빨강"})]
    assert score_demos_per_example(task, [], holdout) == [1.0]
    assert isinstance(seen[0].get("image"), dspy.Image)


VLM_TRAINSET = [  # two examples share the same question and differ only by image
    Example(inputs={"query": "이 그림의 색은?", "image": RED}, outputs={"response": "빨강"}),
    Example(inputs={"query": "이 그림의 색은?", "image": BLUE}, outputs={"response": "파랑"}),
    Example(inputs={"query": "다른 질문", "image": GREEN}, outputs={"response": "초록"}),
    Example(inputs={"query": "이 그림의 색은?"}, outputs={"response": "모름"}),  # synthetic: no image
]


def test_vlm_demos_are_recovered_after_selection():
    task = FewShotTask(supports_image=True)
    subset = [VLM_TRAINSET[1], VLM_TRAINSET[2], VLM_TRAINSET[3]]
    program = task.build_dspy_program(subset)
    assert _extract_demos(program, VLM_TRAINSET, task) == subset


def test_vlm_mipro_examples_carry_images_and_are_recovered():
    task = FewShotTask(supports_image=True)
    converted = _to_dspy(VLM_TRAINSET[1], task)
    assert set(converted.inputs().keys()) == {"query", "image"}
    assert isinstance(converted.image, dspy.Image)

    program = task.build_dspy_program([])
    for _name, predictor in program.named_predictors():  # what MIPRO's compile leaves behind
        predictor.demos = [_to_dspy(e, task) for e in (VLM_TRAINSET[3], VLM_TRAINSET[1])]
    assert _extract_demos(program, VLM_TRAINSET, task) == [VLM_TRAINSET[3], VLM_TRAINSET[1]]


# --------------------------------------------------------------------- #
# leave-one-out scoring
# --------------------------------------------------------------------- #

A = Example(inputs={"query": "a?"}, outputs={"response": "A"})
B = Example(inputs={"query": "b?"}, outputs={"response": "B"})
C = Example(inputs={"query": "c?"}, outputs={"response": "C"})


def _system_prompt_seen(task, demos, query_inputs):
    lm = RecordingLM("x")
    with dspy.context(lm=lm):
        build_program(task, demos, "I")(**task.prepare_inputs(query_inputs))
    return lm.calls[0][0]["content"]


def test_an_example_is_answered_without_its_own_demo():
    task = FewShotTask()
    assert _system_prompt_seen(task, [A, B, C], A.inputs) == task.render_system_prompt("I", [B, C])
    # a new query matches no demo: the prompt is exactly the one the service returns
    assert _system_prompt_seen(task, [A, B, C], {"query": "new?"}) == task.render_system_prompt("I", [A, B, C])


def test_synthetic_demos_stay_out_of_the_prompts_of_the_examples_they_came_from():
    task = FewShotTask()
    s = Example(inputs={"query": "s?"}, outputs={"response": "S"}, origin=(A.key,))
    assert _system_prompt_seen(task, [A, B, s], A.inputs) == task.render_system_prompt("I", [B])
    assert _system_prompt_seen(task, [A, B, s], B.inputs) == task.render_system_prompt("I", [A, s])


def test_same_question_about_another_image_is_another_example():
    task = FewShotTask(supports_image=True)
    red = Example(inputs={"query": "색은?", "image": RED}, outputs={"response": "빨강"})
    blue = Example(inputs={"query": "색은?", "image": BLUE}, outputs={"response": "파랑"})
    assert _system_prompt_seen(task, [red, blue], red.inputs) == task.render_system_prompt("I", [blue])


def test_leave_one_out_holds_in_mipro_copies_of_the_program():
    import copy

    task = FewShotTask()
    s = Example(inputs={"query": "s?"}, outputs={"response": "S"}, origin=(A.key,))
    program = copy.deepcopy(build_program(task, [A, B, s], "I"))
    lm = RecordingLM("x")
    with dspy.context(lm=lm):
        program(query="a?")
    assert lm.calls[0][0]["content"] == task.render_system_prompt("I", [B])
