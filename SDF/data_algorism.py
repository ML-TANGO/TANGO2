# =============================================================================
# 하우스 농업 자동화 학습 데이터 샘플 변수 정의
# =============================================================================

# 기본 작물 정보
CROP_NAME = "토마토"                    # 작물명
GROWTH_STAGE = "개화기"                 # 생육단계 (발아, 유묘, 성장, 개화, 결실, 수확)
SEASON = "여름"                        # 계절 (봄, 여름, 가을, 겨울)
SOLAR_TERM = "소서"                    # 절기 (입춘, 경칩, 청명, 입하, 망종, 소서, 입추, 백로, 한로, 입동, 대설, 동지)

# 시간 정보
DATE = "2025-07-28"                    # 날짜 (YYYY-MM-DD 형식)
TIME = "14:30:00"                         # 시간 (HH:MM:SS 형식)

# 온도 및 습도 센서 데이터
INDOOR_TEMPERATURE = 24.5              # 내부온도 (°C)
INDOOR_HUMIDITY = 65.2                 # 내부습도 (%)
OUTDOOR_TEMPERATURE = 28.3             # 외부온도 (°C)
OUTDOOR_HUMIDITY = 58.7                # 외부습도 (%)

# 기상 센서 데이터
RAIN_SENSOR_BOOL = False               # 강우센서 (True: 비가 옴, False: 비가 안 옴)
OUTDOOR_WIND_DIRECTION = 45            # 외부풍향(각도) (0-360도), 북쪽이 0도, 동쪽이 90도, 남쪽이 180도, 서쪽이 270도
OUTDOOR_WIND_SPEED = 3.2               # 외부풍속 (m/s)

# 창문 개폐 상태 (0-100% 범위)
OUTER_LEFT_WINDOW_TOP_OPENING = 75           # 바깥쪽좌측창문상단 개폐정도 (%)
OUTER_LEFT_WINDOW_BOTTOM_OPENING = 60        # 바깥쪽좌측창문하단 개폐정도 (%)
OUTER_RIGHT_WINDOW_TOP_OPENING = 25          # 바깥쪽우측창문상단 개폐정도 (%)
OUTER_RIGHT_WINDOW_BOTTOM_OPENING = 40       # 바깥쪽우측창문하단 개폐정도 (%)
INNER_LEFT_WINDOW_TOP_OPENING = 75           # 안쪽좌측창문상단 개폐정도 (%)
INNER_LEFT_WINDOW_BOTTOM_OPENING = 60        # 안쪽좌측창문하단 개폐정도 (%)
INNER_RIGHT_WINDOW_TOP_OPENING = 25          # 안쪽우측창문상단 개폐정도 (%)
INNER_RIGHT_WINDOW_BOTTOM_OPENING = 40       # 안쪽우측창문하단 개폐정도 (%)

# 급수 이력 (YYYY-MM-DD HH:MM 형식)
LATEST_WATERING_START = "2025-07-28 12:00"     # 가장 최근 급수 시작시각
LATEST_WATERING_END = "2025-07-28 12:15"       # 가장 최근 급수 종료시각
SECOND_LATEST_WATERING_START = "2025-07-28 08:30"  # 2번째로 최근 급수 시작시각
SECOND_LATEST_WATERING_END = "2025-07-28 08:45"    # 2번째로 최근 급수 종료시각

# 온도 변화율 분석 데이터
TEMPERATURE_5M_AGO = 24.3              # 5분 전 온도 (°C)
TEMPERATURE_10M_AGO = 24.2             # 10분 전 온도 (°C)
TEMPERATURE_30M_AGO = 24.1             # 30분 전 온도 (°C)
TEMPERATURE_1H_AGO = 23.8              # 1시간 전 온도 (°C)

TEMP_CHANGE_5M_TO_NOW = 0.2            # 5분 전 ~ 현재시간까지의 시간 변화 대비 온도변화 (°C)
TEMP_CHANGE_10M_TO_5M = 0.1            # 10분 전 ~ 5분 전까지의 시간 변화 대비 온도변화 (°C)
TEMP_CHANGE_30M_TO_10M = 0.1           # 30분 전 ~ 10분 전까지의 시간 변화 대비 온도변화 (°C)
TEMP_CHANGE_1H_TO_30M = 0.3            # 1시간 전 ~ 30분 전까지의 시간 변화 대비 온도변화 (°C)

