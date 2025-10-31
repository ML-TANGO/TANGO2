import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

def merge_kma_data():
    """
    data_sample.csv와 3_smoothed_5min_kma_data.csv를 시간 기준으로 병합
    """
    print("데이터 로딩 중...")
    
    # 데이터 로드
    sample_df = pd.read_csv('data/data_sample.csv')
    kma_df = pd.read_csv('data/kma_data/3_smoothed_5min_kma_data.csv')
    
    print(f"Sample data shape: {sample_df.shape}")
    print(f"KMA data shape: {kma_df.shape}")
    
    # datetime 컬럼 생성
    sample_df['datetime'] = pd.to_datetime(sample_df['date'] + ' ' + sample_df['time'])
    kma_df['datetime'] = pd.to_datetime(kma_df['date'] + ' ' + kma_df['time'])
    
    print(f"Sample data time range: {sample_df['datetime'].min()} ~ {sample_df['datetime'].max()}")
    print(f"KMA data time range: {kma_df['datetime'].min()} ~ {kma_df['datetime'].max()}")
    
    # KMA 데이터를 시간 기준으로 정렬
    kma_df = kma_df.sort_values('datetime').reset_index(drop=True)
    
    # 매칭할 KMA 컬럼들 (필요한 기상 데이터만)
    kma_columns_to_merge = [
        'wind_direction', 'wind_speed', 'temperature', 'humidity',
        'solar_irradiance', 'solar_time', 'rain_per_hour', 'snow_per_hour'
    ]
    
    print(f"\n매칭할 KMA 컬럼들: {kma_columns_to_merge}")
    
    # 각 sample 데이터에 대해 가장 가까운 KMA 데이터 찾기
    print("\n시간 매칭 중...")
    
    # 결과를 저장할 리스트
    merged_data = []
    
    for idx, sample_row in sample_df.iterrows():
        if idx % 1000 == 0:
            print(f"  처리 중: {idx:,}/{len(sample_df):,} ({idx/len(sample_df)*100:.1f}%)")
        
        sample_time = sample_row['datetime']
        
        # 가장 가까운 KMA 데이터 찾기 (이진 탐색)
        time_diffs = np.abs(kma_df['datetime'] - sample_time)
        closest_idx = time_diffs.idxmin()
        closest_kma_row = kma_df.iloc[closest_idx]
        
        # 시간 차이 계산
        time_diff = abs((closest_kma_row['datetime'] - sample_time).total_seconds())
        
        # 새로운 행 생성 (sample 데이터 + KMA 데이터)
        merged_row = sample_row.copy()
        
        # KMA 데이터 추가
        for col in kma_columns_to_merge:
            merged_row[f'kma_{col}'] = closest_kma_row[col]
        
        merged_data.append(merged_row)
    
    # 결과 데이터프레임 생성
    merged_df = pd.DataFrame(merged_data)
    
    # datetime 컬럼 제거
    if 'datetime' in merged_df.columns:
        merged_df = merged_df.drop('datetime', axis=1)
    
    print(f"\n병합 완료!")
    print(f"최종 데이터 shape: {merged_df.shape}")
    print(f"추가된 컬럼 수: {len(kma_columns_to_merge)}")
    
    # 결과 저장
    output_filename = 'data/merged_sample_with_kma.csv'
    merged_df.to_csv(output_filename, index=False)
    
    print(f"\n결과 저장: {output_filename}")
    
    # 샘플 데이터 출력
    print("\n샘플 데이터 (병합된 결과):")
    sample_columns = ['date', 'time', 'indoor_temperature', 'indoor_humidity', 
                     'kma_temperature', 'kma_humidity', 'kma_wind_direction', 
                     'kma_wind_speed', 'kma_rain_per_hour']
    sample_data = merged_df[sample_columns].head(10)
    print(sample_data.to_string(index=False))
    
    return merged_df

def analyze_merge_quality(merged_df):
    """
    병합 품질 분석
    """
    print("\n=== 병합 품질 분석 ===")
    
    # 데이터 완성도
    kma_columns = [col for col in merged_df.columns if col.startswith('kma_')]
    print(f"KMA 데이터 완성도:")
    for col in kma_columns:
        non_null_count = merged_df[col].notna().sum()
        print(f"  {col}: {non_null_count:,}/{len(merged_df):,} ({non_null_count/len(merged_df)*100:.1f}%)")

def create_summary_report(merged_df):
    """
    병합 결과 요약 보고서 생성
    """
    print("\n=== 병합 결과 요약 보고서 ===")
    
    # 기본 정보
    print(f"총 데이터 포인트: {len(merged_df):,}개")
    print(f"시간 범위: {merged_df['date'].min()} ~ {merged_df['date'].max()}")
    print(f"추가된 KMA 컬럼: {len([col for col in merged_df.columns if col.startswith('kma_')])}개")
    
    # 컬럼 목록
    print(f"\n전체 컬럼 목록:")
    for i, col in enumerate(merged_df.columns, 1):
        print(f"  {i:2d}. {col}")
    
    # 데이터 타입
    print(f"\n데이터 타입:")
    print(merged_df.dtypes.value_counts())

if __name__ == "__main__":
    print("KMA 데이터 병합 시작...")
    
    # 데이터 병합
    merged_df = merge_kma_data()
    
    # 품질 분석
    analyze_merge_quality(merged_df)
    
    # 요약 보고서
    create_summary_report(merged_df)
    
    print("\n병합 완료!")
