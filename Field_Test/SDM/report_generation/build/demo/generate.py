#!/usr/bin/env python3
"""Step 4 — generate one report per CT volume, with live progress and timing.

    python3 /app/demo/generate.py --data /data --out /out

Runs the bundle's run_inference.py unmodified. Before it starts, seeds are fixed and
ReportGenerator is wrapped with timers (model load, each batch); the wrappers also
drive the progress bar. run_inference.py's own output goes to inference_log.txt.

Writes generated_reports.json, inference_log.txt, timing.json under --out.
"""
from __future__ import annotations

import argparse
import contextlib
import glob
import hashlib
import json
import os
import random
import runpy
import sys
import time
from datetime import datetime

import numpy as np
import torch

import ui

APP = "/app"


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="/data")
    ap.add_argument("--out", default="/out")
    # Fixed: the bundle left-pads each batch to its longest prompt, so batch size and
    # case order change the generated text.
    ap.add_argument("--batch_size", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    pred = os.path.join(args.out, "generated_reports.json")
    log = open(os.path.join(args.out, "inference_log.txt"), "w", buffering=1)

    def record(line: str) -> None:
        log.write(line + "\n")

    vols = sorted(glob.glob(os.path.join(args.data, "volumes", "*.npz")))
    gpu = torch.cuda.get_device_properties(0) if torch.cuda.is_available() else None
    env = [
        ("GPU", f"{torch.cuda.device_count()}x {gpu.name if gpu else 'none'}"),
        ("torch / CUDA", f"{torch.__version__} / available={torch.cuda.is_available()}"),
        ("model", "JECT_Generator"),
        ("decoding", f"greedy, seed {args.seed}, batch size {args.batch_size}"),
        ("inputs", f"{len(vols)} CT volumes in {args.data}/volumes"),
        ("output", pred),
    ]
    weights = sorted(glob.glob(f"{APP}/weights/*.pt") + glob.glob(f"{APP}/ject/*.pt"))
    hashes = [(os.path.relpath(w, APP), sha256(w)[:16] + "…") for w in weights]

    ui.step("4", "Report generation", "3D chest CT → FINDINGS text, one pass over all cases")
    ui.console.print(ui.kv_table(env, title="Environment"))
    ui.console.print(ui.kv_table(hashes, title="Pretrained weights (sha256)"))
    for k, v in env:
        record(f"{k}: {v}")
    for w in weights:
        record(f"sha256 {sha256(w)}  {os.path.relpath(w, APP)}")

    random.seed(args.seed); np.random.seed(args.seed)
    torch.manual_seed(args.seed); torch.cuda.manual_seed_all(args.seed)

    sys.path.insert(0, f"{APP}/src")
    import pipeline
    timing = {"model_load_s": None, "batches": []}
    init, gen = pipeline.ReportGenerator.__init__, pipeline.ReportGenerator.generate
    prog = ui.progress()
    load = prog.add_task("Loading model onto GPU", total=None, rate="")
    task = prog.add_task("Generating reports", total=len(vols), rate="", visible=False)

    def timed_init(self, *a, **k):
        t = time.perf_counter()
        init(self, *a, **k)
        torch.cuda.synchronize()
        timing["model_load_s"] = round(time.perf_counter() - t, 2)
        prog.update(load, total=1, completed=1, rate=f"{timing['model_load_s']} s")
        prog.update(task, visible=True)

    def timed_generate(self, volumes, *a, **k):
        torch.cuda.synchronize()
        t = time.perf_counter()
        res = gen(self, volumes, *a, **k)
        torch.cuda.synchronize()
        dt = time.perf_counter() - t
        timing["batches"].append({"n_cases": len(volumes), "seconds": round(dt, 3)})
        done = sum(b["n_cases"] for b in timing["batches"])
        spent = sum(b["seconds"] for b in timing["batches"])
        mem = torch.cuda.max_memory_allocated() / 2**30
        prog.update(task, advance=len(volumes),
                    rate=f"{spent / done:.1f} s/case • GPU {mem:.1f} GiB")
        record(f"batch {len(timing['batches'])}: {len(volumes)} cases in {dt:.2f} s")
        return res

    pipeline.ReportGenerator.__init__, pipeline.ReportGenerator.generate = timed_init, timed_generate

    started = datetime.now().astimezone()
    record(f"start {started.isoformat(timespec='seconds')}")
    t0 = time.perf_counter()
    sys.argv = ["run_inference.py", "--npz_dir", os.path.join(args.data, "volumes"),
                "--out", pred, "--batch_size", str(args.batch_size)]
    prog.start()
    try:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            runpy.run_path(f"{APP}/run_inference.py", run_name="__main__")
    except SystemExit as e:                     # run_inference.py ends with sys.exit(main())
        if e.code not in (None, 0):
            ui.check(False, f"run_inference.py exited with {e.code} — see inference_log.txt")
            return 1
    finally:
        prog.stop()
    total = time.perf_counter() - t0
    record(f"end {datetime.now().astimezone().isoformat(timespec='seconds')}")

    per_case = [b["seconds"] / b["n_cases"] for b in timing["batches"] for _ in range(b["n_cases"])]
    gen_s = sum(b["seconds"] for b in timing["batches"])
    timing.update(
        started=started.isoformat(timespec="seconds"),
        script_total_s=round(total, 2),                   # load + reading + generation + save
        generation_total_s=round(gen_s, 2), n_cases=len(per_case), batch_size=args.batch_size,
        per_case_mean_s=round(gen_s / len(per_case), 3),
        per_case_max_s=round(max(per_case), 3),           # batch time / batch size, worst batch
        batch_max_s=max(b["seconds"] for b in timing["batches"]))
    json.dump(timing, open(os.path.join(args.out, "timing.json"), "w"), indent=2)
    record("timing " + json.dumps({k: v for k, v in timing.items() if k != "batches"}))

    ui.console.print(ui.kv_table([
        ("model load", f"{timing['model_load_s']} s"),
        ("generation", f"{timing['generation_total_s']} s for {timing['n_cases']} cases"),
        ("per case", f"mean {timing['per_case_mean_s']} s · max {timing['per_case_max_s']} s"),
        ("total", f"{timing['script_total_s']} s ({timing['script_total_s'] / 60:.1f} min)"),
    ], title="Timing"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
