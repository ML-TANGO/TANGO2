from pathlib import Path

import pandas as pd
import pytest
import requests

from src.data_collection.weather_api import WeatherAPIClient


@pytest.fixture
def sample_kma_text() -> str:
    """기상청 API 응답과 같은 공백 구분 TXT fixture"""
    return "\n".join(
        [
            "# YYMMDDHHMI STN WD WS TA HM RN",
            "202602110000 181 270 1.5 3.2 71.0 0.0",
            "202602110100 181 260 1.8 3.5 70.0 -9.0",
        ]
    )


@pytest.fixture
def weather_client(monkeypatch, tmp_path) -> WeatherAPIClient:
    """실제 API와 실제 pipeline_output을 사용하지 않는 테스트용 클라이언트 fixture"""
    monkeypatch.setenv("WEATHER_API_TIMEOUT", "30")
    monkeypatch.setenv("WEATHER_API_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("LOGGING_LEVEL", "INFO")
    monkeypatch.chdir(tmp_path)
    return WeatherAPIClient()


def test_parse_kma_text_to_dataframe_should_parse_rows_and_save_csv(weather_client, sample_kma_text):
    """정상 TXT 응답을 DataFrame으로 파싱하고 CSV로 저장하는지 검증"""
    dataframe = weather_client.parse_kma_text_to_dataframe(
        sample_kma_text,
        station_id=181,
        start_datetime="202602110000",
        end_datetime="202602110100",
    )

    assert list(dataframe.columns) == ["YYMMDDHHMI", "STN", "WD", "WS", "TA", "HM", "RN"]
    assert len(dataframe) == 2
    assert dataframe.loc[0, "YYMMDDHHMI"] == "202602110000"

    csv_path = Path("pipeline_output/kma_data/csv/kma_181_20260211_20260211.csv")
    assert csv_path.exists()
    saved_dataframe = pd.read_csv(csv_path, dtype=str)
    assert len(saved_dataframe) == 2


def test_parse_kma_text_to_dataframe_should_pad_short_rows_and_trim_long_rows(weather_client):
    """컬럼 수보다 짧거나 긴 데이터 행의 파일 포맷 예외 상황을 검증"""
    text = "\n".join(
        [
            "# YYMMDDHHMI STN WD WS",
            "202602110000 181 270",
            "202602110100 181 260 1.8 EXTRA_VALUE",
        ]
    )

    dataframe = weather_client.parse_kma_text_to_dataframe(
        text,
        station_id=181,
        start_datetime="202602110000",
        end_datetime="202602110100",
    )

    assert dataframe.loc[0, "WS"] is None
    assert list(dataframe.columns) == ["YYMMDDHHMI", "STN", "WD", "WS"]
    assert dataframe.loc[1, "WS"] == "1.8"


def test_parse_kma_text_to_dataframe_should_return_empty_dataframe_when_header_is_missing(weather_client):
    """헤더가 없는 비정상 TXT 포맷은 빈 DataFrame으로 처리되는지 검증"""
    dataframe = weather_client.parse_kma_text_to_dataframe(
        "202602110000 181 270 1.5",
        station_id=181,
        start_datetime="202602110000",
        end_datetime="202602110100",
    )

    assert dataframe.empty
    assert Path("pipeline_output/kma_data/csv/kma_181_20260211_20260211.csv").exists()


def test_get_short_term_weather_data_should_save_text_and_csv_when_api_succeeds(
    weather_client,
    sample_kma_text,
    mocker,
):
    """단기 조회 성공 시 원본 TXT와 파싱 CSV가 함께 생성되는지 검증"""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.encoding = None
    mock_response.apparent_encoding = "utf-8"
    mock_response.text = sample_kma_text
    weather_client.session.get = mocker.MagicMock(return_value=mock_response)

    result = weather_client.get_short_term_weather_data("202602110000", "202602110100", station_id=181)

    assert result == sample_kma_text
    weather_client.session.get.assert_called_once()
    _, call_kwargs = weather_client.session.get.call_args
    assert call_kwargs["params"]["authKey"] == "test-service-key"
    assert call_kwargs["params"]["stn"] == 181
    assert Path("pipeline_output/kma_data/text/kma_181_20260211_20260211.txt").exists()
    assert Path("pipeline_output/kma_data/csv/kma_181_20260211_20260211.csv").exists()


@pytest.mark.parametrize(
    ("start_datetime", "end_datetime", "expected_message"),
    [
        ("2026-02-11", "202602110100", "날짜 형식이 올바르지 않습니다"),
        ("202602110000", "202603200000", "한달보다 긴 기간은 조회할 수 없습니다"),
    ],
)
def test_get_short_term_weather_data_should_raise_value_error_for_invalid_input(
    weather_client,
    start_datetime,
    end_datetime,
    expected_message,
):
    """단기 조회 입력 날짜 형식과 기간 제한 예외를 검증"""
    with pytest.raises(ValueError, match=expected_message):
        weather_client.get_short_term_weather_data(start_datetime, end_datetime, station_id=181)


def test_get_short_term_weather_data_should_retry_and_raise_runtime_error_when_request_fails(
    weather_client,
    mocker,
):
    """외부 API 요청 실패가 반복되면 재시도 후 RuntimeError가 발생하는지 검증"""
    weather_client.session.get = mocker.MagicMock(side_effect=requests.RequestException("network down"))
    mock_sleep = mocker.patch("src.data_collection.weather_api.time.sleep")

    with pytest.raises(RuntimeError, match="최대 재시도 횟수"):
        weather_client.get_short_term_weather_data("202602110000", "202602110100", station_id=181)

    assert weather_client.session.get.call_count == 5
    assert mock_sleep.call_count == 4


def test_get_short_term_weather_data_should_retry_when_status_code_is_not_200(weather_client, mocker):
    """HTTP 200이 아닌 응답이 반복될 때 RuntimeError가 발생하는지 검증"""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 500
    mock_response.text = "server error"
    weather_client.session.get = mocker.MagicMock(return_value=mock_response)
    mock_sleep = mocker.patch("src.data_collection.weather_api.time.sleep")

    with pytest.raises(RuntimeError, match="최대 재시도 횟수"):
        weather_client.get_short_term_weather_data("202602110000", "202602110100", station_id=181)

    assert weather_client.session.get.call_count == 5
    assert mock_sleep.call_count == 4


def test_get_long_term_weather_data_should_delegate_to_short_term_when_period_is_within_31_days(
    weather_client,
    mocker,
):
    """31일 이하 장기 조회 요청은 단기 조회로 위임되는지 검증"""
    mock_short_term = mocker.patch.object(weather_client, "get_short_term_weather_data", return_value="short text")

    result = weather_client.get_long_term_weather_data("202602110000", "202602200000", station_id=181)

    assert result == "short text"
    mock_short_term.assert_called_once_with("202602110000", "202602200000", 181)


def test_get_long_term_weather_data_should_split_period_and_save_combined_outputs(
    weather_client,
    sample_kma_text,
    mocker,
):
    """31일 초과 장기 조회는 기간을 분할하고 합쳐진 TXT/CSV를 저장하는지 검증"""
    mock_short_term = mocker.patch.object(
        weather_client,
        "get_short_term_weather_data",
        side_effect=[sample_kma_text, sample_kma_text],
    )

    result = weather_client.get_long_term_weather_data("202602010000", "202603100000", station_id=181)

    assert result == f"{sample_kma_text}\n{sample_kma_text}"
    assert mock_short_term.call_count == 2
    assert mock_short_term.call_args_list[0].args == ("202602010000", "202603040000", 181)
    assert mock_short_term.call_args_list[1].args == ("202603040001", "202603100000", 181)
    assert Path("pipeline_output/kma_data/text/kma_181_20260201_20260310.txt").exists()
    assert Path("pipeline_output/kma_data/csv/kma_181_20260201_20260310.csv").exists()


def test_get_long_term_weather_data_should_raise_value_error_when_start_is_after_end(weather_client):
    """장기 조회 시작 시각이 종료 시각보다 늦은 예외 상황을 검증"""
    with pytest.raises(ValueError, match="시작 시각은 종료 시각보다 이후일 수 없습니다"):
        weather_client.get_long_term_weather_data("202603100000", "202602010000", station_id=181)
