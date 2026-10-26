"""Synthetic-demo Generator.

Calls an LM with real examples of the task and parses the JSONL synthetic
examples it returns. Each synthetic example records which real examples it was
generated from (``Example.origin``), so scoring can keep it out of those
examples' own prompts.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from typing import Any

from src.optimizer.task import Example

ChatMessage = dict[str, str]
LMFn = Callable[[Sequence[ChatMessage]], str]

GENERATION_PROMPT = """You write new examples for a task, given real examples of it. A new example must be indistinguishable from the real ones:

- inputs: exactly the same format and fields as the real inputs, realistic values in the same ranges, but a different situation from every real example (do not copy an input).
- outputs: the correct output for YOUR inputs, written the way the real outputs are written: same structure and sentence order, similar length, the same wording habits, the same number formatting (rounding) and the same level of detail. Every value or category an output states about its input must be right for your inputs. Details the real outputs add beyond their inputs may be invented in the same style.

Work in a "notes" field first: list the facts of your inputs that the output must state, and derive anything the output concludes from them. Then write the output."""

VARIATION_PROMPT = """You write a new training example for a task by varying a real one. The new example must keep every conclusion of the real output true:

- inputs: exactly the same format and fields as the real inputs. Change the values a little — identifiers, times, sizes, and small changes to the other numbers — so that it stays the same kind of situation and every conclusion the real output states still holds for the new inputs. Do not copy the real inputs unchanged.
- outputs: the output for the NEW inputs, written the way the real output is written: same structure and sentence order, the same wording habits, the same number formatting and level of detail. Keep its conclusions, update every value it takes from the inputs, and details that do not depend on the inputs may be varied in the same style.

