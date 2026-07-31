"""Synthetic-demo Generator.

Calls an LM with a (generation_prompt, seed examples) prompt and parses the
JSONL synthetic examples it returns.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from typing import Any

from src.optimizer.task import Example

ChatMessage = dict[str, str]
LMFn = Callable[[Sequence[ChatMessage]], str]

DEFAULT_GENERATION_PROMPT = """You generate high-quality synthetic training examples for a downstream task.

You will be shown a few seed examples. Produce {n_new} NEW example(s) that are
correct, realistic, diverse, and COMPLEMENTARY to the seeds — cover cases the
seeds likely miss; do not paraphrase the seeds or repeat each other.

Output EXACTLY {n_new} line(s). Each line is one JSON object on its own line:
{"inputs": {...}, "outputs": {...}}
The "inputs" and "outputs" keys must match the seed examples' schema exactly.
No commentary, no numbering, no markdown fences."""


class Generator:
    """Calls an LM with a (generation_prompt, seed examples) prompt and parses
    JSONL synthetic examples.

    The LM interface matches GEPA's chat callable
    (``Sequence[{role, content}] -> str``), so a ``gepa.lm.LM`` instance,
    OpenAI-style wrapper, or a test closure can be passed directly.
    """

    def __init__(self, lm: LMFn, *, n_per_call: int = 4) -> None:
        self.lm = lm
        self.n_per_call = n_per_call

    def generate(
        self,
        generation_prompt: str,
        seeds: Sequence[Example],
        input_keys: Sequence[str],
        output_keys: Sequence[str],
        *,
        n: int | None = None,
        task_instruction: str | None = None,
    ) -> list[Example]:
        n = n if n is not None else self.n_per_call
        if n <= 0:
            return []
        # Plain string replacement (not str.format) so reflection-mutated
        # prompts are robust to stray ``{...}`` in JSON; only ``{n_new}`` is
        # reserved.
        system = generation_prompt.replace("{n_new}", str(n))
        user = self._format_user_message(seeds, n, task_instruction)
        messages: list[ChatMessage] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        raw = self.lm(messages)
        results = self._parse(raw, input_keys, output_keys)
        if not results:
            preview = raw[:800] if isinstance(raw, str) else repr(raw)[:800]
            print(
                f"[generator debug] _parse() returned 0 demos. "
                f"raw type={type(raw).__name__}, len={len(raw) if isinstance(raw, str) else 'N/A'}; "
                f"first 800 chars:\n{preview!r}"
            )
        return results

    @staticmethod
    def _format_user_message(seeds: Sequence[Example], n: int, task_instruction: str | None) -> str:
        lines = [f"{i}. {json.dumps(ex.to_dict(), ensure_ascii=False)}" for i, ex in enumerate(seeds, 1)]
        seeds_block = "\n".join(lines) if lines else "(no seed examples — invent reasonable ones from scratch)"
        parts = [f"Seed examples:\n{seeds_block}"]
        if task_instruction:
            parts.append(
                "The downstream model is given this exact instruction when solving the task:\n"
                f'"""\n{task_instruction}\n"""\n'
                "Generate examples whose (inputs -> outputs) this instruction should handle well."
            )
        parts.append(f"Now produce {n} new example(s).")
        return "\n\n".join(parts)

    def _parse(
        self,
        raw: str,
        input_keys: Sequence[str],
        output_keys: Sequence[str],
    ) -> list[Example]:
        # Fast path: line-by-line JSONL (the canonical format the seed
        # generation prompt asks for: one JSON object per line, no fences).
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
