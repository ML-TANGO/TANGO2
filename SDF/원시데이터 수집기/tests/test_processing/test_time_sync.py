import numpy as np
import pandas as pd
import pytest

from src.processing.time_sync import (
    adjust_to_edge_value,
    align_time_series,
    col_specific_linear_interpolation,
    general_linear_interpolation,
    get_common_valid_minutes,
    merge_asof_nearest,
    out_wind_direction_interpolation,
    resample_time_index,
    resample_to_minute,
    to_datetime_index,
)


def test_to_datetime_index_should_sort_parse_mixed_formats_and_keep_last_duplicate():
    df = pd.DataFrame(
        {
            "ts": ["2026-03-09T00:01:00", "2026-03-09 00:00:00", "2026-03-09 00:00:00.000000"],
            "value": [2, 1, 99],
        }
    )

    result = to_datetime_index(df, "ts")

    assert list(result.index) == [pd.Timestamp("2026-03-09 00:00:00"), pd.Timestamp("2026-03-09 00:01:00")]
    assert result.loc[pd.Timestamp("2026-03-09 00:00:00"), "value"] == 99



def test_to_datetime_index_should_raise_value_error_when_time_column_is_missing():
    with pytest.raises(ValueError, match="time_col"):
        to_datetime_index(pd.DataFrame({"value": [1]}), "ts")


@pytest.mark.parametrize("agg", ["mean", "first", "last"])
def test_resample_time_index_should_support_core_aggregations(agg):
    df = pd.DataFrame(
        {"value": [1.0, 3.0, 5.0]},
        index=pd.to_datetime(["2026-03-09 00:00:10", "2026-03-09 00:00:50", "2026-03-09 00:01:10"]),
    )

    result = resample_time_index(df, "1min", agg=agg)

    assert list(result.index) == [pd.Timestamp("2026-03-09 00:00:00"), pd.Timestamp("2026-03-09 00:01:00")]
    if agg == "mean":
        assert result.loc[pd.Timestamp("2026-03-09 00:00:00"), "value"] == 2.0
    if agg == "first":
        assert result.loc[pd.Timestamp("2026-03-09 00:00:00"), "value"] == 1.0
    if agg == "last":
        assert result.loc[pd.Timestamp("2026-03-09 00:00:00"), "value"] == 3.0



def test_resample_time_index_should_raise_value_error_for_invalid_inputs():
    with pytest.raises(ValueError, match="DatetimeIndex"):
        resample_time_index(pd.DataFrame({"value": [1]}), "1min")

    df = pd.DataFrame({"value": [1]}, index=pd.to_datetime(["2026-03-09 00:00:00"]))
    with pytest.raises(ValueError, match="agg"):
        resample_time_index(df, "1min", agg="median")



def test_merge_asof_nearest_should_apply_tolerance_and_suffix():
    left = pd.DataFrame({"a": [1, 2]}, index=pd.to_datetime(["2026-03-09 00:00:00", "2026-03-09 00:03:00"]))
    right = pd.DataFrame({"a": [10, 20], "b": [100, 200]}, index=pd.to_datetime(["2026-03-09 00:00:30", "2026-03-09 00:10:00"]))

    merged = merge_asof_nearest(left, right, tolerance="60s", suffix="other")

    assert merged.loc[pd.Timestamp("2026-03-09 00:00:00"), "a_other"] == 10
    assert merged.loc[pd.Timestamp("2026-03-09 00:00:00"), "b"] == 100
    assert pd.isna(merged.loc[pd.Timestamp("2026-03-09 00:03:00"), "b"])



def test_merge_asof_nearest_should_raise_value_error_when_index_is_not_datetime():
    left = pd.DataFrame({"a": [1]}, index=[0])
    right = pd.DataFrame({"b": [1]}, index=pd.to_datetime(["2026-03-09 00:00:00"]))

    with pytest.raises(ValueError, match="DatetimeIndex"):
        merge_asof_nearest(left, right)


