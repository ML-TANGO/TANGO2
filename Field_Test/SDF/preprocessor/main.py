from __future__ import annotations

from pathlib import Path

import pandas as pd

from preprocessor.delete_error_data import delete_error_data
from preprocessor.get_validate_area import (
    get_threshold_seconds,
    get_valid_time_ranges_for_sensor,
    intersect_valid_time_ranges_two,
)
from preprocessor.time_sync import resample_to_minute
from preprocessor.merge_data import merge_time_sync_dfs
from preprocessor.merge_si_data import merge_kma_into_merged_minute_data
from preprocessor.post_process_merged_data import post_process_qa_dataframe


# 온실 동별 작물 정보 정리
def _build_facility_meta(data_dict: dict) -> pd.DataFrame:
    rows = []
    for facility_id, sensors in data_dict["facility_env"].items():
        crop_info = sensors.get("crop_info", {})
        rows.append({
            "facility_id": facility_id,
            "planting_date": pd.to_datetime(crop_info.get("planting_date")).tz_localize("Asia/Seoul").normalize(),
            "plant_name": str(crop_info.get("plant_name", "")),
            "manual": str(crop_info.get("manual", "")),
            "min_accumulated_temperature": crop_info.get("min_accumulated_temperature"),
            "max_accumulated_temperature": crop_info.get("max_accumulated_temperature"),
        })
    return pd.DataFrame(rows)


# 센서 및 제어기 데이터에서 작물 정보 분리
def _strip_crop_info(data_dict: dict) -> dict:
    return {
        "site_env": data_dict["site_env"],
        "facility_env": {
            fid: {k: v for k, v in sensors.items() if k != "crop_info"}
            for fid, sensors in data_dict["facility_env"].items()
        },
    }


# 센서 유형 컬럼 추가
def _add_sensor_type(data_dict: dict) -> dict:
    for key, df in data_dict["site_env"].items():
        if key == "kma" or df.empty:
            continue
        df["sensor_type"] = key

    for sensors in data_dict["facility_env"].values():
        for sensor_key, value in sensors.items():
            if sensor_key == "agsmotor_green":
                for probe in value.values():
                    probe["data"]["sensor_type"] = "agsmotor_green"
            else:
                value["sensor_type"] = sensor_key

    return data_dict


# 센서 및 제어기 데이터 순회
def _iter_sensor_dfs(data_dict: dict):
    for key, df in data_dict["site_env"].items():
        if key != "kma" and not df.empty:
            yield df
    for sensors in data_dict["facility_env"].values():
        for sensor_key, value in sensors.items():
            if sensor_key == "agsmotor_green":
                for probe in value.values():
                    if not probe["data"].empty:
                        yield probe["data"]
            else:
                if not value.empty:
                    yield value


# 센서 공통 유효 구간 추출
def _get_valid_ranges(data_dict: dict) -> pd.DataFrame:
    intersection = None
    for df in _iter_sensor_dfs(data_dict):
        if "ts" not in df.columns:
            continue
        thr = get_threshold_seconds(df)
        ranges = get_valid_time_ranges_for_sensor(df, threshold_seconds=thr)
        if ranges.empty:
            continue
        intersection = ranges if intersection is None else intersect_valid_time_ranges_two(intersection, ranges)
        if intersection.empty:
            break
    return intersection if intersection is not None else pd.DataFrame(columns=["start_ts", "end_ts"])


# 유효 구간 내 데이터만 추출
def _filter_df(df: pd.DataFrame, valid_ranges: pd.DataFrame) -> pd.DataFrame:
    if "ts" not in df.columns or valid_ranges.empty:
        return df
    ts_col = pd.to_datetime(df["ts"])
    mask = pd.Series(False, index=df.index)
    for _, row in valid_ranges.iterrows():
        mask |= (ts_col >= row["start_ts"]) & (ts_col <= row["end_ts"])
    return df[mask].reset_index(drop=True)


# 전체 센서 및 제어기 데이터를 유효 구간으로 필터링
def _filter_to_valid_ranges(data_dict: dict, valid_ranges: pd.DataFrame) -> dict:
    for key in list(data_dict["site_env"]):
        if key == "kma":
            continue
        data_dict["site_env"][key] = _filter_df(data_dict["site_env"][key], valid_ranges)
    for sensors in data_dict["facility_env"].values():
        for sensor_key in list(sensors):
            value = sensors[sensor_key]
            if sensor_key == "agsmotor_green":
                for probe in value.values():
                    probe["data"] = _filter_df(probe["data"], valid_ranges)
            else:
                sensors[sensor_key] = _filter_df(value, valid_ranges)
    return data_dict


# 전체 센서 및 제어기 데이터 1분 단위 시간 보정
def _time_sync_all(data_dict: dict, valid_ranges: pd.DataFrame) -> dict:
    for key in list(data_dict["site_env"]):
        if key == "kma":
            continue
        data_dict["site_env"][key] = resample_to_minute(data_dict["site_env"][key], valid_ranges)
    for sensors in data_dict["facility_env"].values():
        for sensor_key in list(sensors):
            value = sensors[sensor_key]
            if sensor_key == "agsmotor_green":
                for probe in value.values():
                    probe["data"] = resample_to_minute(probe["data"], valid_ranges)
            else:
                sensors[sensor_key] = resample_to_minute(value, valid_ranges)
    return data_dict


# 전처리 단계 순차 실행
def preprocess(data_dict: dict) -> pd.DataFrame:
    facility_meta = _build_facility_meta(data_dict)
    data = delete_error_data(_strip_crop_info(data_dict))
    data = _add_sensor_type(data)
    valid_ranges = _get_valid_ranges(data)
    data = _filter_to_valid_ranges(data, valid_ranges)
    data = _time_sync_all(data, valid_ranges)
    merged = merge_time_sync_dfs(_iter_sensor_dfs(data))
    merged = merge_kma_into_merged_minute_data(
        merged, data["site_env"]["kma"], kma_tz="Asia/Seoul"
    )
    result = post_process_qa_dataframe(merged, facility_meta)
    return result.dropna().reset_index(drop=True)
