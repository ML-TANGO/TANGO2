"""The (Example, Task) contract the optimizer operates on."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


def example_key(inputs: dict[str, Any]) -> str:
    """Identity of an example by its inputs. Images count by their reference, so
    the same question asked about two different images is two examples."""
    flat = {k: (getattr(v, "url", None) or str(v)) for k, v in inputs.items() if v is not None}
    return hashlib.sha1(json.dumps(flat, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


@dataclass
class Example:
    """A single (inputs, outputs) record. Plain dicts so it stays JSON-friendly
    and independent of any LM framework; converted to ``dspy.Example`` only at
    the DSPy boundary (mipro_step / scoring).

    ``origin`` lists the keys of the given examples a synthetic example was
    generated from (empty for a given example). Scoring uses it to keep an
    example and everything derived from it out of its own prompt."""

    inputs: dict[str, str]
    outputs: dict[str, str]
    origin: tuple[str, ...] = field(default=(), compare=False)

    @property
    def key(self) -> str:
        return example_key(self.inputs)

    @property
    def synthetic(self) -> bool:
        return bool(self.origin)

    def to_dict(self) -> dict[str, Any]:
        return {"inputs": dict(self.inputs), "outputs": dict(self.outputs)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Example:
        return cls(inputs=dict(d["inputs"]), outputs=dict(d["outputs"]))


@runtime_checkable
class Task(Protocol):
    """User-supplied task contract.

    DSPy-based on purpose: ``build_dspy_program`` returns a ``dspy.Module`` so
    the *public* ``dspy.teleprompt.MIPROv2`` can compile it directly and the
    same program (with an instruction override) is what we score.
    """

    name: str
    input_keys: tuple[str, ...]
    output_keys: tuple[str, ...]

    def build_dspy_program(self, demos: Sequence[Example]) -> Any:
        """Return a ``dspy.Module`` seeded with ``demos`` as few-shot context."""
        ...

    def metric(self, example: Example, prediction: dict[str, str]) -> float:
        """Score one prediction against gold. Should be in [0, 1] (higher is better)."""
        ...


def split_examples(examples: Sequence[Example], holdout_fraction: float, seed: int = 0) -> tuple[list[Example], list[Example]]:
    """(train, holdout): ``round(holdout_fraction * N)`` examples held out for
    scoring (at least 1, and at least 2 left to train on), the rest kept as demo
    candidates. Which examples are held out is decided by a hash of each
    example and ``seed``, not by their order, so a sorted input still gets a
    random-like split, and the train sets of smaller fractions contain those of
    larger ones (the same seed gives nested splits)."""
    examples = list(examples)
    n_hold = min(max(1, round(holdout_fraction * len(examples))), len(examples) - 2)
    ranked = sorted(examples, key=lambda e: hashlib.sha1(f"{seed}:{e.key}".encode()).hexdigest())
    held = {id(e) for e in ranked[len(examples) - n_hold:]}
    return [e for e in examples if id(e) not in held], [e for e in examples if id(e) in held]
