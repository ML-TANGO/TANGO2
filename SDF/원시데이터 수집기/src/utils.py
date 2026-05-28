COLUMN_LIST = [
    "out_temp",
    "out_humi",
    "out_wind_speed",
    "out_wind_direction",
    "out_rain",
    "open_rate_ch8",
    "open_rate_ch2",
    "open_rate_ch7",
    "open_rate_ch3",
    "open_rate_ch6",
    "open_rate_ch5",
    "open_rate_ch4",
    "open_rate_ch1",
    "temp",
    "humi",
    "SS",
    "SI",
    "PA"]

COLUMN_CONDITION = {
    "out_temp": {"min": -100, "max": 50},
    "out_humi": {"min": 0, "max": 100},
    "out_wind_speed": {"min": 0, "max": 80},
    "out_wind_direction": {"min": 0, "max": 360},
    "out_rain": {"min": 0, "max": 1.0},
    "open_rate_ch8": {"min": 0, "max": 100},
    "open_rate_ch2": {"min": 0, "max": 100},
    "open_rate_ch7": {"min": 0, "max": 100},
    "open_rate_ch3": {"min": 0, "max": 100},
    "open_rate_ch6": {"min": 0, "max": 100},
    "open_rate_ch5": {"min": 0, "max": 100},
    "open_rate_ch4": {"min": 0, "max": 100},
    "open_rate_ch1": {"min": 0, "max": 100},
    "temp": {"min": -100, "max": 50},
    "humi": {"min": 0, "max": 100},
    "SS": {"min": 0, "max": 1.0},
    "SI": {"min": 0, "max": 100000},
    "default": {"min": float("-inf"), "max": float("inf")}
}

#각 센서 타입 별 threshold
# motor센서: 130 초
# 환경 센서 : 120 초
SENSOR_THRESHOLD = {
    "motor" : 130,
    "env_sensor" : 120
}