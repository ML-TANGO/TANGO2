# 합쳐진 데이터들을, 소수점 첫째 자리, 혹은 정수로 반올림
# 그리고 재배하는 품목, 매뉴얼 등을 여기서 조합함. (현재 해당 데이터가 DB에 없으므로, facility_meta.csv를 직접 만들어서 사용중)

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_INPUT = "6_merged_data/time_sync_valid_data_merged_no_na_kma.csv"
DEFAULT_FACILITY_META = "6_merged_data/facility_meta.csv"
DEFAULT_OUTPUT = "7_merged_data_postprocessed/time_sync_valid_data_merged_no_na_post.csv"

WIND_COLS = ["Out_anemometer_wind_speed", "Out_anemometer_wind_direction"]
META_MERGE_COLS = [
    "facility_id",
    "planting_date",
    "plant_name",
    "manual",
    "min_accumulated_temperature",
    "max_accumulated_temperature",
]
DEFAULT_GROWING_DEGREE_DAYS_BASE_C = 10.0


def drop_anemometer_wind_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Out_anemometer_wind_speed, Out_anemometer_wind_direction 가 있으면 제거한다."""
    out = df.copy()
    to_drop = [c for c in WIND_COLS if c in out.columns]
    return out.drop(columns=to_drop, errors="ignore")


def load_facility_meta(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(
            f"시설 메타 CSV가 없습니다: {p}\n"
            "필수 컬럼: facility_id, planting_date\n"
            "선택: plant_name, manual, min_accumulated_temperature, max_accumulated_temperature"
        )
    meta = pd.read_csv(p)
    need = {"facility_id", "planting_date"}
    miss = need - set(meta.columns)
    if miss:
        raise ValueError(f"시설 메타 CSV에 컬럼이 없습니다: {sorted(miss)}")
    meta = meta.copy()
    meta["planting_date"] = pd.to_datetime(meta["planting_date"], utc=True).dt.normalize()
    if "plant_name" not in meta.columns:
        meta["plant_name"] = ""
    else:
        meta["plant_name"] = meta["plant_name"].fillna("").astype(str)
    if "manual" not in meta.columns:
        meta["manual"] = ""
    else:
        meta["manual"] = meta["manual"].fillna("").astype(str)
    if "min_accumulated_temperature" not in meta.columns:
        meta["min_accumulated_temperature"] = np.nan
    else:
        meta["min_accumulated_temperature"] = pd.to_numeric(
            meta["min_accumulated_temperature"], errors="coerce"
        )
    if "max_accumulated_temperature" not in meta.columns:
        meta["max_accumulated_temperature"] = np.nan
    else:
        meta["max_accumulated_temperature"] = pd.to_numeric(
            meta["max_accumulated_temperature"], errors="coerce"
        )
    return meta

def compute_growing_degree_days_by_facility(
    df: pd.DataFrame,
    *,
    temp_col: str,
    tmin_col: str = "min_accumulated_temperature",
    tmax_col: str = "max_accumulated_temperature",
) -> pd.Series:
    """
    시설별 누적 growing_degree_days를 계산한다.
    growing_degree_days 증가량(분 단위): max(0, min(T, Tmax) - Tmin) * dt_day
    """
    need = ["facility_id", "ts", temp_col, tmin_col, tmax_col]
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise ValueError(f"growing_degree_days 계산에 필요한 컬럼이 없습니다: {miss}")

    work = df[need].copy()
    work[temp_col] = pd.to_numeric(work[temp_col], errors="coerce")
    work[tmin_col] = pd.to_numeric(work[tmin_col], errors="coerce")
    work[tmax_col] = pd.to_numeric(work[tmax_col], errors="coerce")
    work = work.sort_values(["facility_id", "ts"], kind="mergesort")

    growing_degree_days_parts: list[pd.Series] = []
    for _, g in work.groupby("facility_id", sort=False):
        g = g.copy()
        ts = pd.to_datetime(g["ts"], format="ISO8601", utc=True)
        dt_s = ts.diff().dt.total_seconds().to_numpy(dtype=float)
        
        # 첫 행은, 이전 데이터와의 시간 차이가 1분이라고 가정
        if len(dt_s) > 0:
            dt_s[0] = 60.0
            
        dt_day = dt_s / 86400.0

        t = g[temp_col].to_numpy(dtype=float)
        tmin = g[tmin_col].to_numpy(dtype=float)
        tmax = g[tmax_col].to_numpy(dtype=float)

        # 온도 범위 클리핑 후 Tmin 기준 누적
        clipped_t = np.minimum(t, tmax)
        eff = np.maximum(0.0, clipped_t - tmin)
        eff = np.nan_to_num(eff, nan=0.0)
        inc = eff * dt_day
        growing_degree_days_parts.append(pd.Series(np.cumsum(inc), index=g.index))

    if not growing_degree_days_parts:
        return pd.Series(index=df.index, dtype=float)
    combined = pd.concat(growing_degree_days_parts)
    return combined.reindex(df.index)


def replace_facility_with_metadata(
    df: pd.DataFrame,
    facility_meta: pd.DataFrame,
    *,
    temp_col: str = "In_thermohygro_temp",
    growing_degree_days_base_c: float = DEFAULT_GROWING_DEGREE_DAYS_BASE_C,
) -> pd.DataFrame:
    """
    facility_id 를 제거하고, 동일 키로 메타를 붙인 뒤
    days_after_planting, plant_name, manual,
    growing_degree_days 컬럼을 채운다.

    - days_after_planting: ts(UTC 일) - planting_date(UTC 일)
    """
    if "facility_id" not in df.columns:
        raise ValueError("입력 df 에 'facility_id' 컬럼이 없습니다.")
    if "ts" not in df.columns:
        raise ValueError("입력 df 에 'ts' 컬럼이 없습니다.")

    out = df.copy()
    out["ts"] = pd.to_datetime(out["ts"], format="ISO8601", utc=True)
    meta = facility_meta[META_MERGE_COLS].drop_duplicates(subset=["facility_id"], keep="first")

    merged = out.merge(meta, on="facility_id", how="left")
    unknown = merged["planting_date"].isna()
    if unknown.any():
        bad = merged.loc[unknown, "facility_id"].dropna().unique().tolist()
        raise ValueError(f"시설 메타에 없는 facility_id 가 있습니다: {bad[:20]}")

    ts_day = merged["ts"].dt.normalize()
    merged["days_after_planting"] = (ts_day - merged["planting_date"]).dt.days
    merged["growing_degree_days"] = compute_growing_degree_days_by_facility(merged, temp_col=temp_col)

    merged = merged.drop(
        columns=[
            "planting_date",
            "min_accumulated_temperature",
            "max_accumulated_temperature",
        ]
    )

    head = [
        "ts",
        "site_id",
        "days_after_planting",
        "plant_name",
        "growing_degree_days",
        "manual",
    ]
    tail = [c for c in merged.columns if c not in head]
    return merged[head + tail].copy()


def post_process_qa_dataframe(
    df: pd.DataFrame,
    facility_meta: pd.DataFrame,
    *,
    temp_col: str = "In_thermohygro_temp",
    growing_degree_days_base_c: float = DEFAULT_GROWING_DEGREE_DAYS_BASE_C,
) -> pd.DataFrame:
    x = drop_anemometer_wind_columns(df)
    return replace_facility_with_metadata(x, facility_meta, temp_col=temp_col, growing_degree_days_base_c=growing_degree_days_base_c)


def round_numeric_columns(df: pd.DataFrame, *, decimals: int) -> pd.DataFrame:
    """ts·문자열 컬럼은 유지하고, 숫자형 컬럼만 반올림한 복사본을 반환한다."""
    out = df.copy()
    for c in out.columns:
        if c == "ts":
            continue
        s = out[c]
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            out[c] = pd.to_numeric(s, errors="coerce").round(decimals)
    return out


def save_round0_csv_with_si_ss_round1(
    df: pd.DataFrame, path: str | Path, *, si_col: str = "si", ss_col: str = "ss"
) -> pd.DataFrame:
    """
    round0 저장 규칙:
    - 기본: 숫자형 컬럼은 정수(0자리) 반올림
    - 예외: si, ss 컬럼은 round1처럼 소수 1자리로 저장

    주의: pandas의 float_format은 모든 float에 동일 적용되므로,
    si/ss만 소수 1자리로 유지하려면 해당 컬럼을 문자열로 포맷팅해서 저장한다.
    """
    out = round_numeric_columns(df, decimals=0)

    for col in (si_col, ss_col):
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors="coerce").round(1)
            # 1자리 고정 포맷. NaN은 빈칸으로 저장되도록 처리
            out[col] = vals.map(lambda x: "" if pd.isna(x) else f"{x:.1f}")

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return out


def _derived_round_paths(base: Path) -> tuple[Path, Path]:
    """예: foo_post.csv -> foo_post_round0.csv, foo_post_round1.csv"""
    return (
        base.with_name(f"{base.stem}_round0{base.suffix}"),
        base.with_name(f"{base.stem}_round1{base.suffix}"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "QA CSV 에서 풍속/풍향 제거, facility_id 대신 "
            "정식일수·작물명·growing_degree_days·매뉴얼 컬럼 부착 후 저장."
        )
    )
    parser.add_argument(
        "input_csv",
        nargs="?",
        default=DEFAULT_INPUT,
        help=f"입력 CSV (기본: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--facility-meta",
        default=DEFAULT_FACILITY_META,
        help=f"시설 메타 CSV (기본: {DEFAULT_FACILITY_META})",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=DEFAULT_OUTPUT,
        help=(
            f"원본(전체 정밀도) 출력 CSV; 같은 폴더에 "
            f"{{stem}}_round0.csv(정수)·{{stem}}_round1.csv(소수1자리)도 저장 (기본: {DEFAULT_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--growing_degree_days-base",
        type=float,
        default=DEFAULT_GROWING_DEGREE_DAYS_BASE_C,
        help=f"적산 기준 온도 °C (기본 {DEFAULT_GROWING_DEGREE_DAYS_BASE_C})",
    )
    parser.add_argument(
        "--temp-col",
        default="In_thermohygro_temp",
        help="growing_degree_days 계산에 사용할 온도 컬럼명",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.input_csv)
    meta = load_facility_meta(args.facility_meta)
    out_df = post_process_qa_dataframe(
        df,
        meta,
        temp_col=args.temp_col,
        growing_degree_days_base_c=args.growing_degree_days_base,
    )
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    print(f"saved: {out_path}")

    path0, path1 = _derived_round_paths(out_path)
    round0_df = save_round0_csv_with_si_ss_round1(out_df, path0)
    round0_df.to_csv(path0, index=False)
    round_numeric_columns(out_df, decimals=1).to_csv(
        path1, index=False, float_format="%.1f"
    )
    print(f"saved: {path0}")
    print(f"saved: {path1}")


if __name__ == "__main__":
    main()
