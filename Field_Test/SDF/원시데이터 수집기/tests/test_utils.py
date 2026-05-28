import importlib
from pathlib import Path

import pytest

from src import utils


class TestUtils:
    """src.utils 모듈 테스트"""

    def test_utils_module_exists(self):
        """프로젝트 루트의 src/utils.py 파일이 존재하는지 검증"""
        utils_path = Path(__file__).resolve().parents[1] / "src" / "utils.py"

        assert utils_path.exists(), "src/utils.py 파일이 존재해야 합니다"

    def test_utils_import_success(self):
        """src.utils 모듈 import가 정상 동작하는지 검증"""
        assert utils is not None
        assert utils.__name__ == "src.utils"

    def test_column_list_should_contain_core_sensor_columns(self):
        """핵심 센서 컬럼들이 COLUMN_LIST에 포함되어 있는지 검증"""
        expected_columns = {"temp", "humi", "out_temp", "out_humi", "open_rate_ch1", "SS", "SI", "PA"}

        assert expected_columns.issubset(set(utils.COLUMN_LIST))

    def test_column_condition_should_define_min_max_for_known_columns(self):
        """컬럼별 경계 조건이 min/max 구조로 정의되어 있는지 검증"""
        for column_name in ["out_temp", "out_humi", "out_wind_speed", "open_rate_ch1", "temp", "default"]:
            assert column_name in utils.COLUMN_CONDITION
            assert "min" in utils.COLUMN_CONDITION[column_name]
            assert "max" in utils.COLUMN_CONDITION[column_name]

    @pytest.mark.parametrize(
        ("column_name", "expected_min", "expected_max"),
        [
            ("out_humi", 0, 100),
            ("out_wind_speed", 0, 80),
            ("out_rain", 0, 1.0),
            ("open_rate_ch1", 0, 100),
            ("temp", -100, 50),
        ],
    )
    def test_column_condition_should_match_expected_ranges(self, column_name, expected_min, expected_max):
        """주요 컬럼별 허용 범위가 기대값과 일치하는지 검증"""
        condition = utils.COLUMN_CONDITION[column_name]

        assert condition["min"] == expected_min
        assert condition["max"] == expected_max

    def test_sensor_threshold_should_define_motor_and_environment_thresholds(self):
        """센서 타입별 threshold 설정이 존재하고 양수인지 검증"""
        assert utils.SENSOR_THRESHOLD["motor"] == 130
        assert utils.SENSOR_THRESHOLD["env_sensor"] == 120
        assert all(value > 0 for value in utils.SENSOR_THRESHOLD.values())

    def test_utils_module_should_reload_without_side_effects(self):
        """utils 모듈 재로딩 시 예외가 발생하지 않는지 검증"""
        reloaded_utils = importlib.reload(utils)

        assert reloaded_utils.COLUMN_LIST == utils.COLUMN_LIST
