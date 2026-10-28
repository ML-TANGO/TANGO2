"""Write coarse runner timing after measurement; never part of the outage KPI."""

import json
import sys
from decimal import Decimal
from pathlib import Path


def write_timing(path, event_id, clock, exit_code, marks):
    points = [mark.split("=", 1) for mark in marks]
    started = previous = Decimal(points[0][1])
    phases = []
    for name, value in points[1:]:
        current = Decimal(value)
        if not current.is_finite() or current < previous:
            raise ValueError("runner clock must be finite and nondecreasing")
        phases.append(
            {"name": name, "elapsed_seconds": float(current - previous)}
        )
        previous = current
    result = {
        "event_id": event_id,
        "clock": clock,
        "exit_code": int(exit_code),
        "elapsed_seconds": float(previous - started),
        "phases": phases,
    }
    Path(path).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_timing(*sys.argv[1:5], sys.argv[5:])
