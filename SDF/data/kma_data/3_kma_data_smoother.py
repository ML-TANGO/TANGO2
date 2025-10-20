import pandas as pd
import numpy as np
from scipy.interpolate import CubicSpline, PchipInterpolator, Akima1DInterpolator
from scipy.signal import savgol_filter
import warnings
warnings.filterwarnings('ignore')

def smooth_kma_data():
    """
    1시간 간격 KMA 데이터를 5분 간격으로 자연스럽게 보간
    """
    print("데이터 로딩 중...")
    # 데이터 로드
    df = pd.read_csv('2_fixed_rainsnow_kma_data.csv')
    
    print(f"원본 데이터 shape: {df.shape}")
    print(f"컬럼명: {df.columns.tolist()}")
    
    # datetime 컬럼 생성
    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
    
    # 5분 간격의 새로운 시간 인덱스 생성
    min_time = df['datetime'].min()
    max_time = df['datetime'].max()
    new_time_index = pd.date_range(start=min_time, end=max_time, freq='5T')
    
    print(f"새로운 5분 간격 데이터 포인트 수: {len(new_time_index)}")
    
    # 새로운 데이터프레임 생성
    new_df = pd.DataFrame({'datetime': new_time_index})
    new_df['date'] = new_df['datetime'].dt.date
    new_df['time'] = new_df['datetime'].dt.time
    new_df['stn_id'] = df['stn_id'].iloc[0]  # 관측소 ID는 동일
    
    # 보간할 수치형 컬럼들
    numeric_columns = ['wind_direction', 'wind_speed', 'temperature', 'humidity', 
                      'solar_irradiance', 'solar_time', 'rain_per_hour', 'snow_per_hour']
    
    print("\n컬럼별 보간 방법 적용 중...")
    
    for col in numeric_columns:
        print(f"  - {col} 처리 중...")
        
        # 유효한 데이터만 추출 (NaN 제거)
        valid_mask = df[col].notna()
        if not valid_mask.any():
            new_df[col] = np.nan
            continue
            
        valid_data = df[valid_mask].copy()
        valid_data = valid_data.sort_values('datetime')
        
        if len(valid_data) < 2:
            new_df[col] = valid_data[col].iloc[0] if len(valid_data) == 1 else np.nan
            continue
        
        # 시간을 숫자로 변환 (보간을 위해)
        time_numeric = valid_data['datetime'].astype(np.int64)
        new_time_numeric = new_time_index.astype(np.int64)
        
        try:
            # 컬럼별로 다른 보간 방법 적용
            if col in ['rain_per_hour', 'snow_per_hour']:
                # 강수/강설 데이터: PCHIP (단조성 보장, 음수 방지)
                interpolator = PchipInterpolator(time_numeric, valid_data[col])
                interpolated = interpolator(new_time_numeric)
                # 음수 값은 0으로 설정
                interpolated = np.maximum(interpolated, 0)
                
            elif col in ['wind_direction']:
                # 풍향: 36방향계 (0-36도, 10도 간격) 보간
                wind_dir = valid_data[col].values
                
                # 0과 36을 같은 값으로 처리 (0으로 통일)
                wind_dir_normalized = wind_dir.copy()
                wind_dir_normalized[wind_dir_normalized == 36] = 0
                
                # 각도 차이를 고려한 보간 (0-360도로 변환 후 보간)
                wind_dir_degrees = wind_dir_normalized * 10  # 36방향계를 360도로 변환
                wind_dir_rad = np.radians(wind_dir_degrees)
                cos_interp = np.interp(new_time_numeric, time_numeric, np.cos(wind_dir_rad))
                sin_interp = np.interp(new_time_numeric, time_numeric, np.sin(wind_dir_rad))
                interpolated_degrees = np.degrees(np.arctan2(sin_interp, cos_interp)) % 360
                
                # 다시 36방향계로 변환 (0-35)
                interpolated = (interpolated_degrees / 10) % 36
                
                # 가장 가까운 36방향계 값으로 반올림
                interpolated = np.round(interpolated).astype(int)
                interpolated = interpolated % 36
                
            elif col in ['temperature', 'humidity']:
                # 온도, 습도: Cubic Spline (자연스러운 곡선)
                interpolator = CubicSpline(time_numeric, valid_data[col])
                interpolated = interpolator(new_time_numeric)
                
            else:
                # 기타 컬럼: Akima Spline (안정적)
                interpolator = Akima1DInterpolator(time_numeric, valid_data[col])
                interpolated = interpolator(new_time_numeric)
            
            # Savitzky-Golay 필터로 추가 스무딩 (선택적)
            if col in ['wind_speed', 'solar_irradiance']:
                # 연속적인 값들에만 적용
                if len(interpolated) > 5:
                    interpolated = savgol_filter(interpolated, 
                                              min(5, len(interpolated)//2*2+1), 2)
            
            # 일사량과 일조시간은 0보다 아래로 갈 수 없음
            if col in ['solar_irradiance', 'solar_time']:
                interpolated = np.maximum(interpolated, 0)
            
            new_df[col] = interpolated
            
        except Exception as e:
            print(f"    경고: {col} 보간 중 오류 발생 - 선형 보간으로 대체")
            new_df[col] = np.interp(new_time_numeric, time_numeric, valid_data[col])
    
    # 결과 정리
    new_df = new_df.round(2)  # 소수점 둘째자리 반올림
    
    # 컬럼 순서 정리 (datetime 제외)
    column_order = ['date', 'time', 'stn_id', 'wind_direction', 'wind_speed', 
                   'temperature', 'humidity', 'solar_irradiance', 'solar_time', 
                   'rain_per_hour', 'snow_per_hour']
    new_df = new_df[column_order]
    
    # 결과 저장
    output_filename = '3_smoothed_5min_kma_data.csv'
    new_df.to_csv(output_filename, index=False)
    
    print(f"\n처리 완료!")
    print(f"원본 데이터: {df.shape[0]}개 (1시간 간격)")
    print(f"보간 데이터: {new_df.shape[0]}개 (5분 간격)")
    print(f"확장 비율: {new_df.shape[0] / df.shape[0]:.1f}배")
    print(f"결과 저장: {output_filename}")
    
    # 샘플 데이터 출력
    print("\n샘플 데이터 (처리된 결과):")
    sample_data = new_df.head(20)
    print(sample_data.to_string(index=False))
    
    # 통계 정보
    print(f"\n통계 정보:")
    print(f"시간 범위: {new_time_index.min()} ~ {new_time_index.max()}")
    print(f"총 데이터 포인트: {len(new_df):,}개")
    
    return new_df

def analyze_interpolation_quality(original_df, interpolated_df):
    """
    보간 품질 분석
    """
    print("\n=== 보간 품질 분석 ===")
    
    # 원본 데이터의 시간 간격
    original_intervals = original_df['datetime'].diff().dropna()
    print(f"원본 데이터 평균 시간 간격: {original_intervals.mean()}")
    
    # 보간 데이터의 시간 간격 (5분 고정)
    print(f"보간 데이터 시간 간격: 5분 (고정)")
    
    # 연속성 검사
    numeric_cols = ['temperature', 'humidity', 'wind_speed']
    for col in numeric_cols:
        if col in interpolated_df.columns:
            diff = interpolated_df[col].diff().abs()
            max_change = diff.max()
            print(f"{col} 최대 변화량: {max_change:.2f}")

if __name__ == "__main__":
    # 원본 데이터 로드 (비교용)
    original_df = pd.read_csv('2_fixed_rainsnow_kma_data.csv')
    original_df['datetime'] = pd.to_datetime(original_df['date'] + ' ' + original_df['time'])
    
    # 보간 실행
    result_df = smooth_kma_data()
    
    # 품질 분석
    analyze_interpolation_quality(original_df, result_df)
