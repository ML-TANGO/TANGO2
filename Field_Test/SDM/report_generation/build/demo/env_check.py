#!/usr/bin/env python3
"""Step 2 — show the container's environment: GPUs visible, driver, torch / CUDA.

    python3 /app/demo/env_check.py

Exit 0 when exactly one GPU is visible and CUDA is usable.
"""
from __future__ import annotations

import subprocess
import sys

import torch

import ui

EXPECT_GPUS = 1


def main() -> int:
    ui.step("2", "Container environment", "only one GPU is exposed to the container")
    smi = subprocess.run(["nvidia-smi", "--query-gpu=index,name,driver_version,memory.total",
                          "--format=csv,noheader"], capture_output=True, text=True)
    gpus = [l.strip() for l in smi.stdout.splitlines() if l.strip()]
    rows = [(f"GPU {g.split(',')[0]}", ", ".join(p.strip() for p in g.split(",")[1:])) for g in gpus]
    rows += [("torch", torch.__version__), ("CUDA available", torch.cuda.is_available()),
             ("torch device count", torch.cuda.device_count())]
    ui.console.print(ui.kv_table(rows))
    results = [
        ui.check(smi.returncode == 0, "nvidia-smi runs inside the container"),
        ui.check(len(gpus) == EXPECT_GPUS, f"{len(gpus)} GPU visible (expected {EXPECT_GPUS})"),
        ui.check(torch.cuda.is_available() and torch.cuda.device_count() == EXPECT_GPUS,
                 "torch sees the GPU"),
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
