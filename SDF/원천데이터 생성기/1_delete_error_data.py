# csv_data 폴더 안에 있는, 모든 csv 파일들에 대해, ts, created_at 두 칼럼이 전부 존재하는 csv 파일들을 찾고, 총 csv파일과 저 두 칼럼이 존재하는 파일의 수가 각각 몇개인지 출력한다.
# 그 후, csv_data_deleted_error_data 폴더 안에, 저 세부 폴더구조와 파일명은 전부 그대로 유지한 채로, 다음 과정을 수행하여 저장한다.
# ts, created_at 두 칼럼의 값이 1분 이상의 차이를 가진 row를 각각 csv 파일별로 파악하여 출력하고, 해당되는 row를 제거한 후 저장한다.
# 저장할 때는 created_at 칼럼은 출력하지 않는다.
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, TextIO, Tuple


class _Tee:
    """log 파일에 동시에 쓴다."""

    def __init__(self, *streams: TextIO) -> None:
        self._streams = streams

    def write(self, data: str) -> int:
        for s in self._streams:
            s.write(data)
            s.flush()
        return len(data)

    def flush(self) -> None:
        for s in self._streams:
            s.flush()

    def isatty(self) -> bool:
        return False


def _normalize_ts_str(s: str) -> str:
    """
    - 공백이 있는 경우 첫 공백을 'T'로 치환 (예: '2026-01-01 00:00:00+00:00')
    - 끝에 'Z'가 붙으면 +00:00으로 변환
    """
    x = (s or "").strip()
    if not x:
        return ""
    if " " in x and "T" not in x:
        x = x.replace(" ", "T", 1)
    if x.endswith("Z"):
        x = x[:-1] + "+00:00"
    return x


def _try_parse_dt(s: str) -> Optional[datetime]:
    """
    ISO8601 계열을 최대한 파싱한다.
    - timezone 없는 값은 UTC로 간주
    """
    x = _normalize_ts_str(s)
    if not x:
        return None
    try:
        dt = datetime.fromisoformat(x)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _diff_seconds(a: str, b: str) -> Tuple[Optional[float], bool]:
    """
    두 timestamp 문자열의 차이(초)를 반환한다.
    반환:
    - (diff_seconds, ok)
      - ok=False면 파싱 실패(둘 중 하나라도)
    """
    da = _try_parse_dt(a)
    db = _try_parse_dt(b)
    if da is None or db is None:
        return None, False
    return abs((da - db).total_seconds()), True


@dataclass
class FileSummary:
    rel: Path
    has_ts: bool
    has_created_at: bool
    total_rows: int
    removed_rows: int
    parse_failed_rows: int
    written_rows: int


def _iter_csv_files(root: Path, glob_pat: str) -> Iterable[Path]:
    return sorted(root.rglob(glob_pat))


