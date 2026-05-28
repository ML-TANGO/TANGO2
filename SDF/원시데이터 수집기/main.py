
#main.py
# 프로그램 실행 진입점
from src.pipeline import DataPipeline
from dotenv import load_dotenv
from src.data_collection.db_client import DatabaseClient
from src.data_collection.weather_api import WeatherAPIClient
import argparse
import json
from pathlib import Path
import yaml

def display_file_content(file_path: str, title: str, max_rows: int = 3):
    """파일 내용을 보기 좋게 표시"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n📄 {title}")
        print("=" * 50)
        print(f"📁 파일: {file_path}")
        print(f"📊 데이터 개수: {len(data)}개")
        
        if data:
            print(f"📋 컬럼 개수: {len(data[0])}개")
            columns = list(data[0].keys())
            print(f"📝 컬럼 목록: {columns}")
            
            print(f"\n📄 데이터 내용 (상위 {max_rows}개 행):")
            for i, row in enumerate(data[:max_rows], 1):
                print(f"\n  행 {i}:")
                # 모든 컬럼 표시 (긴 경우 줄임)
                for col, val in row.items():
                    val_str = str(val)
                    if len(val_str) > 50:
                        val_str = val_str[:47] + "..."
                    print(f"    {col}: {val_str}")
                
                if i < max_rows and len(data) > max_rows:
                    print(f"    ... (총 {len(data)}개 중 {max_rows}개만 표시)")
                    break
        else:
            print("⚠️ 데이터가 없습니다.")
            
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ 파일 읽기 오류 ({file_path}): {e}")
# .env 파일에서 환경 변수 로드
def parse_query_file(file_path: Path) -> dict:
    """key=value 형태의 쿼리 설정 파일을 파싱
    
    한국 시간대 기준의 시간을 UTC로 변환하여 DB에 요청합니다.
    """
    from datetime import datetime, timedelta, timezone
    import pytz
    
    config = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # 양쪽 따옴표 제거
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                
                # 한국 시간대 기준의 시간을 UTC로 변환
                if key in ['start_date', 'end_date']:
                    try:
                        # 한국 시간대로 파싱
                        kst = pytz.timezone('Asia/Seoul')
                        dt_kst = kst.localize(datetime.strptime(value, '%Y-%m-%d %H:%M:%S'))
                        # UTC로 변환
                        dt_utc = dt_kst.astimezone(pytz.UTC)
                        config[key] = dt_utc.strftime('%Y-%m-%d %H:%M:%S')
                        print(f"🕐 시간대 변환: {key} {value} (KST) -> {config[key]} (UTC)")
                    except Exception as e:
                        print(f"⚠️ 시간대 변환 실패 ({key}): {e}, 원본 값 사용")
                        config[key] = value
                else:
                    config[key] = value
    return config


load_dotenv()

# 데이터 수집
def collect_data(pipe_line_instance, args):
    print("=" * 60)
    print("🚀 데이터 수집 파이프라인 실행")
    print("=" * 60)
    pipe_line_instance.run_db_load(
        args["start_time"],
        args["end_time"],
        args["sensor_with_channels"],
        output_dir=args.get("output_dir", "pipeline_output"),
    )

#전처리 기능
def preprocess_data(pipe_line_instance):
    print("=" * 60)
    print("🧪 전처리 기능 테스트")
    print("=" * 60)
    # pipeline_config.yaml에서 설정 로드
    config_path = Path("pipeline_config.yaml")
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    else:
        print("⚠️ pipeline_config.yaml 파일을 찾을 수 없습니다.")
        return

    # pipeline의 파일 찾기 기능 사용
    print("📁 데이터 파일 찾는 중...")
    saved_files = pipe_line_instance.find_all_data_files(include_organized=True)
    
    if not saved_files:
        print("❌ 데이터 파일을 찾을 수 없습니다.")
        print("� 먼저 데이터 수집을 실행해주세요.")
        return
    
    print(f"📋 찾은 파일들: {list(saved_files.keys())}")
    
    # 메타데이터 파일 찾기
    metadata_file = pipe_line_instance.find_metadata_file(include_organized=True)
    if metadata_file:
        print(f"� 사용할 메타데이터 파일: {metadata_file}")
    else:
        print("⚠️ 메타데이터 파일을 찾을 수 없습니다. 계속 진행합니다.")
    
    # 전처리 실행
    try:
        print("🔄 전처리 실행 중...")
        preprocess_outputs = pipe_line_instance.run_preprocessing(saved_files, "pipeline_output", config)
        
        if preprocess_outputs:
            print("\n✅ 전처리 결과:")
            for site_key, site_path in preprocess_outputs.items():
                print(f"  • {site_key}: {site_path}")
            print("=" * 50)
            
            # 각 site별 파일 내용 확인
            for site_key, site_path in preprocess_outputs.items():
                if Path(site_path).exists():
                    print(f"\n📄 🏢 {site_key.upper()} 데이터")
                    print("=" * 50)
                    display_file_content(site_path, f"{site_key.upper()} 데이터")
                    print("=" * 50)
            
            # 메타데이터 파일 표시
            metadata_file = None
            for file_key, file_path in preprocess_outputs.items():
                if 'metadata' in file_key.lower():
                    metadata_file = file_path
                    break
            
            if metadata_file and Path(metadata_file).exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        meta_data = json.load(f)
                    print(f"\n📋 전처리 메타데이터:")
                    print("=" * 50)
                    print(f"  • 처리 시간: {meta_data.get('timestamp', 'N/A')}")
                    print(f"  • 기준 테이블: {meta_data.get('base_table', 'N/A')}")
                    print(f"  • 시간 허용오차: {meta_data.get('tolerance', 'N/A')}")
                    print(f"  • 분 단위 리샘플링: {meta_data.get('resample_to_minute', 'N/A')}")
                    print(f"  • 분 단위 집계 방식: {meta_data.get('minute_aggregation', 'N/A')}")
                    print(f"  • 빈 값 채우기 방식: {meta_data.get('fill_method', 'N/A')}")
                    print(f"  • 출력 디렉토리: {meta_data.get('output_dir', 'N/A')}")
                    print(f"  • 사이트별 파일:")
                    for site_key, site_path in meta_data.get('site_files', {}).items():
                        print(f"    - {site_key}: {site_path}")
                    print("=" * 50)
                except Exception as e:
                    print(f"❌ 메타데이터 읽기 오류: {e}")
            else:
                print("⚠️ 전처리 결과가 없습니다.")
        else:
            print("⚠️ 전처리 결과가 없습니다.")
                
    except Exception as e:
        print(f"❌ 전처리 실행 중 오류: {e}")
        import traceback
        print(f"🔍 상세 오류 정보: {traceback.format_exc()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="데이터 수집 파이프라인")
    parser.add_argument(
        "--config",
        type=str,
        help="쿼리 설정 파일 경로 (예: config/260511_query.yaml)"
    )
    args = parser.parse_args()

    if args.config:
        # 파일 입력 모드: 사이트/시설 입력 없이 설정 파일로 실행
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"❌ 설정 파일을 찾을 수 없습니다: {config_path}")
            exit(1)

        config = parse_query_file(config_path)
        start_time = config.get('start_date', '')
        end_time = config.get('end_date', '')
        sensor_id_str = config.get('sensor_id_str', '')
        output_dir = config.get('output_dir', 'pipeline_output')
        
        # 날짜시간 폴더명 생성 (현재 시간 기준)
        from datetime import datetime
        timestamp_folder = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir_with_timestamp = f"{output_dir}/{timestamp_folder}"

        # 센서 ID와 채널 파싱
        sensor_entries = sensor_id_str.split(',') if sensor_id_str else []
        sensor_with_channels = []
        for entry in sensor_entries:
            entry = entry.strip()
            if not entry:
                continue
            if ':' in entry:
                sensor_id, channel = entry.split(':', 1)
                sensor_with_channels.append({
                    'sensor_id': sensor_id.strip(),
                    'channel': channel.strip()
                })
            else:
                sensor_with_channels.append({
                    'sensor_id': entry.strip(),
                    'channel': None
                })

        run_args = {
            "site_id": "",
            "facility_id": "",
            "sensor_with_channels": sensor_with_channels,
            "start_time": start_time,
            "end_time": end_time,
            "output_dir": output_dir_with_timestamp
        }

        print("=" * 60)
        print("🚀 파일 입력 모드로 실행 중")
        print(f"📁 설정 파일: {config_path}")
        print(f"⏰ 시간 범위: {start_time} ~ {end_time}")
        print(f"🔢 센서 개수: {len(sensor_with_channels)}개")
        print(f"📂 출력 디렉토리: {output_dir_with_timestamp}")
        print("=" * 60)

        pipeline = DataPipeline()
        collect_data(pipeline, run_args)
        pipeline.tideup_collect_data(output_dir=output_dir_with_timestamp)

    else:
        # 대화형 메뉴 모드
        print("=" * 60)
        print("데이터 소스를 선택하세요.")
        print("1) Beymons (기존 센서/DB 데이터)")
        print("2) 기상청 지상관측 데이터")
        print("3) 전처리 진행")
        print("=" * 60)
        source_choice = input("번호를 입력하세요 (1 또는 2, 기본: 1): ").strip() or "1"

        if source_choice == "2":
            # 기상청 데이터 수집 플로우
            print("\n=== 기상청 지상관측 데이터 수집 ===")
            stn_id_input = input("기상대 번호(stn_id)를 입력하세요 (예: 108): ").strip() #181 : 청주
            start_dt = input("시작 시간을 입력하세요 (YYYYMMDDHHMM): ").strip()
            end_dt = input("종료 시간을 입력하세요 (YYYYMMDDHHMM): ").strip()

            try:
                stn_id = int(stn_id_input)
            except ValueError:
                raise ValueError("stn_id 는 정수여야 합니다.")

            client = WeatherAPIClient()
            text = client.get_long_term_weather_data(start_dt, end_dt, stn_id)

            print("\n=== 기상청 데이터 수집 완료 ===")
            print(f"지점번호: {stn_id}, 기간: {start_dt} ~ {end_dt}")
            print(f"응답 길이: {len(text)} 문자")
            print("텍스트/CSV 파일은 pipeline_output/kma_data/ 아래에 저장되었습니다.")

        elif source_choice == "3":
            # 전처리 진행
            print("전처리를 진행합니다.")
            pipeline = DataPipeline()
            pipeline.set_weather_file("pipeline_output/kma_data/csv/kma_181_20260211_20260402.csv")
            preprocess_data(pipeline)
        else:
            # Beymons (기존) 데이터 수집 플로우
            site_id = input("사이트 ID를 입력하세요: ")
            facility_id = input("설비 ID를 입력하세요: ")
            sensor_ids_input = input("센서 ID와 채널을 입력하세요 (콤마로 구분, 예: sensor1:ch1,sensor2:ch2): ")
            start_time = input("시작 시간을 입력하세요 (YYYY-MM-DD HH:MM:SS): ")
            end_time = input("종료 시간을 입력하세요 (YYYY-MM-DD HH:MM:SS): ")

            # 센서 ID와 채널 파싱
            sensor_entries = sensor_ids_input.split(',')
            sensor_with_channels = []
            
            for entry in sensor_entries:
                entry = entry.strip()
                if ':' in entry:
                    # 채널이 포함된 경우: sensor_id:channel
                    sensor_id, channel = entry.split(':', 1)
                    sensor_with_channels.append({
                        'sensor_id': sensor_id.strip(),
                        'channel': channel.strip()
                    })
                else:
                    # 채널이 없는 경우: sensor_id만
                    sensor_with_channels.append({
                        'sensor_id': entry.strip(),
                        'channel': None
                    })
            
            run_args = {
                "site_id": site_id,
                "facility_id": facility_id,
                "sensor_with_channels": sensor_with_channels,
                "start_time": start_time,
                "end_time": end_time
            }
            pipeline = DataPipeline()
            
            # 1. 기본 파이프라인 실행 (데이터 수집)
            collect_data(pipeline, run_args)

            # 2. 수집 데이터 분류
            pipeline.tideup_collect_data()

    print("\n" + "=" * 60)
    print("🎉 전체 작업 완료!")
    print("=" * 60)
    print("main.py end")