@pytest.mark.parametrize(
    ("column_name", "value", "expected"),
    [
        ("out_wind_direction", -10, 0),
        ("out_wind_direction", 400, 360),
        ("out_rain", -0.5, 0),
        ("out_rain", 1.5, 1.0),
        ("open_rate_ch1", -5, 0),
        ("open_rate_ch1", 105, 100),
        ("temp", -150, -100),
        ("unknown_column", -999, -999),
    ],
)
def test_adjust_to_edge_value_should_apply_column_conditions(column_name, value, expected):
    assert adjust_to_edge_value(column_name, value) == expected



def test_general_linear_interpolation_should_interpolate_between_sparse_points_and_extrapolate_edges():
    series = pd.Series(
        [10.0, 20.0],
        index=pd.to_datetime(["2026-03-09 00:01:00", "2026-03-09 00:03:00"]),
        name="temp",
    )
    time_index = pd.date_range("2026-03-09 00:00:00", "2026-03-09 00:04:00", freq="1min")

    result = general_linear_interpolation(time_index, series)

    assert pytest.approx(result.loc[pd.Timestamp("2026-03-09 00:00:00")]) == 5.0
    assert pytest.approx(result.loc[pd.Timestamp("2026-03-09 00:02:00")]) == 15.0
    assert pytest.approx(result.loc[pd.Timestamp("2026-03-09 00:04:00")]) == 25.0



def test_general_linear_interpolation_should_keep_last_value_for_duplicate_index():
    series = pd.Series(
        [10.0, 99.0, 20.0],
        index=pd.to_datetime(["2026-03-09 00:00:00", "2026-03-09 00:00:00", "2026-03-09 00:02:00"]),
        name="temp",
    )
    time_index = pd.date_range("2026-03-09 00:00:00", "2026-03-09 00:02:00", freq="1min")

    result = general_linear_interpolation(time_index, series)

    assert result.loc[pd.Timestamp("2026-03-09 00:00:00")] == 99.0



def test_out_wind_direction_interpolation_should_use_shortest_circular_path():
    series = pd.Series(
        [350.0, 10.0],
        index=pd.to_datetime(["2026-03-09 00:00:00", "2026-03-09 00:02:00"]),
        name="out_wind_direction",
    )
    time_index = pd.date_range("2026-03-09 00:00:00", "2026-03-09 00:02:00", freq="1min")

    result = out_wind_direction_interpolation(time_index, series)

    assert result.loc[pd.Timestamp("2026-03-09 00:01:00")] == 0.0



def test_col_specific_linear_interpolation_should_clip_interpolated_values_to_column_range():
    original_series = pd.Series(
        [-10.0, 120.0],
        index=pd.to_datetime(["2026-03-09 00:00:00", "2026-03-09 00:02:00"]),
        name="open_rate_ch1",
    )
    time_index = pd.date_range("2026-03-09 00:00:00", "2026-03-09 00:02:00", freq="1min")

    interpolated = col_specific_linear_interpolation(time_index, original_series)

    assert interpolated.min() >= 0
    assert interpolated.max() <= 100
    assert interpolated.loc[pd.Timestamp("2026-03-09 00:00:00")] == 0
    assert interpolated.loc[pd.Timestamp("2026-03-09 00:02:00")] == 100


@pytest.mark.parametrize("agg", ["mean", "first", "last", "max", "min"])
def test_resample_to_minute_should_support_all_aggregations(agg):
    df = pd.DataFrame(
        {"value": [1.0, 3.0, 5.0]},
        index=pd.to_datetime(["2026-03-09 00:00:10", "2026-03-09 00:00:50", "2026-03-09 00:01:10"]),
    )

    result = resample_to_minute(df, agg=agg, fill_method="none")

    assert len(result) == 2
    if agg == "max":
        assert result.loc[pd.Timestamp("2026-03-09 00:00:00"), "value"] == 3.0
    if agg == "min":
        assert result.loc[pd.Timestamp("2026-03-09 00:00:00"), "value"] == 1.0


