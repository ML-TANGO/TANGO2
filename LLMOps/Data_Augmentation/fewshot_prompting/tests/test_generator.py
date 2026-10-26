"""generator.py: prompt assembly, JSONL parsing and synthetic-example origin."""

from __future__ import annotations

import json

from src.optimizer.generator import GENERATION_PROMPT, OUTPUT_FORMAT, Generator
from src.optimizer.task import Example

SEEDS = [
    Example(inputs={"query": "q1", "image": "data:image/png;base64,AAAA"}, outputs={"response": "r1"}),
    Example(inputs={"query": "q2"}, outputs={"response": "r2"}),
]


class FakeLM:
    def __init__(self, reply: str):
        self.reply = reply
        self.messages = None

    def __call__(self, messages):
        self.messages = list(messages)
        return self.reply


def _line(q: str, r: str) -> str:
    return json.dumps({"notes": "n", "inputs": {"query": q}, "outputs": {"response": r}})


def test_generation_prompt_and_seeds_reach_the_lm():
    lm = FakeLM(_line("new", "out"))
    Generator(lm).generate(SEEDS, ("query",), ("response",), n=2, guidance="cover more cases")
    system, user = lm.messages
    assert system["content"] == f"{GENERATION_PROMPT}\n\n{OUTPUT_FORMAT}".replace("{n_new}", "2")
    assert "base64" not in user["content"]  # only the text inputs are shown
    assert '"query": "q1"' in user["content"] and "cover more cases" in user["content"]
    assert user["content"].endswith("Now produce 2 new example(s).")


def test_parsed_examples_record_their_seeds():
    lm = FakeLM("\n".join([_line("n1", "o1"), "noise", _line("n2", "o2"), _line("n3", "o3")]))
    out = Generator(lm).generate(SEEDS, ("query",), ("response",), n=2)
    assert [e.inputs for e in out] == [{"query": "n1"}, {"query": "n2"}]  # capped at n
    assert all(e.origin == (SEEDS[0].key, SEEDS[1].key) and e.synthetic for e in out)


def test_pretty_printed_json_in_markdown_still_parses():
    reply = '**Example**\n```json\n{\n  "notes": "x",\n  "inputs": {"query": "n1"},\n  "outputs": {"response": "o1"}\n}\n```'
    out = Generator(FakeLM(reply)).generate(SEEDS, ("query",), ("response",), n=1)
    assert [(e.inputs, e.outputs) for e in out] == [({"query": "n1"}, {"response": "o1"})]


def test_objects_missing_a_field_are_dropped():
    reply = json.dumps({"inputs": {"q": "x"}, "outputs": {"response": "y"}})
    assert Generator(FakeLM(reply)).generate(SEEDS, ("query",), ("response",), n=1) == []



def test_a_variation_points_at_its_one_real_example_and_must_change_the_inputs():
    from src.optimizer.generator import Generator
    from src.optimizer.task import Example

    seed = Example(inputs={"query": "speed 12.3"}, outputs={"response": "Speed 12.3, overtaking."})
    replies = iter([
        '{"notes": "-", "inputs": {"query": "speed 12.9"}, "outputs": {"response": "Speed 12.9, overtaking."}}',
        '{"notes": "-", "inputs": {"query": "speed 12.3"}, "outputs": {"response": "Speed 12.3, overtaking."}}',
    ])
    seen = []

    def lm(messages):
        seen.append(messages)
        return next(replies)

    gen = Generator(lm)
    out = gen.vary(seed, ("query",), ("response",))
    assert [e.inputs for e in out] == [{"query": "speed 12.9"}] and out[0].origin == (seed.key,)
    assert "keep every conclusion" in seen[0][0]["content"] and "speed 12.3" in seen[0][1]["content"]
    assert gen.vary(seed, ("query",), ("response",)) == []  # an unchanged copy is not a variation
