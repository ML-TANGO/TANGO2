import pandas as pd
from pathlib import Path


def resample_to_minute(df: pd.DataFrame, valid_time_range_df: pd.DataFrame) -> pd.DataFrame:
    """
    valid_time_range_df 에 정의된 구간 안에서,
    각 분의 00초(ts 의 초, 마이크로초가 0) 시점 값들을
    원본 df 의 데이터를 이용해 선형보간하여 생성한다.

    - df            : 센서 원시 데이터 (ts 컬럼 필수)
    - valid_time_range_df : start_ts, end_ts 컬럼을 가진 유효 시간 구간 정보
    """
    if df.empty or valid_time_range_df.empty:
        return df.iloc[0:0].copy()

    # ts / start_ts / end_ts 를 datetime 으로 통일
    df = df.copy()
    # ts 형식이 '...+00:00', '...000+00:00' 등 섞여 있어서 ISO8601/mixed 로 파싱
    df["ts"] = pd.to_datetime(df["ts"], format="ISO8601", utc=True)

    vtr = valid_time_range_df.copy()
    vtr["start_ts"] = pd.to_datetime(vtr["start_ts"], format="ISO8601", utc=True)
    vtr["end_ts"] = pd.to_datetime(vtr["end_ts"], format="ISO8601", utc=True)

    # 각 valid range 안에다, "분 단위 00초" 타임스탬프 생성
    all_minutes = []
    for _, row in vtr.iterrows():
        start_ts = row["start_ts"]
        end_ts = row["end_ts"]

        # 시작/끝을 분단위로 정리
        start_floor = start_ts.replace(second=0, microsecond=0)
        if start_ts > start_floor:
            start_min = start_floor + pd.Timedelta(minutes=1)
        else:
            start_min = start_floor

        end_floor = end_ts.replace(second=0, microsecond=0)
        end_min = end_floor

        if start_min <= end_min:
            rng = pd.date_range(start=start_min, end=end_min, freq="min", tz="UTC")
            all_minutes.append(rng)

    if not all_minutes:
        return df.iloc[0:0].copy()

    # 여러 DatetimeIndex 들을 하나로 합쳐
    target_minutes = pd.DatetimeIndex(
        sorted({ts for idx in all_minutes for ts in idx})
    )

    # 원본 데이터의 ts 범위를 벗어나는 분은 제외
    min_ts = df["ts"].min()
    max_ts = df["ts"].max()
    target_minutes = target_minutes[(target_minutes >= min_ts) & (target_minutes <= max_ts)]

    if len(target_minutes) == 0:
        return df.iloc[0:0].copy()

    # 인터폴레이션 준비
    df = df.sort_values("ts").set_index("ts")

    # 계산에서 제외할 컬럼들
    exclude_cols = {
        "facility_id",
        "probe",
        "sensor_id",
        "sensor_type",
        "ts",
        "site_id",
    }

    # 실제 df 에 존재하는 컬럼만 대상으로 삼기
    cols = list(df.columns)
    value_cols = [c for c in cols if c not in exclude_cols]

    numeric_cols = [c for c in value_cols if pd.api.types.is_numeric_dtype(df[c])]
    other_cols = [c for c in cols if c not in numeric_cols]

    # 타겟 분(minute) 인덱스를 포함하도록 확장 후 시간 기반 선형보간
    expanded_index = df.index.union(target_minutes)
    df_expanded = df.reindex(expanded_index)

    if numeric_cols:
        df_expanded[numeric_cols] = df_expanded[numeric_cols].interpolate(
            method="time", limit_direction="both"
        )
    # 나머지 컬럼은 기존 df의 첫 행 데이터로 채워
    if other_cols:
        df_expanded.loc[:, other_cols] = df.iloc[0][other_cols].to_numpy()

    # 최종적으로 각 분 00초 시점만 선택
    result = df_expanded.loc[target_minutes].reset_index().rename(columns={"index": "ts"})


    # TODO 선형보간된 데이터는 1의 자리 숫자로 반올림해서 저장하자.

    return result


def main() -> None:
    base_dir = Path(__file__).resolve().parent

    valid_data_dir = base_dir / "4_valid_data"
    valid_range_path = base_dir / "3_valid_time_ranges" / "_merged_all.valid_ranges.csv"
    output_root = base_dir / "5_time_sync_valid_data"

    # 유효 시간 범위 로드
    valid_time_range_df = pd.read_csv(valid_range_path)

    # valid_data 아래 모든 csv 순회
    for csv_path in valid_data_dir.rglob("*.csv"):
        rel_path = csv_path.relative_to(valid_data_dir)
        out_path = output_root / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)

        df = pd.read_csv(csv_path)
        resampled = resample_to_minute(df, valid_time_range_df)

        resampled.to_csv(out_path, index=False)
        print(f"saved: {out_path}")


if __name__ == "__main__":
    main()

