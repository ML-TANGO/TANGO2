"""Few-shot prompt optimizer.

Given a ``Task`` (a query->response program + a holdout metric), a few seed
examples, and a holdout set, ``run_optimization`` produces a curated
instruction + few-shot demo set that maximizes the holdout score. It combines
DSPy's MIPROv2 (instruction + demo selection) with a textual-gradient harvest
loop that grows the demo pool with synthetic examples.

Modules:
  task.py       — Example / Task contract
  generator.py  — synthetic-demo Generator (JSONL parsing)
  scoring.py    — score_demos (the holdout-scoring primitive)
  mipro_step.py — run_mipro (MIPROv2 instruction + demo selection)
  harvest.py    — the textual-gradient harvest loop
  pipeline.py   — pre-pass MIPRO -> harvest -> selection MIPRO
"""

from __future__ import annotations

from src.optimizer.pipeline import OptimizeConfig, OptimizeResult, run_optimization
from src.optimizer.task import Example, Task

__all__ = [
    "Example",
    "OptimizeConfig",
    "OptimizeResult",
    "Task",
    "run_optimization",
]
