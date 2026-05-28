#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple


JsonObj = Dict[str, Any]


def _is_scalar(v: Any) -> bool:
    return v is None or isinstance(v, (str, int, float, bool))


def flatten_record(
    obj: Any,
    *,
    parent_key: str = "",
    sep: str = ".",
) -> Dict[str, Any]:
    """
    Flatten nested dicts into a single-level dict.
    - Dicts are flattened using dot-separated keys: a.b.c
    - Lists/tuples are serialized as JSON strings (preserving structure)
    - Non-scalar leaf values are serialized as JSON strings
    """
    out: Dict[str, Any] = {}

    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{parent_key}{sep}{k}" if parent_key else str(k)
            if isinstance(v, dict):
                out.update(flatten_record(v, parent_key=key, sep=sep))
            elif isinstance(v, (list, tuple)):
                out[key] = json.dumps(v, ensure_ascii=False)
            else:
                out[key] = v if _is_scalar(v) else json.dumps(v, ensure_ascii=False)
        return out

    # non-dict record: represent as a single column
    if parent_key:
        out[parent_key] = obj if _is_scalar(obj) else json.dumps(obj, ensure_ascii=False)
    else:
        out["value"] = obj if _is_scalar(obj) else json.dumps(obj, ensure_ascii=False)
    return out


class JsonArrayStreamError(RuntimeError):
    pass


def iter_json_array_stream(path: Path, *, encoding: str = "utf-8") -> Iterator[Any]:
    """
    Stream-parse a JSON file that contains a single top-level array:
      [ {...}, {...}, ... ]

    Uses json.JSONDecoder().raw_decode to avoid loading entire file into memory.
    """
    decoder = json.JSONDecoder()
    buf = ""
    idx = 0
    inited = False

    with path.open("r", encoding=encoding) as f:
        while True:
            if idx >= len(buf) - 1:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                buf = buf[idx:] + chunk
                idx = 0

            if not inited:
                # Skip whitespace to find '['
                while True:
                    while idx < len(buf) and buf[idx].isspace():
                        idx += 1
                    if idx < len(buf):
                        break
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        raise JsonArrayStreamError(f"Unexpected EOF before '[' in {path}")
                    buf += chunk

                if buf[idx] != "[":
                    raise JsonArrayStreamError(f"Expected '[' at start of {path}")
                idx += 1
                inited = True

            # Skip whitespace / commas
            while True:
                while idx < len(buf) and buf[idx].isspace():
                    idx += 1
                if idx < len(buf) and buf[idx] == ",":
                    idx += 1
                    continue
                break

            # Need more data?
            while idx >= len(buf):
                chunk = f.read(1024 * 1024)
                if not chunk:
                    raise JsonArrayStreamError(f"Unexpected EOF inside array in {path}")
                buf += chunk

            # End of array?
            if buf[idx] == "]":
                return

            # Decode next value
            while True:
                try:
                    obj, next_idx = decoder.raw_decode(buf, idx)
                    idx = next_idx
                    yield obj
                    break
                except json.JSONDecodeError:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        raise JsonArrayStreamError(f"Invalid JSON array in {path}")
                    buf += chunk


def iter_jsonl(path: Path, *, encoding: str = "utf-8") -> Iterator[Any]:
    with path.open("r", encoding=encoding) as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            yield json.loads(s)


def load_top_level_kind(path: Path, *, encoding: str = "utf-8") -> Tuple[str, Any]:
    """
    Peek top-level kind:
    - "array": top-level array stream
    - "object": top-level object (returned fully loaded)
    - "jsonl": line-delimited JSON
    """
    with path.open("r", encoding=encoding) as f:
        head = f.read(64 * 1024)
    s = head.lstrip()
    if not s:
        return ("empty", None)
    if s[0] == "[":
        return ("array", None)
    if s[0] == "{":
        # Try full JSON load. If it fails, treat as JSONL (each line is a JSON object).
        try:
            with path.open("r", encoding=encoding) as f:
                return ("object", json.load(f))
        except Exception:
            return ("jsonl", None)
    # fallback: jsonl or invalid
    return ("jsonl", None)


