import pytest

from src.data_collection.query_builder import QueryBuilder


def test_build_per_sensor_should_create_anemometer_query(mocker):
    """anemometer 센서에 대한 단일 센서 쿼리 생성 결과를 검증"""
    query_builder = QueryBuilder(db_client=mocker.MagicMock())

    sql_query = query_builder.build_per_sensor(
        sensor_id="sensor-1",
        sensor_type="anemometer",
        start_date="2026-03-09 00:00:00",
        end_date="2026-03-09 01:00:00",
    )

    assert "FROM anemometer t" in sql_query
    assert "t.wind_speed" in sql_query
    assert "t.wind_direction" in sql_query
    assert "WHERE t.sensor_id = 'sensor-1'" in sql_query
    assert "AND ts BETWEEN '2026-03-09 00:00:00' AND '2026-03-09 01:00:00'" in sql_query


def test_build_per_sensor_should_add_channel_condition_for_motor_sensor(mocker):
    """채널이 있는 모터 센서는 probe 조건과 facility_controls 조인이 포함되는지 검증"""
    query_builder = QueryBuilder(db_client=mocker.MagicMock())

    sql_query = query_builder.build_per_sensor(
        sensor_id="motor-1",
        sensor_type="agsmotor_green",
        start_date="2026-03-09 00:00:00",
        end_date="2026-03-09 01:00:00",
        channel="ch1",
    )

    assert "FROM agsmotor_green t" in sql_query
    assert "LEFT JOIN facility_controls fc" in sql_query
    assert "t.open_rate" in sql_query
    assert "t.probe" in sql_query
    assert "and probe = ch1" in sql_query


def test_build_should_return_query_list_for_multiple_sensor_ids(mocker):
    """여러 센서 ID 입력 시 sensor_type 조회 결과를 기반으로 쿼리 리스트가 생성되는지 검증"""
    mock_database_client = mocker.MagicMock()
    mock_database_client.execute_sensor_types_query.return_value = [
        {"sensor_id": "sensor-1", "sensor_type": "anemometer"},
        {"sensor_id": "motor-1", "sensor_type": "agsmotor_green"},
    ]
    query_builder = QueryBuilder(db_client=mock_database_client)

    queries = query_builder.build(
        sensor_ids=["sensor-1", "motor-1:ch2"],
        start_date="2026-03-09 00:00:00",
        end_date="2026-03-09 01:00:00",
    )

    assert len(queries) == 2
    assert "FROM anemometer t" in queries[0]
    assert "FROM agsmotor_green t" in queries[1]
    assert "and probe = ch2" in queries[1]
    mock_database_client.execute_sensor_types_query.assert_called_once_with(["sensor-1", "motor-1"])


def test_build_should_use_unknown_type_when_sensor_type_query_fails(mocker):
    """sensor_type 조회 실패 시 unknown 타입 쿼리로 fallback 되는지 검증"""
    mock_database_client = mocker.MagicMock()
    mock_database_client.execute_sensor_types_query.side_effect = Exception("DB connection failed")
    query_builder = QueryBuilder(db_client=mock_database_client)

    queries = query_builder.build(
        sensor_ids=["sensor-1"],
        start_date="2026-03-09 00:00:00",
        end_date="2026-03-09 01:00:00",
    )

    assert len(queries) == 1
    assert "FROM unknown t" in queries[0]
    assert "WHERE t.sensor_id = 'sensor-1'" in queries[0]


@pytest.mark.parametrize("mode", ["exact", "nearest", "nearest_within_60s", "bucket"])
def test_set_ts_join_mode_should_accept_supported_modes(mocker, mode):
    """지원되는 ts_join_mode 값들이 정상 설정되는지 검증"""
    query_builder = QueryBuilder(db_client=mocker.MagicMock())

    query_builder.set_ts_join_mode(mode)

    assert query_builder.ts_join_mode == mode


def test_set_ts_join_mode_should_raise_value_error_for_invalid_mode(mocker):
    """지원하지 않는 ts_join_mode 입력 시 ValueError가 발생하는지 검증"""
    query_builder = QueryBuilder(db_client=mocker.MagicMock())

    with pytest.raises(ValueError, match="ts_join_mode"):
        query_builder.set_ts_join_mode("invalid")


def test_set_bucket_seconds_should_raise_value_error_for_non_positive_value(mocker):
    """bucket_seconds가 0 이하이면 ValueError가 발생하는지 검증"""
    query_builder = QueryBuilder(db_client=mocker.MagicMock())

    with pytest.raises(ValueError, match="bucket_seconds"):
        query_builder.set_bucket_seconds(0)
