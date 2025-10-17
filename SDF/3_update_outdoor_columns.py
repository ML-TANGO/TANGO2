import pandas as pd

def update_outdoor_columns():
    """
    outdoor_temperature, outdoor_humidity, wind_direction, wind_speed 칼럼을
    kma_temperature, kma_humidity, kma_wind_direction, kma_wind_speed 값으로 채우고
    KMA 칼럼들을 제거합니다.
    """
    
    # CSV 파일 읽기
    print("CSV 파일을 읽는 중...")
    df = pd.read_csv('/Users/hyunwoo/works/sdx/code/data/merged_sample_with_kma.csv')
    
    print(f"원본 데이터 shape: {df.shape}")
    print(f"원본 칼럼들: {list(df.columns)}")
    
    # outdoor 칼럼들을 KMA 값으로 채우기
    print("\noutdoor 칼럼들을 KMA 값으로 업데이트 중...")
    df['outdoor_temperature'] = df['kma_temperature']
    df['outdoor_humidity'] = df['kma_humidity']
    df['wind_direction'] = df['kma_wind_direction']
    df['wind_speed'] = df['kma_wind_speed']
    
    # KMA 칼럼들 제거
    print("KMA 칼럼들을 제거 중...")
    kma_columns_to_remove = ['kma_wind_direction', 'kma_wind_speed', 'kma_temperature', 'kma_humidity']
    df = df.drop(columns=kma_columns_to_remove)
    
    print(f"업데이트된 데이터 shape: {df.shape}")
    print(f"업데이트된 칼럼들: {list(df.columns)}")
    
    # 업데이트된 데이터를 새 파일로 저장
    output_file = '/Users/hyunwoo/works/sdx/code/data/updated_merged_sample_with_kma.csv'
    print(f"\n업데이트된 데이터를 {output_file}에 저장 중...")
    df.to_csv(output_file, index=False)
    
    print("완료!")
    
    # 샘플 데이터 확인
    print("\n샘플 데이터 확인:")
    print(df.head())
    
    return df

if __name__ == "__main__":
    updated_df = update_outdoor_columns()
