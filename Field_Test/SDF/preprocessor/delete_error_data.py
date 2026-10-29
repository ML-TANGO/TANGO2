from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

THRESHOLD_SECONDS = 60.0
KST = timezone(timedelta(hours=9))


# 시각 문자열을 ISO 형식으로 정규화
def _normalize_ts(raw_ts: str) -> str:
    ts_str = (raw_ts or "").strip()
    if not ts_str:
        return ""
    if " " in ts_str and "T" not in ts_str:
        ts_str = ts_str.replace(" ", "T", 1)
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return ts_str


# 시각 문자열을 한국 시각으로 변환
def _parse_dt(raw_ts: str) -> datetime | None:
    ts_str = _normalize_ts(raw_ts)
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(ts_str)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


# 두 시각의 차이(초) 계산
def _diff_seconds(ts_a: str, ts_b: str) -> float | None:
    dt_a, dt_b = _parse_dt(ts_a), _parse_dt(ts_b)
    if dt_a is None or dt_b is None:
        return None
    return abs((dt_a - dt_b).total_seconds())


# 측정 시각과 저장 시각의 오차가 큰 행 제거
def delete_error_rows(df: pd.DataFrame) -> pd.DataFrame:
    if "ts" not in df.columns or "created_at" not in df.columns:
        return df.copy()

    def _should_keep(row) -> bool:
        diff = _diff_seconds(str(row["ts"]), str(row["created_at"]))
        return diff is None or diff < THRESHOLD_SECONDS

    mask = df.apply(_should_keep, axis=1)
    return df[mask].drop(columns=["created_at"]).reset_index(drop=True)


# 이상 데이터 제거
def delete_error_data(data_dict: dict) -> dict:
    result: dict = {"site_env": {}, "facility_env": {}}

    for key, df in data_dict["site_env"].items():
        result["site_env"][key] = delete_error_rows(df)

    for facility_id, sensors in data_dict["facility_env"].items():
        result["facility_env"][facility_id] = {}
        for sensor_key, value in sensors.items():
            if sensor_key == "agsmotor_green":
                new_probes = {}
                for probe_key, probe in value.items():
                    new_probes[probe_key] = {
                        "name": probe["name"],
                        "data": delete_error_rows(probe["data"]),
                    }
                result["facility_env"][facility_id]["agsmotor_green"] = new_probes
            else:
                result["facility_env"][facility_id][sensor_key] = delete_error_rows(value)

    return result