def process_one_csv(
    src_csv: Path,
    dst_csv: Path,
    *,
    threshold_seconds: float,
    overwrite: bool,
    sample_print: int,
) -> FileSummary:
    if dst_csv.exists() and not overwrite:
        # 컬럼 유무를 보기 위해 헤더만 확인
        with src_csv.open("r", encoding="utf-8", newline="") as f_in:
            reader = csv.DictReader(f_in)
            fields = list(reader.fieldnames or [])
        return FileSummary(
            rel=src_csv,
            has_ts=("ts" in fields),
            has_created_at=("created_at" in fields),
            total_rows=0,
            removed_rows=0,
            parse_failed_rows=0,
            written_rows=0,
        )

    dst_csv.parent.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    removed_rows = 0
    parse_failed_rows = 0
    written_rows = 0
    printed = 0

    with src_csv.open("r", encoding="utf-8", newline="") as f_in:
        reader = csv.DictReader(f_in)
        fields = list(reader.fieldnames or [])
        has_ts = "ts" in fields
        has_created_at = "created_at" in fields

        # 요구사항: 두 칼럼이 모두 있어야 필터링 수행. 아니면 그대로 복사 저장.
        # 출력 CSV에는 created_at 칼럼을 넣지 않는다.
        out_fields = [c for c in fields if c != "created_at"]
        with dst_csv.open("w", encoding="utf-8", newline="") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=out_fields, extrasaction="ignore")
            if out_fields:
                writer.writeheader()

            for row_idx, row in enumerate(reader, start=2):  # header 다음이 2번째 줄
                total_rows += 1

                if has_ts and has_created_at:
                    diff, ok = _diff_seconds(row.get("ts", ""), row.get("created_at", ""))
                    if not ok:
                        parse_failed_rows += 1
                        writer.writerow(row)
                        written_rows += 1
                        continue

                    if diff is not None and diff >= threshold_seconds:
                        removed_rows += 1
                        if printed < sample_print:
                            printed += 1
                            print(
                                f"  - drop line={row_idx} diff_sec={diff:.3f} ts={row.get('ts','')} created_at={row.get('created_at','')}"
                            )
                        continue

                writer.writerow(row)
                written_rows += 1

    return FileSummary(
        rel=src_csv,
        has_ts=has_ts,
        has_created_at=has_created_at,
        total_rows=total_rows,
        removed_rows=removed_rows,
        parse_failed_rows=parse_failed_rows,
        written_rows=written_rows,
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "csv_data 아래 모든 CSV에 대해 ts/created_at 컬럼 존재 여부를 집계하고, "
            "두 컬럼이 모두 있는 파일은 ts-created_at 차이가 1분 이상인 행을 제거해 "
            "csv_data_deleted_error_data 아래에 동일 구조로 저장합니다."
        )
    )
    ap.add_argument("--src-root", default="csv_data", help="입력 루트 (default: csv_data)")
    ap.add_argument(
        "--dst-root",
        default="1_csv_data_deleted_error_data",
        help="출력 루트 (default: 1_csv_data_deleted_error_data)",
    )
    ap.add_argument("--glob", default="*.csv", help="대상 패턴 (default: *.csv)")
    ap.add_argument(
        "--threshold-seconds",
        type=float,
        default=60.0,
        help="제거 기준(초). diff >= threshold면 제거 (default: 60.0)",
    )
    ap.add_argument(
        "--sample-print",
        type=int,
        default=3,
        help="각 파일별 drop 예시 출력 최대 개수 (default: 3)",
    )
    ap.add_argument("--overwrite", action="store_true", help="기존 파일 덮어쓰기")
    args = ap.parse_args()

    src_root = Path(args.src_root)
    dst_root = Path(args.dst_root)
    if not src_root.exists() or not src_root.is_dir():
        raise SystemExit(f"src-root가 없거나 디렉토리가 아닙니다: {src_root}")

    dst_root.mkdir(parents=True, exist_ok=True)
    log_path = dst_root / "log.txt"
    orig_stdout = sys.stdout
    log_f = log_path.open("w", encoding="utf-8")
    try:
        sys.stdout = _Tee(orig_stdout, log_f)
        try:
            files = _iter_csv_files(src_root, args.glob)
            total_files = len(files)
            if total_files == 0:
                print(f"대상 CSV 없음: {src_root} 아래 {args.glob}")
                return 0

            files_with_both = 0
            ok = 0
            skipped = 0
            fail = 0

            # 1) 전체 파일 헤더 스캔 + 2) 변환/복사
            summaries: list[FileSummary] = []
            for i, src_csv in enumerate(files, start=1):
                rel = src_csv.relative_to(src_root)
                dst_csv = dst_root / rel
                try:
                    res = process_one_csv(
                        src_csv,
                        dst_csv,
                        threshold_seconds=float(args.threshold_seconds),
                        overwrite=bool(args.overwrite),
                        sample_print=int(args.sample_print),
                    )
                    # rel을 사람이 보기 좋게
                    res.rel = rel
                    summaries.append(res)

                    if res.has_ts and res.has_created_at:
                        files_with_both += 1

                    if dst_csv.exists() and (not args.overwrite):
                        skipped += 1
                    else:
                        ok += 1

                    # 파일별 요약 출력
                    if res.has_ts and res.has_created_at:
                        print(
                            f"[{i}/{total_files}] {rel} (has ts+created_at) total={res.total_rows} "
                            f"removed={res.removed_rows} parse_fail={res.parse_failed_rows} written={res.written_rows}"
                        )
                    else:
                        print(f"[{i}/{total_files}] {rel} (missing ts/created_at) copied={res.written_rows}")
                except Exception as e:
                    fail += 1
                    print(f"[{i}/{total_files}] FAIL {rel}: {e}")

            print(
                f"\nCount: total_csv_files={total_files}, files_with_ts_and_created_at={files_with_both}\n"
                f"Done. ok={ok}, skipped={skipped}, fail={fail}, dst_root={dst_root}"
            )
            return 0 if fail == 0 else 2
        finally:
            sys.stdout = orig_stdout
    finally:
        log_f.close()


if __name__ == "__main__":
    raise SystemExit(main())