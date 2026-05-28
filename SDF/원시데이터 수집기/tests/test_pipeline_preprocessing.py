import json
from pathlib import Path

import pandas as pd
import pytest

from src.pipeline_preprocessing import (
    _cleanup_aligned_frame,
    _find_metadata_file,
    _load_data_file,
    _load_metadata,
    _load_weather_df,
    _parse_merge_key,
    _save_final_results,
)


def test_find_metadata_file_should_return_metadata_path_when_present():
    saved_files = {"temperature": "temperature.csv", "metadata": "metadata.json"}

    assert _find_metadata_file(saved_files) == "metadata.json"



def test_find_metadata_file_should_return_none_when_metadata_is_absent():
    saved_files = {"temperature": "temperature.csv"}

    assert _find_metadata_file(saved_files) is None



def test_load_metadata_should_parse_json_and_normalize_iso_timestamp(tmp_path):
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-03-09T01:02:03Z",
                "sensor_file_mapping": {"In_thermohygro_sensor-1": {"site_id": "ags_003"}},
            }
        ),
        encoding="utf-8",
    )

    metadata, timestamp = _load_metadata(str(metadata_path))

    assert metadata["sensor_file_mapping"]["In_thermohygro_sensor-1"]["site_id"] == "ags_003"
    assert timestamp == "20260309_010203"



def test_load_metadata_should_parse_csv_with_nested_json_values(tmp_path):
    metadata_path = tmp_path / "metadata.csv"
    pd.DataFrame(
        [
            {"key": "timestamp", "value": "20260309_010203"},
            {"key": "config_run_processing", "value": "True"},
            {"key": "output_file_temperature", "value": "temperature.csv"},
            {"key": "sensor_file_mapping", "value": json.dumps({"sensor-a": {"site_id": "ags_003"}})},
            {"key": "sensor_categories", "value": json.dumps({"temperature": ["sensor-a"]})},
            {"key": "table_queries", "value": json.dumps({"temperature": "SELECT 1"})},
        ]
    ).to_csv(metadata_path, index=False, encoding="utf-8")

    metadata, timestamp = _load_metadata(str(metadata_path))

    assert timestamp == "20260309_010203"
    assert metadata["config"]["run_processing"] == "True"
    assert metadata["output_files"]["temperature"] == "temperature.csv"
    assert metadata["sensor_file_mapping"]["sensor-a"]["site_id"] == "ags_003"
    assert metadata["sensor_categories"]["temperature"] == ["sensor-a"]
    assert metadata["table_queries"]["temperature"] == "SELECT 1"



def test_load_metadata_should_raise_value_error_for_missing_or_unsupported_file(tmp_path):
    with pytest.raises(ValueError, match="메타데이터 파일"):
        _load_metadata(str(tmp_path / "missing.json"))

    unsupported_path = tmp_path / "metadata.txt"
    unsupported_path.write_text("metadata", encoding="utf-8")
    with pytest.raises(ValueError, match="지원하지 않는"):
        _load_metadata(str(unsupported_path))



def test_load_data_file_should_read_json_csv_and_return_none_for_missing_or_unsupported(tmp_path):
    json_path = tmp_path / "rows.json"
    json_path.write_text(json.dumps([{"ts": "2026-03-09 00:00:00", "value": 1}]), encoding="utf-8")
    csv_path = tmp_path / "rows.csv"
    pd.DataFrame([{"ts": "2026-03-09 00:01:00", "value": 2}]).to_csv(csv_path, index=False, encoding="utf-8")
    text_path = tmp_path / "rows.txt"
    text_path.write_text("unsupported", encoding="utf-8")

    json_df = _load_data_file(str(json_path))
    csv_df = _load_data_file(str(csv_path))

    assert json_df.loc[0, "value"] == 1
    assert csv_df.loc[0, "value"] == 2
    assert _load_data_file(str(tmp_path / "missing.csv")) is None
    assert _load_data_file(str(text_path)) is None


@pytest.mark.parametrize(
    ("raw_key", "expected"),
    [
        ("In_agsmotor_green_motor-1_ch2_site_ags_003_facility_f1", "agsmotor_green_motor-1_ch2"),
        ("Out_thermohygro_sensor-1_site_ags_003_facility_f1", "thermohygro_sensor-1_site_no_channel"),
        ("short", "short"),
    ],
)
def test_parse_merge_key_should_normalize_channel_and_non_channel_keys(raw_key, expected):
    assert _parse_merge_key(raw_key) == expected



def test_load_weather_df_should_select_weather_columns_and_convert_timestamp(tmp_path):
    weather_path = tmp_path / "weather.csv"
    pd.DataFrame(
        [
            {"YYMMDDHHMI": "202603090000", "SS": 1.2, "SI": 3.4, "TA": 10.0},
        ]
    ).to_csv(weather_path, index=False, encoding="utf-8")

    weather_df = _load_weather_df(str(weather_path))

    assert list(weather_df.columns) == ["SS", "SI", "ts"]
    assert str(weather_df.loc[0, "ts"]) == "2026-03-09 00:00:00+00:00"



def test_load_weather_df_should_return_none_when_required_columns_are_absent(tmp_path):
    weather_path = tmp_path / "weather.csv"
    pd.DataFrame([{"TA": 10.0}]).to_csv(weather_path, index=False, encoding="utf-8")

    assert _load_weather_df(str(weather_path)) is None



def test_cleanup_aligned_frame_should_drop_transient_columns_and_keep_measurements():
    frame = pd.DataFrame(
        {
            "sensor_id": ["sensor-1"],
            "date": ["2026-03-09"],
            "time": ["00:00:00"],
            "site_id_other": ["ags_003"],
            "probe": ["ch1"],
            "wind_speed": [1.2],
            "temp": [25.0],
        }
    )

    cleaned = _cleanup_aligned_frame(frame)

    assert list(cleaned.columns) == ["temp"]
    assert cleaned.loc[0, "temp"] == 25.0



def test_save_final_results_should_remove_duplicate_columns_and_write_csv(tmp_path):
    final_results = {
        "site_ags_003_facility_f1": pd.DataFrame(
            {
                "ts": ["2026-03-09 00:00:00"],
                "open_rate": [50],
                "open_rate_ch1": [75],
                "open_rate_dup": [0],
                "site_id_extra": ["ags_003"],
                "facility_id_extra": ["f1"],
                "temp": [25.0],
            }
        )
    }

    output_paths = _save_final_results(final_results=final_results, output_dir=str(tmp_path))

    json_like_path = Path(output_paths["site_ags_003_facility_f1"])
    csv_path = json_like_path.with_suffix(".csv")
    assert csv_path.exists()

    saved_df = pd.read_csv(csv_path)
    assert "open_rate" not in saved_df.columns
    assert "open_rate_dup" not in saved_df.columns
    assert "site_id_extra" not in saved_df.columns
    assert "facility_id_extra" not in saved_df.columns
    assert saved_df.loc[0, "open_rate_ch1"] == 75
    assert saved_df.loc[0, "temp"] == 25.0
