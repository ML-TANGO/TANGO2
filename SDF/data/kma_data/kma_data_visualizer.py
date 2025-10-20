import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# 한글 폰트 설정
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

def visualize_original_data():
    """
    2_fixed_rainsnow_kma_data.csv 원본 데이터 시각화 (6월 13-14일만)
    """
    print("원본 데이터 시각화 중...")
    
    # 데이터 로드
    df = pd.read_csv('2_fixed_rainsnow_kma_data.csv')
    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
    
    # 4월 13-14일 데이터만 필터링
    df = df[(df['datetime'].dt.month == 4) & (df['datetime'].dt.day.isin([13, 14]))].copy()
    
    print(f"원본 데이터 shape: {df.shape}")
    print(f"4월 13-14일 시간 범위: {df['datetime'].min()} ~ {df['datetime'].max()}")
    
    if len(df) == 0:
        print("4월 13-14일 원본 데이터가 없습니다!")
        return
    
    # 시각화할 컬럼들
    columns_to_plot = {
        'temperature': {'title': 'Temperature (°C) - April 13-14 (1-hour intervals)', 'color': 'red', 'ylabel': 'Temperature (°C)'},
        'humidity': {'title': 'Humidity (%) - April 13-14 (1-hour intervals)', 'color': 'blue', 'ylabel': 'Humidity (%)'},
        'rain_per_hour': {'title': 'Rain per Hour (mm) - April 13-14 (1-hour intervals)', 'color': 'green', 'ylabel': 'Rain (mm/h)'},
        'solar_irradiance': {'title': 'Solar Irradiance - April 13-14 (1-hour intervals)', 'color': 'orange', 'ylabel': 'Solar Irradiance'},
        'solar_time': {'title': 'Solar Time - April 13-14 (1-hour intervals)', 'color': 'purple', 'ylabel': 'Solar Time'},
        'wind_speed': {'title': 'Wind Speed (m/s) - April 13-14 (1-hour intervals)', 'color': 'brown', 'ylabel': 'Wind Speed (m/s)'},
        'wind_direction': {'title': 'Wind Direction (°) - April 13-14 (1-hour intervals)', 'color': 'pink', 'ylabel': 'Wind Direction (°)'}
    }
    
    # 7개 서브플롯 생성
    fig, axes = plt.subplots(7, 1, figsize=(15, 28))
    fig.suptitle('Original KMA Data - April 13-14 (1-hour intervals)', fontsize=16, fontweight='bold')
    
    for i, (col, config) in enumerate(columns_to_plot.items()):
        ax = axes[i]
        
        # 데이터가 있는 경우만 플롯
        if col in df.columns and df[col].notna().any():
            # 유효한 데이터만 필터링
            valid_data = df[df[col].notna()].copy()
            
            if len(valid_data) > 0:
                ax.plot(valid_data['datetime'], valid_data[col], 
                       color=config['color'], linewidth=1.5, alpha=0.8)
                ax.set_title(config['title'], fontsize=12, fontweight='bold')
                ax.set_ylabel(config['ylabel'], fontsize=10)
                ax.grid(True, alpha=0.3)
                
                # x축 날짜 포맷팅
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
                ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
                
                # 통계 정보 추가
                mean_val = valid_data[col].mean()
                max_val = valid_data[col].max()
                min_val = valid_data[col].min()
                ax.text(0.02, 0.95, f'Mean: {mean_val:.2f}\nMax: {max_val:.2f}\nMin: {min_val:.2f}', 
                       transform=ax.transAxes, verticalalignment='top',
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            else:
                ax.text(0.5, 0.5, 'No valid data', ha='center', va='center', transform=ax.transAxes)
                ax.set_title(config['title'] + ' (No Data)', fontsize=12, fontweight='bold')
        else:
            ax.text(0.5, 0.5, 'Column not found', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(config['title'] + ' (Not Found)', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('original_data_visualization.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print("원본 데이터 시각화 완료: original_data_visualization.png")

def visualize_interpolated_data():
    """
    3_smoothed_5min_kma_data.csv 6월 데이터 시각화
    """
    print("보간된 6월 데이터 시각화 중...")
    
    # 데이터 로드
    df = pd.read_csv('3_smoothed_5min_kma_data.csv')
    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
    
    # 4월 13-14일 데이터만 필터링
    june_data = df[(df['datetime'].dt.month == 4) & (df['datetime'].dt.day.isin([13, 14]))].copy()
    
    print(f"전체 보간 데이터 shape: {df.shape}")
    print(f"4월 13-14일 데이터 shape: {june_data.shape}")
    print(f"4월 13-14일 시간 범위: {june_data['datetime'].min()} ~ {june_data['datetime'].max()}")
    
    if len(june_data) == 0:
        print("4월 13-14일 데이터가 없습니다!")
        return
    
    # 시각화할 컬럼들
    columns_to_plot = {
        'temperature': {'title': 'Temperature (°C) - April 13-14 (5-min intervals)', 'color': 'red', 'ylabel': 'Temperature (°C)'},
        'humidity': {'title': 'Humidity (%) - April 13-14 (5-min intervals)', 'color': 'blue', 'ylabel': 'Humidity (%)'},
        'rain_per_hour': {'title': 'Rain per Hour (mm) - April 13-14 (5-min intervals)', 'color': 'green', 'ylabel': 'Rain (mm/h)'},
        'solar_irradiance': {'title': 'Solar Irradiance - April 13-14 (5-min intervals)', 'color': 'orange', 'ylabel': 'Solar Irradiance'},
        'solar_time': {'title': 'Solar Time - April 13-14 (5-min intervals)', 'color': 'purple', 'ylabel': 'Solar Time'},
        'wind_speed': {'title': 'Wind Speed (m/s) - April 13-14 (5-min intervals)', 'color': 'brown', 'ylabel': 'Wind Speed (m/s)'},
        'wind_direction': {'title': 'Wind Direction (°) - April 13-14 (5-min intervals)', 'color': 'pink', 'ylabel': 'Wind Direction (°)'}
    }
    
    # 7개 서브플롯 생성
    fig, axes = plt.subplots(7, 1, figsize=(15, 28))
    fig.suptitle('Interpolated KMA Data - April 13-14 (5-minute intervals)', fontsize=16, fontweight='bold')
    
    for i, (col, config) in enumerate(columns_to_plot.items()):
        ax = axes[i]
        
        # 데이터가 있는 경우만 플롯
        if col in june_data.columns and june_data[col].notna().any():
            # 유효한 데이터만 필터링
            valid_data = june_data[june_data[col].notna()].copy()
            
            if len(valid_data) > 0:
                ax.plot(valid_data['datetime'], valid_data[col], 
                       color=config['color'], linewidth=0.8, alpha=0.8)
                ax.set_title(config['title'], fontsize=12, fontweight='bold')
                ax.set_ylabel(config['ylabel'], fontsize=10)
                ax.grid(True, alpha=0.3)
                
                # x축 날짜 포맷팅 (6월이므로 일별로)
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
                ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
                ax.xaxis.set_minor_locator(mdates.HourLocator(interval=6))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
                
                # 통계 정보 추가
                mean_val = valid_data[col].mean()
                max_val = valid_data[col].max()
                min_val = valid_data[col].min()
                std_val = valid_data[col].std()
                ax.text(0.02, 0.95, f'Mean: {mean_val:.2f}\nMax: {max_val:.2f}\nMin: {min_val:.2f}\nStd: {std_val:.2f}', 
                       transform=ax.transAxes, verticalalignment='top',
                       bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
            else:
                ax.text(0.5, 0.5, 'No valid data', ha='center', va='center', transform=ax.transAxes)
                ax.set_title(config['title'] + ' (No Data)', fontsize=12, fontweight='bold')
        else:
            ax.text(0.5, 0.5, 'Column not found', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(config['title'] + ' (Not Found)', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('interpolated_june_data_visualization.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print("보간된 6월 13-14일 데이터 시각화 완료: interpolated_june_data_visualization.png")

def compare_interpolation_quality():
    """
    원본 데이터와 보간 데이터 비교 시각화
    """
    print("보간 품질 비교 시각화 중...")
    
    # 원본 데이터 로드
    original_df = pd.read_csv('2_fixed_rainsnow_kma_data.csv')
    original_df['datetime'] = pd.to_datetime(original_df['date'] + ' ' + original_df['time'])
    
    # 보간 데이터 로드
    interpolated_df = pd.read_csv('3_smoothed_5min_kma_data.csv')
    interpolated_df['datetime'] = pd.to_datetime(interpolated_df['date'] + ' ' + interpolated_df['time'])
    
    # 4월 13-14일 데이터만 필터링
    original_june = original_df[(original_df['datetime'].dt.month == 4) & (original_df['datetime'].dt.day.isin([13, 14]))].copy()
    interpolated_june = interpolated_df[(interpolated_df['datetime'].dt.month == 4) & (interpolated_df['datetime'].dt.day.isin([13, 14]))].copy()
    
    if len(original_june) == 0 or len(interpolated_june) == 0:
        print("4월 13-14일 데이터가 없습니다!")
        return
    
    # 비교할 컬럼들
    compare_columns = ['temperature', 'humidity', 'rain_per_hour', 'wind_speed', 'wind_direction', 'solar_irradiance', 'solar_time']
    
    fig, axes = plt.subplots(len(compare_columns), 1, figsize=(15, 28))
    fig.suptitle('Original vs Interpolated Data Comparison - April 13-14', fontsize=16, fontweight='bold')
    
    for i, col in enumerate(compare_columns):
        ax = axes[i]
        
        if col in original_june.columns and col in interpolated_june.columns:
            # 원본 데이터 (큰 점으로)
            valid_orig = original_june[original_june[col].notna()]
            if len(valid_orig) > 0:
                ax.scatter(valid_orig['datetime'], valid_orig[col], 
                          color='red', s=50, alpha=0.8, label='Original (1h)', zorder=3)
            
            # 보간 데이터 (선으로)
            valid_interp = interpolated_june[interpolated_june[col].notna()]
            if len(valid_interp) > 0:
                ax.plot(valid_interp['datetime'], valid_interp[col], 
                       color='blue', linewidth=0.5, alpha=0.6, label='Interpolated (5min)', zorder=1)
            
            ax.set_title(f'{col.title()} - Original vs Interpolated', fontsize=12, fontweight='bold')
            ax.set_ylabel(col.title(), fontsize=10)
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            # x축 포맷팅
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    plt.savefig('interpolation_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print("보간 품질 비교 시각화 완료: interpolation_comparison.png")

def analyze_data_statistics():
    """
    데이터 통계 분석
    """
    print("\n=== 데이터 통계 분석 ===")
    
    # 원본 데이터
    original_df = pd.read_csv('2_fixed_rainsnow_kma_data.csv')
    original_df['datetime'] = pd.to_datetime(original_df['date'] + ' ' + original_df['time'])
    
    # 보간 데이터
    interpolated_df = pd.read_csv('3_smoothed_5min_kma_data.csv')
    interpolated_df['datetime'] = pd.to_datetime(interpolated_df['date'] + ' ' + interpolated_df['time'])
    
    print(f"원본 데이터:")
    print(f"  - 총 데이터 포인트: {len(original_df):,}개")
    print(f"  - 시간 범위: {original_df['datetime'].min()} ~ {original_df['datetime'].max()}")
    print(f"  - 평균 시간 간격: {original_df['datetime'].diff().mean()}")
    
    print(f"\n보간 데이터:")
    print(f"  - 총 데이터 포인트: {len(interpolated_df):,}개")
    print(f"  - 시간 범위: {interpolated_df['datetime'].min()} ~ {interpolated_df['datetime'].max()}")
    print(f"  - 확장 비율: {len(interpolated_df) / len(original_df):.1f}배")
    
    # 4월 13일, 14일 데이터 통계
    june_orig = original_df[(original_df['datetime'].dt.month == 4) & (original_df['datetime'].dt.day.isin([13, 14]))]
    june_interp = interpolated_df[(interpolated_df['datetime'].dt.month == 4) & (interpolated_df['datetime'].dt.day.isin([13, 14]))]
    
    print(f"\n4월 13-14일 데이터:")
    print(f"  - 원본: {len(june_orig):,}개")
    print(f"  - 보간: {len(june_interp):,}개")
    if len(june_orig) > 0:
        print(f"  - 4월 13-14일 확장 비율: {len(june_interp) / len(june_orig):.1f}배")
    else:
        print(f"  - 4월 13-14일 확장 비율: 원본 데이터 없음")

if __name__ == "__main__":
    print("KMA 데이터 시각화 시작...")
    
    # 통계 분석
    analyze_data_statistics()
    
    # 원본 데이터 시각화
    visualize_original_data()
    
    # 보간된 6월 데이터 시각화
    visualize_interpolated_data()
    
    # 보간 품질 비교
    compare_interpolation_quality()
    
    print("\n모든 시각화 완료!")
    print("생성된 파일:")
    print("- original_data_visualization.png")
    print("- interpolated_june_data_visualization.png") 
    print("- interpolation_comparison.png")
