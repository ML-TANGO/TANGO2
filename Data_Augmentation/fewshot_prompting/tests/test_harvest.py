"""harvest.py and feedback.py: the score gate, the second attempt, and the
feedback refinement (scoring and generation faked)."""

from __future__ import annotations

from types import SimpleNamespace

from src.optimizer import feedback
from src.optimizer import judge as judge_mod
from src.optimizer.harvest import harvest
from src.optimizer.judge import Judge
from src.optimizer.scoring import Scored
from src.optimizer.task import Example

TASK = SimpleNamespace(input_keys=("query",), text_input_keys=("query",), output_keys=("response",))
GIVEN = [Example(inputs={"query": f"g{i}"}, outputs={"response": f"G{i}"}) for i in range(4)]


class FakeGenerator:
    """Each call returns one batch of synthetic examples tagged good/bad."""

    def __init__(self, tags):
        self.tags = iter(tags)
        self.calls = 0

    def generate(self, seeds, input_keys, output_keys, *, n=None, guidance=None):
        self.calls += 1
        tag = next(self.tags)
        origin = tuple(s.key for s in seeds)
        return [Example(inputs={"query": f"{tag}-{self.calls}-{i}"}, outputs={"response": tag}, origin=origin)
                for i in range(n)]


def fake_evaluate(task, demos, scoring, *, instruction=None):
    """+0.01 per 'good' demo, -0.01 per 'bad' demo, on every scoring example."""
    value = 0.5 + sum(0.01 if d.outputs["response"] == "good" else -0.01 for d in demos if d.synthetic)
    return [Scored(e, {"response": "x"}, value) for e in scoring]


def _run(monkeypatch, tags, n_iterations, margin=0.0, feedback_on=False):
    monkeypatch.setattr(judge_mod, "evaluate_demos", fake_evaluate)
    gen = FakeGenerator(tags)
    judge = Judge(TASK, list(GIVEN), scorer=None, z=1.0, margin=margin)
    state = judge.candidate("I", list(GIVEN))
    out = harvest(TASK, state, GIVEN, judge, generator=gen, reflection_lm=None,
                  n_iterations=n_iterations, n_per_iteration=2, seeds_per_iteration=2,
                  feedback=feedback_on, seed=0)
    return out, gen


def test_only_batches_that_raise_the_score_join(monkeypatch):
    out, gen = _run(monkeypatch, ["good", "bad", "bad", "good"], n_iterations=3)
    # iter 0: good accepted; iter 1: bad, then fresh variants (bad) rejected; iter 2: good accepted
    assert [d.outputs["response"] for d in out.accepted] == ["good"] * 4
    assert round(out.state.score, 4) == 0.54 and out.state.demos == [*GIVEN, *out.accepted]
    assert gen.calls == 4 and out.generated_total == 8
    assert [[a["accepted"] for a in it["attempts"]] for it in out.iterations] == [[True], [False, False], [True]]
    assert all(len(d.origin) == 2 for d in out.accepted)  # each example points at the seeds it came from


def test_the_margin_raises_the_bar(monkeypatch):
    out, _ = _run(monkeypatch, ["good", "good"], n_iterations=1, margin=0.05)
    assert out.accepted == []


def test_feedback_refines_every_batch_before_the_gate(monkeypatch):
    seen = []

    def fake_refine(task, batch, seeds, *, reflection_lm, conventions=""):
        seen.append(([d.outputs["response"] for d in batch], len(seeds)))
        return [Example(inputs=d.inputs, outputs={"response": "good"}, origin=d.origin) for d in batch]

    monkeypatch.setattr(feedback, "refine", fake_refine)
    out, gen = _run(monkeypatch, ["bad"], n_iterations=1, feedback_on=True)
    assert gen.calls == 1 and seen == [(["bad", "bad"], 2)]  # the batch, critiqued against its two seeds
    assert len(out.accepted) == 2 and round(out.state.score, 4) == 0.52


def test_refine_rewrites_only_the_output_of_examples_with_problems():
    seeds = [Example(inputs={"query": "speed 12.34"}, outputs={"response": "Speed 12.3."})]
    batch = [Example(inputs={"query": "speed 15.00"}, outputs={"response": "Speed 15.00 knots, rising."}, origin=(seeds[0].key,)),
             Example(inputs={"query": "speed 9.00"}, outputs={"response": "Speed 9.0."}, origin=(seeds[0].key,))]
    calls = []

    def lm(messages):
        calls.append(messages)
        user = messages[1]["content"]
        if messages[0]["content"].startswith("You check"):
            return "1. 'rising' is not used in real outputs; '15.00' should be '15.0'." if "15.00" in user else "NO PROBLEMS"
        return '{"inputs": {"query": "speed 99"}, "outputs": {"response": "Speed 15.0."}}'

    fixed, kept = feedback.refine(TASK, batch, seeds, reflection_lm=lm)
    assert "Speed 12.3." in calls[0][0]["content"]  # critiqued against the real examples
    assert fixed.outputs == {"response": "Speed 15.0."} and fixed.inputs == batch[0].inputs  # inputs kept
    assert fixed.origin == batch[0].origin and kept == batch[1]
    assert len(calls) == 3  # two critiques, one rewrite


