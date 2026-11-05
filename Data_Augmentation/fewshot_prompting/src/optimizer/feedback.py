"""Textual feedback on synthetic demos.

Feedback goes straight to the generated data (instance-level refinement, as in
Self-Refine and TextGrad's instance optimization). Two forms:

``refine_by_likelihood`` (used when the server scores references): the loss of
a synthetic example is how improbable its output is to the task model primed
with the current prompt (the real examples): the words it finds improbable are
the textual gradient, a reviser rewrites exactly those the way the real outputs
write such things, and the rewrite is kept only if the task model then finds
the output more probable (without having dropped content). On held-out scenes
this raised the value of synthetic batches in Korean (+0.011 token-F1 over the
same batches unrevised, 5 of 6 batches) and left English unchanged (−0.003 ±
0.004 SPICE); the critique below did not help in either. Rewording only the
flagged words, or judging without the seeds, did no better.

``refine`` (critique, then revise): a critic compares each synthetic example
with the real examples it was generated from and lists concrete problems, and
a reviser rewrites the example to fix exactly those.

Either way the gate then decides on the revised examples as usual.

The critic checks only what it can check reliably by comparison — how the
output is written next to the real outputs (structure, length, wording, number
format) and whether the values it copies from its own inputs match them. It
does not judge the output's conclusions: a small model "correcting" those
replaces right conclusions with wrong ones as often as the reverse. The
conventions measured from the real outputs (length, number rounding — see
``style.py``) are stated to both critic and reviser; without them the reviser
"fixes" rounded values back into the inputs' full precision.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from src.optimizer.generator import Generator
from src.optimizer.scoring import build_program, program_inputs
from src.optimizer.task import Example, Task

_CRITIC_PROMPT = """You check a synthetic training example for a task against real examples of the same task.

Real examples:
{real}

{conventions}
Check only these two things in the synthetic example the user gives you:
1. Writing: its output must be written the way the real outputs are written — the same structure and sentence order, a similar length, the same wording habits and number formatting. Point out phrases or sentences that the real outputs would not use, and parts of the real outputs' structure that are missing.
2. Values: every value its output takes from its own inputs must match them once rounded the way the real outputs round. A correctly rounded value is not a problem; never ask for more decimals than the real outputs use.
Do not judge the output's conclusions or categories.

Reply with a short numbered list of the problems you found, each quoting the synthetic example and saying what it should be. If there are none, reply exactly: NO PROBLEMS"""

_REVISE_PROMPT = """You fix a synthetic training example for a task.

Real examples:
{real}

Problems found in the synthetic example the user gives you:
{critique}

{conventions}
Rewrite the synthetic example's output so that every listed problem is fixed, reusing the real outputs' wording wherever it fits and writing numbers with the real outputs' rounding. Keep its conclusions and every fact that follows from its inputs, and keep its inputs unchanged. Reply with exactly one JSON object on one line: {{"inputs": {{...}}, "outputs": {{...}}}}, with the same field names. No commentary."""

_REALISM_PROMPT = """You revise a synthetic training example for a task so that it reads like the real examples.

Real examples:
{real}

{conventions}
Measured against the real examples, these parts of the synthetic example's output are improbable — the real outputs would rarely write them this way:
{spans}

Rewrite each of these parts the way the real outputs write such things (their wording, sentence structure and number format), so that the output reads like one more real example. Keep every fact the output takes from its own inputs, keep its conclusions, keep its inputs unchanged, and change nothing else. Reply with exactly one JSON object on one line: {{"inputs": {{...}}, "outputs": {{...}}}}, with the same field names. No commentary."""

NO_PROBLEMS = "NO PROBLEMS"


def chat(lm: Any, messages: list[dict[str, str]], **kwargs: Any) -> str:
    """One chat completion from a ``dspy.LM`` (kwargs override its settings)
    or from a plain ``messages -> str`` callable."""
    if hasattr(lm, "kwargs") and hasattr(lm, "model"):  # dspy.LM
        out = lm(messages=messages, **kwargs)
        return str(out[0]) if out else ""
    return lm(messages)


def _shown(ex: Example, input_keys: Sequence[str], output_keys: Sequence[str]) -> str:
    return json.dumps(
        {"inputs": {k: ex.inputs[k] for k in input_keys if k in ex.inputs},
         "outputs": {k: ex.outputs[k] for k in output_keys if k in ex.outputs}},
        ensure_ascii=False,
    )


