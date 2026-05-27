from __future__ import annotations

import argparse
import math
import json
from pathlib import Path
from typing import List, Tuple, Optional

import pandas as pd
import numpy as np

THRESHOLD_SECONDS_MOTOR = 130
THRESHOLD_SECONDS_SENSOR = 120


def get_valid_time_ranges_for_sensor(
    sensor_data: pd.DataFrame,
    *,
    threshold_seconds: int,
    ts_col: str = "ts"
) -> pd.DataFrame:
    """
    각 행의 ts와 다음 행의 ts의 차이를 초 단위로 반올림(half-up)하고,
    그 차이가 threshold_seconds 이하인 "연속 구간"들을 [start_ts, end_ts]로 반환.
    기본적으로는 "연속(=간격 조건을 만족하는 엣지 1개 이상)"인 구간만 반환하므로 n_points >= 2 입니다.
    (include_singletons=True면 n_points==1 구간도 포함)

    반환 컬럼:
    - start_ts
    - end_ts
    - n_points: 해당 구간에 포함된 원본 ts 개수
    """
    if ts_col not in sensor_data.columns:
        raise ValueError(f"'{ts_col}' 컬럼이 없습니다. columns={list(sensor_data.columns)}")

    if len(sensor_data) < 2:
        return pd.DataFrame(columns=["start_ts", "end_ts", "n_points"])

    # `ts` 파싱 (중요)
    # - 이 데이터는 마이크로초가 있는 ts/없는 ts가 섞여 있음 (예: '...07:05:07+00:00')
    # - pandas 버전에 따라 기본 파서가 일부 형식을 NaT로 만들 수 있어
    #   `format="ISO8601"`로 파싱.
    raw = sensor_data[ts_col].astype(str).str.strip()
    normalized = raw.str.replace(" ", "T", n=1, regex=False)
    ts = pd.to_datetime(normalized, utc=True, errors="coerce", format="ISO8601")

    # NaT 없애기.
    ts = ts.dropna().reset_index(drop=True)
    if len(ts) < 2:
        return pd.DataFrame(columns=["start_ts", "end_ts", "n_points"])

    # 인접한 두 ts 간 차이를 초 단위로 구하고, 반올림(half-up)해서 정수 초로 만든다.
    delta_sec = ts.diff().dt.total_seconds().to_numpy()[1:]
    rounded = np.floor(delta_sec + 0.5).astype(int)

    valid_edge = rounded <= int(threshold_seconds)  # edge i connects ts[i] -> ts[i+1]

    ranges: List[Tuple[pd.Timestamp, pd.Timestamp, int]] = []
    start_edge: int | None = None

    for i, ok in enumerate(valid_edge):
        if ok and start_edge is None:
            start_edge = i
        if (not ok) and start_edge is not None:
            start_i = start_edge
            # ok가 마지막으로 True였던 엣지는 i-1이고, 구간의 마지막 ts는 ts[i]가 된다.
            end_i = i
            n_points = (end_i - start_i) + 1
            ranges.append((ts.iloc[start_i], ts.iloc[end_i], n_points))
            start_edge = None

    if start_edge is not None:
        start_i = start_edge
        end_i = len(ts) - 1
        n_points = (end_i - start_i) + 1
        ranges.append((ts.iloc[start_i], ts.iloc[end_i], n_points))

    return pd.DataFrame(ranges, columns=["start_ts", "end_ts", "n_points"])

def get_threshold_seconds(df: pd.DataFrame, *, default: int = THRESHOLD_SECONDS_SENSOR) -> int:
    """
    threshold 값 결정:
    - sensor_type == 'agsmotor_green' 이면 motor threshold
    - 그 외는 일반 센서 threshold
    """
    if "sensor_type" in df.columns and len(df) > 0:
        st = str(df["sensor_type"].iloc[0])
        if st == "agsmotor_green":
            return THRESHOLD_SECONDS_MOTOR
        return THRESHOLD_SECONDS_SENSOR
    return int(default)


