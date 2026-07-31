"""The (Example, Task) contract the optimizer operates on."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class Example:
    """A single (inputs, outputs) record. Plain dicts so it stays JSON-friendly
    and independent of any LM framework; converted to ``dspy.Example`` only at
    the DSPy boundary (mipro_step / scoring)."""

    inputs: dict[str, str]
    outputs: dict[str, str]

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
    same program (with an instruction override) is what we score on holdout.
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
