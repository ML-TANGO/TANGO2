"""Helper for run_eval.sh: `plan` writes the NIAH configs, `summary` prints scores.

Run with the NIAH venv's python from inside the NIAH clone.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

ALL_K = [4, 8, 16, 32, 64, 128]


def plan(a: argparse.Namespace) -> None:
    # Imported here so `summary` works without loading any tokenizer.
    from transformers import AutoConfig, AutoTokenizer

    from needlehaystack.core import tokens
    from needlehaystack.haystacks.files import FilesHaystack
    from needlehaystack.tasks.single_needle import SingleNeedleTask

    ks = ALL_K if a.context_length == ["all"] else [int(k) for k in a.context_length]
    cfg = AutoConfig.from_pretrained(a.model, trust_remote_code=True)
    model_max = getattr(cfg, "text_config", cfg).max_position_embeddings
    input_limit = model_max - a.max_new_tokens
    chat_tok = AutoTokenizer.from_pretrained(a.tokenizer_path or a.model, model_max_length=10**9)

    # Build the exact prompt the runner will send and count it in model tokens.
    task = SingleNeedleTask()
    needle = task.generate_needle(seed=1)
    haystack = tokens.encode(FilesHaystack().load(min_tokens=max(ks) * 1024 + 1024))

    def prompt_tokens(length: int) -> int:
        new_tokens, _ = task.insert(haystack[:length], needle, 50.0)
        user = f"{tokens.decode(new_tokens)}\n\n{task.question(needle)}"
        text = chat_tok.apply_chat_template(
            [{"role": "user", "content": user}], add_generation_prompt=True, tokenize=False
        )
        return len(chat_tok.encode(text, add_special_tokens=False))

    labels: dict[int, str] = {}
    print(f"model max length {model_max:,} -> prompt limit {input_limit:,} "
          f"(minus max_new_tokens {a.max_new_tokens})")
    for k in ks:
        length = k * 1024
        n = prompt_tokens(length)
        if n > input_limit and a.length_unit == "model":
            # Measuring in model tokens: trim the haystack by the overflow so 128k still fits.
            length -= n - input_limit
            n = prompt_tokens(length)
        if n > input_limit:
            print(f"  {k}k: skipped, prompt is {n:,} model tokens (> {input_limit:,})")
            continue
        labels[length] = f"{k}k"
        print(f"  {k}k: context_length={length:,} -> prompt {n:,} model tokens")
    if not labels:
        sys.exit("error: no context length fits the model")

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    request = {
        "model": a.model,
        "max_tokens": a.max_new_tokens,
        "temperature": 0.0,
        "dtype": a.dtype,
        "device": "auto",
        "trust_remote_code": True,
        "do_sample": False,
    }
    if a.adapter:
        request["adapter_path"] = a.adapter
    if a.tokenizer_path:
        request["tokenizer_path"] = a.tokenizer_path
    model_cfg = {"id": a.run_name, "runtime": {"sdk": "transformers", "api": "generate"},
                 "client": {}, "request": request}
    run_cfg = {
        "run_name": a.run_name,
        "model": str(out / "model.yaml"),
        "task": {"type": "single"},
        "haystack": {"type": "files", "path": "PaulGrahamEssays"},
        "sweep": {"context_lengths": list(labels), "depth_percents": a.depths, "seeds": [1]},
        "runner": {"concurrency": 1, "retries": 0, "sleep_between_seconds": 0, "resume": True},
        "store": {"type": "jsonl", "path": str(out / "results.jsonl")},
    }
    (out / "model.yaml").write_text(yaml.safe_dump(model_cfg, sort_keys=False))
    (out / "run.yaml").write_text(yaml.safe_dump(run_cfg, sort_keys=False))
    (out / "plan.json").write_text(json.dumps({
        "model": a.model, "adapter": a.adapter, "length_tokenizer": tokens.encoding_name(),
        "model_max_length": model_max, "max_new_tokens": a.max_new_tokens,
        "labels": {str(k): v for k, v in labels.items()},
    }, indent=2))


def summary(a: argparse.Namespace) -> None:
    out = Path(a.out_dir)
    labels = json.loads((out / "plan.json").read_text())["labels"]
    rows = [json.loads(line) for line in (out / "results.jsonl").read_text().splitlines() if line]
    table: dict[str, dict[float, str]] = {}
    depths: set[float] = set()
    for r in rows:
        label = labels.get(str(r["context_length"]), str(r["context_length"]))
        depth = r["target_depth_percent"]
        depths.add(depth)
        table.setdefault(label, {})[depth] = (
            f"{r['score']['value']:.2f}" if r["status"] == "ok" else "error"
        )
    cols = sorted(depths)
    order = sorted(table, key=lambda s: int(s.rstrip("k")) if s.endswith("k") else 10**9)
    header = ["context"] + [f"depth {d:g}%" for d in cols]
    print("  ".join(f"{h:>10}" for h in header))
    with open(out / "summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for label in order:
            line = [label] + [table[label].get(d, "-") for d in cols]
            print("  ".join(f"{c:>10}" for c in line))
            w.writerow(line)
    print(f"saved {out / 'summary.csv'}")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("--model", required=True)
    pl.add_argument("--adapter")
    pl.add_argument("--tokenizer-path")
    pl.add_argument("--length-unit", choices=["gpt", "model"], required=True)
    pl.add_argument("--context-length", nargs="+", required=True)
    pl.add_argument("--depths", nargs="+", type=float, required=True)
    pl.add_argument("--max-new-tokens", type=int, required=True)
    pl.add_argument("--dtype", required=True)
    pl.add_argument("--run-name", required=True)
    pl.add_argument("--out-dir", required=True)
    su = sub.add_parser("summary")
    su.add_argument("--out-dir", required=True)
    a = p.parse_args()
    plan(a) if a.cmd == "plan" else summary(a)


if __name__ == "__main__":
    main()
