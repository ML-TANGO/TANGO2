from typing import Dict, List, Optional

from utility.db.client import DatabaseClient


_SENSOR_COLUMNS: Dict[str, List[str]] = {
    "anemometer":     ["wind_speed", "wind_direction"],
    "thermohygro":    ["temp", "humi"],
    "agsmotor_green": ["open_rate"],
    "raindrop":       ["rain"],
    "counter":        ["current_count", "accumulated_count"],
    "amperemeter":    ["amp"],
    "temperature":    ["probe", "temp"],
    "pyranometer":    ["insolation"],
    "carbondioxide":  ["co2"],
}

_CHANNEL_TABLES = {"agsmotor_green", "temperature"}

# 센서 및 제어기 조회 SQL 생성
class QueryBuilder:

    # DB 클라이언트 설정
    def __init__(self, db_client: DatabaseClient):
        self._db = db_client


    # 센서 및 제어기별 기간 조회 SQL 생성
    def build_period(
        self,
        sensor_ids: List[str],
        start_date: str,
        end_date: str,
    ) -> List[str]:
        type_map = self._fetch_sensor_types(sensor_ids)
        queries = []
        for raw_id in sensor_ids:
            sensor_id, channel = self._parse_sensor_id(raw_id)
            sensor_type = type_map.get(sensor_id, "unknown")
            queries.append(
                self._build_period_query(sensor_id, sensor_type, start_date, end_date, channel)
            )
        return queries


    # 센서 ID와 채널 분리
    @staticmethod
    def _parse_sensor_id(raw: str) -> tuple:
        if ":" in raw:
            sensor_id, channel = raw.split(":", 1)
            return sensor_id.strip(), channel.strip()
        return raw.strip(), None

    # 센서 유형 조회
    def _fetch_sensor_types(self, sensor_ids: List[str]) -> Dict[str, str]:
        pure_ids = list({self._parse_sensor_id(s)[0] for s in sensor_ids})
        try:
            return self._db.get_sensor_types(pure_ids)
        except Exception as e:
            print(f"sensor_type 조회 오류: {e}")
            return {}

    # SELECT 컬럼 목록 생성
    @staticmethod
    def _col_select(columns: List[str], alias: str = "t") -> str:
        return ", ".join(f"{alias}.{col}" for col in columns)

    # 센서 유형별 조회 컬럼 결정
    def _base_columns(self, sensor_type: str, channel: Optional[str]) -> List[str]:
        data_cols = _SENSOR_COLUMNS.get(sensor_type, [])
        cols = ["ts", "site_id", "sensor_id", "created_at"] + data_cols
        if sensor_type in _CHANNEL_TABLES and channel is not None:
            cols.append("probe")
        return cols

    # 제어기 채널 조건 생성
    def _channel_condition(self, sensor_type: str, channel: Optional[str]) -> str:
        if sensor_type in _CHANNEL_TABLES and channel is not None:
            clean_ch = channel
            if isinstance(channel, str) and channel.startswith("ch"):
                clean_ch = channel[2:]
            return f" AND t.probe = {clean_ch}"
        return ""

    # 센서가 속한 온실 동 조회 서브쿼리 생성
    def _facility_subquery(self, sensor_type: str, channel: Optional[str]) -> str:
        if sensor_type == "agsmotor_green":
            ch = channel or "0"
            if isinstance(ch, str) and ch.startswith("ch"):
                ch = ch[2:]
            return (
                f"(SELECT fc.facility_id FROM facility_controls fc "
                f"WHERE fc.device_id = s.device_id "
                f"AND fc.modbus = s.channel_id "
                f"AND fc.payload LIKE '%\"{ch}\"%' "
                f"LIMIT 1)"
            )
        return (
            f"(SELECT fd.facility_id FROM facility_devices fd "
            f"WHERE fd.device_id = s.device_id "
            f"AND fd.modbus = s.channel_id "
            f"LIMIT 1)"
        )

    # 단일 센서 기간 조회 SQL 생성
    def _build_period_query(
        self,
        sensor_id: str,
        sensor_type: str,
        start_date: str,
        end_date: str,
        channel: Optional[str],
    ) -> str:
        cols = self._base_columns(sensor_type, channel)
        select = self._col_select(cols)
        facility_sub = self._facility_subquery(sensor_type, channel)
        ch_cond = self._channel_condition(sensor_type, channel)

        return (
            f"SELECT {select}, {facility_sub} AS facility_id\n"
            f"FROM {sensor_type} t\n"
            f"LEFT JOIN sensors s ON t.sensor_id = s.sensor_id\n"
            f"WHERE t.sensor_id = '{sensor_id}'{ch_cond}\n"
            f"AND t.ts BETWEEN '{start_date}' AND '{end_date}'\n"
            f"ORDER BY t.ts"
        )
