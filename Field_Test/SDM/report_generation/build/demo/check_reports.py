#!/usr/bin/env python3
"""Step 5 — confirm 100 reports were generated and the file is well-formed.

    python3 /app/demo/check_reports.py --data /data --pred /out/generated_reports.json

generated_reports.json is one object keyed by case_id; each value holds
  report          the generated FINDINGS text (this is what gets labeled)
  findings_block  the classifier summary the generator was conditioned on
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import pandas as pd
from rich.panel import Panel

import ui


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="/data")
    ap.add_argument("--pred", default="/out/generated_reports.json")
    args = ap.parse_args()

    ui.step("5", "Generation output check", "one report per case, keyed by case_id, well-formed")
    ids = set(pd.read_csv(os.path.join(args.data, "manifest.csv")).case_id)
    results = []
    check = lambda ok, msg: results.append(ui.check(ok, msg))

    try:
        raw = open(args.pred, "rb").read()
        pred = json.loads(raw)
    except (OSError, json.JSONDecodeError) as e:
        ui.check(False, f"cannot read {args.pred}: {e}")
        ui.verdict(False, "Output unreadable")
        return 1
    ui.console.print(ui.kv_table([("file", args.pred), ("sha256", hashlib.sha256(raw).hexdigest())]))

    check(isinstance(pred, dict), "top level is an object keyed by case_id")
    check(len(pred) == len(ids), f"{len(pred)} reports (expected {len(ids)})")
    check(set(pred) == ids, "case ids match the manifest exactly"
          + (f" — missing {sorted(ids - set(pred))[:3]}" if ids - set(pred) else "")
          + (f" — extra {sorted(set(pred) - ids)[:3]}" if set(pred) - ids else ""))
    bad = [k for k, v in pred.items()
           if not (isinstance(v, dict) and isinstance(v.get("report"), str)
                   and isinstance(v.get("findings_block"), str))]
    check(not bad, "every entry has string 'report' and 'findings_block'"
          + (f" — bad: {bad[:3]}" if bad else ""))
    empty = [k for k, v in pred.items() if isinstance(v, dict) and not str(v.get("report", "")).strip()]
    check(not empty, "no empty reports" + (f" — empty: {empty[:3]}" if empty else ""))

    lens = [len(v["report"].split()) for v in pred.values() if isinstance(v, dict) and "report" in v]
    if lens:
        ui.console.print(f"  [dim]report length (words): min {min(lens)}, "
                         f"median {sorted(lens)[len(lens) // 2]}, max {max(lens)}[/]")
    if pred and not bad:
        k = sorted(pred)[0]
        ui.console.print(Panel(pred[k]["report"][:600] + ("…" if len(pred[k]["report"]) > 600 else ""),
                               title=f"[bold]example · {k}[/]", title_align="left",
                               border_style="dim", padding=(0, 1)))

    failed = results.count(False)
    ui.verdict(not failed, f"{len(pred)} reports generated, format valid" if not failed
               else f"{failed} check(s) failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