def test_the_critic_is_told_the_measured_conventions():
    seeds = [Example(inputs={"query": "speed 12.34"}, outputs={"response": "Speed 12.3 knots."})]
    batch = [Example(inputs={"query": "speed 15.06"}, outputs={"response": "Speed 15.1 knots."}, origin=(seeds[0].key,))]
    calls = []

    def lm(messages):
        calls.append(messages[0]["content"])
        return "NO PROBLEMS"

    note = "The real outputs write numbers rounded to 1 decimal place, even where their inputs give more decimals."
    feedback.refine(TASK, batch, seeds, reflection_lm=lm, conventions=note)
    assert note in calls[0] and "never ask for more decimals" in calls[0]


# --------------------------------------------------------------------- #
# feedback by reference likelihood
# --------------------------------------------------------------------- #

def test_improbable_spans_are_the_least_likely_words_in_order():
    toks = [(" The", -0.1), (" sky", -5.0), (" is", -0.1), (" very", -2.0), (" gre", -2.0), ("en", -1.5), (".", -0.1)]
    assert feedback.improbable_spans(toks) == ["sky", "green."]  # a word sums its tokens: -3.6
    assert feedback.improbable_spans(toks, max_spans=1) == ["sky"]
    assert feedback.improbable_spans([(" a", -4.0), (" b", -4.0), (" c", 0.0)]) == ["a b"]  # neighbours merge
    assert feedback.improbable_spans([(" fine", -0.5)]) == []


class TokenScorer:
    """The task model's view, faked: every word of an output scores -1 except
    'weird' (-6); the end-of-turn marker scores 0."""

    def n_after(self):
        return 1

    def tokens(self, messages, reference):
        return [(" " + w, -6.0 if w == "weird" else -1.0) for w in reference.split()] + [("<end>", 0.0)]

    def mean_logprob(self, messages, reference):
        toks = self.tokens(messages, reference)
        return sum(lp for _, lp in toks) / len(toks)


def _likelihood_refine(reply):
    seeds = [Example(inputs={"query": "q1"}, outputs={"response": "a normal answer here"})]
    batch = [Example(inputs={"query": "q2"}, outputs={"response": "a weird answer here"}, origin=(seeds[0].key,)),
             Example(inputs={"query": "q3"}, outputs={"response": "a plain answer here"}, origin=(seeds[0].key,))]
    calls = []

    def lm(messages):
        calls.append(messages)
        return reply

    task = SimpleNamespace(input_keys=("query",), text_input_keys=("query",), output_keys=("response",),
                           build_dspy_program=lambda demos: SimpleNamespace(
                               messages=lambda **inputs: [{"role": "user", "content": inputs["query"]}],
                               named_predictors=lambda: []))
    out = feedback.refine_by_likelihood(task, batch, seeds, scorer=TokenScorer(), instruction=None, demos=seeds,
                                        reflection_lm=lm)
    return batch, out, calls


def test_likelihood_feedback_rewrites_only_the_improbable_parts():
    batch, out, calls = _likelihood_refine('{"inputs": {"query": "zzz"}, "outputs": {"response": "a usual answer here"}}')
    assert len(calls) == 1  # the plain example has no improbable word: no call
    assert '- "weird"' in calls[0][0]["content"] and "a normal answer here" in calls[0][0]["content"]
    assert out[0].outputs == {"response": "a usual answer here"} and out[0].inputs == batch[0].inputs
    assert out[0].origin == batch[0].origin and out[1] is batch[1]


def test_a_rewrite_that_is_not_more_probable_is_dropped():
    batch, out, _ = _likelihood_refine('{"inputs": {}, "outputs": {"response": "a weird weird answer"}}')
    assert out[0] is batch[0]


def test_a_rewrite_that_drops_content_is_dropped():
    batch, out, _ = _likelihood_refine('{"inputs": {}, "outputs": {"response": "ok"}}')
    assert out[0] is batch[0]  # more probable per token, but far shorter


class VaryingGenerator:
    """vary(): one 'good' variation of each seed, pointing at that seed."""

    def __init__(self):
        self.seeds = []

    def vary(self, seed, input_keys, output_keys, *, n=1):
        self.seeds.append(seed.inputs["query"])
        return [Example(inputs={"query": seed.inputs["query"] + "'"}, outputs={"response": "good"}, origin=(seed.key,))]


def test_vary_mode_writes_one_variation_per_seed(monkeypatch):
    monkeypatch.setattr(judge_mod, "evaluate_demos", fake_evaluate)
    gen = VaryingGenerator()
    judge = Judge(TASK, list(GIVEN), scorer=None)
    out = harvest(TASK, judge.candidate("I", list(GIVEN)), GIVEN, judge, generator=gen, reflection_lm=None,
                  n_iterations=1, n_per_iteration=2, seeds_per_iteration=3, feedback=False, seed=0, generator_mode="vary")
    assert len(gen.seeds) == 2 and len(out.accepted) == 2  # the first n_per_iteration seeds, one variation each
    assert [d.origin for d in out.accepted] == [(g.key,) for q in gen.seeds for g in GIVEN if g.inputs["query"] == q]
