"""optimizer/scoring.py: holdout predictions run concurrently, stay in holdout
order, and see the caller's ``dspy.context(lm=...)``."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import dspy

from src.optimizer.scoring import score_demos, score_demos_per_example
from src.optimizer.task import Example

HOLDOUT = [Example(inputs={"query": f"q{i}"}, outputs={"response": f"q{i}"}) for i in range(5)]


class EchoTask:
    """The 'program' is a plain callable; the metric is exact match."""

    name = "echo"
    input_keys = ("query",)
    output_keys = ("response",)

    def __init__(self, program):
        self._program = program

    def build_dspy_program(self, demos):
        return self._program

    def metric(self, example, prediction):
        return float(prediction["response"] == example.outputs["response"])


def test_predictions_run_concurrently_and_keep_holdout_order():
    lock = threading.Lock()
    active = {"now": 0, "max": 0}

    def program(query):
        with lock:
            active["now"] += 1
            active["max"] = max(active["max"], active["now"])
        time.sleep(0.15 if query == "q0" else 0.05)  # the first item finishes last
        with lock:
            active["now"] -= 1
        return SimpleNamespace(response=query)

    # a prediction zipped with the wrong holdout item would score 0
    assert score_demos_per_example(EchoTask(program), [], HOLDOUT) == [1.0] * 5
    assert active["max"] > 1


def test_workers_see_the_callers_dspy_lm():
    sentinel = dspy.utils.DummyLM([])
    seen = []

    def program(query):
        seen.append(dspy.settings.lm)
        return SimpleNamespace(response=query)

    with dspy.context(lm=sentinel):
        assert score_demos(EchoTask(program), [], HOLDOUT) == 1.0
    assert len(seen) == 5 and all(lm is sentinel for lm in seen)


def test_a_failing_prediction_scores_zero_without_affecting_the_others():
    def program(query):
        if query == "q2":
            raise RuntimeError("LM error")
        return SimpleNamespace(response=query)

    assert score_demos_per_example(EchoTask(program), [], HOLDOUT) == [1.0, 1.0, 0.0, 1.0, 1.0]


def test_style_rules_are_measured_from_the_responses():
    from src.optimizer.style import style_instructions, style_profile

    examples = [
        Example(inputs={"query": "speed 12.34, course 101.55"}, outputs={"response": "Speed 12.3 knots on course 101.6. All clear."}),
        Example(inputs={"query": "speed 8.10, course 7.25"}, outputs={"response": "Speed 8.1 knots on course 7.3. Keep watch."}),
    ]
    assert style_profile(examples) == {"unit": "words", "size": 8, "sentences": 2, "decimals": 1}
    candidates = style_instructions("Answer.", examples)
    assert candidates["rounding"] == "Answer. Write numbers rounded to 1 decimal place, as the examples do."
    assert set(candidates) == {"length", "rounding", "length+rounding"}
    # a rule already in the instruction is not offered again
    assert "rounding" not in style_instructions(candidates["rounding"], examples)


def test_korean_numbers_next_to_hangul_are_counted():
    from src.optimizer.style import style_profile

    examples = [Example(inputs={"query": "12.34,101.55"}, outputs={"response": "속력 12.3노트, 침로 101.6도로 항해 중이다."})] * 2
    assert style_profile(examples)["decimals"] == 1


def test_style_notes_state_length_and_rounding():
    from src.optimizer.style import style_notes

    examples = [
        Example(inputs={"query": "speed 12.34"}, outputs={"response": "Speed 12.3 knots. Clear."}),
        Example(inputs={"query": "speed 8.10"}, outputs={"response": "Speed 8.1 knots. Fog."}),
    ]
    assert style_notes(examples) == ("The real outputs are about 4 words long (2 sentences) and write numbers rounded to "
                                     "1 decimal place, even where their inputs give more decimals.")
