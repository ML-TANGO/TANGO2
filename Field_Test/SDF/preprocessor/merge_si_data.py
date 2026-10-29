from __future__ import annotations

import pandas as pd


# 병합 데이터 시각 변환
def _parse_merged_ts(df: pd.DataFrame) -> pd.Series:
    if "ts" not in df.columns:
        raise ValueError("merged CSV에 'ts' 컬럼이 없습니다.")
    ts = pd.to_datetime(df["ts"])
    if ts.isna().any():
        raise ValueError("merged CSV의 ts 파싱 실패 값이 있습니다.")
    return ts


# 일사 데이터 시각 변환
def _parse_kma_ts(df: pd.DataFrame, *, tz: str) -> pd.Series:
    if "YYMMDDHHMI" not in df.columns:
        raise ValueError("KMA CSV에 'YYMMDDHHMI' 컬럼이 없습니다.")
    raw = df["YYMMDDHHMI"].astype(str).str.strip()
    dt = pd.to_datetime(raw, format="%Y%m%d%H%M", errors="coerce")
    if dt.isna().any():
        raise ValueError("KMA CSV의 YYMMDDHHMI 파싱 실패 값이 있습니다.")
    dt = dt.dt.tz_localize(tz).dt.tz_convert("Asia/Seoul")
    return dt


# 일사 데이터 결측 값 처리
def _coerce_missing_kma_values(kma: pd.DataFrame) -> pd.DataFrame:
    out = kma.copy()
    for c in out.columns:
        if c in {"YYMMDDHHMI"}:
            continue
        col_values = pd.to_numeric(out[c], errors="coerce")
        col_values = col_values.mask(col_values.isin([-9, -99, -999, -99.0, -9.0]))
        out[c] = col_values
    return out


# 일사 데이터 1분 단위 시간 보정
def resample_kma_to_minute(
    kma_df: pd.DataFrame,
    *,
    start_ts_kst: pd.Timestamp,
    end_ts_kst: pd.Timestamp,
) -> pd.DataFrame:
    if kma_df.empty:
        return kma_df.copy()

    kma = kma_df.copy()
    kma = kma.dropna(subset=["ts"])
    kma["ts"] = pd.to_datetime(kma["ts"], utc=True, errors="coerce").dt.tz_convert("Asia/Seoul")
    kma = kma.sort_values("ts").drop_duplicates(subset=["ts"], keep="last")
    kma = kma.set_index("ts")

    minute_index = pd.date_range(
        start=start_ts_kst.floor("min"),
        end=end_ts_kst.floor("min"),
        freq="min",
        tz="Asia/Seoul",
    )
    expanded_index = kma.index.union(minute_index)
    expanded = kma.reindex(expanded_index)
    expanded = expanded[~expanded.index.isna()]
    expanded = expanded.sort_index()
    numeric_cols = [c for c in expanded.columns if pd.api.types.is_numeric_dtype(expanded[c])]
    if numeric_cols:
        expanded[numeric_cols] = expanded[numeric_cols].interpolate(
            method="time", limit_direction="both"
        )
    expanded = expanded.reindex(minute_index)
    return expanded


# 일사 데이터 병합
def merge_kma_into_merged_minute_data(
    merged_df: pd.DataFrame,
    kma_hourly_df: pd.DataFrame,
    *,
    kma_tz: str,
) -> pd.DataFrame:
    merged = merged_df.copy()
    merged_ts = _parse_merged_ts(merged)

    kma = kma_hourly_df.copy()
    kma = _coerce_missing_kma_values(kma)
    kma["ts"] = _parse_kma_ts(kma, tz=kma_tz)

    need = {"SI", "SS"}
    missing = sorted(need - set(kma.columns))
    if missing:
        raise ValueError(f"KMA CSV에 필요한 컬럼이 없습니다: {missing}")
    kma = kma[["ts", "SI", "SS"]].rename(columns={"SI": "si", "SS": "ss"})

    kma_min = resample_kma_to_minute(
        kma,
        start_ts_kst=merged_ts.min(),
        end_ts_kst=merged_ts.max(),
    ).reset_index().rename(columns={"index": "ts"})

    merged["ts"] = merged_ts
    out = merged.merge(kma_min, on="ts", how="left")
    out[["si", "ss"]] = out[["si", "ss"]].fillna(0)
    return out
