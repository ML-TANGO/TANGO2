"""judge.py and likelihood.py: paired decisions, the reference-likelihood scorer
(server faked), and the messages it scores (the program's own, leave-one-out)."""

from __future__ import annotations

import dspy
import pytest

from src.fewshot_task import FewShotTask
from src.optimizer import judge as judge_mod
from src.optimizer.judge import Candidate, Judge, paired_gain
from src.optimizer.likelihood import LikelihoodUnavailable, ReferenceScorer
from src.optimizer.scoring import Scored, build_program, likelihood_per_example
from src.optimizer.task import Example

A = Example(inputs={"query": "a?"}, outputs={"response": "A"})
B = Example(inputs={"query": "b?"}, outputs={"response": "B"})
C = Example(inputs={"query": "c?"}, outputs={"response": "C"})


def test_paired_gain_is_the_mean_difference_and_its_standard_error():
    gain, se = paired_gain([1.0, 2.0, 3.0, 6.0], [0.0, 1.0, 2.0, 1.0])  # differences 1, 1, 1, 5
    assert gain == 2.0 and se == pytest.approx(1.0)
    assert paired_gain([0.5, 0.5], [0.4, 0.4]) == (pytest.approx(0.1), pytest.approx(0.0))


class FakeScorer:
    """Reference likelihood (and first-choice share) = the value a test assigns
    to each prompt."""

    def __init__(self, table):
        self.table = table

    def mean_logprob(self, messages, reference):
        return self.table[messages[0]["content"]][reference]

    def stats(self, messages, reference):
        value = self.table[messages[0]["content"]][reference]
        return value, value


def _judge(monkeypatch, llh_table, metric_table):
    calls = []

    def fake_evaluate(task, demos, scoring, *, instruction=None):
        calls.append(instruction)
        return [Scored(e, {"response": ""}, metric_table[instruction]) for e in scoring]

    monkeypatch.setattr(judge_mod, "evaluate_demos", fake_evaluate)
    task = FewShotTask(metric_name="token_f1")
    scorer = FakeScorer({task.render_system_prompt(i, [C]): v for i, v in llh_table.items()})
    return Judge(task, [A, B], scorer=scorer, z=1.0, kind="llh"), calls


def test_a_change_needs_a_clear_likelihood_gain_and_no_metric_loss(monkeypatch):
    llh = {"old": {"A": -1.0, "B": -1.0}, "clear": {"A": -0.8, "B": -0.7},
           "noisy": {"A": -0.5, "B": -1.4}, "worse_metric": {"A": -0.8, "B": -0.7}}
    metric = {"old": 0.50, "clear": 0.52, "noisy": 0.60, "worse_metric": 0.49}
    judge, calls = _judge(monkeypatch, llh, metric)
    with dspy.context(lm=None):
        old = judge.candidate("old", [C], metric=True)
        assert calls == ["old"]
        noisy = judge.candidate("noisy", [C])
        ok, why = judge.improves(noisy, old)  # mean gain 0.05, standard error 0.45
        assert not ok and "llh" in why and calls == ["old"]  # its metric is never measured
        clear = judge.candidate("clear", [C])
        assert judge.improves(clear, old)[0] and calls == ["old", "clear"]
        worse = judge.candidate("worse_metric", [C])
        assert not judge.improves(worse, old)[0]  # the reported score must not drop


def test_metric_only_judge_uses_the_metric_as_evidence(monkeypatch):
    def fake_evaluate(task, demos, scoring, *, instruction=None):
        return [Scored(e, {"response": ""}, {"old": 0.5, "new": 0.6}[instruction]) for e in scoring]

    monkeypatch.setattr(judge_mod, "evaluate_demos", fake_evaluate)
    judge = Judge(FewShotTask(metric_name="token_f1"), [A, B], scorer=None)
    old, new = judge.candidate("old", [C]), judge.candidate("new", [C])
    assert old.score == 0.5 and old.evidence == [0.5, 0.5]
    assert judge.improves(new, old)[0] and not judge.improves(old, new)[0]
    assert not judge.uses_likelihood


def test_measure_fills_a_missing_metric_once(monkeypatch):
    seen = []

    def fake_evaluate(task, demos, scoring, *, instruction=None):
        seen.append(instruction)
        return [Scored(e, {"response": ""}, 0.25) for e in scoring]

    monkeypatch.setattr(judge_mod, "evaluate_demos", fake_evaluate)
    judge = Judge(FewShotTask(metric_name="token_f1"), [A], scorer=FakeScorer({}))
    cand = Candidate("x", [C], None, [0.0])
    assert judge.measure(cand) == 0.25 and judge.measure(cand) == 0.25 and seen == ["x"]


# --------------------------------------------------------------------- #
# likelihood.ReferenceScorer (server faked)
# --------------------------------------------------------------------- #

class FakeServer:
    """Tokenizes by whitespace; the chat template puts 2 tokens (role marker,
    role) before every message and as the generation prompt, and 2 tokens (end
    marker, newline) after an assistant message."""

    def __init__(self):
        self.bodies = []

    def __call__(self, url, body):
        self.bodies.append((url, body))
        if url.endswith("/tokenize"):
            if "prompt" in body:
                return {"count": len(body["prompt"].split())}
            n = sum(2 + len(str(m["content"]).split()) for m in body["messages"])
            if body["messages"][-1]["role"] == "assistant":
                n += 2
            elif body.get("add_generation_prompt"):
                n += 2
            return {"count": n}
        msgs = body["messages"]
        tokens = []
        for m in msgs:
            tokens += ["<role>", m["role"], *str(m["content"]).split()]
        tokens += ["<end>", "\n"]
        # every reference word scores -1, the end marker -2, the template newline -9
        lps = [None] + [{"1": {"logprob": -5.0}} for _ in tokens[1:]]
        n_ref = len(str(msgs[-1]["content"]).split())
        for i in range(len(tokens) - 2 - n_ref, len(tokens) - 2):
            lps[i] = {"1": {"logprob": -1.0}}
        lps[-2] = {"1": {"logprob": -2.0}}
        lps[-1] = {"1": {"logprob": -9.0}}
        return {"prompt_logprobs": lps}