def iter_records(path: Path, *, encoding: str = "utf-8") -> Iterator[JsonObj]:
    kind, obj = load_top_level_kind(path, encoding=encoding)
    if kind == "empty":
        return iter(())

    if kind == "array":
        return (r for r in iter_json_array_stream(path, encoding=encoding) if r is not None)

    if kind == "jsonl":
        return (r for r in iter_jsonl(path, encoding=encoding) if r is not None)

    # object
    assert kind == "object"
    if isinstance(obj, dict):
        # common pattern: {"data":[{...},...], ...}
        data = obj.get("data")
        if isinstance(data, list) and all(isinstance(x, dict) for x in data):
            return iter(data)
        return iter([obj])
    if isinstance(obj, list):
        return iter(obj)
    return iter([{"value": obj}])


@dataclass
class ConvertResult:
    src: Path
    dst: Path
    rows: int
    cols: int


def convert_one_file(
    src_path: Path,
    dst_path: Path,
    *,
    encoding: str = "utf-8",
    sep: str = ".",
) -> ConvertResult:
    # pass1: collect fieldnames in first-seen order
    fieldnames: List[str] = []
    seen: set[str] = set()
    row_count = 0

    for rec in iter_records(src_path, encoding=encoding):
        flat = flatten_record(rec, sep=sep)
        for k in flat.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)
        row_count += 1

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    # write even if empty (header only)
    with dst_path.open("w", encoding="utf-8", newline="") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        if row_count == 0:
            return ConvertResult(src=src_path, dst=dst_path, rows=0, cols=len(fieldnames))

        # pass2: write rows
        for rec in iter_records(src_path, encoding=encoding):
            flat = flatten_record(rec, sep=sep)
            writer.writerow(flat)

    return ConvertResult(src=src_path, dst=dst_path, rows=row_count, cols=len(fieldnames))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Convert all JSON files under json_data/ to CSV under csv_data/ preserving folder structure."
    )
    ap.add_argument("--src-root", default="json_data", help="Source root directory (default: json_data)")
    ap.add_argument("--dst-root", default="csv_data", help="Destination root directory (default: csv_data)")
    ap.add_argument("--glob", default="*.json", help="File glob to include (default: *.json)")
    ap.add_argument("--encoding", default="utf-8", help="Input text encoding (default: utf-8)")
    ap.add_argument("--sep", default=".", help="Flatten key separator (default: .)")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing CSV files")
    args = ap.parse_args()

    src_root = Path(args.src_root)
    dst_root = Path(args.dst_root)

    if not src_root.exists() or not src_root.is_dir():
        raise SystemExit(f"Source root not found or not a directory: {src_root}")

    json_files = sorted(src_root.rglob(args.glob))
    if not json_files:
        print(f"No files matched {args.glob} under {src_root}")
        return 0

    converted = 0
    skipped = 0
    failed = 0

    for i, src_path in enumerate(json_files, start=1):
        rel = src_path.relative_to(src_root)
        dst_path = dst_root / rel
        dst_path = dst_path.with_suffix(".csv")

        if dst_path.exists() and not args.overwrite:
            skipped += 1
            continue

        try:
            res = convert_one_file(src_path, dst_path, encoding=args.encoding, sep=args.sep)
            converted += 1
            if converted <= 3 or converted % 50 == 0:
                print(f"[{i}/{len(json_files)}] OK {res.rows} rows, {res.cols} cols -> {res.dst}")
        except Exception as e:
            failed += 1
            print(f"[{i}/{len(json_files)}] FAIL {src_path}: {e}")

    print(f"Done. converted={converted}, skipped={skipped}, failed={failed}, dst_root={dst_root}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