@pytest.mark.parametrize("fill_method", ["nearest", "forward", "backward", "both", "none"])
def test_resample_to_minute_should_support_fill_methods(fill_method):
    df = pd.DataFrame(
        {"value": [1.0, 3.0]},
        index=pd.to_datetime(["2026-03-09 00:00:00", "2026-03-09 00:02:00"]),
    )

    result = resample_to_minute(df, agg="first", fill_method=fill_method)

    if fill_method == "none":
        assert pd.isna(result.loc[pd.Timestamp("2026-03-09 00:01:00"), "value"])
    else:
        assert not pd.isna(result.loc[pd.Timestamp("2026-03-09 00:01:00"), "value"])



def test_resample_to_minute_linear_should_preserve_categorical_columns_with_forward_fill():
    df = pd.DataFrame(
        {"temp": [10.0, 20.0], "status": ["open", "close"]},
        index=pd.to_datetime(["2026-03-09 00:00:00", "2026-03-09 00:02:00"]),
    )

    result = resample_to_minute(df, agg="first", fill_method="linear")

    assert result.loc[pd.Timestamp("2026-03-09 00:01:00"), "temp"] == 15.0
    assert result.loc[pd.Timestamp("2026-03-09 00:01:00"), "status"] == "open"



def test_resample_to_minute_should_raise_value_error_for_invalid_inputs():
    with pytest.raises(ValueError, match="DatetimeIndex"):
        resample_to_minute(pd.DataFrame({"value": [1]}))

    df = pd.DataFrame({"value": [1]}, index=pd.to_datetime(["2026-03-09 00:00:00"]))
    with pytest.raises(ValueError, match="agg"):
        resample_to_minute(df, agg="median")
    with pytest.raises(ValueError, match="fill_method"):
        resample_to_minute(df, fill_method="invalid")



def test_get_common_valid_minutes_should_return_intersection_with_table_specific_thresholds():
    frames = {
        "motor": pd.DataFrame({"ts": ["2026-03-09 00:00:00", "2026-03-09 00:02:00"]}),
        "sensor": pd.DataFrame({"ts": ["2026-03-09 00:01:00", "2026-03-09 00:03:00"]}),
    }
    time_cols = {"motor": "ts", "sensor": "ts"}

    result = get_common_valid_minutes(
        frames=frames,
        time_cols=time_cols,
        motor_tables=["motor"],
        motor_threshold="3min",
        sensor_threshold="3min",
    )

    assert list(result) == [pd.Timestamp("2026-03-09 00:01:00"), pd.Timestamp("2026-03-09 00:02:00")]



def test_get_common_valid_minutes_should_return_empty_when_any_frame_is_empty():
    result = get_common_valid_minutes(
        frames={"a": pd.DataFrame({"ts": []})},
        time_cols={"a": "ts"},
        motor_tables=[],
    )

    assert result.empty



def test_get_common_valid_minutes_should_raise_value_error_when_time_column_is_missing():
    with pytest.raises(ValueError, match="time_col"):
        get_common_valid_minutes(
            frames={"a": pd.DataFrame({"value": [1]})},
            time_cols={"a": "ts"},
            motor_tables=[],
        )



def test_align_time_series_should_merge_resampled_frames_with_suffixes():
    base = pd.DataFrame({"ts": ["2026-03-09 00:00:10", "2026-03-09 00:01:10"], "value": [1.0, 2.0]})
    other = pd.DataFrame({"ts": ["2026-03-09 00:00:40", "2026-03-09 00:01:40"], "value": [10.0, 20.0]})

    merged = align_time_series(
        frames={"base": base, "other": other},
        time_cols={"base": "ts", "other": "ts"},
        base_key="base",
        tolerance="60s",
        resample_to_min=True,
        minute_agg="first",
        fill_method="nearest",
    )

    assert "value" in merged.columns
    assert "value_other" in merged.columns
    assert merged.loc[pd.Timestamp("2026-03-09 00:00:00"), "value_other"] == 10.0



def test_align_time_series_should_raise_value_error_for_missing_base_key_or_time_column():
    frames = {"base": pd.DataFrame({"ts": ["2026-03-09 00:00:00"], "value": [1]})}

    with pytest.raises(ValueError, match="base_key"):
        align_time_series(frames=frames, time_cols={"base": "ts"}, base_key="missing")

    with pytest.raises(ValueError, match="time_col"):
        align_time_series(frames=frames, time_cols={}, base_key="base")