def test_reference_scorer_scores_the_reference_and_the_end_marker(monkeypatch):
    scorer = ReferenceScorer("http://llm/v1", "m", "key")
    server = FakeServer()
    monkeypatch.setattr(scorer, "_post", server)
    lps = scorer.logprobs([{"role": "user", "content": "hi there"}], " one two three ")
    assert scorer.n_after() == 2
    assert lps == [-1.0, -1.0, -1.0, -2.0]  # not the template's newline after the marker
    chat = [b for u, b in server.bodies if u.endswith("/chat/completions")][0]
    assert chat["messages"][-1] == {"role": "assistant", "content": "one two three"}
    assert chat["prompt_logprobs"] == 0 and chat["add_generation_prompt"] is False
    assert scorer.mean_logprob([{"role": "user", "content": "hi there"}], "one two three") == pytest.approx(-1.25)


def test_reference_scores_are_cached(monkeypatch):
    scorer = ReferenceScorer("http://llm/v1", "m", cache={})
    server = FakeServer()
    monkeypatch.setattr(scorer, "_post", server)
    scorer.mean_logprob([{"role": "user", "content": "q"}], "a b")
    n = len(server.bodies)
    scorer.mean_logprob([{"role": "user", "content": "q"}], "a b")
    assert len(server.bodies) == n


def test_a_server_without_prompt_logprobs_is_reported(monkeypatch):
    scorer = ReferenceScorer("http://llm/v1", "m")

    def no_logprobs(url, body):
        if url.endswith("/tokenize"):
            return {"count": 1}
        return {"choices": [{"message": {"content": "x"}}]}

    monkeypatch.setattr(scorer, "_post", no_logprobs)
    assert "prompt_logprobs" in scorer.probe()
    with pytest.raises(LikelihoodUnavailable):
        scorer.logprobs([{"role": "user", "content": "q"}], "a")


def test_from_dspy_lm_reads_the_endpoint():
    lm = dspy.LM(model="openai/Qwen/Qwen3-4B", api_base="http://h:8000/v1", api_key="k")
    scorer = ReferenceScorer.from_dspy_lm(lm)
    assert (scorer.base_url, scorer.root, scorer.model) == ("http://h:8000/v1", "http://h:8000", "Qwen/Qwen3-4B")


# --------------------------------------------------------------------- #
# the scored messages are the program's own (leave-one-out)
# --------------------------------------------------------------------- #

def test_messages_are_what_the_program_sends_without_its_own_demos():
    task = FewShotTask(metric_name="token_f1")
    s = Example(inputs={"query": "s?"}, outputs={"response": "S"}, origin=(A.key,))
    prog = build_program(task, [A, B, s], "I")
    assert prog.messages(query="a?") == [{"role": "system", "content": task.render_system_prompt("I", [B])},
                                         {"role": "user", "content": "a?"}]
    assert prog.messages(query="b?")[0]["content"] == task.render_system_prompt("I", [A, s])


def test_likelihood_per_example_scores_each_reference_leave_one_out():
    task = FewShotTask(metric_name="token_f1")
    seen = []

    class Recorder:
        def mean_logprob(self, messages, reference):
            seen.append((messages[0]["content"], reference))
            return -float(len(seen))

    with dspy.context(num_threads=1):
        out = likelihood_per_example(task, [A, B, C], [A, B], instruction="I", scorer=Recorder())
    assert out == [-1.0, -2.0]
    assert seen == [(task.render_system_prompt("I", [B, C]), "A"), (task.render_system_prompt("I", [A, C]), "B")]


def test_by_default_the_evidence_is_the_metric():
    judge = Judge(FewShotTask(metric_name="token_f1"), [A, B], scorer=FakeScorer({}))
    assert (judge.kind, judge.z, judge.uses_likelihood) == ("metric", 0.0, False)


def test_first_choice_evidence_must_rise_and_the_metric_must_not_fall(monkeypatch):
    def fake_evaluate(task, demos, scoring, *, instruction=None):
        return [Scored(e, {"response": ""}, {"old": 0.5, "up": 0.5, "down": 0.6}[instruction]) for e in scoring]

    monkeypatch.setattr(judge_mod, "evaluate_demos", fake_evaluate)
    task = FewShotTask(metric_name="token_f1")
    table = {"old": {"A": 0.70, "B": 0.70}, "up": {"A": 0.72, "B": 0.71}, "down": {"A": 0.69, "B": 0.70}}
    judge = Judge(task, [A, B], scorer=FakeScorer({task.render_system_prompt(i, [C]): v for i, v in table.items()}), kind="top1")
    old = judge.candidate("old", [C], metric=True)
    assert judge.improves(judge.candidate("up", [C]), old)[0]  # first choices up, metric level
    assert not judge.improves(judge.candidate("down", [C]), old)[0]  # metric up, first choices down
