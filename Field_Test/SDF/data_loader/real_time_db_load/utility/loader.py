import csv
import logging
import os
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from utility import load_env
from utility.db.client import DatabaseClient
from utility.query.query_builder import QueryBuilder


_KST = timezone(timedelta(hours=9))
_logger = logging.getLogger(__name__)


# 현재 한국 시각 조회
def _kst_now() -> datetime:
    return datetime.now(_KST).replace(tzinfo=None)


_WM2_PER_MJ = 277.8


# 일사계 데이터를 일사 데이터 형식으로 변환 (W/m² → MJ/m²)
def _solar_from_pyranometer(pyranometer: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if pyranometer is None or pyranometer.empty:
        return None
    if "ts" not in pyranometer.columns or "insolation" not in pyranometer.columns:
        return None

    ts = pd.to_datetime(pyranometer["ts"], errors="coerce")
    si = pd.to_numeric(pyranometer["insolation"], errors="coerce") / _WM2_PER_MJ
    out = pd.DataFrame({"YYMMDDHHMI": ts.dt.strftime("%Y%m%d%H%M"), "SI": si, "SS": 0.0})
    out = out.dropna(subset=["YYMMDDHHMI", "SI"])
    return out if not out.empty else None


# 센서의 온실 내부/외부 구분
def _get_facility_status(rows: list[dict]) -> str:
    for r in rows:
        if r.get("facility_id"):
            return "In"
    return "Out"


# 조회 결과를 시각 순 DataFrame으로 변환
def _rows_to_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in ("ts", "created_at"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True).dt.tz_convert("Asia/Seoul")
    return df.sort_values("ts").reset_index(drop=True)


# 센서 및 제어기 데이터를 외부/온실 동별로 분류
def _assemble_sensor(records: list[dict], output: dict, _name_map: dict = None) -> None:
    _name_map = _name_map or {}

    for rec in records:
        sensor_type  = rec["sensor_type"]
        status       = rec["status"]
        df           = rec["df"]
        channel      = rec["channel"]
        sensor_id    = rec["sensor_id"]

        facility_ids = df["facility_id"].dropna().unique()

        if status == "Out" or len(facility_ids) == 0:
            output["site_env"][f"{sensor_type}_out" if sensor_type == "thermohygro" else sensor_type] = df
        else:
            for fid in facility_ids:
                f_df = df[df["facility_id"] == fid].copy()
                if f_df.empty:
                    continue

                fenv = output["facility_env"].setdefault(fid, {})

                if sensor_type == "agsmotor_green":
                    ch = channel or "0"
                    motors = fenv.setdefault("agsmotor_green", {})
                    
                    display_name = _name_map.get(sensor_id, {}).get(str(ch))
                    if not display_name:
                        display_name = f"probe_{ch}"

                    motors[f"probe_{ch}"] = {
                        "name": display_name,
                        "data": f_df,
                    }
                else:
                    fenv[f"{sensor_type}_in"] = f_df


# 센서 유형 및 표시 이름 조회
def prefetch_sensor_meta(db: DatabaseClient, sensor_id_list: list[str]) -> dict:
    pure_ids = list({sid.split(":")[0] for sid in sensor_id_list})
    return {
        "type_map":    db.get_sensor_types(pure_ids),
        "display_map": db.get_sensor_display_names(pure_ids),
    }


# 센서 및 제어기 데이터 조회
def query_sensor_records(
    db: DatabaseClient,
    sensor_id_list: list[str],
    start_utc: str,
    end_utc: str,
    meta: Optional[dict] = None,
    debug: bool = False,
) -> list[dict]:
    if meta is None:
        meta = prefetch_sensor_meta(db, sensor_id_list)

    type_map    = meta["type_map"]
    display_map = meta["display_map"]

    return _fetch_sensor_data_from_db(db, sensor_id_list, start_utc, end_utc, type_map, display_map, debug)


# 센서 및 제어기별 조회 SQL 실행 및 결과 수집
def _fetch_sensor_data_from_db(
    db: DatabaseClient,
    sensor_id_list: list[str],
    start_utc: str,
    end_utc: str,
    type_map: dict,
    display_map: dict,
    debug: bool,
) -> list[dict]:
    qb = QueryBuilder(db)
    queries = qb.build_period(sensor_id_list, start_utc, end_utc)

    records = []
    for raw_id, query in zip(sensor_id_list, queries):
        parts = raw_id.split(":", 1)
        sensor_id    = parts[0]
        channel      = parts[1] if len(parts) > 1 else None
        sensor_type  = type_map.get(sensor_id, "unknown")
        display_name = display_map.get(sensor_id) or sensor_id

        if debug:
            print(f"[DEBUG] DB 신규 수집 쿼리 실행: {raw_id}")

        rows = db.execute_query(query)
        if not rows:
            continue

        records.append({
            "sensor_id":    sensor_id,
            "channel":      channel,
            "sensor_type":  sensor_type,
            "status":       _get_facility_status(rows),
            "display_name": display_name,
            "df":           _rows_to_df(rows),
        })

    return records


# 사이트의 센서 및 제어기 데이터 로드
def fetch_data_by_site(
    site_id: str,
    facility_ids: Optional[list] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    env = load_env()

    if start_date and end_date:
        start_kst = start_date
        end_kst = end_date
    else:
        window = int(env.get("collection", {}).get("window_minutes", 30))
        now = _kst_now()
        end_kst = now.strftime("%Y-%m-%d %H:%M:%S")
        start_kst = (now - timedelta(minutes=window)).strftime("%Y-%m-%d %H:%M:%S")

    output: dict = {"site_env": {}, "facility_env": {}}

    with DatabaseClient(env["database"], env["logging"]).get_connection() as db:
        sensors = db.get_sensors_by_site(site_id, facility_ids)
        sensor_id_list = sensors["sensor_id_list"]
        _name_map = sensors["name_map"]
        records = query_sensor_records(db, sensor_id_list, start_kst, end_kst)
        _assemble_sensor(records, output, _name_map)

    solar = _solar_from_pyranometer(output["site_env"].get("pyranometer"))
    if solar is None:
        _logger.warning("일사량: 현장 일사계 데이터 없음")
        solar = pd.DataFrame()
    output["site_env"]["kma"] = solar

    return output


# 사이트의 최근 센서 및 제어기 데이터 로드
def fetch_latest_data_by_site(
    site_id: str,
    facility_ids: Optional[list] = None,
) -> dict:
    return fetch_data_by_site(site_id, facility_ids)


_CROP_INFO_PATH = Path(__file__).parent.parent / "config" / "crop_info.csv"


# 작물 정보 파일 로드
def _load_crop_info(crop_info_path: Optional[Path] = None) -> list[dict]:
    path = crop_info_path or _CROP_INFO_PATH
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# 작물별 온실 동의 최근 센서 및 제어기 데이터 로드
def fetch_latest_data_by_crop(
    crop_name: str,
    site_id: Optional[str] = None,
    crop_info_path: Optional[str] = None,
) -> dict[str, dict]:
    path = Path(crop_info_path) if crop_info_path else None
    rows = _load_crop_info(path)

    crop_lower = crop_name.lower()
    matched_facility_ids = [
        r["facility_id"]
        for r in rows
        if crop_lower in r.get("plant_name", "").lower()
    ]

    if not matched_facility_ids:
        return {}

    env = load_env()

    with DatabaseClient(env["database"], env["logging"]).get_connection() as db:
        facility_site_map = db.get_site_ids_by_facilities(matched_facility_ids)

    grouped: dict[str, list[str]] = {}
    for fid, sid in facility_site_map.items():
        if site_id and sid != site_id:
            continue
        grouped.setdefault(sid, []).append(fid)

    if not grouped:
        return {}

    results: dict[str, dict] = {}
    for sid, fids in grouped.items():
        results[sid] = fetch_latest_data_by_site(sid, fids)

    return results
