import os
import sys
import types
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, call, patch

import pytest


if "psycopg2" not in sys.modules:
    fake_psycopg2 = types.ModuleType("psycopg2")
    fake_psycopg2_extras = types.ModuleType("psycopg2.extras")
    fake_psycopg2.Error = Exception
    fake_psycopg2.connect = lambda *args, **kwargs: None
    fake_psycopg2_extras.RealDictCursor = object
    fake_psycopg2.extras = fake_psycopg2_extras
    sys.modules["psycopg2"] = fake_psycopg2
    sys.modules["psycopg2.extras"] = fake_psycopg2_extras


class _PatchProxy:
    """pytest-mock이 없는 환경에서 mocker.patch API 일부를 대체하는 helper"""

    def __init__(self, request):
        self._request = request

    def __call__(self, target, *args, **kwargs):
        patcher = patch(target, *args, **kwargs)
        mocked_object = patcher.start()
        self._request.addfinalizer(patcher.stop)
        return mocked_object

    def object(self, target, attribute, *args, **kwargs):
        patcher = patch.object(target, attribute, *args, **kwargs)
        mocked_object = patcher.start()
        self._request.addfinalizer(patcher.stop)
        return mocked_object


@pytest.fixture
def mocker(request):
    """pytest-mock이 설치되지 않은 환경을 위한 최소 mocker fixture"""

    class Mocker:
        MagicMock = MagicMock
        Mock = Mock
        call = call

        def __init__(self):
            self.patch = _PatchProxy(request)

    return Mocker()


@pytest.fixture
def sample_settings_dictionary(tmp_path) -> Dict[str, Any]:
    """테스트용 설정 딕셔너리 fixture"""
    return {
        "database": {
            "host": "localhost",
            "port": 3306,
            "username": "test_user",
            "password": "test_password",
            "database_name": "test_database",
            "charset": "utf8mb4",
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "sites": {
            "valid_site_ids": ["ags_003", "ags_005", "ags_006"],
        },
    }


@pytest.fixture
def sample_relation_graph_dictionary() -> Dict[str, Any]:
    """테스트용 연관성 그래프 fixture"""
    return {
        "site_id": "ags_003",
        "devices": ["0D2509224001", "0D2509224002"],
        "available_tables": ["temperature", "anemometer"],
        "main_tables": ["temperature", "anemometer"],
        "joins": [],
        "time_conditions": {},
        "table_nodes": {
            "temperature": {"time_column": "ts"},
            "anemometer": {"time_column": "ts"},
        },
    }


@pytest.fixture
def mock_environment_variables(monkeypatch):
    """환경 변수 치환이 필요한 설정 로딩 테스트를 위한 환경 변수 fixture"""
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "3306")
    monkeypatch.setenv("DB_USERNAME", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_password")
    monkeypatch.setenv("DB_NAME", "test_database")
    yield


@pytest.fixture
def mock_pymysql_connection(mocker):
    """psycopg2 커넥션을 Mock으로 제공하는 fixture"""
    mock_cursor = mocker.MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_cursor.fetchone.return_value = {"count": 0}

    mock_connection = mocker.MagicMock()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

    return mock_connection
