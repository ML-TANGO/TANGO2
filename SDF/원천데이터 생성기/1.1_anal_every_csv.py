#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional, Tuple


def parse_ts(value: str) -> datetime:
    """
    Parse timestamps like:
      '2026-02-11 00:00:02.903000+00:00'
    Also supports ISO strings with 'T' separator.
    """
    s = (value or "").strip()
    if not s:
        raise ValueError("empty ts")
    # Python's fromisoformat supports both ' ' and 'T' separators and timezone offsets.
    return datetime.fromisoformat(s)


def round_seconds(x: float) -> int:
    """
    Round to nearest integer second.
    Half goes away from zero (consistent for +/-).
    """
    if x >= 0:
        return int(math.floor(x + 0.5))
    return int(math.ceil(x - 0.5))


def iter_ts_deltas_rounded_seconds(csv_path: Path, *, ts_col: str = "ts") -> Iterator[int]:
    """
    Stream a CSV file, compute consecutive ts differences, yield rounded seconds.
    """
    prev_ts: Optional[datetime] = None
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or ts_col not in reader.fieldnames:
            raise ValueError(f"missing '{ts_col}' column (have: {reader.fieldnames})")

        for row in reader:
            cur_raw = row.get(ts_col, "")
            cur_ts = parse_ts(cur_raw)
            if prev_ts is not None:
                delta = (cur_ts - prev_ts).total_seconds()
                yield round_seconds(delta)
            prev_ts = cur_ts


@dataclass
class FileResult:
    src: Path
    out_counts_csv: Path
    out_counts_txt: Path
    out_plot_png: Path
    rows: int
    unique_seconds: int


def save_counts_csv(counts: Counter[int], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["delta_seconds_rounded", "count"])
        for sec in sorted(counts.keys()):
            w.writerow([sec, counts[sec]])


