#!/usr/bin/env python3
"""Run the weekly motor/weather analysis from the C notebook as a script."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_PATH = PROJECT_ROOT / "data_inspect" / "notebook" / "data_inspect_260211-260511_C.ipynb"
OUTPUT_ROOT = PROJECT_ROOT / "data_inspect" / "output" / "weekly_motor_weather_analysis_260211-260511"


def _cell_source(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else str(source)


def _should_skip_source(source: str) -> bool:
    stripped = source.strip()
    return stripped.startswith("week_result = analyze_week(") or stripped.startswith("try:\n    import ipywidgets")


def load_notebook_namespace() -> dict:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    namespace: dict = {"__name__": "__weekly_motor_weather_script__"}
    for cell in notebook["cells"]:
        if cell.get("cell_type") != "code":
            continue
        source = _cell_source(cell)
        if _should_skip_source(source):
            continue
        exec(compile(source, str(NOTEBOOK_PATH), "exec"), namespace)

    namespace["display"] = lambda *args, **kwargs: None
    namespace["clear_output"] = lambda *args, **kwargs: None
    namespace["plt"].show = lambda *args, **kwargs: plt.close("all")
    return namespace


def parse_week_indices(raw: str, available_count: int) -> list[int]:
    if raw == "all":
        return list(range(available_count))
    indices: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = [int(value.strip()) for value in part.split("-", 1)]
            indices.extend(range(start, end + 1))
        else:
            indices.append(int(part))
    invalid = [index for index in indices if index < 0 or index >= available_count]
    if invalid:
        raise ValueError(f"Invalid week indices {invalid}; allowed range is 0~{available_count - 1}")
    return sorted(dict.fromkeys(indices))


def collect_and_save_summary(results: Iterable[dict]) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    correlations = []
    daily = []
    for result in results:
        week_index = result["week_index"]
        if not result["correlation"].empty:
            frame = result["correlation"].copy()
            frame.insert(0, "week_index", week_index)
            correlations.append(frame)
        if not result["daily_summary"].empty:
            frame = result["daily_summary"].copy()
            frame.insert(0, "week_index", week_index)
            daily.append(frame)

    if correlations:
        pd.concat(correlations, ignore_index=True).to_csv(OUTPUT_ROOT / "all_week_correlations.csv", index=False, encoding="utf-8-sig")
    if daily:
        pd.concat(daily, ignore_index=True).to_csv(OUTPUT_ROOT / "all_week_daily_summary.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate C-notebook weekly motor/weather outputs.")
    parser.add_argument("--weeks", default="all", help="Week indices to run: all, 0, 0,1,2, or 0-12")
    args = parser.parse_args()

    namespace = load_notebook_namespace()
    week_table = namespace["week_table"]
    analyze_week = namespace["analyze_week"]
    indices = parse_week_indices(args.weeks, len(week_table))

    results = []
    for index in indices:
        print(f"[weather] analyze week {index}")
        results.append(analyze_week(week_index=index, save_outputs=True))
    collect_and_save_summary(results)
    print(f"[weather] completed {len(results)} week(s). output={OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
