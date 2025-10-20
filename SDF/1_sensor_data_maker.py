import pandas as pd
from datetime import datetime
import numpy as np

# 1. 온습도 정보 db에서 가져온거 data_sample.csv 파일에 추가
def add_thermo_data_to_csv():
    try:
        existing_df = pd.read_csv('data/data_sample.csv')
        print(f"기존 파일에서 {len(existing_df)}개 행을 찾았습니다.")
    except FileNotFoundError:
        # 파일이 없으면 빈 DataFrame 생성 (컬럼만)
        existing_df = pd.DataFrame(columns=[
            'house_number', 'plant_name', 'planting_date', 'date', 'time', 
            'indoor_temperature', 'indoor_humidity', 'outdoor_temperature', 'outdoor_humidity',
            'wind_direction', 'wind_speed', 'inner_left_window_top_opening', 
            'inner_left_window_bottom_opening', 'inner_right_window_top_opening', 
            'inner_right_window_bottom_opening', 'outer_left_window_top_opening', 
            'outer_left_window_bottom_opening', 'outer_right_window_top_opening', 
            'outer_right_window_bottom_opening'
        ])
        print("새로운 파일을 생성합니다.")

    # 원본 온습도 데이터 읽기
    thermo_df = pd.read_csv('data/thermohygro_202509190948.csv')

    # ts 컬럼을 날짜와 시간으로 분리
    thermo_df['ts'] = pd.to_datetime(thermo_df['ts'])
    thermo_df['date'] = thermo_df['ts'].dt.strftime('%Y-%m-%d')
    thermo_df['time'] = thermo_df['ts'].dt.strftime('%H:%M:%S')

    new_data = []
    for idx, row in thermo_df.iterrows():
        new_row = {
            'house_number': None,
            'plant_name': None,
            'planting_date': None,
            'date': row['date'],
            'time': row['time'],
            'indoor_temperature': row['temp'],
            'indoor_humidity': row['humi'],
            'outdoor_temperature': None,
            'outdoor_humidity': None,
            'wind_direction': None,
            'wind_speed': None,
            'inner_left_window_top_opening': None,
            'inner_left_window_bottom_opening': None,
            'inner_right_window_top_opening': None,
            'inner_right_window_bottom_opening': None,
            'outer_left_window_top_opening': None,
            'outer_left_window_bottom_opening': None,
            'outer_right_window_top_opening': None,
            'outer_right_window_bottom_opening': None
        }
        new_data.append(new_row)

    # DataFrame으로 변환
    new_df = pd.DataFrame(new_data)

    # 기존 데이터와 새 데이터를 합치기
    combined_df = pd.concat([existing_df, new_df], ignore_index=True)

    # 결과를 CSV 파일로 저장 (기존 파일에 추가)
    combined_df.to_csv('data/data_sample.csv', index=False)

    print(f"총 {len(combined_df)}개 행이 저장되었습니다.")
    print(f"새로 추가된 행: {len(new_df)}개")

if __name__ == "__main__":
    add_thermo_data_to_csv()
