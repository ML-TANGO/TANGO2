import pandas as pd


def add_diff_features(df: pd.DataFrame, columns: list[str], periods: int = 1, suffix: str = "diff") -> pd.DataFrame:
    result = df.copy()
    for col in columns:
        if col not in result.columns:
            raise ValueError(f"컬럼이 없습니다: {col}")
        result[f"{col}_{suffix}"] = result[col].diff(periods=periods)
    return result


def add_pct_change_features(
    df: pd.DataFrame, columns: list[str], periods: int = 1, suffix: str = "pct_change"
) -> pd.DataFrame:
    result = df.copy()
    for col in columns:
        if col not in result.columns:
            raise ValueError(f"컬럼이 없습니다: {col}")
        result[f"{col}_{suffix}"] = result[col].pct_change(periods=periods)
    return result


def add_rolling_features(
    df: pd.DataFrame,
    columns: list[str],
    window: int,
    stats: list[str] | None = None,
    min_periods: int | None = None,
) -> pd.DataFrame:
    if stats is None:
        stats = ["mean", "std"]

    result = df.copy()
    for col in columns:
        if col not in result.columns:
            raise ValueError(f"컬럼이 없습니다: {col}")

        rolling = result[col].rolling(window=window, min_periods=min_periods)
        for stat in stats:
            if stat == "mean":
                result[f"{col}_roll{window}_mean"] = rolling.mean()
            elif stat == "std":
                result[f"{col}_roll{window}_std"] = rolling.std()
            elif stat == "min":
                result[f"{col}_roll{window}_min"] = rolling.min()
            elif stat == "max":
                result[f"{col}_roll{window}_max"] = rolling.max()
            else:
                raise ValueError("stats는 mean|std|min|max만 지원합니다")

    return result


def add_time_features(df: pd.DataFrame, time_col: str | None = None) -> pd.DataFrame:
    result = df.copy()

    if time_col is None:
        if not isinstance(result.index, pd.DatetimeIndex):
            raise ValueError("time_col이 없으면 df.index가 DatetimeIndex여야 합니다")
        dt_index = result.index
    else:
        if time_col not in result.columns:
            raise ValueError(f"time_col이 df에 없습니다: {time_col}")
        dt_index = pd.to_datetime(result[time_col])

    if isinstance(dt_index, pd.Series):
        result["date"] = dt_index.dt.date
        result["time"] = dt_index.dt.time
    else:
        result["date"] = dt_index.date
        result["time"] = dt_index.time
    return result
