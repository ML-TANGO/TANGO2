from pathlib import Path

import pytest

from src.data_collection.db_client import DatabaseClient


class FakeDatabaseError(Exception):
    """psycopg2.Error 대체용 테스트 예외"""


@pytest.fixture
def database_client_with_mocked_config(mocker, sample_settings_dictionary):
    """설정 파일 로딩을 Mock 처리한 DatabaseClient fixture"""
    mocker.patch.object(DatabaseClient, "_load_config", return_value=sample_settings_dictionary)
    return DatabaseClient(config_path="config/settings.yaml")


# 설정 파일이 존재하지 않는 경우 FileNotFoundError가 발생하는지 검증

def test_load_config_should_raise_file_not_found_for_missing_config():
    missing_path = "config/not_existing_settings.yaml"

    with pytest.raises(FileNotFoundError, match="설정 파일을 찾을 수 없습니다"):
        DatabaseClient(config_path=missing_path)


# YAML 문법이 잘못된 설정 파일은 ValueError로 처리되는지 검증

def test_load_config_should_raise_value_error_for_invalid_yaml(tmp_path):
    invalid_yaml_path = tmp_path / "invalid_settings.yaml"
    invalid_yaml_path.write_text("database: [invalid", encoding="utf-8")

    with pytest.raises(ValueError, match="설정 파일 파싱 오류"):
        DatabaseClient(config_path=str(invalid_yaml_path))


# 설정 파일에 필요한 환경 변수가 없으면 ValueError가 발생하는지 검증

def test_load_config_should_raise_value_error_when_environment_variable_is_missing(tmp_path, monkeypatch):
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        "database:\n"
        "  host: ${MISSING_DB_HOST}\n"
        "  port: 5432\n"
        "  username: test_user\n"
        "  password: REDACTED"
        "  database_name: test_database\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("MISSING_DB_HOST", raising=False)

    with pytest.raises(ValueError, match="환경 변수가 설정되지 않았습니다"):
        DatabaseClient(config_path=str(config_path))


# DB 연결 실패 시 psycopg2 계열 예외가 호출자에게 전달되는지 검증

def test_connect_should_raise_database_error_when_connection_fails(
    mocker,
    sample_settings_dictionary,
):
    mocker.patch.object(DatabaseClient, "_load_config", return_value=sample_settings_dictionary)
    mock_psycopg2 = mocker.patch("src.data_collection.db_client.psycopg2")
    mock_psycopg2.Error = FakeDatabaseError
    mock_psycopg2.connect.side_effect = FakeDatabaseError("connection failed")

    database_client = DatabaseClient(config_path="config/settings.yaml")

    with pytest.raises(FakeDatabaseError, match="connection failed"):
        database_client.connect()


# disconnect() 중 DB 예외가 발생해도 connection이 None으로 정리되는지 검증

def test_disconnect_should_clear_connection_even_when_close_fails(database_client_with_mocked_config, mocker):
    mock_psycopg2 = mocker.patch("src.data_collection.db_client.psycopg2")
    mock_psycopg2.Error = FakeDatabaseError
    mock_connection = mocker.MagicMock()
    mock_connection.close.side_effect = FakeDatabaseError("close failed")
    database_client_with_mocked_config.connection = mock_connection

    database_client_with_mocked_config.disconnect()

    assert database_client_with_mocked_config.connection is None


# 쿼리 실행 중 DB 오류가 발생하면 예외가 다시 전달되는지 검증

def test_execute_query_should_raise_database_error_when_cursor_execute_fails(
    database_client_with_mocked_config,
    mocker,
):
    mock_psycopg2 = mocker.patch("src.data_collection.db_client.psycopg2")
    mock_psycopg2.Error = FakeDatabaseError
    mock_psycopg2.extras.RealDictCursor = object

    mock_cursor = mocker.MagicMock()
    mock_cursor.execute.side_effect = FakeDatabaseError("query failed")
    mock_connection = mocker.MagicMock()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    database_client_with_mocked_config.connection = mock_connection

    with pytest.raises(FakeDatabaseError, match="query failed"):
        database_client_with_mocked_config.execute_query("SELECT * FROM sensors WHERE sensor_id = %s", ("sensor-1",))


# site_id와 facility_id가 모두 비어 있으면 DB 조회 없이 빈 리스트를 반환하는지 검증

def test_get_sensor_ids_specific_should_return_empty_list_without_query_when_inputs_are_empty(
    database_client_with_mocked_config,
    mocker,
):
    database_client_with_mocked_config.execute_query = mocker.MagicMock()

    result = database_client_with_mocked_config.get_sensor_ids_specific("  ", "")

    assert result == []
    database_client_with_mocked_config.execute_query.assert_not_called()


# 센서 ID 조회 중 DB 예외가 발생하면 안전하게 빈 리스트를 반환하는지 검증

def test_get_sensor_ids_specific_should_return_empty_list_when_database_query_fails(
    database_client_with_mocked_config,
    mocker,
):
    database_client_with_mocked_config.execute_query = mocker.MagicMock(side_effect=Exception("query failed"))

    result = database_client_with_mocked_config.get_sensor_ids_specific("ags_003", "facility_1")

    assert result == []


# 중복 센서 ID와 None 값이 섞인 결과에서 유효한 센서 ID만 순서 보존 중복 제거되는지 검증

def test_get_sensor_ids_specific_should_remove_duplicates_and_ignore_none_values(
    database_client_with_mocked_config,
    mocker,
):
    database_client_with_mocked_config.execute_query = mocker.MagicMock(
        side_effect=[
            [{"device_id": "device-1"}, {"device_id": None}],
            [{"sensor_id": "sensor-1"}, {"sensor_id": "sensor-1"}, {"sensor_id": None}, {"sensor_id": "sensor-2"}],
        ]
    )

    result = database_client_with_mocked_config.get_sensor_ids_specific("ags_003", "")

    assert result == ["sensor-1", "sensor-2"]
