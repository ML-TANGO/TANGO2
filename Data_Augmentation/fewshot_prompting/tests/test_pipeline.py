"""pipeline.run_optimization: stages never lower the score, the returned demos
are the ones scored, and every stage's prompt is recorded.

MIPRO, harvest and scoring are replaced by deterministic fakes, so the
orchestration can be checked without an LLM.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.optimizer import Example, OptimizeConfig, pipeline
from src.optimizer import judge as judge_mod
from src.optimizer.harvest import Candidate, HarvestOutcome
from src.optimizer.mipro_step import MIPROOutcome
from src.optimizer.scoring import Scored

TASK = SimpleNamespace(
    name="fake",
    input_keys=("query",),
    output_keys=("response",),
    build_dspy_program=lambda demos: SimpleNamespace(demos=list(demos), named_predictors=lambda: []),
    render_system_prompt=lambda instr, demos: f"{instr}|{','.join(d.inputs['query'] for d in demos)}",
)
GIVEN = [Example(inputs={"query": f"g{i}"}, outputs={"response": f"G{i}"}) for i in range(4)]


def _synth(tag: str) -> Example:
    return Example(inputs={"query": tag}, outputs={"response": tag}, origin=(GIVEN[0].key,))


def fake_score(task, demos, scoring, *, instruction=None) -> float:
    """Scores depend only on the prompt: instruction quality + per-demo values."""
    value = {"I0": 0.30, "good": 0.40, "bad": 0.10}.get(instruction, 0.0)
    for d in demos:
        q = d.inputs["query"]
        value += 0.02 if q.startswith("g") else (0.03 if q.startswith("s+") else -0.03)
    return round(value, 4)


def _patch(monkeypatch, proposals):
    """``proposals[i]`` = (instruction, number of pool demos kept) for the i-th MIPRO call."""
    calls = iter(proposals)
    synth_counter = iter(range(100))

    def fake_run_mipro(task, pool, scoring, *, instruction=None, extra_instructions=(), **kwargs):
        instr, keep = next(calls)
        return MIPROOutcome(program=None, instruction=instr, demos=list(pool[:keep]))

    def fake_harvest(task, state, given, judge, **kwargs):
        new = [_synth(f"s+{next(synth_counter)}")]
        grown = judge.candidate(state.instruction, [*state.demos, *new])
        return HarvestOutcome(state=grown, accepted=new, generated_total=3)

    def fake_evaluate(task, demos, scoring, *, instruction=None):
        value = fake_score(task, demos, scoring, instruction=instruction)
        return [Scored(e, {"response": "x"}, value) for e in scoring]

    monkeypatch.setattr(pipeline, "run_mipro", fake_run_mipro)
    monkeypatch.setattr(pipeline, "harvest", fake_harvest)
    monkeypatch.setattr(judge_mod, "evaluate_demos", fake_evaluate)


def _run(rounds: int):
    return pipeline.run_optimization(
        TASK, GIVEN, generation_lm=None, reflection_lm=None, task_lm=None,
        config=OptimizeConfig(rounds=rounds, instruction="I0", use_likelihood=False),
    )


def test_baseline_is_every_example_under_the_starting_instruction(monkeypatch):
    _patch(monkeypatch, [("bad", 2)])
    result = _run(rounds=0)
    assert result.history[0]["step"] == "baseline"
    assert result.history[0]["system_prompt"] == "I0|g0,g1,g2,g3"
    assert result.base_score == fake_score(TASK, GIVEN, GIVEN, instruction="I0")


def test_a_compression_that_scores_lower_is_rejected(monkeypatch):
    _patch(monkeypatch, [("bad", 2)])
    result = _run(rounds=0)
    assert result.history[1]["chosen"] == "unchanged"
    assert result.instruction == "I0" and result.final_demos == GIVEN
    assert result.final_score == result.base_score


def test_a_compression_that_scores_higher_is_kept(monkeypatch):
    _patch(monkeypatch, [("good", 3)])
    result = _run(rounds=0)
    assert result.history[1]["chosen"] == "mipro"
    assert (result.instruction, result.final_demos) == ("good", GIVEN[:3])


def test_scores_never_drop_from_stage_to_stage(monkeypatch):
    _patch(monkeypatch, [("good", 2), ("bad", 5), ("good", 1), ("I0", 7)])
    scores = [h["holdout"] for h in _run(rounds=3).history]
    assert scores == sorted(scores)


def test_returned_prompt_is_the_one_scored(monkeypatch):
    _patch(monkeypatch, [("good", 3), ("good", 4)])
    result = _run(rounds=1)
    assert result.final_score == fake_score(TASK, result.final_demos, GIVEN, instruction=result.instruction)
    assert result.program.demos == result.final_demos
    assert result.history[-1]["system_prompt"] == TASK.render_system_prompt(result.instruction, result.final_demos)


def test_recompression_can_bring_back_given_examples_dropped_earlier(monkeypatch):
    _patch(monkeypatch, [("good", 2), ("good", 5)])  # round 1 MIPRO keeps all 4 given + the synthetic demo
    result = _run(rounds=1)
    assert [d.inputs["query"] for d in result.final_demos] == ["g0", "g1", "g2", "g3", "s+0"]


def test_a_round_does_not_depend_on_how_many_rounds_follow(monkeypatch):
    proposals = [("good", 3), ("good", 5), ("I0", 2), ("good", 9)]
    _patch(monkeypatch, proposals)
    short = _run(rounds=1).history
    _patch(monkeypatch, proposals)
    long = _run(rounds=3).history
    assert long[: len(short)] == short
    assert [h["step"] for h in long] == ["baseline", "compress", "round1", "round2", "round3"]


def test_measured_style_rules_are_offered_and_can_win(monkeypatch):
    """A style candidate (here: rounding) joins MIPRO's candidates and is kept
    with the current demos when it scores best."""
    from src.optimizer import style

    _patch(monkeypatch, [("bad", 2)])
    seen = {}
    real_run_mipro = pipeline.run_mipro

    def spy(task, pool, scoring, **kwargs):
        seen["extras"] = kwargs["extra_instructions"]
        return real_run_mipro(task, pool, scoring, **kwargs)

    monkeypatch.setattr(pipeline, "run_mipro", spy)
    monkeypatch.setattr(pipeline, "style_instructions", lambda base, examples: {"rounding": "good"})
    result = _run(rounds=0)
    assert seen["extras"] == ["good"]
    assert result.history[1]["chosen"] == "style:rounding"
    assert (result.instruction, result.final_demos) == ("good", GIVEN)


def test_without_a_likelihood_server_decisions_fall_back_to_the_metric(monkeypatch):
    _patch(monkeypatch, [("good", 3)])
    result = pipeline.run_optimization(
        TASK, GIVEN, generation_lm=None, reflection_lm=None, task_lm=None,
        config=OptimizeConfig(rounds=0, instruction="I0", evidence="llh"),  # task_lm=None cannot score references
    )
    assert result.history[1]["chosen"] == "mipro"
    assert any("reference likelihood unavailable" in n for n in result.notes)
    assert "holdout_llh" not in result.history[0]


def test_generation_is_replayed_across_runs_sharing_a_cache(tmp_path):
    import diskcache

    replies = iter(f"reply{i}" for i in range(1, 10))
    calls = []

    def lm(messages):
        calls.append(messages)
        return next(replies)

    cache = diskcache.Cache(str(tmp_path))
    msgs = [{"role": "user", "content": "make examples"}]
    first = pipeline._ReplayedChat(lm, cache)
    assert [first(msgs), first(msgs)] == ["reply1", "reply2"]  # a repeated call is a fresh sample
    second = pipeline._ReplayedChat(lm, cache)  # another run, e.g. the one with feedback
    assert [second(msgs), second(msgs), second(msgs)] == ["reply1", "reply2", "reply3"]
    assert len(calls) == 3  # the first two were replayed


def test_holdout_split_is_seeded_nested_and_order_free():
    from src.optimizer.task import split_examples

    exs = [Example(inputs={"query": f"q{i}"}, outputs={"response": f"r{i}"}) for i in range(50)]
    tr12, ho38 = split_examples(exs, 0.76, seed=0)
    tr25, ho25 = split_examples(exs, 0.5, seed=0)
    tr38, ho12 = split_examples(exs, 0.24, seed=0)
    assert (len(tr12), len(ho38), len(tr25), len(ho25), len(tr38), len(ho12)) == (12, 38, 25, 25, 38, 12)
    keys = lambda xs: {e.key for e in xs}  # noqa: E731
    assert keys(tr12) <= keys(tr25) <= keys(tr38)  # nested train sets
    assert keys(split_examples(exs[::-1], 0.5, seed=0)[0]) == keys(tr25)  # the input order does not matter
    assert keys(split_examples(exs, 0.5, seed=1)[0]) != keys(tr25)  # the seed does
    assert len(split_examples(exs[:3], 0.99, seed=0)[0]) == 2  # at least two left to train on


def test_holdout_examples_are_scored_and_never_offered_as_demos(monkeypatch):
    _patch(monkeypatch, [("good", 2)])
    held = [Example(inputs={"query": "h0"}, outputs={"response": "H0"})]
    scored_sets = []
    real = judge_mod.evaluate_demos

    def spy(task, demos, scoring, *, instruction=None):
        scored_sets.append([e.inputs["query"] for e in scoring])
        assert all(d.inputs["query"] != "h0" for d in demos)
        return real(task, demos, scoring, instruction=instruction)

    monkeypatch.setattr(judge_mod, "evaluate_demos", spy)
    result = pipeline.run_optimization(
        TASK, GIVEN, generation_lm=None, reflection_lm=None, task_lm=None,
        config=OptimizeConfig(rounds=0, instruction="I0", use_likelihood=False), holdout=held,
    )
    assert scored_sets and all(s == ["h0"] for s in scored_sets)
    assert (result.seed_count, result.holdout_count) == (4, 1)