def build_valid_time_ranges_for_all_csv(
    *,
    src_root: Path,
    out_root: Path,
    glob: str = "*.csv",
    ts_col: str = "ts",
    threshold_seconds: Optional[int] = None,
    overwrite: bool = False,
) -> None:
    """
    src_root 아래 모든 CSV를 읽어서 유효 시간 구간을 계산한 뒤,
    out_root 아래에 동일한 폴더 구조로 저장한다.

    출력 파일명 규칙:
    - 원본 파일명 그대로 사용하되, 확장자를 `.valid_ranges.csv`로 바꾼다.
      예) A/B/C.csv -> out_root/A/B/C.valid_ranges.csv
    """
    if not src_root.exists() or not src_root.is_dir():
        raise ValueError(f"src_root가 없거나 디렉토리가 아닙니다: {src_root}")

    files = sorted(src_root.rglob(glob))
    if not files:
        print(f"대상 CSV 없음: {src_root} 아래 {glob}")
        return

    ok = 0
    skipped = 0
    fail = 0

    for i, src_csv in enumerate(files, start=1):
        rel = src_csv.relative_to(src_root)
        dst_csv = (out_root / rel).with_suffix(".valid_ranges.csv")

        if dst_csv.exists() and not overwrite:
            skipped += 1
            continue

        try:
            usecols = [ts_col]
            df_head = pd.read_csv(src_csv, nrows=1)
            if "sensor_type" in df_head.columns:
                usecols = ["sensor_type", ts_col]

            df = pd.read_csv(src_csv, usecols=usecols)

            thr = get_threshold_seconds(df)
            ranges = get_valid_time_ranges_for_sensor(df, threshold_seconds=thr, ts_col=ts_col)

            dst_csv.parent.mkdir(parents=True, exist_ok=True)
            ranges.to_csv(dst_csv, index=False)

            ok += 1
            if ok <= 3 or ok % 50 == 0:
                print(f"[{i}/{len(files)}] OK {rel} thr={thr} ranges={len(ranges)} -> {dst_csv}")
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(files)}] FAIL {rel}: {e}")

    print(f"Done. ok={ok}, skipped={skipped}, fail={fail}, out_root={out_root}")

def intersect_valid_time_ranges_two(
    a: pd.DataFrame,
    b: pd.DataFrame,
    *,
    start_col: str = "start_ts",
    end_col: str = "end_ts",
) -> pd.DataFrame:
    """
    두 유효구간 DataFrame의 겹치는 구간(교집합) 반환.

    입력 형식:
    - a[start_col], a[end_col]
    - b[start_col], b[end_col]

    주의:
    - 구간은 start <= end 라고 가정한다.
    - 겹침 판단은 [max(start), min(end)]에서 start < end 인 경우만 구간으로 인정한다
      (시각이 정확히 같은 한 점짜리 교집합은 기본적으로 버림)
    """
    if a.empty or b.empty:
        return pd.DataFrame(columns=[start_col, end_col])

    aa = a[[start_col, end_col]].copy()
    bb = b[[start_col, end_col]].copy()

    aa[start_col] = pd.to_datetime(aa[start_col], utc=True, errors="coerce", format="ISO8601")
    aa[end_col] = pd.to_datetime(aa[end_col], utc=True, errors="coerce", format="ISO8601")
    bb[start_col] = pd.to_datetime(bb[start_col], utc=True, errors="coerce", format="ISO8601")
    bb[end_col] = pd.to_datetime(bb[end_col], utc=True, errors="coerce", format="ISO8601")

    aa = aa.dropna().sort_values([start_col, end_col]).reset_index(drop=True)
    bb = bb.dropna().sort_values([start_col, end_col]).reset_index(drop=True)
    if aa.empty or bb.empty:
        return pd.DataFrame(columns=[start_col, end_col])

    i = 0
    j = 0
    out: List[Tuple[pd.Timestamp, pd.Timestamp]] = []

    while i < len(aa) and j < len(bb):
        a_s = aa.at[i, start_col]
        a_e = aa.at[i, end_col]
        b_s = bb.at[j, start_col]
        b_e = bb.at[j, end_col]

        s = a_s if a_s >= b_s else b_s
        e = a_e if a_e <= b_e else b_e

        if s < e:
            out.append((s, e))

        # 더 빨리 끝나는 구간을 전진
        if a_e <= b_e:
            i += 1
        else:
            j += 1

    return pd.DataFrame(out, columns=[start_col, end_col])


def merge_valid_time_ranges(
    *,
    valid_root: Path = Path("valid_time_ranges"),
    glob: str = "*.valid_ranges.csv",
    start_col: str = "start_ts",
    end_col: str = "end_ts",
    save_path: Optional[Path] = None,
) -> pd.DataFrame:
    """
    valid_root 아래의 모든 `*.valid_ranges.csv`를 읽고,
    "모든 파일에 대해 공통으로 겹치는 구간(교집합)"만 남긴 결과를 반환한다.

    동작 방식:
    - 첫 번째 파일의 구간을 기준으로 시작
    - 이후 파일들과 `intersect_valid_time_ranges_two()`를 반복 적용해서 교집합을 누적
    - 중간에 교집합이 비면 즉시 종료

    save_path를 주면 결과를 CSV로 저장한다.
    """
    if not valid_root.exists() or not valid_root.is_dir():
        raise ValueError(f"valid_root가 없거나 디렉토리가 아닙니다: {valid_root}")

    files = sorted(valid_root.rglob(glob))
    if not files:
        raise ValueError(f"대상 파일 없음: {valid_root} 아래 {glob}")

    merged: Optional[pd.DataFrame] = None

    for idx, p in enumerate(files):
        df = pd.read_csv(p)
        if start_col not in df.columns or end_col not in df.columns:
            raise ValueError(f"필수 컬럼 누락: {p} columns={list(df.columns)}")

        cur = df[[start_col, end_col]].copy()
        if merged is None:
            merged = cur
            continue

        merged = intersect_valid_time_ranges_two(
            merged, cur, start_col=start_col, end_col=end_col
        )
        if merged.empty:
            break

    assert merged is not None
    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(save_path, index=False)
    return merged

