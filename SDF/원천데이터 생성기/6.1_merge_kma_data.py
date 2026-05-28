# kma_data 폴더에 있는 특정 파일을 읽고, merged_data 폴더에 있는 time_sync_valid_data_merged_no_na 파일에, kma 데이터를 합쳐서 merged_data 폴더 내에, time_sync_valid_data_merged_no_na_kma.csv 파일을 생성하는 코드
# time_sync_valid_data_merged_no_na 데이터는 1분 단위의 데이터이며, kma 데이터는 1시간 단위의 데이터임. kma 데이터는 선형 보간으로 처리함
# 
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

DEFAULT_MERGED_INPUT = "6_merged_data/time_sync_valid_data_merged_no_na.csv"
DEFAULT_KMA_INPUT = "kma_data/kma_181_20260211_20260511.csv"
DEFAULT_OUTPUT = "6_merged_data/time_sync_valid_data_merged_no_na_kma.csv"


def _parse_merged_ts(df: pd.DataFrame) -> pd.Series:
    if "ts" not in df.columns:
        raise ValueError("merged CSV에 'ts' 컬럼이 없습니다.")
    ts = pd.to_datetime(df["ts"], format="ISO8601", utc=True, errors="coerce")
    if ts.isna().any():
        raise ValueError("merged CSV의 ts 파싱 실패 값이 있습니다.")
    return ts


def _parse_kma_ts(df: pd.DataFrame, *, tz: str) -> pd.Series:
    """
    KMA 파일의 YYMMDDHHMI (예: 202602110000) 를 datetime 으로 파싱.
    tz는 원본 시간대(기본 Asia/Seoul 권장)를 의미하며, 최종 반환은 UTC로 맞춘다.
    """
    if "YYMMDDHHMI" not in df.columns:
        raise ValueError("KMA CSV에 'YYMMDDHHMI' 컬럼이 없습니다.")
    raw = df["YYMMDDHHMI"].astype(str).str.strip()
    dt = pd.to_datetime(raw, format="%Y%m%d%H%M", errors="coerce")
    if dt.isna().any():
        raise ValueError("KMA CSV의 YYMMDDHHMI 파싱 실패 값이 있습니다.")
    # 원본 시간대 -> UTC 통일
    dt = dt.dt.tz_localize(tz).dt.tz_convert("UTC")
    return dt


def _coerce_missing_kma_values(kma: pd.DataFrame) -> pd.DataFrame:
    """
    KMA 결측 표기(-9, -99 등)를 NaN으로 바꾸고 수치형으로 변환한다.
    """
    out = kma.copy()
    for c in out.columns:
        if c in {"YYMMDDHHMI"}:
            continue
        # '-', 공백 등도 포함해 숫자 변환 실패는 NaN
        s = pd.to_numeric(out[c], errors="coerce")
        # KMA 결측치 처리
        s = s.mask(s.isin([-9, -99, -999, -99.0, -9.0]))
        out[c] = s
    return out


def resample_kma_to_minute(
    kma_df: pd.DataFrame,
    *,
    start_ts_utc: pd.Timestamp,
    end_ts_utc: pd.Timestamp,
) -> pd.DataFrame:
    """
    1시간 단위 KMA 데이터를 1분 단위로 확장하고 시간 기반 선형 보간
    반환 DF는 index=ts(UTC) 를 가진다.
    """
    if kma_df.empty:
        return kma_df.copy()

    kma = kma_df.copy()
    # ts를 반드시 datetime64[ns, UTC]로 강제
    kma["ts"] = pd.to_datetime(kma["ts"], utc=True, errors="coerce")
    kma = kma.dropna(subset=["ts"])
    kma = kma.sort_values("ts").drop_duplicates(subset=["ts"], keep="last")
    kma = kma.set_index("ts")

    minute_index = pd.date_range(
        start=start_ts_utc.floor("min"),
        end=end_ts_utc.floor("min"),
        freq="min",
        tz="UTC",
    )
    expanded_index = kma.index.union(minute_index)
    expanded = kma.reindex(expanded_index)
    # datetime 인덱스만 남아있도록 보장 후 정렬
    expanded = expanded[~expanded.index.isna()]
    expanded = expanded.sort_index()
    numeric_cols = [c for c in expanded.columns if pd.api.types.is_numeric_dtype(expanded[c])]
    if numeric_cols:
        expanded[numeric_cols] = expanded[numeric_cols].interpolate(
            method="time", limit_direction="both"
        )
    expanded = expanded.reindex(minute_index)
    return expanded

def merge_kma_into_merged_minute_data(
    merged_df: pd.DataFrame,
    kma_hourly_df: pd.DataFrame,
    *,
    kma_tz: str,
) -> pd.DataFrame:
    """
    merged_df(ts=1분) 에 KMA(1시간)를 1분으로 보간 후 ts 기준으로 합친다.
    KMA는 관측소 단일 시계열이므로 ts로만 머지(모든 site/facility에 브로드캐스트).
    """
    merged = merged_df.copy()
    merged_ts = _parse_merged_ts(merged)

    kma = kma_hourly_df.copy()
    kma["ts"] = _parse_kma_ts(kma, tz=kma_tz)
    kma = _coerce_missing_kma_values(kma)

    # 요청사항: KMA는 SI, SS만 병합하고 컬럼명은 단순히 si, ss 로 한다.
    need = {"SI", "SS"}
    missing = sorted(need - set(kma.columns))
    if missing:
        raise ValueError(f"KMA CSV에 필요한 컬럼이 없습니다: {missing}")
    kma = kma[["ts", "SI", "SS"]].rename(columns={"SI": "si", "SS": "ss"})

    kma_min = resample_kma_to_minute(
        kma,
        start_ts_utc=merged_ts.min(),
        end_ts_utc=merged_ts.max(),
    ).reset_index().rename(columns={"index": "ts"})

    merged["ts"] = merged_ts
    out = merged.merge(kma_min, on="ts", how="left")

    # ts를 기존 스타일(문자열)로 되돌려 저장 안정화
    out["ts"] = out["ts"].dt.strftime("%Y-%m-%d %H:%M:%S+00:00")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "KMA(1시간) CSV를 선형보간으로 1분화하여 "
            "merged_data/time_sync_valid_data_merged_no_na.csv에 머지합니다."
        )
    )
    parser.add_argument(
        "--merged",
        default=DEFAULT_MERGED_INPUT,
        help=f"입력 merged CSV (기본: {DEFAULT_MERGED_INPUT})",
    )
    parser.add_argument(
        "--kma",
        default=DEFAULT_KMA_INPUT,
        help=f"입력 KMA CSV (기본: {DEFAULT_KMA_INPUT})",
    )
    parser.add_argument(
        "--kma-tz",
        default="Asia/Seoul",
        help="KMA YYMMDDHHMI의 원본 시간대 (기본: Asia/Seoul)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=DEFAULT_OUTPUT,
        help=f"출력 CSV (기본: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    merged_path = Path(args.merged)
    kma_path = Path(args.kma)
    if not merged_path.is_file():
        raise FileNotFoundError(f"merged CSV가 없습니다: {merged_path}")
    if not kma_path.is_file():
        raise FileNotFoundError(f"KMA CSV가 없습니다: {kma_path}")

    merged_df = pd.read_csv(merged_path)
    kma_df = pd.read_csv(kma_path)
    out = merge_kma_into_merged_minute_data(merged_df, kma_df, kma_tz=args.kma_tz)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()