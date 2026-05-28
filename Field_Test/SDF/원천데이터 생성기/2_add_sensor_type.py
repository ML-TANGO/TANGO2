#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


def infer_sensor_type(src_csv: Path, *, src_root: Path) -> str:
    """
    규칙:
    - 파일명에 'agsmotor_green' 이라는 문자열이 포함되어 있으면: 'agsmotor_green'
    - 그 외: 파일명을 '_'로 split 했을 때 0~1번 조각을 '_'로 합친 값
      예) Out_raindrop_xxx.csv -> Out_raindrop
    """
    name = src_csv.name
    if "agsmotor_green" in name:
        return "agsmotor_green"
    stem = name[:-4] if name.lower().endswith(".csv") else name
    parts = stem.split("_")
    if len(parts) >= 2:
        return f"{parts[0]}_{parts[1]}"
    return parts[0] if parts else "unknown"


@dataclass
class Result:
    src: Path
    dst: Path
    rows: int
    sensor_type: str


def convert_one(src_csv: Path, dst_csv: Path, *, sensor_type: str) -> Result:
    dst_csv.parent.mkdir(parents=True, exist_ok=True)

    rows = 0
    with src_csv.open("r", encoding="utf-8", newline="") as f_in:
        reader = csv.DictReader(f_in)
        in_fields: List[str] = list(reader.fieldnames or [])
        if not in_fields:
            # 빈 파일이면 sensor_type 헤더만 만든다
            with dst_csv.open("w", encoding="utf-8", newline="") as f_out:
                w = csv.DictWriter(f_out, fieldnames=["sensor_type"])
                w.writeheader()
            return Result(src=src_csv, dst=dst_csv, rows=0, sensor_type=sensor_type)

        out_fields = ["sensor_type"] + [c for c in in_fields if c != "sensor_type"]

        with dst_csv.open("w", encoding="utf-8", newline="") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=out_fields, extrasaction="ignore")
            writer.writeheader()
            for row in reader:
                row["sensor_type"] = sensor_type
                writer.writerow(row)
                rows += 1

    return Result(src=src_csv, dst=dst_csv, rows=rows, sensor_type=sensor_type)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "1_csv_data_deleted_error_data 아래 모든 CSV에 sensor_type 컬럼을 추가하고 "
            "2_csv_data_with_sensor_type 아래에 동일한 구조로 저장합니다."
        )
    )
    ap.add_argument("--src-root", default="1_csv_data_deleted_error_data", help="입력 루트 (default: 1_csv_data_deleted_error_data)")
    ap.add_argument(
        "--dst-root",
        default="2_csv_data_with_sensor_type",
        help="출력 루트 (default: csv_data_with_sensor_type)",
    )
    ap.add_argument("--glob", default="*.csv", help="대상 패턴 (default: *.csv)")
    ap.add_argument("--overwrite", action="store_true", help="기존 파일 덮어쓰기")
    args = ap.parse_args()

    src_root = Path(args.src_root)
    dst_root = Path(args.dst_root)
    if not src_root.exists() or not src_root.is_dir():
        raise SystemExit(f"src-root가 없거나 디렉토리가 아닙니다: {src_root}")

    files = sorted(src_root.rglob(args.glob))
    if not files:
        print(f"대상 CSV 없음: {src_root} 아래 {args.glob}")
        return 0

    ok = 0
    skipped = 0
    fail = 0

    for i, src_csv in enumerate(files, start=1):
        rel = src_csv.relative_to(src_root)
        dst_csv = dst_root / rel

        if dst_csv.exists() and not args.overwrite:
            skipped += 1
            continue

        sensor_type = infer_sensor_type(src_csv, src_root=src_root)
        try:
            res = convert_one(src_csv, dst_csv, sensor_type=sensor_type)
            ok += 1
            if ok <= 3 or ok % 50 == 0:
                print(f"[{i}/{len(files)}] OK {rel} sensor_type={res.sensor_type} rows={res.rows}")
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(files)}] FAIL {rel}: {e}")

    print(f"Done. ok={ok}, skipped={skipped}, fail={fail}, dst_root={dst_root}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

