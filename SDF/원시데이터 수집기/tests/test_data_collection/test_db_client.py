import pytest

from src.data_collection.db_client import DatabaseClient


def test_connect_should_call_psycopg2_connect_with_expected_arguments(mocker, sample_settings_dictionary, mock_pymysql_connection):
    """connect() 호출 시 psycopg2.connect가 올바른 인자로 호출되는지 검증"""

    mocker.patch.object(DatabaseClient, "_load_config", return_value=sample_settings_dictionary)
    mock_psycopg2_connect = mocker.patch("src.data_collection.db_client.psycopg2.connect", return_value=mock_pymysql_connection)

    database_client = DatabaseClient(config_path="config/settings.yaml")
    database_client.connect()

    mock_psycopg2_connect.assert_called_once()
    assert database_client.connection == mock_pymysql_connection


def test_execute_query_should_raise_connection_error_when_not_connected(mocker, sample_settings_dictionary):
    """DB 연결 없이 execute_query() 호출 시 ConnectionError가 발생하는지 검증"""

    mocker.patch.object(DatabaseClient, "_load_config", return_value=sample_settings_dictionary)
    database_client = DatabaseClient(config_path="config/settings.yaml")

    with pytest.raises(ConnectionError):
        database_client.execute_query("SELECT 1")


def test_execute_query_should_return_list_of_rows_when_query_succeeds(mocker, sample_settings_dictionary, mock_pymysql_connection):
    """쿼리 실행 성공 시 결과(row list)를 반환하는지 검증"""

    mocker.patch.object(DatabaseClient, "_load_config", return_value=sample_settings_dictionary)

    expected_rows = [{"id": 1}, {"id": 2}]
    mock_cursor = mock_pymysql_connection.cursor.return_value.__enter__.return_value
    mock_cursor.fetchall.return_value = expected_rows

    database_client = DatabaseClient(config_path="config/settings.yaml")
    database_client.connection = mock_pymysql_connection

    rows = database_client.execute_query("SELECT id FROM some_table")

    assert rows == expected_rows


def test_execute_query_should_pass_query_and_params_to_cursor(mocker, sample_settings_dictionary, mock_pymysql_connection):
    """execute_query()가 SQL과 파라미터를 cursor.execute에 전달하는지 검증"""

    mocker.patch.object(DatabaseClient, "_load_config", return_value=sample_settings_dictionary)

    expected_rows = [{"ts": "2026-03-09 00:00:00", "value": 1.0}]
    mock_cursor = mock_pymysql_connection.cursor.return_value.__enter__.return_value
    mock_cursor.fetchall.return_value = expected_rows

    database_client = DatabaseClient(config_path="config/settings.yaml")
    database_client.connection = mock_pymysql_connection

    rows = database_client.execute_query("SELECT ts, value FROM some_table WHERE sensor_id = %s", ("sensor-1",))

    assert rows == expected_rows
    mock_cursor.execute.assert_called_once_with(
        "SELECT ts, value FROM some_table WHERE sensor_id = %s",
        ("sensor-1",),
    )
