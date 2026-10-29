import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from real_time_db_load.main import real_data_main


# 센서 및 제어기 데이터 로드 실행
def get_raw_data(
    start_date: str | None = None,
    end_date: str | None = None,
    facility_ids: list[str] | None = None,
) -> dict:
    data_dict = real_data_main(start_date, end_date, facility_ids)
    return data_dict


# 온실 동별 제어기 정보 조회
def get_agsmotor_controls(site_id: str) -> dict:
    from real_time_db_load.utility import load_env
    from real_time_db_load.utility.db.client import DatabaseClient

    env = load_env()
    with DatabaseClient(env["database"], env["logging"]).get_connection() as db:
        return db.get_agsmotor_controls(site_id)
