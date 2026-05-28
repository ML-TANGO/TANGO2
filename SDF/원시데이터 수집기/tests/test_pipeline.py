from contextlib import contextmanager

import pytest

from src import pipeline as pipeline_module
from src.pipeline import DataPipeline


class DummyDatabaseClient:
    """실제 DB 연결을 하지 않는 테스트용 DatabaseClient"""

    def __init__(self, config_path="config/settings.yaml"):
        self.config_path = config_path
        self.connection = None
        self.execute_query_result = []
        self.execute_query_error = None
        self.executed_queries = []
        self.connected = False

    @contextmanager
    def get_connection(self):
        self.connected = True
        self.connection = object()
        try:
            yield self
        finally:
            self.connected = False
            self.connection = None

    def execute_query(self, query):
        self.executed_queries.append(query)
        if self.execute_query_error is not None:
            raise self.execute_query_error
        return self.execute_query_result


class DummyQueryBuilder:
    """실제 쿼리 생성 세부 구현과 분리된 테스트용 QueryBuilder"""

    def __init__(self, database_client):
        self.database_client = database_client
        self.ts_join_mode = "nearest"
        self.columns = ["temp", "humi", "out_temp"]
        self.build_result = "SELECT * FROM test_table"
        self.build_error = None
        self.build_call_count = 0
        self.build_call_arguments = []

    def set_ts_join_mode(self, mode):
        if mode not in ("exact", "nearest", "nearest_within_60s", "bucket"):
            raise ValueError("invalid mode")
        self.ts_join_mode = mode

    def build(self, *args, **kwargs):
        self.build_call_count += 1
        self.build_call_arguments.append((args, kwargs))
        if self.build_error is not None:
            raise self.build_error
        return self.build_result


@pytest.fixture
def pipeline_with_mocked_dependencies(monkeypatch, tmp_path):
    """DataPipeline의 외부 의존성을 모두 Mock 객체로 교체한 fixture"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pipeline_module, "DatabaseClient", DummyDatabaseClient)
    monkeypatch.setattr(pipeline_module, "QueryBuilder", DummyQueryBuilder)
    return DataPipeline(config_path="config/settings.yaml")


class TestDataPipeline:
    """DataPipeline 클래스 테스트"""

    def test_pipeline_initialization(self, pipeline_with_mocked_dependencies):
        """파이프라인 초기화 시 DB 클라이언트, 쿼리 빌더, 로거가 생성되는지 검증"""
        pipeline = pipeline_with_mocked_dependencies

        assert isinstance(pipeline.db_client, DummyDatabaseClient)
        assert isinstance(pipeline.query_builder, DummyQueryBuilder)
        assert pipeline.logger is not None
        assert pipeline.weather_file is None

    def test_set_weather_file_should_store_file_name(self, pipeline_with_mocked_dependencies):
        """기상 파일명을 파이프라인 상태에 저장하는지 검증"""
        pipeline = pipeline_with_mocked_dependencies

        pipeline.set_weather_file("kma_181_20260211_20260511.csv")

        assert pipeline.weather_file == "kma_181_20260211_20260511.csv"

    def test_set_ts_join_mode_should_delegate_to_query_builder(self, pipeline_with_mocked_dependencies):
        """시간 조인 모드 설정이 QueryBuilder로 위임되는지 검증"""
        pipeline = pipeline_with_mocked_dependencies

        pipeline.set_ts_join_mode("nearest_within_60s")

        assert pipeline.query_builder.ts_join_mode == "nearest_within_60s"

    def test_set_ts_join_mode_should_raise_value_error_for_invalid_mode(self, pipeline_with_mocked_dependencies):
        """지원하지 않는 시간 조인 모드는 ValueError를 발생시키는지 검증"""
        pipeline = pipeline_with_mocked_dependencies

        with pytest.raises(ValueError):
            pipeline.set_ts_join_mode("invalid_mode")

    def test_validate_request_should_return_true_when_query_builder_accepts_request(
        self,
        pipeline_with_mocked_dependencies,
    ):
        """QueryBuilder가 요청을 수락하면 validate_request()가 True를 반환하는지 검증"""
        pipeline = pipeline_with_mocked_dependencies

        result = pipeline.validate_request(["temp", "humi"])

        assert result is True
        assert pipeline.query_builder.build_call_count == 1
        assert pipeline.query_builder.build_call_arguments[0][1]["requested_columns"] == ["temp", "humi"]

    def test_validate_request_should_return_false_when_query_builder_raises_value_error(
        self,
        pipeline_with_mocked_dependencies,
    ):
        """QueryBuilder가 ValueError를 발생시키면 validate_request()가 False를 반환하는지 검증"""
        pipeline = pipeline_with_mocked_dependencies
        pipeline.query_builder.build_error = ValueError("invalid column")

        result = pipeline.validate_request(["invalid_column"])

        assert result is False

    def test_get_available_columns_should_return_query_builder_columns(self, pipeline_with_mocked_dependencies):
        """사용 가능 컬럼 목록이 QueryBuilder.columns에서 반환되는지 검증"""
        pipeline = pipeline_with_mocked_dependencies

        assert pipeline.get_available_columns() == ["temp", "humi", "out_temp"]

    def test_get_pipeline_status_should_return_current_state(self, pipeline_with_mocked_dependencies):
        """파이프라인 상태 딕셔너리에 주요 상태 값이 포함되는지 검증"""
        pipeline = pipeline_with_mocked_dependencies

        status = pipeline.get_pipeline_status()

        assert status["ts_join_mode"] == "nearest"
        assert status["available_columns"] == ["temp", "humi", "out_temp"]
        assert status["db_connected"] is False
        assert "timestamp" in status

    def test_collect_data_should_execute_built_query_and_return_rows(self, pipeline_with_mocked_dependencies):
        """쿼리 생성 후 DB 실행 결과가 반환되는 정상 흐름을 검증"""
        pipeline = pipeline_with_mocked_dependencies
        pipeline.db_client.execute_query_result = [{"temp": 25.1}, {"temp": 25.2}]

        result = pipeline.collect_data(
            requested_columns=["temp"],
            start_time="2026-03-09 00:00:00",
            end_time="2026-03-09 01:00:00",
            ts_join_mode="exact",
        )

        assert result == [{"temp": 25.1}, {"temp": 25.2}]
        assert pipeline.query_builder.ts_join_mode == "exact"
        assert pipeline.query_builder.build_call_count == 1
        assert pipeline.db_client.executed_queries == ["SELECT * FROM test_table"]

    def test_collect_data_should_raise_database_error(self, pipeline_with_mocked_dependencies):
        """DB 실행 중 예외가 발생하면 호출자에게 다시 전달되는지 검증"""
        pipeline = pipeline_with_mocked_dependencies
        pipeline.db_client.execute_query_error = Exception("Database connection failed")

        with pytest.raises(Exception, match="Database connection failed"):
            pipeline.collect_data(
                requested_columns=["temp"],
                start_time="2026-03-09 00:00:00",
                end_time="2026-03-09 01:00:00",
            )

    def test_collect_data_should_raise_query_builder_error(self, pipeline_with_mocked_dependencies):
        """쿼리 생성 중 예외가 발생하면 DB 실행 없이 예외가 전달되는지 검증"""
        pipeline = pipeline_with_mocked_dependencies
        pipeline.query_builder.build_error = ValueError("query build failed")

        with pytest.raises(ValueError, match="query build failed"):
            pipeline.collect_data(
                requested_columns=["invalid_column"],
                start_time="2026-03-09 00:00:00",
                end_time="2026-03-09 01:00:00",
            )

        assert pipeline.db_client.executed_queries == []