Work in a "notes" field first: list the values you changed and check that each conclusion of the real output still holds for them. Then write the example."""

# Appended after the generation prompt; ``_parse`` depends on it.
OUTPUT_FORMAT = """Output EXACTLY {n_new} line(s). Each line is one JSON object on its own line:
{"notes": "...", "inputs": {...}, "outputs": {...}}
The "inputs" and "outputs" keys must match the real examples' schema exactly.
No commentary, no numbering, no markdown fences."""


class Generator:
    """Calls an LM with a (generation prompt, real examples) prompt and parses
    JSONL synthetic examples.

    The LM interface is a chat callable (``Sequence[{role, content}] -> str``),
    so an OpenAI-style wrapper or a test closure can be passed directly.
    """

    def __init__(self, lm: LMFn, *, n_per_call: int = 3) -> None:
        self.lm = lm
        self.n_per_call = n_per_call

    def generate(
        self,
        seeds: Sequence[Example],
        input_keys: Sequence[str],
        output_keys: Sequence[str],
        *,
        n: int | None = None,
        guidance: str | None = None,
    ) -> list[Example]:
        """New examples in the style of ``seeds`` (only ``input_keys`` /
        ``output_keys`` are shown and parsed). ``guidance`` is extra direction
        for this call, e.g. what earlier synthetic examples got wrong."""
        n = n if n is not None else self.n_per_call
        if n <= 0:
            return []
        system = f"{GENERATION_PROMPT}\n\n{OUTPUT_FORMAT}".replace("{n_new}", str(n))
        messages: list[ChatMessage] = [
            {"role": "system", "content": system},
            {"role": "user", "content": self._format_user_message(seeds, input_keys, output_keys, n, guidance)},
        ]
        raw = self.lm(messages)
        results = self._parse(raw, input_keys, output_keys)[:n]
        if not results:
            preview = raw[:800] if isinstance(raw, str) else repr(raw)[:800]
            print(f"[generator] parsed 0 examples; first 800 chars of the reply:\n{preview!r}")
        origin = tuple(s.key for s in seeds)
        return [Example(inputs=r.inputs, outputs=r.outputs, origin=origin) for r in results]

    def vary(
        self,
        seed: Example,
        input_keys: Sequence[str],
        output_keys: Sequence[str],
        *,
        n: int = 1,
    ) -> list[Example]:
        """``n`` variations of one real example that keep its conclusions true
        (its decisive inputs barely change, so its labels stay right). Each
        records that one example as its origin."""
        if n <= 0:
            return []
        system = f"{VARIATION_PROMPT}\n\n{OUTPUT_FORMAT}".replace("{n_new}", str(n))
        shown = {"inputs": {k: seed.inputs[k] for k in input_keys if k in seed.inputs},
                 "outputs": {k: seed.outputs[k] for k in output_keys if k in seed.outputs}}
        user = f"Real example:\n{json.dumps(shown, ensure_ascii=False)}\n\nNow produce {n} variation(s)."
        raw = self.lm([{"role": "system", "content": system}, {"role": "user", "content": user}])
        results = [r for r in self._parse(raw, input_keys, output_keys)[:n] if r.inputs != shown["inputs"]]
        if not results:
            preview = raw[:400] if isinstance(raw, str) else repr(raw)[:400]
            print(f"[generator] no usable variation; first 400 chars of the reply:\n{preview!r}")
        return [Example(inputs=r.inputs, outputs=r.outputs, origin=(seed.key,)) for r in results]

    @staticmethod
    def _format_user_message(
        seeds: Sequence[Example],
        input_keys: Sequence[str],
        output_keys: Sequence[str],
        n: int,
        guidance: str | None,
    ) -> str:
        lines = []
        for i, ex in enumerate(seeds, 1):
            shown = {
                "inputs": {k: ex.inputs[k] for k in input_keys if k in ex.inputs},
                "outputs": {k: ex.outputs[k] for k in output_keys if k in ex.outputs},
            }
            lines.append(f"{i}. {json.dumps(shown, ensure_ascii=False)}")
        parts = ["Real examples:\n" + ("\n".join(lines) if lines else "(none)")]
        if guidance:
            parts.append(f"Guidance for this batch:\n{guidance}")
        parts.append(f"Now produce {n} new example(s).")
        return "\n\n".join(parts)

    def _parse(
        self,
        raw: str,
        input_keys: Sequence[str],
        output_keys: Sequence[str],
    ) -> list[Example]:
        # Fast path: line-by-line JSONL (the format the prompt asks for).
        results: list[Example] = []
        for line in raw.splitlines():
            line = re.sub(r"^\s*\d+[\.\)]\s*", "", line).strip()
            line = line.strip("` ")
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            ex = self._coerce(obj, input_keys, output_keys)
            if ex is not None:
                results.append(ex)
        if results:
            return results
        # Fallback: scan the raw text for balanced {...} blocks. Triggered
        # when the LM emits multi-line pretty-printed JSON wrapped in
        # markdown ("**Example 7:**\n```json\n{...}\n```"), which the
        # line-based path can't reassemble.
        for blob in self._extract_json_objects(raw):
            try:
                obj = json.loads(blob)
            except json.JSONDecodeError:
                continue
            ex = self._coerce(obj, input_keys, output_keys)
            if ex is not None:
                results.append(ex)
        return results

    @staticmethod
    def _extract_json_objects(text: str) -> list[str]:
        """Return all balanced ``{...}`` substrings of ``text``, ignoring
        braces inside string literals. Top-level objects only — nested
        ``{}`` inside a larger object are part of their parent's span."""
        out: list[str] = []
        depth = 0
        start = -1
        in_string = False
        escape = False
        for i, ch in enumerate(text):
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                if depth == 0:
                    continue
                depth -= 1
                if depth == 0 and start != -1:
                    out.append(text[start : i + 1])
                    start = -1
        return out

    @staticmethod
    def _coerce(
        obj: Any,
        input_keys: Sequence[str],
        output_keys: Sequence[str],
    ) -> Example | None:
        if not isinstance(obj, dict):
            return None
        inputs = obj.get("inputs")
        outputs = obj.get("outputs")
        if not isinstance(inputs, dict) or not isinstance(outputs, dict):
            return None
        if not all(k in inputs for k in input_keys):
            return None
        if not all(k in outputs for k in output_keys):
            return None
        return Example(
            inputs={k: str(inputs[k]) for k in input_keys},
            outputs={k: str(outputs[k]) for k in output_keys},
        )
