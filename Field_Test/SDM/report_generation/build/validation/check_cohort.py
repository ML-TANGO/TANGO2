#!/usr/bin/env python3
"""Pre-flight a cohort directory: is it complete, and will the joins actually land?

    python check_cohort.py --data_root /data

Run this before `preprocess`. Every problem it reports is one that otherwise surfaces
late and quietly: a renamed id column makes the scorer drop every case, a mask naming
change makes preprocessing skip every case, and a partly-copied cohort produces a real
but unrepresentative F1 with no error anywhere.

Exit codes: 0 ready, 1 usable but incomplete, 2 unusable.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Set

NIFTI_SUFFIXES = (".nii.gz", ".nii")
TRUE = {"1", "1.0", "True", "true", "yes"}
FALSE = {"0", "0.0", "False", "false", "no"}


def strip_nifti(name: str) -> str:
    for suffix in NIFTI_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def index(directory: Path, strip_suffix: str = "") -> Set[str]:
    ids = set()
    if not directory.is_dir():
        return ids
    for path in directory.rglob("*"):
        if not path.is_file() or not path.name.endswith(NIFTI_SUFFIXES):
            continue
        case_id = strip_nifti(path.name)
        if strip_suffix and case_id.endswith(strip_suffix):
            case_id = case_id[: -len(strip_suffix)]
        ids.add(case_id)
    return ids


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data_root", default="/data")
    ap.add_argument("--ct_dirname", default="nii")
    ap.add_argument("--totalseg_dirname", default="totalseg")
    ap.add_argument("--seg_suffix", default="_totalseg")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--id_col", default="object_id")
    ap.add_argument("--label_col", default="nodule_label")
    args = ap.parse_args()

    root = Path(args.data_root)
    problems: List[str] = []
    warnings: List[str] = []

    csv_path = Path(args.csv) if args.csv else None
    if csv_path is None:
        found = sorted(root.glob("*.csv"))
        if not found:
            print(f"[FAIL] no CSV in {root}")
            return 2
        if len(found) > 1:
            print(f"[FAIL] several CSVs in {root}, pass --csv: {[p.name for p in found]}")
            return 2
        csv_path = found[0]

    with open(csv_path, newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        print(f"[FAIL] {csv_path.name} has no rows")
        return 2
    columns = list(rows[0])
    print(f"cohort CSV     : {csv_path.name}  {len(rows)} rows x {len(columns)} cols")

    if args.id_col not in columns:
        print(f"[FAIL] no '{args.id_col}' column. Candidates: "
              f"{[c for c in columns if 'id' in c.lower()][:6]}")
        return 2
    if args.label_col not in columns:
        print(f"[FAIL] no '{args.label_col}' column. Candidates: "
              f"{[c for c in columns if 'nodul' in c.lower() or 'label' in c.lower()][:6]}")
        return 2

    ids = [(r[args.id_col] or "").strip() for r in rows]
    blank = sum(1 for i in ids if not i)
    dupes = len(ids) - len(set(ids)) - blank
    if blank:
        problems.append(f"{blank} rows have a blank {args.id_col}")
    if dupes:
        problems.append(f"{dupes} duplicate {args.id_col} values")

    pos = sum(1 for r in rows if (r[args.label_col] or "").strip() in TRUE)
    neg = sum(1 for r in rows if (r[args.label_col] or "").strip() in FALSE)
    other = len(rows) - pos - neg
    print(f"{args.label_col:15s}: {pos} positive / {neg} negative"
          + (f" / {other} unparseable" if other else ""))
    if other:
        problems.append(f"{other} rows have an unparseable {args.label_col}")
    if pos == 0 or neg == 0:
        problems.append("one class is empty — F1 would be degenerate")

    cohort = {i for i in ids if i}
    cts = index(root / args.ct_dirname)
    segs = index(root / args.totalseg_dirname, strip_suffix=args.seg_suffix)
    print(f"{args.ct_dirname + '/':15s}: {len(cts)} volumes")
    print(f"{args.totalseg_dirname + '/':15s}: {len(segs)} masks")

    have_both = cohort & cts & segs
    no_ct = sorted(cohort - cts)
    no_seg = sorted((cohort & cts) - segs)
    extra = sorted(cts - cohort)

    print(f"joinable       : {len(have_both)}/{len(cohort)} cohort rows have CT + mask")
    label_of: Dict[str, str] = {(r[args.id_col] or "").strip():
                                (r[args.label_col] or "").strip() for r in rows}
    jp = sum(1 for i in have_both if label_of.get(i) in TRUE)
    jn = sum(1 for i in have_both if label_of.get(i) in FALSE)
    print(f"                 of those: {jp} positive / {jn} negative")

    if not have_both:
        problems.append("no cohort row has both a CT and a mask — check the id/filename "
                        "convention and --seg_suffix")
    if no_ct:
        warnings.append(f"{len(no_ct)} rows have no CT volume, e.g. {no_ct[:2]}")
    if no_seg:
        warnings.append(f"{len(no_seg)} rows have a CT but no mask, e.g. {no_seg[:2]}")
    if extra:
        warnings.append(f"{len(extra)} volumes are not in the CSV and will be scored "
                        f"as unlabelled, e.g. {extra[:2]}")

    for line in problems:
        print(f"[FAIL] {line}")
    for line in warnings:
        print(f"[WARN] {line}")

    if problems:
        print("\nNot usable as-is.")
        return 2
    if no_ct or no_seg:
        pct = 100 * len(have_both) / max(len(cohort), 1)
        print(f"\nUsable but INCOMPLETE: {len(have_both)}/{len(cohort)} ({pct:.0f}%) would "
              f"be scored. Finish the copy before quoting the number.")
        return 1
    print("\nReady: every cohort row has a CT and a mask.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
