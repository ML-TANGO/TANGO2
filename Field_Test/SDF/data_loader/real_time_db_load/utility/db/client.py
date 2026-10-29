import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
import re


# DB 연결 및 조회
class DatabaseClient:

    # DB 접속 정보 및 로거 초기화
    def __init__(self, db_config: Dict[str, Any], logging_config: Dict[str, Any] = None):
        self._db_config = db_config
        self.connection = None
        self.logger = self._setup_logger(logging_config or {})

    # DB 로그 설정
    def _setup_logger(self, logging_config: Dict[str, Any]) -> logging.Logger:
        logger = logging.getLogger(__name__)
        if logger.handlers:
            return logger

        level = getattr(logging, logging_config.get("level", "INFO"))
        fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        console = logging.StreamHandler()
        console.setFormatter(fmt)
        console.setLevel(level)
        logger.addHandler(console)

        log_file = logging_config.get("file")
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_path, encoding="utf-8")
            fh.setFormatter(fmt)
            fh.setLevel(level)
            logger.addHandler(fh)

        logger.setLevel(level)
        return logger

    _CONNECT_RETRIES = 3
    _CONNECT_BACKOFF = 1.0

    # DB 연결 (실패 시 재시도)
    def connect(self) -> None:
        cfg = self._db_config
        last_err = None
        for attempt in range(1, self._CONNECT_RETRIES + 1):
            try:
                self.connection = psycopg2.connect(
                    host=cfg["host"],
                    port=int(cfg["port"]),
                    user=cfg["username"],
                    password=cfg["password"],
                    database=cfg["database_name"],
                    connect_timeout=10,
                    options="-c timezone=Asia/Seoul",
                )
                self.logger.info("데이터베이스 연결 성공")
                return
            except psycopg2.Error as e:
                last_err = e
                self.logger.warning(
                    f"DB 연결 실패 (시도 {attempt}/{self._CONNECT_RETRIES}): {e}"
                )
                if attempt < self._CONNECT_RETRIES:
                    time.sleep(self._CONNECT_BACKOFF)
        self.logger.error(f"DB 연결 최종 실패: {last_err}")
        raise last_err

    # DB 연결 해제
    def disconnect(self) -> None:
        if self.connection:
            try:
                self.connection.close()
                self.logger.info("데이터베이스 연결 해제")
            except psycopg2.Error as e:
                self.logger.error(f"연결 해제 중 오류: {e}")
            finally:
                self.connection = None

    # DB 연결 후 사용이 끝나면 자동 해제
    @contextmanager
    def get_connection(self):
        self.connect()
        try:
            yield self
        finally:
            self.disconnect()

    # SQL 실행
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        if not self.connection:
            raise ConnectionError("데이터베이스에 연결되어 있지 않습니다")

        self.logger.debug(f"쿼리 실행: {query} | params={params}")
        try:
            with self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                self.logger.debug(f"쿼리 완료: {len(rows)}행 반환")
                return [dict(row) for row in rows]
        except psycopg2.Error as e:
            self.logger.error(f"쿼리 실패: {e} | query={query}")
            raise


    # 센서 유형 조회
    def get_sensor_types(self, sensor_ids: List[str]) -> Dict[str, str]:
        if not sensor_ids:
            return {}
        query = "SELECT sensor_id, sensor_type FROM sensors WHERE sensor_id IN %s"
        rows = self.execute_query(query, (tuple(sensor_ids),))
        return {row["sensor_id"]: row["sensor_type"] for row in rows}

    # 센서 표시 이름 조회
    def get_sensor_display_names(self, sensor_ids: List[str]) -> Dict[str, str]:
        if not sensor_ids:
            return {}
        query = "SELECT sensor_id, display_name FROM sensors WHERE sensor_id IN %s"
        rows = self.execute_query(query, (tuple(set(sensor_ids)),))
        return {row["sensor_id"]: row.get("display_name", "") for row in rows}

    # 사이트에 설치된 센서 및 제어기 목록 조회
    def get_sensors_by_site(
        self,
        site_id: str,
        facility_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:

        if isinstance(facility_ids, str):
            facility_ids = [facility_ids]

        if not facility_ids:
            fac_rows = self.execute_query(
                "SELECT facility_id FROM facilities WHERE site_id = %s",
                (site_id,),
            )
            facility_ids = [r["facility_id"] for r in fac_rows if r.get("facility_id")]

        sensor_ids: List[str] = []
        name_map: Dict[str, Dict[str, str]] = {}

        for fid in facility_ids:
            motor_rows = self.execute_query(
                "SELECT DISTINCT s.sensor_id, fc.payload, fc.control_name "
                "FROM facility_controls fc "
                "JOIN sensors s ON fc.device_id = s.device_id AND fc.modbus = s.channel_id "
                "WHERE fc.facility_id = %s AND fc.sensor_type = 'agsmotor_green'",
                (fid,),
            )
            for r in motor_rows:
                m = re.search(r'"(\d+)"', r.get("payload") or "")
                if not m:
                    continue
                probe = m.group(1)
                sid = r["sensor_id"]
                sensor_ids.append(f"{sid}:{probe}")
                name_map.setdefault(sid, {})[probe] = r.get("control_name") or f"probe_{probe}"

            dev_rows = self.execute_query(
                "SELECT s.sensor_id, s.sensor_type, s.description FROM sensors s "
                "WHERE (s.device_id, s.channel_id) IN "
                "(SELECT device_id, modbus FROM facility_devices WHERE facility_id = %s)",
                (fid,),
            )
            for r in dev_rows:
                sensor_ids.append(r["sensor_id"])

        out_rows = self.execute_query(
            "SELECT s.sensor_id, s.sensor_type, s.description, s.display_name FROM site_devices sd "
            "JOIN sensors s ON sd.device_id = s.device_id WHERE sd.site_id = %s",
            (site_id,),
        )
        for r in out_rows:
            if r["sensor_type"] in ("anemometer", "raindrop", "pyranometer", "carbondioxide"):
                sensor_ids.append(r["sensor_id"])
            elif r["sensor_type"] == "thermohygro" and (
                (r.get("description") and "외부" in r["description"])
                or (r.get("display_name") and "외부" in r["display_name"])
            ):
                sensor_ids.append(r["sensor_id"])

        return {
            "sensor_id_list": list(dict.fromkeys(sensor_ids)),
            "name_map": name_map,
        }

    # 온실 동별 제어기 정보 조회
    def get_agsmotor_controls(self, site_id: str) -> dict[str, dict]:
        rows = self.execute_query(
            "SELECT DISTINCT fc.facility_id, fc.modbus, fc.device_id, "
            "       COALESCE(dr.parent_id, fc.device_id) AS gateway_id "
            "FROM facility_controls fc "
            "JOIN facilities f ON f.facility_id = fc.facility_id "
            "LEFT JOIN device_relations dr ON dr.child_id = fc.device_id "
            "WHERE f.site_id = %s AND fc.sensor_type = 'agsmotor_green'",
            (site_id,),
        )
        return {
            str(r["facility_id"]): {
                "address": int(r["modbus"]),
                "node_id": str(r["device_id"]),
                "gateway_id": str(r["gateway_id"]),
            }
            for r in rows
            if r["modbus"] is not None and r["device_id"]
        }

    # 온실 동이 속한 사이트 조회
    def get_site_ids_by_facilities(self, facility_ids: list[str]) -> dict[str, str]:
        if not facility_ids:
            return {}
        placeholders = ", ".join(["%s"] * len(facility_ids))
        rows = self.execute_query(
            f"SELECT facility_id, site_id FROM facilities WHERE facility_id IN ({placeholders})",
            tuple(facility_ids),
        )
        return {str(r["facility_id"]): r["site_id"] for r in rows}
