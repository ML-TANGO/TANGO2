import pandas as pd


# 유효 구간 내 1분 단위 시간 보정 및 정렬
def resample_to_minute(df: pd.DataFrame, valid_time_range_df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or valid_time_range_df.empty:
        return df.iloc[0:0].copy()

    df = df.copy()

    valid_ranges = valid_time_range_df.copy()

    all_minutes = []
    for _, row in valid_ranges.iterrows():
        start_ts = row["start_ts"]
        end_ts = row["end_ts"]

        start_floor = start_ts.replace(second=0, microsecond=0)
        if start_ts > start_floor:
            start_min = start_floor + pd.Timedelta(minutes=1)
        else:
            start_min = start_floor

        end_floor = end_ts.replace(second=0, microsecond=0)
        end_min = end_floor

        if start_min <= end_min:
            minute_range = pd.date_range(start=start_min, end=end_min, freq="min", tz="Asia/Seoul")
            all_minutes.append(minute_range)

    if not all_minutes:
        return df.iloc[0:0].copy()

    target_minutes = pd.DatetimeIndex(
        sorted({ts for idx in all_minutes for ts in idx})
    )

    min_ts = df["ts"].min()
    max_ts = df["ts"].max()
    target_minutes = target_minutes[(target_minutes >= min_ts) & (target_minutes <= max_ts)]

    if len(target_minutes) == 0:
        return df.iloc[0:0].copy()

    df = df.sort_values("ts").set_index("ts")

    exclude_cols = {
        "facility_id",
        "probe",
        "sensor_id",
        "sensor_type",
        "ts",
        "site_id",
    }

    cols = list(df.columns)
    value_cols = [c for c in cols if c not in exclude_cols]

    numeric_cols = [c for c in value_cols if pd.api.types.is_numeric_dtype(df[c])]
    other_cols = [c for c in cols if c not in numeric_cols]

    expanded_index = df.index.union(target_minutes)
    df_expanded = df.reindex(expanded_index)

    if numeric_cols:
        df_expanded[numeric_cols] = df_expanded[numeric_cols].interpolate(
            method="time", limit_direction="both"
        )
    if other_cols:
        df_expanded.loc[:, other_cols] = df.iloc[0][other_cols].to_numpy()

    result = df_expanded.loc[target_minutes].reset_index().rename(columns={"index": "ts"})


    return result
