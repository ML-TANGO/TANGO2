import os
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env")

from . import settings as _settings


# 필수 환경변수 읽기
def _require(key: str) -> str:
    value = os.environ.get(key, "")
    if not value:
        raise ValueError(f"환경변수가 설정되지 않았습니다: {key}")
    return value


# DB 접속·수집 범위·로그 설정 로드
def load_env(window_minutes: int | None = None) -> dict:
    return {
        "database": {
            "host":          _require("DB_HOST"),
            "port":          _require("DB_PORT"),
            "username":      _require("DB_USERNAME"),
            "password":      _require("DB_PASSWORD"),
            "database_name": _require("DB_NAME"),
        },
        "collection": {
            "window_minutes": (window_minutes if window_minutes is not None
                               else int(os.getenv("WINDOW_MINUTES", "30"))),
        },
        "logging": {
            "level":        _settings.LOG_LEVEL,
            "file":         _settings.LOG_FILE,
            "max_bytes":    _settings.LOG_MAX_BYTES,
            "backup_count": _settings.LOG_BACKUP_COUNT,
        },
    }

from utility.db.client import DatabaseClient
from utility.query.query_builder import QueryBuilder
from utility.loader import (
    fetch_data_by_site,
    fetch_latest_data_by_site,
    query_sensor_records,
    prefetch_sensor_meta,
    fetch_latest_data_by_crop,
)

__all__ = [
    "load_env",
    "DatabaseClient",
    "QueryBuilder",
    "fetch_data_by_site",
    "fetch_latest_data_by_site",
    "query_sensor_records",
    "prefetch_sensor_meta",
    "fetch_latest_data_by_crop",
]