def save_counts_txt(counts: Counter[int], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for sec in sorted(counts.keys()):
            f.write(f"{sec}\t{counts[sec]}\n")


def save_plot_png(
    counts: Counter[int],
    out_path: Path,
    *,
    title: str,
    max_bars: int = 400,
) -> None:
    """
    Save a bar plot: x=seconds, y=count.
    If there are too many distinct seconds, it plots the most frequent ones.
    """
    try:
        import matplotlib as mpl
        import matplotlib.pyplot as plt
    except Exception as e: 
        raise RuntimeError(
            "matplotlib이 필요합니다. 설치: pip install matplotlib"
        ) from e

    out_path.parent.mkdir(parents=True, exist_ok=True)


    mpl.rcParams["font.family"] = ["AppleGothic", "Malgun Gothic", "DejaVu Sans"]
    mpl.rcParams["axes.unicode_minus"] = False

    items = list(counts.items())
    if not items:
        xs, ys = [], []
        subtitle = "no deltas (rows < 2)"
    else:
        if len(items) > max_bars:
            items = sorted(items, key=lambda kv: (-kv[1], kv[0]))[:max_bars]
            items = sorted(items, key=lambda kv: kv[0])
            subtitle = f"top {max_bars} by frequency"
        else:
            items = sorted(items, key=lambda kv: kv[0])
            subtitle = f"unique seconds: {len(items)}"

        xs = [k for k, _ in items]
        ys = [v for _, v in items]

    width = max(10.0, min(24.0, 0.06 * max(1, len(xs))))
    fig_h = 6.0
    plt.figure(figsize=(width, fig_h), dpi=140)
    # Treat x as categorical to avoid showing "missing" seconds gaps.
    pos = list(range(len(xs)))
    plt.bar(pos, ys, width=0.9, color="#2E6F9E")
    plt.title(f"{title}\n{subtitle}")
    plt.xlabel("ts 차이 (초, 반올림)")
    plt.ylabel("행 개수")

    # If one bin dominates heavily, use log-scale so smaller bins are visible too.
    if ys:
        ymax = max(ys)
        ymin_nonzero = min((v for v in ys if v > 0), default=0)
        if ymin_nonzero > 0 and (ymax / ymin_nonzero) >= 200:
            plt.yscale("log")
            plt.ylabel("행 개수 (log)")

    if xs:
        # Show only existing seconds as tick labels (no missing values).
        if len(xs) <= 40:
            tick_pos = pos
            tick_labels = [str(x) for x in xs]
        else:
            step = max(1, len(xs) // 25)
            tick_pos = pos[::step]
            tick_labels = [str(x) for x in xs[::step]]

        plt.xticks(tick_pos, tick_labels, rotation=0)

    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def analyze_one_csv(
    src_csv: Path,
    out_root: Path,
    *,
    src_root: Path,
    ts_col: str = "ts",
    max_bars: int = 400,
) -> FileResult:
    rel = src_csv.relative_to(src_root)
    out_counts = (out_root / rel).with_suffix(".ts_delta_counts.csv")
    out_txt = (out_root / rel).with_suffix(".ts_delta_counts.txt")
    out_plot = (out_root / rel).with_suffix(".ts_delta_counts.png")

    counts: Counter[int] = Counter()
    rows = 0
    for d in iter_ts_deltas_rounded_seconds(src_csv, ts_col=ts_col):
        counts[d] += 1
        rows += 1

    save_counts_csv(counts, out_counts)
    save_counts_txt(counts, out_txt)
    save_plot_png(counts, out_plot, title=str(rel), max_bars=max_bars)

    return FileResult(
        src=src_csv,
        out_counts_csv=out_counts,
        out_counts_txt=out_txt,
        out_plot_png=out_plot,
        rows=rows,
        unique_seconds=len(counts),
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "For every CSV under csv_data/, compute consecutive ts deltas, "
            "round to seconds, and visualize counts per second."
        )
    )
    ap.add_argument("--src-root", default="1_csv_data_deleted_error_data", help="CSV root directory (default: 1_csv_data_deleted_error_data)")
    ap.add_argument(
        "--out-root",
        default="1.1_csv_data_deleted_error_data_anal/ts_delta_hist",
        help="Output root for plots/counts (default: 1.1_csv_data_deleted_error_data_anal/ts_delta_hist)",
    )
    ap.add_argument("--glob", default="*.csv", help="CSV glob to include (default: *.csv)")
    ap.add_argument("--ts-col", default="ts", help="Timestamp column name (default: ts)")
    ap.add_argument(
        "--max-bars",
        type=int,
        default=400,
        help="Max distinct-second bars to plot (default: 400)",
    )
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing outputs")
    args = ap.parse_args()

    src_root = Path(args.src_root)
    out_root = Path(args.out_root)

    if not src_root.exists() or not src_root.is_dir():
        raise SystemExit(f"src-root not found or not a directory: {src_root}")

    csv_files = sorted(src_root.rglob(args.glob))
    if not csv_files:
        print(f"No files matched {args.glob} under {src_root}")
        return 0

    ok = 0
    skipped = 0
    fail = 0

    for i, src_csv in enumerate(csv_files, start=1):
        rel = src_csv.relative_to(src_root)
        out_counts = (out_root / rel).with_suffix(".ts_delta_counts.csv")
        out_txt = (out_root / rel).with_suffix(".ts_delta_counts.txt")
        out_plot = (out_root / rel).with_suffix(".ts_delta_counts.png")

        if (
            not args.overwrite
            and out_counts.exists()
            and out_txt.exists()
            and out_plot.exists()
        ):
            skipped += 1
            continue

        try:
            res = analyze_one_csv(
                src_csv,
                out_root,
                src_root=src_root,
                ts_col=args.ts_col,
                max_bars=args.max_bars,
            )
            ok += 1
            if ok <= 3 or ok % 50 == 0:
                print(
                    f"[{i}/{len(csv_files)}] OK {rel} "
                    f"(deltas={res.rows}, unique_seconds={res.unique_seconds})"
                )
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(csv_files)}] FAIL {rel}: {e}")

    print(f"Done. ok={ok}, skipped={skipped}, fail={fail}, out_root={out_root}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