def refine(
    task: Task,
    batch: Sequence[Example],
    seeds: Sequence[Example],
    *,
    reflection_lm: Any,
    conventions: str = "",
) -> list[Example]:
    """Critique every example of ``batch`` against ``seeds`` (the real examples
    it was generated from) and rewrite the ones with problems. ``conventions``
    states the measured length / rounding conventions of the real outputs. An
    example whose rewrite cannot be parsed is kept as generated."""
    input_keys = getattr(task, "text_input_keys", task.input_keys)
    output_keys = task.output_keys
    real = "\n".join(_shown(s, input_keys, output_keys) for s in seeds)
    parser = Generator(lambda _: "")

    def one(ex: Example) -> Example:
        shown = _shown(ex, input_keys, output_keys)
        try:
            critique = chat(
                reflection_lm,
                [{"role": "system", "content": _CRITIC_PROMPT.format(real=real, conventions=conventions)},
                 {"role": "user", "content": shown}],
                temperature=0.0, max_tokens=700,
            ).strip()
            if not critique or NO_PROBLEMS in critique.upper():
                return ex
            revised = chat(
                reflection_lm,
                [{"role": "system", "content": _REVISE_PROMPT.format(real=real, critique=critique, conventions=conventions)},
                 {"role": "user", "content": shown}],
                temperature=0.0, max_tokens=1200,
            )
        except Exception as e:  # noqa: BLE001 — keep the example as generated
            print(f"[feedback] refine failed: {type(e).__name__}: {e}")
            return ex
        parsed = parser._parse(revised, input_keys, output_keys)
        if not parsed:
            print(f"[feedback] unparseable revision, keeping the original: {revised[:200]!r}")
            return ex
        # Only the output is revised; the example keeps its own inputs.
        fixed = Example(inputs=dict(ex.inputs), outputs=parsed[0].outputs, origin=ex.origin)
        print("[feedback] trace " + json.dumps(
            {"before": ex.to_dict(), "critique": critique, "after": fixed.to_dict()}, ensure_ascii=False))
        return fixed

    with ThreadPoolExecutor(max_workers=max(1, len(batch))) as pool:
        return list(pool.map(one, batch))


def improbable_spans(
    tokens: Sequence[tuple[str, float]], *, threshold: float = -3.0, max_spans: int = 5
) -> list[str]:
    """The parts of a reply the model found improbable. A word's log-probability
    is the sum over its tokens; words below ``threshold`` are flagged, adjacent
    flagged words form one span, and the ``max_spans`` most improbable spans are
    returned in reply order."""
    words: list[list] = []  # [text, logprob]
    for text, lp in tokens:
        if not words or text[:1].isspace():
            words.append([text, lp])
        else:
            words[-1][0] += text
            words[-1][1] += lp
    spans: list[list] = []  # [text, logprob, position]
    flagged_before = False
    for i, (text, lp) in enumerate(words):
        flagged = lp < threshold and bool(text.strip())
        if flagged and flagged_before:
            spans[-1][0] += text
            spans[-1][1] += lp
        elif flagged:
            spans.append([text, lp, i])
        flagged_before = flagged
    worst = sorted(spans, key=lambda sp: sp[1])[:max_spans]
    return [sp[0].strip() for sp in sorted(worst, key=lambda sp: sp[2])]


def refine_by_likelihood(
    task: Task,
    batch: Sequence[Example],
    seeds: Sequence[Example],
    *,
    scorer: Any,
    instruction: str | None,
    demos: Sequence[Example],
    reflection_lm: Any,
    conventions: str = "",
    threshold: float = -3.0,
) -> list[Example]:
    """Rewrite the improbable parts of each example of ``batch``. Improbable =
    under the prompt (``instruction``, ``demos``) the gate scores with, by the
    task model (``scorer``, a ``likelihood.ReferenceScorer``); ``seeds`` are the
    real examples shown to the reviser. A rewrite is kept only if its output is
    more probable per token and its length is still like the real outputs'
    (70-130% of their median, or closer to it than before) — so dropping
    content cannot pass for an improvement."""
    input_keys = getattr(task, "text_input_keys", task.input_keys)
    output_keys = task.output_keys
    out_key = output_keys[0]
    real = "\n".join(_shown(s, input_keys, output_keys) for s in seeds)
    parser = Generator(lambda _: "")
    prog = build_program(task, list(demos), instruction)
    lengths = sorted(len(s.outputs.get(out_key, "")) for s in seeds)
    median = lengths[len(lengths) // 2] if lengths else 0

    def one(ex: Example) -> Example:
        try:
            messages = prog.messages(**program_inputs(task, ex))
            toks = scorer.tokens(messages, ex.outputs[out_key])
            text_toks = toks[:-1] if scorer.n_after() else toks  # not the end-of-turn marker
            spans = improbable_spans(text_toks, threshold=threshold)
            if not spans:
                return ex
            revised = chat(
                reflection_lm,
                [{"role": "system", "content": _REALISM_PROMPT.format(
                    real=real, conventions=conventions, spans="\n".join(f"- \"{sp}\"" for sp in spans))},
                 {"role": "user", "content": _shown(ex, input_keys, output_keys)}],
                temperature=0.0, max_tokens=1200,
            )
            parsed = parser._parse(revised, input_keys, output_keys)
            if not parsed:
                print(f"[feedback] unparseable revision, keeping the original: {revised[:200]!r}")
                return ex
            fixed = Example(inputs=dict(ex.inputs), outputs=parsed[0].outputs, origin=ex.origin)
            before = sum(lp for _, lp in toks) / len(toks)
            after = scorer.mean_logprob(messages, fixed.outputs[out_key])
        except Exception as e:  # noqa: BLE001 — keep the example as generated
            print(f"[feedback] refine failed: {type(e).__name__}: {e}")
            return ex
        n_old, n_new = len(ex.outputs[out_key]), len(fixed.outputs[out_key])
        length_ok = 0.7 * median <= n_new <= 1.3 * median or abs(n_new - median) < abs(n_old - median)
        keep = after > before and length_ok
        print("[feedback] trace " + json.dumps(
            {"before": ex.to_dict(), "spans": spans, "after": fixed.to_dict(), "llh": [round(before, 4), round(after, 4)],
             "kept": keep}, ensure_ascii=False))
        return fixed if keep else ex

    with ThreadPoolExecutor(max_workers=max(1, len(batch))) as pool:
        return list(pool.map(one, batch))
