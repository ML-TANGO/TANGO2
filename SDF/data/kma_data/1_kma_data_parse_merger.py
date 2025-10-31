import pandas as pd
import os
from datetime import datetime

def parse_kma_txt_to_csv(txt_file_path, output_csv_path):
    """
    기상청 txt 파일을 파싱하여 CSV 파일로 변환하는 함수
    
    Args:
        txt_file_path (str): 입력 txt 파일 경로
        output_csv_path (str): 출력 CSV 파일 경로
    """
    print(f"파싱 시작: {txt_file_path}")
    
    # 데이터를 저장할 리스트
    data_rows = []
    
    with open(txt_file_path, 'r', encoding='utf-8') as file:
        for line_num, line in enumerate(file, 1):
            line = line.strip()
            
            # 주석이나 빈 줄은 건너뛰기
            if line.startswith('#') or not line:
                continue
            
            # 데이터 파싱 (고정폭 형식)
            try:
                # YYMMDDHHMI (12자리) - 날짜시간
                datetime_str = line[:12]
                
                # STN ID (3자리) - 위치 13-15
                stn_id = line[13:16].strip()
                
                # WD (풍향, 3자리) - 위치 17-19
                wind_direction = line[17:20].strip()
                
                # WS (풍속, 4자리) - 위치 21-24
                wind_speed = line[21:25].strip()
                
                
                # TA (기온, 4자리) - 위치 64-67 (소수점 포함)
                temperature = line[63:68].strip()
                
                # HM (습도, 4자리) - 위치 76-79 (소수점 포함)
                humidity = line[76:80].strip()
                                
                # RN (강수량 관련)
                rn_day = line[94:100].strip()
                
                # sd_day
                sd_day = line[122:128].strip()
                
                # SI (일사량 관련)
                si = line[210:215].strip()
                
                # SS (일조시간)
                ss = line[204:209].strip()
                # 날짜시간을 표준 형식으로 변환
                try:
                    dt = datetime.strptime(datetime_str, '%Y%m%d%H%M')
                    date = dt.strftime('%Y-%m-%d')
                    time = dt.strftime('%H:%M:%S')
                except:
                    date = None
                    time = None
                
                # 데이터 행 생성
                row = {
                    'date': date,
                    'time': time,
                    'stn_id': stn_id,
                    'wind_direction': wind_direction if wind_direction != '-9' else None,
                    'wind_speed': wind_speed if wind_speed != '-9.0' else None,
                    'temperature': temperature if temperature != '-9.0' and float(temperature) > -50 and float(temperature) < 80 else None,
                    'humidity': humidity if float(humidity) >= 0 else None,
                    'rain_day': rn_day if float(rn_day) >= 0 else None,
                    'snow_day': sd_day if float(sd_day) >= 0 else None,
                    'solar_irradiance': si if float(si) >= 0 else None,
                    'solar_time': ss if float(ss) >= 0 else None,
                }
                
                data_rows.append(row)
                
            except Exception as e:
                print(f"라인 {line_num} 파싱 오류: {e}")
                continue
    
    # DataFrame 생성
    df = pd.DataFrame(data_rows)
    
    # CSV 파일로 저장
    df.to_csv(output_csv_path, index=False, encoding='utf-8')
    
    print(f"CSV 파일 생성 완료: {output_csv_path}")
    print(f"총 {len(df)}개 행이 저장되었습니다.")
    
    return df

def convert_all_txt_to_csv():
    """
    모든 txt 파일을 CSV로 변환하는 함수
    """
    # 파일 경로 설정
    txt_files = [
        'data/kma_data/0301_0331.txt',
        'data/kma_data/0401_0430.txt', 
        'data/kma_data/0501_0531.txt'
    ]
    
    csv_files = [
        'data/kma_data/0301_0331.csv',
        'data/kma_data/0401_0430.csv',
        'data/kma_data/0501_0531.csv'
    ]
    
    # 각 txt 파일을 CSV로 변환
    for txt_file, csv_file in zip(txt_files, csv_files):
        if os.path.exists(txt_file):
            parse_kma_txt_to_csv(txt_file, csv_file)
        else:
            print(f"파일을 찾을 수 없습니다: {txt_file}")

def merge_csv_files():
    """
    3개의 CSV 파일을 하나로 합치는 함수
    """
    print("CSV 파일들을 합치는 중...")
    
    # CSV 파일 경로
    csv_files = [
        'data/kma_data/0301_0331.csv',
        'data/kma_data/0401_0430.csv',
        'data/kma_data/0501_0531.csv'
    ]
    
    # 모든 CSV 파일을 읽어서 합치기
    dataframes = []
    
    for csv_file in csv_files:
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            dataframes.append(df)
            print(f"읽어온 파일: {csv_file} ({len(df)}개 행)")
        else:
            print(f"파일을 찾을 수 없습니다: {csv_file}")
    
    if dataframes:
        # 모든 DataFrame 합치기
        merged_df = pd.concat(dataframes, ignore_index=True)
        
        # 날짜순으로 정렬
        merged_df = merged_df.sort_values(['date', 'time']).reset_index(drop=True)
        
        # 합쳐진 파일 저장
        output_path = 'data/kma_data/0301_0531_merged_kma_data.csv'
        merged_df.to_csv(output_path, index=False, encoding='utf-8')
        
        print(f"합쳐진 파일 저장 완료: {output_path}")
        print(f"총 {len(merged_df)}개 행이 저장되었습니다.")
        
        return merged_df
    else:
        print("합칠 CSV 파일이 없습니다.")
        return None

def main():
    """
    메인 실행 함수
    """
    print("=== 기상청 데이터 변환 및 합치기 시작 ===")
    
    # 1단계: 모든 txt 파일을 CSV로 변환
    print("\n1단계: TXT 파일들을 CSV로 변환")
    convert_all_txt_to_csv()
    
    # 2단계: CSV 파일들을 하나로 합치기
    print("\n2단계: CSV 파일들을 하나로 합치기")
    merged_data = merge_csv_files()
    
    print("\n=== 작업 완료 ===")
    
    if merged_data is not None:
        print(f"\n최종 데이터 요약:")
        print(f"- 총 행 수: {len(merged_data)}")
        print(f"- 날짜 범위: {merged_data['date'].min()} ~ {merged_data['date'].max()}")
        print(f"- 컬럼 수: {len(merged_data.columns)}")
        print(f"\n컬럼 목록:")
        for i, col in enumerate(merged_data.columns, 1):
            print(f"  {i:2d}. {col}")

if __name__ == "__main__":
    main()
