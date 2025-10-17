import pandas as pd
import numpy as np

def calculate_hourly_precipitation_intensity():
    """
    merged_kma_data.csv의 누적 강수량을 시간당 강수강도로 변환
    """
    # CSV 파일 읽기
    df = pd.read_csv('1_merged_kma_data.csv')
    
    print(f"원본 데이터 shape: {df.shape}")
    print(f"컬럼명: {df.columns.tolist()}")
    
    # rain_day와 snow_day 컬럼을 숫자형으로 변환 (빈 값은 NaN으로 처리)
    df['rain_day'] = pd.to_numeric(df['rain_day'], errors='coerce')
    df['snow_day'] = pd.to_numeric(df['snow_day'], errors='coerce')
    
    # 시간당 강수강도 계산을 위한 새로운 컬럼 초기화
    df['rain_per_hour'] = 0.0
    df['snow_per_hour'] = 0.0
    
    # 각 관측소별로 그룹화하여 처리
    for stn_id in df['stn_id'].unique():
        if pd.isna(stn_id):
            continue
            
        # 해당 관측소의 데이터만 추출
        stn_mask = df['stn_id'] == stn_id
        stn_data = df[stn_mask].copy()
        
        # 날짜별로 그룹화
        for date in stn_data['date'].unique():
            if pd.isna(date):
                continue
                
            # 해당 날짜의 데이터만 추출
            date_mask = stn_data['date'] == date
            date_data = stn_data[date_mask].copy()
            
            # 시간순으로 정렬 (time 컬럼 기준)
            date_data = date_data.sort_values('time')
            
            # rain_day의 시간당 강수강도 계산
            rn_values = date_data['rain_day'].values
            rain_per_hour = np.zeros(len(rn_values))
            
            for i in range(len(rn_values)):
                if i == 0:
                    # 첫 번째 시간: 다음 시간과의 차이
                    if len(rn_values) > 1 and not pd.isna(rn_values[i+1]):
                        rain_per_hour[i] = rn_values[i+1] - rn_values[i]
                elif i == len(rn_values) - 1:
                    # 마지막 시간: 이전 시간과의 차이
                    if not pd.isna(rn_values[i-1]):
                        rain_per_hour[i] = rn_values[i] - rn_values[i-1]
                else:
                    # 중간 시간: 앞뒤 시간과의 차이의 평균
                    prev_diff = 0
                    next_diff = 0
                    
                    if not pd.isna(rn_values[i-1]):
                        prev_diff = rn_values[i] - rn_values[i-1]
                    if not pd.isna(rn_values[i+1]):
                        next_diff = rn_values[i+1] - rn_values[i]
                    
                    if not pd.isna(rn_values[i-1]) and not pd.isna(rn_values[i+1]):
                        rain_per_hour[i] = (prev_diff + next_diff) / 2
                    elif not pd.isna(rn_values[i-1]):
                        rain_per_hour[i] = prev_diff
                    elif not pd.isna(rn_values[i+1]):
                        rain_per_hour[i] = next_diff
            
            # snow_day의 시간당 강설강도 계산 (동일한 로직)
            sd_values = date_data['snow_day'].values
            snow_per_hour = np.zeros(len(sd_values))
            
            for i in range(len(sd_values)):
                if i == 0:
                    if len(sd_values) > 1 and not pd.isna(sd_values[i+1]):
                        snow_per_hour[i] = sd_values[i+1] - sd_values[i]
                elif i == len(sd_values) - 1:
                    if not pd.isna(sd_values[i-1]):
                        snow_per_hour[i] = sd_values[i] - sd_values[i-1]
                else:
                    prev_diff = 0
                    next_diff = 0
                    
                    if not pd.isna(sd_values[i-1]):
                        prev_diff = sd_values[i] - sd_values[i-1]
                    if not pd.isna(sd_values[i+1]):
                        next_diff = sd_values[i+1] - sd_values[i]
                    
                    if not pd.isna(sd_values[i-1]) and not pd.isna(sd_values[i+1]):
                        snow_per_hour[i] = (prev_diff + next_diff) / 2
                    elif not pd.isna(sd_values[i-1]):
                        snow_per_hour[i] = prev_diff
                    elif not pd.isna(sd_values[i+1]):
                        snow_per_hour[i] = next_diff
            
            # 음수 값은 0으로 처리 (누적값이 감소하는 경우)
            rain_per_hour = np.maximum(rain_per_hour, 0)
            snow_per_hour = np.maximum(snow_per_hour, 0)
            
            # 원본 데이터프레임에 결과 업데이트
            date_indices = df[stn_mask & (df['date'] == date)].index
            df.loc[date_indices, 'rain_per_hour'] = rain_per_hour
            df.loc[date_indices, 'snow_per_hour'] = snow_per_hour
    
    # 소수점 둘째자리에서 반올림
    df['rain_per_hour'] = df['rain_per_hour'].round(2)
    df['snow_per_hour'] = df['snow_per_hour'].round(2)
    
    # 원본 컬럼 제거
    df = df.drop(['rain_day', 'snow_day'], axis=1)
    
    # 결과 저장
    output_filename = '2_fixed_rainsnow_kma_data.csv'
    df.to_csv(output_filename, index=False)
    
    print(f"\n처리 완료!")
    print(f"새로운 컬럼 추가: rain_per_hour, snow_per_hour")
    print(f"원본 컬럼 제거: rain_day, snow_day")
    print(f"결과 저장: {output_filename}")
    print(f"최종 데이터 shape: {df.shape}")
    
    # 샘플 데이터 출력
    print("\n샘플 데이터 (처리된 결과):")
    sample_data = df[['date', 'time', 'stn_id', 'rain_per_hour', 'snow_per_hour']].head(10)
    print(sample_data.to_string(index=False))
    
    return df

if __name__ == "__main__":
    result_df = calculate_hourly_precipitation_intensity()
