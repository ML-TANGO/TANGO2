from __future__ import annotations

from typing import List, Tuple

import pandas as pd
import numpy as np

THRESHOLD_SECONDS_MOTOR = 130
THRESHOLD_SECONDS_SENSOR = 120


# 센서별 유효 구간 추출 (수집 간격이 기준 이하인 연속 구간)
def get_valid_time_ranges_for_sensor(
    sensor_data: pd.DataFrame,
    *,
    threshold_seconds: int,
    ts_col: str = "ts"
) -> pd.DataFrame:
    if ts_col not in sensor_data.columns:
        raise ValueError(f"'{ts_col}' 컬럼이 없습니다. columns={list(sensor_data.columns)}")

    if len(sensor_data) < 2:
        return pd.DataFrame(columns=["start_ts", "end_ts", "n_points"])

    ts = pd.to_datetime(sensor_data[ts_col]).dropna().reset_index(drop=True)
    if len(ts) < 2:
        return pd.DataFrame(columns=["start_ts", "end_ts", "n_points"])

    delta_sec = ts.diff().dt.total_seconds().to_numpy()[1:]
    rounded = np.floor(delta_sec + 0.5).astype(int)

    valid_edge = rounded <= int(threshold_seconds)

    ranges: List[Tuple[pd.Timestamp, pd.Timestamp, int]] = []
    start_edge: int | None = None

    for i, ok in enumerate(valid_edge):
        if ok and start_edge is None:
            start_edge = i
        if (not ok) and start_edge is not None:
            start_i = start_edge
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


# 센서 유형별 유효 구간 판정 기준 간격 조회
def get_threshold_seconds(df: pd.DataFrame, *, default: int = THRESHOLD_SECONDS_SENSOR) -> int:
    if "sensor_type" in df.columns and len(df) > 0:
        st = str(df["sensor_type"].iloc[0])
        if st == "agsmotor_green":
            return THRESHOLD_SECONDS_MOTOR
        return THRESHOLD_SECONDS_SENSOR
    return int(default)


# 두 유효 구간의 공통 구간 추출
def intersect_valid_time_ranges_two(
    a: pd.DataFrame,
    b: pd.DataFrame,
    *,
    start_col: str = "start_ts",
    end_col: str = "end_ts",
) -> pd.DataFrame:
    if a.empty or b.empty:
        return pd.DataFrame(columns=[start_col, end_col])

    df_a = a[[start_col, end_col]].copy()
    df_b = b[[start_col, end_col]].copy()

    df_a = df_a.dropna().sort_values([start_col, end_col]).reset_index(drop=True)
    df_b = df_b.dropna().sort_values([start_col, end_col]).reset_index(drop=True)
    if df_a.empty or df_b.empty:
        return pd.DataFrame(columns=[start_col, end_col])

    idx_a = 0
    idx_b = 0
    overlaps: List[Tuple[pd.Timestamp, pd.Timestamp]] = []

    while idx_a < len(df_a) and idx_b < len(df_b):
        start_a = df_a.at[idx_a, start_col]
        end_a   = df_a.at[idx_a, end_col]
        start_b = df_b.at[idx_b, start_col]
        end_b   = df_b.at[idx_b, end_col]

        overlap_start = start_a if start_a >= start_b else start_b
        overlap_end   = end_a   if end_a   <= end_b   else end_b

        if overlap_start < overlap_end:
            overlaps.append((overlap_start, overlap_end))

        if end_a <= end_b:
            idx_a += 1
        else:
            idx_b += 1

    return pd.DataFrame(overlaps, columns=[start_col, end_col])