TEMP_SECOND_DERIVATIVE_SHORT = 0.02     # 7.5분전~2.5분전까지의시간대비온도변화값에서12.5분전~7.5분전까지의시간변화대비온도변화를뺀값을5으로나눈값(단기2차미분값)
TEMP_SECOND_DERIVATIVE_LONG = 0.033     # 45분전~15분전까지의시간대비온도변화값에서1시간15분전~45분전까지의시간변화대비온도변화를뺀값을30으로나눈값(장기2차미분값)

# 예측 데이터 - 미분값과 2차 미분값을 통해 계산한 값을 사용할 예정
PREDICTED_NEXT_TIME = "2025-07-28 15:00"  # 예측된 다음 지점의 시간
PREDICTED_NEXT_TEMPERATURE = 25.1         # 예측된 다음 지점의 온도 (°C)

# 적정 환경 기준값
OPTIMAL_TEMPERATURE = 24.0             # 현재기준 적절한 온도 (°C)
OPTIMAL_HUMIDITY = 65.0                # 현재기준 적절한 습도 (%)

# =============================================================================
# 하우스 농업 자동화 학습 데이터 샘플 딕셔너리
# =============================================================================
house_agriculture_sample = {
    "작물명": CROP_NAME,
    "생육단계": GROWTH_STAGE,
    "계절": SEASON,
    "절기": SOLAR_TERM,
    "날짜": DATE,
    "시간": TIME,
    "내부온도": INDOOR_TEMPERATURE,
    "내부습도": INDOOR_HUMIDITY,
    "외부온도": OUTDOOR_TEMPERATURE,
    "외부습도": OUTDOOR_HUMIDITY,
    "강우센서bool": RAIN_SENSOR_BOOL,
    "외부풍향": OUTDOOR_WIND_DIRECTION,
    "외부풍속": OUTDOOR_WIND_SPEED,
    "바깥쪽좌측창문상단개폐정도": OUTER_LEFT_WINDOW_TOP_OPENING,
    "바깥쪽좌측창문하단개폐정도": OUTER_LEFT_WINDOW_BOTTOM_OPENING,
    "바깥쪽우측창문상단개폐정도": OUTER_RIGHT_WINDOW_TOP_OPENING,
    "바깥쪽우측창문하단개폐정도": OUTER_RIGHT_WINDOW_BOTTOM_OPENING,
    "안쪽좌측창문상단개폐정도": INNER_LEFT_WINDOW_TOP_OPENING,
    "안쪽좌측창문하단개폐정도": INNER_LEFT_WINDOW_BOTTOM_OPENING,
    "안쪽우측창문상단개폐정도": INNER_RIGHT_WINDOW_TOP_OPENING,
    "안쪽우측창문하단개폐정도": INNER_RIGHT_WINDOW_BOTTOM_OPENING,
    "가장최근급수시작시각": LATEST_WATERING_START,
    "가장최근급수종료시각": LATEST_WATERING_END,
    "2번째로최근급수시작시각": SECOND_LATEST_WATERING_START,
    "2번째로최근급수종료시각": SECOND_LATEST_WATERING_END,
    "1시간전온도": TEMPERATURE_1H_AGO,
    "30분전온도": TEMPERATURE_30M_AGO,
    "5분전온도": TEMPERATURE_5M_AGO,
    "10분전온도": TEMPERATURE_10M_AGO,
    "1시간전~30분전까지의시간변화대비온도변화": TEMP_CHANGE_1H_TO_30M,
    "5분전~10분전까지의시간변화대비온도변화": TEMP_CHANGE_10M_TO_5M,
    "10분전~30분전까지의시간변화대비온도변화": TEMP_CHANGE_30M_TO_10M,
    "45분전~15분전까지의시간대비온도변화값에서1시간15분전~45분전까지의시간변화대비온도변화를뺀값을30으로나눈값(2차미분값)": TEMP_SECOND_DERIVATIVE_LONG,
    "7.5분전~2.5분전까지의시간대비온도변화값에서12.5분전~7.5분전까지의시간변화대비온도변화를뺀값을5으로나눈값(단기2차미분값)": TEMP_SECOND_DERIVATIVE_SHORT,
    "예측된다음지점의시간": PREDICTED_NEXT_TIME,
    "예측된다음지점의온도": PREDICTED_NEXT_TEMPERATURE,
    "현재기준적절한온도": OPTIMAL_TEMPERATURE,
    "현재기준적절한습도": OPTIMAL_HUMIDITY
}

