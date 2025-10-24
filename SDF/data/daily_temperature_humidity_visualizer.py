import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# 한글 폰트 설정
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

def visualize_daily_temperature_humidity():
    """
    merged_sample_with_kma.csv에서 온도와 습도를 5분 단위로 하루씩 시각화
    """
    print("5분 단위 온도/습도 시각화 중...")
    
    # 데이터 로드
    df = pd.read_csv('merged_sample_with_kma.csv')
    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
    
    print(f"데이터 로드 완료: {len(df):,}개 행")
    print(f"시간 범위: {df['datetime'].min()} ~ {df['datetime'].max()}")
    
    # 날짜별로 그룹화
    df['date_only'] = df['datetime'].dt.date
    unique_dates = sorted(df['date_only'].unique())
    
    print(f"총 {len(unique_dates)}일의 데이터")
    
    # 월별로 그룹화하고 각 월에서 랜덤하게 5일씩 선택
    df['month'] = df['datetime'].dt.month
    months = sorted(df['month'].unique())
    
    # 모든 날짜 선택
    selected_dates = sorted(df['date_only'].unique())
    print(f"\n총 {len(selected_dates)}일 시각화 예정")
    
    # 모든 날짜 시각화
    for i, date in enumerate(selected_dates):
        daily_df = df[df['date_only'] == date].copy()
        daily_df = daily_df.sort_values('datetime')
        
        print(f"\n{date} 시각화 중... ({len(daily_df)}개 데이터 포인트)")
        
        # 절대습도 계산 함수
        def calculate_absolute_humidity(temp_c, rh_percent):
            """절대습도 계산 (g/m³)"""
            # Magnus 공식으로 포화수증기압 계산
            es = 6.11 * 10 ** (7.5 * temp_c / (237.7 + temp_c))
            # 절대습도 계산
            ah = (rh_percent / 100) * es * 18.016 / (8.314 * (273.15 + temp_c))
            return ah
        
        # 절대습도 계산
        daily_df['kma_absolute_humidity'] = calculate_absolute_humidity(daily_df['kma_temperature'], daily_df['kma_humidity'])
        daily_df['indoor_absolute_humidity'] = calculate_absolute_humidity(daily_df['indoor_temperature'], daily_df['indoor_humidity'])
        
        # 시각화
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 15))
        fig.suptitle(f'Temperature, Absolute Humidity, and Solar Irradiance - {date} (5-minute intervals)', fontsize=16, fontweight='bold')
        
        # 시간을 x축으로 사용 (시간만 표시)
        time_labels = daily_df['datetime'].dt.strftime('%H:%M')
        
        # 온도 그래프 (KMA vs 실내 센서 데이터 비교)
        ax1.plot(daily_df['datetime'], daily_df['kma_temperature'], 'r-', linewidth=2, marker='o', markersize=3, label='KMA Temperature (Outdoor)', alpha=0.8)
        ax1.plot(daily_df['datetime'], daily_df['indoor_temperature'], 'b-', linewidth=2, marker='s', markersize=3, label='Sensor Temperature (Indoor)', alpha=0.8)
        ax1.set_title(f'Temperature Comparison (°C) - {date}', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Temperature (°C)', fontsize=12)
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        ax1.tick_params(axis='x', rotation=45)
        
        # 절대습도 그래프 (KMA vs 실내 센서 데이터 비교)
        ax2.plot(daily_df['datetime'], daily_df['kma_absolute_humidity'], 'r-', linewidth=2, marker='o', markersize=3, label='KMA Absolute Humidity (Outdoor)', alpha=0.8)
        ax2.plot(daily_df['datetime'], daily_df['indoor_absolute_humidity'], 'b-', linewidth=2, marker='s', markersize=3, label='Sensor Absolute Humidity (Indoor)', alpha=0.8)
        ax2.set_title(f'Absolute Humidity Comparison (g/m³) - {date}', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Absolute Humidity (g/m³)', fontsize=12)
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        ax2.tick_params(axis='x', rotation=45)
        
        # 일조량 그래프 (KMA 데이터만)
        ax3.plot(daily_df['datetime'], daily_df['kma_solar_irradiance'], 'g-', linewidth=2, marker='o', markersize=3, label='KMA Solar Irradiance', alpha=0.8)
        ax3.set_title(f'Solar Irradiance - {date}', fontsize=14, fontweight='bold')
        ax3.set_ylabel('Solar Irradiance', fontsize=12)
        ax3.set_xlabel('Time', fontsize=12)
        ax3.grid(True, alpha=0.3)
        ax3.legend()
        ax3.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(f'temperature_humidity_{date}.png', dpi=300, bbox_inches='tight')
        plt.close()  # 창을 띄우지 않고 닫기
        
        # 해당 날짜 통계 (KMA vs 실내 센서 데이터 비교)
        print(f"  KMA 온도 범위: {daily_df['kma_temperature'].min():.2f}°C ~ {daily_df['kma_temperature'].max():.2f}°C")
        print(f"  실내 센서 온도 범위: {daily_df['indoor_temperature'].min():.2f}°C ~ {daily_df['indoor_temperature'].max():.2f}°C")
        print(f"  온도 차이 평균: {(daily_df['kma_temperature'] - daily_df['indoor_temperature']).mean():.2f}°C")
        print(f"  KMA 절대습도 범위: {daily_df['kma_absolute_humidity'].min():.2f} ~ {daily_df['kma_absolute_humidity'].max():.2f} g/m³")
        print(f"  실내 센서 절대습도 범위: {daily_df['indoor_absolute_humidity'].min():.2f} ~ {daily_df['indoor_absolute_humidity'].max():.2f} g/m³")
        print(f"  절대습도 차이 평균: {(daily_df['kma_absolute_humidity'] - daily_df['indoor_absolute_humidity']).mean():.2f} g/m³")
        print(f"  KMA 일조량 범위: {daily_df['kma_solar_irradiance'].min():.2f} ~ {daily_df['kma_solar_irradiance'].max():.2f}")
        print(f"  일조량 평균: {daily_df['kma_solar_irradiance'].mean():.2f}")
    
    return df

if __name__ == "__main__":
    daily_data = visualize_daily_temperature_humidity()