def analyze_and_visualize_merged_valid_ranges(
    merged: pd.DataFrame,
    *,
    save_png_path: Path,
    save_meta_json_path: Optional[Path] = None,
    start_col: str = "start_ts",
    end_col: str = "end_ts",
    title: str = "Merged valid time ranges (intersection)",
) -> dict:
    """
    머지(교집합) 결과를 분석하고(메타정보 산출), 시각화(PNG)까지 저장한다.

    산출 메타(예시):
    - 전체 범위(최소 start ~ 최대 end)
    - 총 유효 시간(구간 길이 합)
    - 유효 비율(총 유효 시간 / 전체 범위)
    - 구간 개수, 가장 긴 공백 등
    """
    try:
        import matplotlib as mpl
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        raise RuntimeError("시각화를 위해 matplotlib이 필요합니다. 설치: pip install matplotlib") from e

    save_png_path.parent.mkdir(parents=True, exist_ok=True)

    if merged is None or merged.empty:
        meta = {
            "segments": 0,
            "overall_start_ts": None,
            "overall_end_ts": None,
            "overall_span_seconds": 0.0,
            "valid_seconds": 0.0,
            "valid_percent_of_overall": 0.0,
            "largest_gap_seconds": 0.0,
        }
        plt.figure(figsize=(12, 2.6), dpi=160)
        plt.title(title + "\n(no intersection ranges)")
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(save_png_path)
        plt.close()
        _save_meta(meta, save_meta_json_path=save_meta_json_path)
        return meta

    df = merged[[start_col, end_col]].copy()
    df[start_col] = pd.to_datetime(df[start_col], utc=True, errors="coerce", format="ISO8601")
    df[end_col] = pd.to_datetime(df[end_col], utc=True, errors="coerce", format="ISO8601")
    df = df.dropna().sort_values([start_col, end_col]).reset_index(drop=True)
    if df.empty:
        meta = {
            "segments": 0,
            "overall_start_ts": None,
            "overall_end_ts": None,
            "overall_span_seconds": 0.0,
            "valid_seconds": 0.0,
            "valid_percent_of_overall": 0.0,
            "largest_gap_seconds": 0.0,
        }
        plt.figure(figsize=(12, 2.6), dpi=160)
        plt.title(title + "\n(no parsable ranges)")
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(save_png_path)
        plt.close()
        _save_meta(meta, save_meta_json_path=save_meta_json_path)
        return meta

    # 메타 계산을 위해 겹치거나 붙어있는 구간은 합친다(중복 시간 방지).
    norm = df.copy()
    norm = norm.sort_values([start_col, end_col]).reset_index(drop=True)
    merged_starts: List[pd.Timestamp] = []
    merged_ends: List[pd.Timestamp] = []
    cur_s = norm.at[0, start_col]
    cur_e = norm.at[0, end_col]
    for k in range(1, len(norm)):
        s = norm.at[k, start_col]
        e = norm.at[k, end_col]
        if s <= cur_e:  # 겹침/붙음 -> 확장
            if e > cur_e:
                cur_e = e
        else:
            merged_starts.append(cur_s)
            merged_ends.append(cur_e)
            cur_s, cur_e = s, e
    merged_starts.append(cur_s)
    merged_ends.append(cur_e)

    overall_start = merged_starts[0]
    overall_end = merged_ends[-1]
    overall_span = (overall_end - overall_start).total_seconds()
    valid_seconds = float(sum((e - s).total_seconds() for s, e in zip(merged_starts, merged_ends)))
    valid_percent = (valid_seconds / overall_span * 100.0) if overall_span > 0 else 0.0

    # 가장 긴 공백(무효 시간)
    largest_gap = 0.0
    for s_prev, e_prev, s_next in zip(merged_starts, merged_ends, merged_starts[1:]):
        gap = (s_next - e_prev).total_seconds()
        if gap > largest_gap:
            largest_gap = float(gap)

    meta = {
        "segments": len(merged_starts),
        "overall_start_ts": overall_start.isoformat(),
        "overall_end_ts": overall_end.isoformat(),
        "overall_span_seconds": float(overall_span),
        "valid_seconds": float(valid_seconds),
        "valid_percent_of_overall": float(valid_percent),
        "largest_gap_seconds": float(largest_gap),
    }

    # 한글 깨짐 방지(가능한 폰트 우선)
    mpl.rcParams["font.family"] = ["AppleGothic", "Malgun Gothic", "DejaVu Sans"]
    mpl.rcParams["axes.unicode_minus"] = False

    # matplotlib 날짜 축으로 변환
    starts = mdates.date2num(pd.Series(merged_starts).dt.tz_convert("UTC").dt.to_pydatetime())
    ends = mdates.date2num(pd.Series(merged_ends).dt.tz_convert("UTC").dt.to_pydatetime())
    widths = (ends - starts)

    fig_h = 2.8
    fig_w = 14
    plt.figure(figsize=(fig_w, fig_h), dpi=170)
    ax = plt.gca()

    # y=0 한 줄에 broken_barh로 구간 표시
    bars = [(s, w) for s, w in zip(starts, widths) if w > 0]
    ax.broken_barh(bars, (0.25, 0.5), facecolors="#2E6F9E")

    ax.set_yticks([])
    ax.set_ylim(0, 1)
    ax.set_title(
        f"{title}\n"
        f"segments={len(bars)}, valid={meta['valid_percent_of_overall']:.2f}%"
    )

    # x축 포맷
    ax.xaxis_date()
    locator = mdates.AutoDateLocator(minticks=5, maxticks=12)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.grid(axis="x", alpha=0.25)

    # 전체 범위 조금 여유
    xmin = min(starts)
    xmax = max(ends)
    pad = (xmax - xmin) * 0.02 if xmax > xmin else 0.01
    ax.set_xlim(xmin - pad, xmax + pad)

    plt.tight_layout()
    plt.savefig(save_png_path)
    plt.close()
    _save_meta(meta, save_meta_json_path=save_meta_json_path)
    return meta


