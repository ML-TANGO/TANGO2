import pandas as pd
import pytest

from src.processing.feature_gen import (
    add_diff_features,
    add_pct_change_features,
    add_rolling_features,
    add_time_features,
)


def test_add_diff_features_should_create_diff_column():
    df = pd.DataFrame({"x": [1.0, 3.0, 6.0]})
    out = add_diff_features(df, ["x"], periods=1)
    assert "x_diff" in out.columns
    assert pd.isna(out.loc[0, "x_diff"])
    assert out.loc[1, "x_diff"] == 2.0


def test_add_diff_features_should_handle_multiple_columns_custom_period_and_suffix():
    df = pd.DataFrame({"temp": [10.0, 12.0, 15.0, 20.0], "humi": [50.0, 49.0, 47.0, 44.0]})

    out = add_diff_features(df, ["temp", "humi"], periods=2, suffix="delta_2")

    assert out.loc[2, "temp_delta_2"] == 5.0
    assert out.loc[3, "humi_delta_2"] == -5.0
    assert "temp_delta_2" not in df.columns


def test_add_diff_features_should_raise_value_error_for_missing_column():
    df = pd.DataFrame({"x": [1.0, 2.0]})

    with pytest.raises(ValueError, match="컬럼이 없습니다"):
        add_diff_features(df, ["missing"])


def test_add_pct_change_features_should_create_percentage_change_column():
    df = pd.DataFrame({"x": [10.0, 15.0, 30.0]})

    out = add_pct_change_features(df, ["x"], periods=1)

    assert "x_pct_change" in out.columns
    assert pd.isna(out.loc[0, "x_pct_change"])
    assert out.loc[1, "x_pct_change"] == 0.5
    assert out.loc[2, "x_pct_change"] == 1.0


def test_add_pct_change_features_should_raise_value_error_for_missing_column():
    df = pd.DataFrame({"x": [1.0, 2.0]})

    with pytest.raises(ValueError, match="컬럼이 없습니다"):
        add_pct_change_features(df, ["missing"])


def test_add_rolling_features_should_create_rolling_mean():
    df = pd.DataFrame({"x": [1.0, 3.0, 6.0]})
    out = add_rolling_features(df, ["x"], window=2, stats=["mean"], min_periods=1)
    assert "x_roll2_mean" in out.columns
    assert out.loc[0, "x_roll2_mean"] == 1.0
    assert out.loc[1, "x_roll2_mean"] == 2.0


def test_add_rolling_features_should_create_all_supported_stats_for_multiple_columns():
    df = pd.DataFrame({"temp": [10.0, 20.0, 30.0], "humi": [40.0, 45.0, 55.0]})

    out = add_rolling_features(df, ["temp", "humi"], window=2, stats=["mean", "std", "min", "max"], min_periods=1)

    assert out.loc[2, "temp_roll2_mean"] == 25.0
    assert out.loc[2, "temp_roll2_min"] == 20.0
    assert out.loc[2, "temp_roll2_max"] == 30.0
    assert pytest.approx(out.loc[2, "humi_roll2_std"]) == 7.0710678118654755


def test_add_rolling_features_should_raise_value_error_for_unknown_stat():
    df = pd.DataFrame({"x": [1.0, 2.0]})

    with pytest.raises(ValueError, match="stats"):
        add_rolling_features(df, ["x"], window=2, stats=["median"])


def test_add_rolling_features_should_raise_value_error_for_missing_column():
    df = pd.DataFrame({"x": [1.0, 2.0]})

    with pytest.raises(ValueError, match="컬럼이 없습니다"):
        add_rolling_features(df, ["missing"], window=2)


def test_add_time_features_should_use_datetime_index_when_time_col_is_none():
    df = pd.DataFrame(
        {"value": [1, 2]},
        index=pd.to_datetime(["2026-03-09 01:02:03", "2026-03-09 04:05:06"]),
    )

    out = add_time_features(df)

    assert str(out.loc[df.index[0], "date"]) == "2026-03-09"
    assert str(out.loc[df.index[1], "time"]) == "04:05:06"


def test_add_time_features_should_use_explicit_time_column_and_preserve_original_columns():
    df = pd.DataFrame({"ts": ["2026-03-09 01:02:03", "2026-03-10 04:05:06"], "value": [1, 2]})

    out = add_time_features(df, time_col="ts")

    assert list(out["value"]) == [1, 2]
    assert str(out.loc[0, "date"]) == "2026-03-09"
    assert str(out.loc[1, "time"]) == "04:05:06"


def test_add_time_features_should_raise_value_error_for_non_datetime_index_without_time_col():
    df = pd.DataFrame({"value": [1, 2]})

    with pytest.raises(ValueError, match="DatetimeIndex"):
        add_time_features(df)


def test_add_time_features_should_raise_value_error_for_missing_time_column():
    df = pd.DataFrame({"value": [1, 2]})

    with pytest.raises(ValueError, match="time_col"):
        add_time_features(df, time_col="ts")
