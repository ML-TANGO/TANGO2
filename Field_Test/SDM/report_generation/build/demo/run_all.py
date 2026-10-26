#!/usr/bin/env python3
"""The whole TC1 run, start to finish — what the container does by default.

    docker run -it --rm --gpus '"device=0"' ... chest-ct-foundation:tc1

  Step 2  environment          env_check.py
  Step 3  dataset              verify_dataset.py
  Step 4  report generation    generate.py          (once)
  Step 5  output check         check_reports.py
  Step 6  labeling, 3 rounds   crg_eval.py
  Step 7  nodule F1            crg_eval.py
          export               export_reports.py    -> generated_reports.csv

Each step must pass before the next starts, except the export, which always runs
once reports exist so the generated text is never lost to a labeling failure.
Writes run_summary.json (per-step time and status) under /out.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime

from rich import box
from rich.table import Table

import ui

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("DATA", "/data")
OUT = os.environ.get("OUT", "/out")
PRED = f"{OUT}/generated_reports.json"


def py(script: str, *args: str) -> list:
    return [sys.executable, os.path.join(HERE, script), *args]


STEPS = [
    ("2", "Environment", py("env_check.py")),
    ("3", "Dataset verification", py("verify_dataset.py", "--data", DATA)),
    ("4", "Report generation", py("generate.py", "--data", DATA, "--out", OUT,
                                  "--batch_size", os.environ.get("BATCH_SIZE", "4"),
                                  "--seed", os.environ.get("SEED", "42"))),
    ("5", "Output check", py("check_reports.py", "--data", DATA, "--pred", PRED)),
    ("6–7", "Labeling + nodule F1", py("crg_eval.py", "--data", DATA, "--pred", PRED,
                                       "--out", f"{OUT}/crg")),
]
EXPORT = py("export_reports.py", "--data", DATA, "--pred", PRED, "--crg", f"{OUT}/crg",
            "--out", f"{OUT}/generated_reports.csv")


def main() -> int:
    started = datetime.now().astimezone()
    ui.console.rule("[bold cyan]TC1 · Chest CT report generation · nodule accuracy[/]")
    ui.console.print(f"[dim]  started {started.isoformat(timespec='seconds')} · data {DATA} · output {OUT}[/]")

    t_all = time.perf_counter()
    done, failed_at = [], None
    for n, name, cmd in STEPS:
        t = time.perf_counter()
        code = subprocess.call(cmd)
        done.append({"step": n, "name": name, "exit_code": code,
                     "seconds": round(time.perf_counter() - t, 1)})
        if code != 0:
            failed_at = n
            break

    if os.path.exists(PRED):
        t = time.perf_counter()
        code = subprocess.call(EXPORT)
        done.append({"step": "—", "name": "Export generated_reports.csv", "exit_code": code,
                     "seconds": round(time.perf_counter() - t, 1)})
    total = round(time.perf_counter() - t_all, 1)

    crg = {}
    if os.path.exists(f"{OUT}/crg/summary.json"):
        crg = json.load(open(f"{OUT}/crg/summary.json"))
    verdict = crg.get("verdict", "NOT REACHED") if failed_at in (None, "6–7") else "NOT REACHED"
    # crg_eval exits 1 on a FAIL verdict: that is a result, not a broken step.
    status = lambda s: ("[green]done[/]" if s["exit_code"] == 0
                        else "[red]FAIL verdict[/]" if s["step"] == "6–7" and verdict == "FAIL"
                        else "[red]error[/]")

    t = Table(box=box.ROUNDED, header_style="bold cyan", title="Run summary", title_style="bold")
    for c, j in (("step", "center"), ("", "left"), ("status", "center"), ("time", "right")):
        t.add_column(c, justify=j)
    for s in done:
        t.add_row(s["step"], s["name"], status(s), f"{s['seconds']:.0f} s")
    t.add_section()
    t.add_row("", "[bold]total[/]", "", f"[bold]{total:.0f} s ({total / 60:.1f} min)[/]")
    ui.console.print()
    ui.console.print(t)
    ui.console.print(f"[dim]  outputs in {OUT}: generated_reports.json, generated_reports.csv, "
                     f"timing.json, inference_log.txt, crg/, run_summary.json[/]")

    summary = {"started": started.isoformat(timespec="seconds"),
               "finished": datetime.now().astimezone().isoformat(timespec="seconds"),
               "total_s": total, "steps": done, "verdict": verdict,
               "mean_f1": crg.get("mean_f1"), "rounds": crg.get("rounds")}
    json.dump(summary, open(f"{OUT}/run_summary.json", "w"), indent=2)

    if verdict in ("PASS", "FAIL"):
        f1s = " · ".join(f"R{r['round']} {r['f1']:.4f}" for r in crg["rounds"])
        ui.verdict(verdict == "PASS", f"TC1 nodule F1 (mean of {len(crg['rounds'])}) "
                   f"{crg['mean_f1']:.4f} {'≥' if verdict == 'PASS' else '<'} {crg['config']['threshold']}",
                   f"{f1s} · total run {total / 60:.1f} min")
        return 0 if verdict == "PASS" else 1
    ui.console.print(f"\n  [bold red]Stopped at step {failed_at}[/] — see the output above; "
                     "rerunning resumes labeling from the calls already made.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