def _save_meta(
    meta: dict,
    *,
    save_meta_json_path: Optional[Path],
) -> None:
    if save_meta_json_path is not None:
        save_meta_json_path.parent.mkdir(parents=True, exist_ok=True)
        save_meta_json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="CSV에서 유효 시간 구간(start/end)을 출력합니다.")
    ap.add_argument(
        "--all",
        action="store_true",
        help="csv_data_with_sensor_type 아래 모든 CSV를 처리해서 valid_time_ranges에 저장",
    )
    ap.add_argument("--ts-col", default="ts", help="timestamp 컬럼명 (default: ts)")
    ap.add_argument("--src-root", default="2_csv_data_with_sensor_type", help="--all 입력 루트")
    ap.add_argument("--out-root", default="3_valid_time_ranges", help="--all 출력 루트")
    ap.add_argument("--glob", default="*.csv", help="--all 대상 패턴")
    ap.add_argument("--overwrite", action="store_true", help="--all 결과 덮어쓰기")
    args = ap.parse_args()

    if args.all:
        build_valid_time_ranges_for_all_csv(
            src_root=Path(args.src_root),
            out_root=Path(args.out_root),
            glob=args.glob,
            ts_col=args.ts_col,
            overwrite=args.overwrite,
        )
        merged_path = Path(args.out_root) / "_merged_all.valid_ranges.csv"
        merged = merge_valid_time_ranges(
            valid_root=Path(args.out_root),
            save_path=merged_path,
        )
        merged_png = Path(args.out_root) / "_merged_all.valid_ranges.png"
        merged_meta_json = Path(args.out_root) / "_merged_all.valid_ranges.meta.json"
        analyze_and_visualize_merged_valid_ranges(
            merged,
            save_png_path=merged_png,
            save_meta_json_path=merged_meta_json,
            title="모든 센서 공통 유효구간(교집합)",
        )
        print(f"Merged(common intersection) ranges={len(merged)} -> {merged_path}")
        return 0

    if not args.csv:
        ap.error("--all 이 아니면 CSV 경로를 인자로 주세요. 예: python3 3_get_validate_area.py path/to/file.csv")

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV 파일이 없습니다: {csv_path}")

    df = pd.read_csv(csv_path)
    thr = int(args.threshold) if args.threshold is not None else get_threshold_seconds(df)
    res = get_valid_time_ranges_for_sensor(
        df, threshold_seconds=thr, ts_col=args.ts_col
    )

    # 보기 좋게 전체 출력
    with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", 200):
        print(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


