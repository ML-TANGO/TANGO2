#!/usr/bin/env python3
"""Generate chest-CT reports for a directory of preprocessed npz files.

    python run_inference.py --npz_dir /data/preprocessed --out reports.json
    python run_inference.py --npz_dir /data/preprocessed --ids case1 case2 --out r.json

Input contract (get this wrong and output degrades silently):
  * orientation LPS, axes (D, H, W) = (R-L, A-P, I-S)
  * isotropic 1.5 mm, lung-centred crop/pad to 256^3
  * raw Hounsfield units as int16, padded with -1024
  * one `<case_id>.npz` per case with the volume under key `ct`, shape (1, 256, 256, 256)

The volume is centre-cropped to 224^3 and windowed on device; do not pre-window it.
"""
from __future__ import annotations

import argparse, glob, json, os, sys, time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))
from pipeline import ReportGenerator, centre_crop      # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--npz_dir", required=True)
    ap.add_argument("--ids", nargs="+", default=None, help="default: every npz in the dir")
    ap.add_argument("--out", default="reports.json")
    ap.add_argument("--weights", default=os.path.join(HERE, "weights"))
    # The encoder ships inside the bundle; the env vars only exist so a site that
    # already has the full JECT release can point at its own copy.
    ap.add_argument("--ject_dir",
                    default=os.environ.get("JECT_DIR", os.path.join(HERE, "ject")))
    ap.add_argument("--ject_checkpoint",
                    default=os.environ.get("JECT_CHECKPOINT",
                                           os.path.join(HERE, "ject",
                                                        "ject_224_ep45_encoder.pt")))
    ap.add_argument("--medgemma", default="google/medgemma-1.5-4b-it")
    ap.add_argument("--batch_size", type=int, default=4)
    ap.add_argument("--max_new_tokens", type=int, default=320)
    ap.add_argument("--npz_key", default="ct")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    ids = args.ids or sorted(os.path.basename(p)[:-4]
                             for p in glob.glob(os.path.join(args.npz_dir, "*.npz")))
    if not ids:
        raise SystemExit(f"no .npz files in {args.npz_dir}")
    print(f"[infer] {len(ids)} cases | device {args.device}")

    model = ReportGenerator(args.weights, args.ject_dir, args.ject_checkpoint,
                            args.medgemma, args.device)
    print("[infer] model loaded")

    out, skipped, t0 = {}, [], time.time()
    for i in range(0, len(ids), args.batch_size):
        chunk, vols = [], []
        for cid in ids[i:i + args.batch_size]:
            try:
                with np.load(os.path.join(args.npz_dir, cid + ".npz")) as d:
                    vols.append(torch.from_numpy(
                        np.ascontiguousarray(centre_crop(d[args.npz_key]))).unsqueeze(0))
                chunk.append(cid)
            except Exception as e:                  # unreadable or wrong shape
                skipped.append((cid, repr(e)))
                print(f"  skip {cid}: {e}", flush=True)
        if not chunk:
            continue
        for cid, res in zip(chunk, model.generate(torch.stack(vols),
                                                  max_new_tokens=args.max_new_tokens)):
            out[cid] = res
        done = len(out)
        print(f"  {done}/{len(ids)}  {done / max(time.time() - t0, 1e-6):.2f} case/s",
              flush=True)

    json.dump(out, open(args.out, "w"), indent=2)
    print(f"[saved] {args.out}  {len(out)} reports, {len(skipped)} skipped")
    if out:
        k = next(iter(out))
        print(f"\nEXAMPLE ({k})\n{out[k]['findings_block']}\n---\n{out[k]['report'][:400]}")


if __name__ == "__main__":
    sys.exit(main())
