"""Style profile of the given examples -> extra instruction candidates.

MIPRO's instruction proposer asks the task LM to write instructions; a small
model tends to write long, generic ones that make its answers longer still.
The given responses themselves say how long an answer should be and how numbers
are written, so those conventions are measured directly (no LLM) and offered
to MIPRO as additional instruction candidates; MIPRO's search and the score
gate decide whether any of them is used.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from collections.abc import Sequence

from src.optimizer.task import Example

# ASCII boundaries: in "22.0노트" the number ends where the Hangul begins.
_NUMBER_RE = re.compile(r"(?<![0-9A-Za-z_.])\d+(?:\.(\d+))?(?![0-9A-Za-z_.])")
_SENTENCE_END_RE = re.compile(r"[.!?。](?:\s|$)|(?:다|함|됨|음|임)\.(?:\s|$)")
_HANGUL_RE = re.compile(r"[가-힣]")


def _decimals(text: str) -> list[int]:
    return [len(m.group(1) or "") for m in _NUMBER_RE.finditer(text)]


def style_profile(examples: Sequence[Example], output_key: str = "response") -> dict:
    """Length and number-formatting conventions of the examples' responses."""
    responses = [e.outputs.get(output_key, "") for e in examples]
    queries = " ".join(str(v) for e in examples for v in e.inputs.values() if isinstance(v, str) and len(v) < 20_000)
    korean = 2 * sum(bool(_HANGUL_RE.search(r)) for r in responses) > len(responses)
    sizes = [len(r) if korean else len(r.split()) for r in responses]
    sentences = [max(1, len(_SENTENCE_END_RE.findall(r.strip()))) for r in responses]
    out_dec = Counter(d for r in responses for d in _decimals(r))
    in_dec = Counter(d for d in _decimals(queries) if d > 0)
    profile = {
        "unit": "characters" if korean else "words",
        "size": int(statistics.median(sizes)) if sizes else 0,
        "sentences": int(statistics.median(sentences)) if sentences else 0,
        "decimals": None,
    }
    # Responses round numbers more coarsely than the inputs state them.
    fractional = {d: c for d, c in out_dec.items() if d > 0}
    if fractional and in_dec:
        dominant, count = max(fractional.items(), key=lambda kv: kv[1])
        in_dominant = max(in_dec.items(), key=lambda kv: kv[1])[0]
        if count >= 0.6 * sum(fractional.values()) and in_dominant > dominant:
            profile["decimals"] = dominant
    return profile


def style_instructions(base: str | None, examples: Sequence[Example]) -> dict[str, str]:
    """Instruction candidates: ``base`` plus the measured length and rounding
    conventions (each alone and both together)."""
    p = style_profile(examples)
    base = (base or "").strip()
    length = (
        f"Keep each response about {p['size']} {p['unit']} long ({p['sentences']} sentence"
        f"{'s' if p['sentences'] != 1 else ''}), like the examples; do not add content the examples do not have."
        if p["size"] else ""
    )
    rounding = (
        f"Write numbers rounded to {p['decimals']} decimal place{'s' if p['decimals'] != 1 else ''}, as the examples do."
        if p["decimals"] else ""
    )
    length = "" if length and length in base else length  # already part of the instruction
    rounding = "" if rounding and rounding in base else rounding
    out = {}
    if length:
        out["length"] = f"{base} {length}".strip()
    if rounding:
        out["rounding"] = f"{base} {rounding}".strip()
    if length and rounding:
        out["length+rounding"] = f"{base} {length} {rounding}".strip()
    return out


def style_notes(examples: Sequence[Example]) -> str:
    """The measured conventions as one plain sentence (for the feedback critic)."""
    p = style_profile(examples)
    parts = []
    if p["size"]:
        parts.append(f"are about {p['size']} {p['unit']} long ({p['sentences']} sentence{'s' if p['sentences'] != 1 else ''})")
    if p["decimals"]:
        parts.append(f"write numbers rounded to {p['decimals']} decimal place{'s' if p['decimals'] != 1 else ''}, "
                     "even where their inputs give more decimals")
    return ("The real outputs " + " and ".join(parts) + ".") if parts else ""
