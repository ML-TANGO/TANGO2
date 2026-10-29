from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

META_MERGE_COLS = [
    "facility_id",
    "planting_date",
    "plant_name",
    "manual",
    "min_accumulated_temperature",
    "max_accumulated_temperature",
]
DEFAULT_GROWING_DEGREE_DAYS_BASE_C = 10.0


# 작물 정보 결합 및 정식 후 일수 계산
def replace_facility_with_metadata(
    df: pd.DataFrame,
    facility_meta: pd.DataFrame,
    *,
    temp_col: str = "thermohygro_in_temp",
    growing_degree_days_base_c: float = DEFAULT_GROWING_DEGREE_DAYS_BASE_C,
) -> pd.DataFrame:
    if "facility_id" not in df.columns:
        raise ValueError("입력 df 에 'facility_id' 컬럼이 없습니다.")
    if "ts" not in df.columns:
        raise ValueError("입력 df 에 'ts' 컬럼이 없습니다.")

    out = df.copy()
    meta = facility_meta[META_MERGE_COLS].drop_duplicates(subset=["facility_id"], keep="first")

    merged = out.merge(meta, on="facility_id", how="left")
    missing_mask = merged["planting_date"].isna()
    if missing_mask.any():
        missing_facility_ids = merged.loc[missing_mask, "facility_id"].dropna().unique().tolist()
        raise ValueError(f"시설 메타에 없는 facility_id 가 있습니다: {missing_facility_ids[:20]}")

    ts_day = merged["ts"].dt.normalize()
    merged["days_after_planting"] = (ts_day - merged["planting_date"]).dt.days

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
        "manual",
    ]
    tail = [c for c in merged.columns if c not in head]
    return merged[head + tail].copy()


# 작물 정보 결합 실행
def post_process_qa_dataframe(
    df: pd.DataFrame,
    facility_meta: pd.DataFrame,
    *,
    temp_col: str = "thermohygro_in_temp",
    growing_degree_days_base_c: float = DEFAULT_GROWING_DEGREE_DAYS_BASE_C,
) -> pd.DataFrame:
    return replace_facility_with_metadata(df, facility_meta, temp_col=temp_col, growing_degree_days_base_c=growing_degree_days_base_c)
