#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


Interval = Tuple[datetime, datetime]  # [start, end], inclusive


def _parse_ts(s: str) -> datetime:
    v = (s or "").strip()
    if not v:
        raise ValueError("empty ts")
    # '2026-02-11 00:00:02.903000+00:00' / '...T...' 모두 지원
    return datetime.fromisoformat(v)


def _load_and_normalize_intervals(path: Path) -> List[Interval]:
    """
    merged_all.valid_ranges.csv 를 읽어 구간을 정렬/병합해서 반환.
    - 병합 기준: 다음 start <= 현재 end 이면 합침 (붙어있는 구간도 합침)
    - 포함 판단은 start <= ts <= end
    """
    if not path.exists():
        raise FileNotFoundError(path)

    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        if not r.fieldnames or "start_ts" not in r.fieldnames or "end_ts" not in r.fieldnames:
            raise ValueError(f"구간 파일 컬럼이 필요합니다: start_ts,end_ts (have={r.fieldnames})")
        rows = [( _parse_ts(row["start_ts"]), _parse_ts(row["end_ts"]) ) for row in r]

    rows = [(s, e) for s, e in rows if s is not None and e is not None and s <= e]
    rows.sort(key=lambda t: (t[0], t[1]))
    if not rows:
        return []

    merged: List[Interval] = []
    cur_s, cur_e = rows[0]
    for s, e in rows[1:]:
        if s <= cur_e:
            if e > cur_e:
                cur_e = e
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    merged.append((cur_s, cur_e))
    return merged


def _build_starts(intervals: Sequence[Interval]) -> List[datetime]:
    return [s for s, _ in intervals]


def ts_in_intervals(ts: datetime, intervals: Sequence[Interval], starts: Sequence[datetime]) -> bool:
    """
    intervals는 start 오름차순으로 정렬되어 있어야 함.
    """
    if not intervals:
        return False
    i = bisect_right(starts, ts) - 1
    if i < 0:
        return False
    s, e = intervals[i]
    return s <= ts <= e


@dataclass
class FileResult:
    src: Path
    dst: Path
    total_rows: int
    kept_rows: int


def filter_one_csv(
    src_csv: Path,
    dst_csv: Path,
    *,
    intervals: Sequence[Interval],
    starts: Sequence[datetime],
    ts_col: str = "ts",
) -> FileResult:
    dst_csv.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    kept = 0

    with src_csv.open("r", encoding="utf-8", newline="") as f_in:
        reader = csv.DictReader(f_in)
        fieldnames = list(reader.fieldnames or [])
        if not fieldnames:
            # 빈 파일은 빈 파일로 출력
            with dst_csv.open("w", encoding="utf-8", newline="") as f_out:
                csv.writer(f_out).writerow([])
            return FileResult(src=src_csv, dst=dst_csv, total_rows=0, kept_rows=0)

        if ts_col not in fieldnames:
            raise ValueError(f"'{ts_col}' 컬럼이 없습니다. columns={fieldnames}")

        with dst_csv.open("w", encoding="utf-8", newline="") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()

            for row in reader:
                total += 1
                try:
                    ts = _parse_ts(row.get(ts_col, ""))
                except Exception:
                    continue

                if ts_in_intervals(ts, intervals, starts):
                    writer.writerow(row)
                    kept += 1

    return FileResult(src=src_csv, dst=dst_csv, total_rows=total, kept_rows=kept)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "merged valid_ranges 시간구간 안의 데이터만 추출해서 4_valid_data 폴더에 저장합니다."
        )
    )
    ap.add_argument("--src-root", default="2_csv_data_with_sensor_type", help="입력 루트 (default: 2_csv_data_with_sensor_type)")
    ap.add_argument("--dst-root", default="4_valid_data", help="출력 루트 (default: 4_valid_data)")
    ap.add_argument(
        "--ranges",
        default="3_valid_time_ranges/_merged_all.valid_ranges.csv",
        help="머지된 유효구간 CSV 경로 (default: 3_valid_time_ranges/_merged_all.valid_ranges.csv)",
    )
    ap.add_argument("--glob", default="*.csv", help="대상 CSV 패턴 (default: *.csv)")
    ap.add_argument("--ts-col", default="ts", help="timestamp 컬럼명 (default: ts)")
    ap.add_argument("--overwrite", action="store_true", help="기존 출력 덮어쓰기")
    args = ap.parse_args()

    src_root = Path(args.src_root)
    dst_root = Path(args.dst_root)
    ranges_path = Path(args.ranges)

    if not src_root.exists() or not src_root.is_dir():
        raise SystemExit(f"src-root가 없거나 디렉토리가 아닙니다: {src_root}")

    intervals = _load_and_normalize_intervals(ranges_path)
    if not intervals:
        raise SystemExit(f"유효구간이 비어있습니다: {ranges_path}")
    starts = _build_starts(intervals)

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

        try:
            res = filter_one_csv(
                src_csv,
                dst_csv,
                intervals=intervals,
                starts=starts,
                ts_col=args.ts_col,
            )
            ok += 1
            if ok <= 3 or ok % 50 == 0:
                print(f"[{i}/{len(files)}] OK {rel} kept={res.kept_rows}/{res.total_rows}")
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(files)}] FAIL {rel}: {e}")

    print(f"Done. ok={ok}, skipped={skipped}, fail={fail}, dst_root={dst_root}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

