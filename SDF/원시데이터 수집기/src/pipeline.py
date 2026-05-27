# 데이터 수집 및 처리 파이프라인
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime
import logging
import yaml
import json
import os
from pathlib import Path
import pandas as pd
import csv
import shutil

from src.data_collection.query_builder import QueryBuilder
from src.data_collection.db_client import DatabaseClient
from src.processing.time_sync import align_time_series
from src.processing.feature_gen import add_diff_features, add_rolling_features, add_time_features
from src.pipeline_preprocessing import run_preprocessing as run_pipeline_preprocessing
TIMESTAMP_TABLES = {
    'agsmotor_green': 'ts',
    'anemometer': 'ts',
    'raindrop': 'ts',
    'temperature': 'ts',
    'thermohygro': 'ts',
    'forecasts': 'record_dt',
}


class DataPipeline:
    """데이터 수집 및 처리를 위한 파이프라인 클래스"""
    
    def __init__(self, config_path: str = "config/settings.yaml"):
        """
        파이프라인 초기화
        
        Args:
            config_path: 설정 파일 경로
        """
        
        self.db_client = DatabaseClient(config_path)
        self.query_builder = QueryBuilder(self.db_client)
        self.logger = self._setup_logger()
        self.weather_file = None

    def set_weather_file(self, f_name: str):
        self.weather_file = f_name
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            # 로그 폴더 생성
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            # 파일 핸들러
            file_handler = logging.FileHandler(log_dir / "pipeline.log", encoding='utf-8')
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.INFO)
            logger.addHandler(file_handler)
            
            # 콘솔 핸들러
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            console_handler.setLevel(logging.INFO)
            logger.addHandler(console_handler)
            
            logger.setLevel(logging.INFO)
        return logger
    
    def set_ts_join_mode(self, mode: str):
        """시간 조인 모드 설정"""
        self.query_builder.set_ts_join_mode(mode)

    def display_sensor_ids_from_site_facilities(self, site_id: str, facility_ids: List[str]):
        # site_id와 facility_id_list에 해당하는 sensor_id 목록을 반환
        with self.db_client.get_connection() as conn:
            # TODO: 실제 쿼리 작성
            pass
        
        pass
    
    def collect_data(
        self, 
        requested_columns: List[str], 
        start_time: str, 
        end_time: str,
        ts_join_mode: Optional[str] = None,
        site_id: Optional[Union[str, List[str]]] = None
     ) -> List[Dict[str, Any]]:
        """
        데이터 수집 실행
        
        Args:
            requested_columns: 요청할 컬럼 리스트
            start_time: 시작 시간
            end_time: 종료 시간
            ts_join_mode: 시간 조인 모드 (可选)
            
        Returns:
            조회된 데이터 리스트
        """
        try:
            # 시간 조인 모드 설정
            if ts_join_mode:
                self.set_ts_join_mode(ts_join_mode)
            
            # 쿼리 빌드
            self.logger.info(f"쿼리 빌드 시작: 시간범위={start_time} ~ {end_time}")
            sql_query = self.query_builder.build(
                
            )
            
            self.logger.info(f"생성된 쿼리: {sql_query}")
            
            # 데이터베이스 연결 및 쿼리 실행
            with self.db_client.get_connection():
                self.logger.info("데이터베이스 연결 성공")
                result = self.db_client.execute_query(sql_query)
                self.logger.info(f"데이터 조회 완료: {len(result)}개 행")
                
                return result
                
        except Exception as e:
            self.logger.error(f"데이터 수집 중 오류 발생: {e}")
            raise
    
    def validate_request(self, requested_columns: List[str]) -> bool:
        """
        요청된 컬럼들의 유효성 검사
        
        Args:
            requested_columns: 요청할 컬럼 리스트
            
        Returns:
            유효성 여부
        """
        try:
            # 쿼리 빌드를 통해 유효성 검사 (실제 실행은 하지 않음)
            self.query_builder.build(
                requested_columns=requested_columns,
                start_time="2026-01-01 00:00:00",
                end_time="2026-01-01 01:00:00"
            )
            return True
        except ValueError:
            return False
    
    def get_available_columns(self) -> List[str]:
        """
        사용 가능한 컬럼 리스트 반환
        
        Returns:
            사용 가능한 컬럼 리스트
        """
        return self.query_builder.columns
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """
        파이프라인 상태 정보 반환
        
        Returns:
            파이프라인 상태 딕셔너리
        """
        return {
            "ts_join_mode": self.query_builder.ts_join_mode,
            "available_columns": self.get_available_columns(),
            "db_connected": self.db_client.connection is not None,
            "timestamp": datetime.now().isoformat()
        }

    def _load_metadata_content(self, metadata_file: Optional[Path]) -> Dict[str, Any]:
        if metadata_file is None or not metadata_file.exists():
            return {}

        if metadata_file.suffix == '.json':
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        if metadata_file.suffix == '.csv':
            metadata_df = pd.read_csv(metadata_file, encoding='utf-8')
            metadata: Dict[str, Any] = {}
            for _, row in metadata_df.iterrows():
                key = row.get('key')
                value = row.get('value')
                if key in ['sensor_file_mapping', 'sensor_categories', 'table_queries']:
                    try:
                        metadata[key] = json.loads(value)
                    except Exception:
                        metadata[key] = {}
                else:
                    metadata[key] = value
            return metadata

        return {}

    def _get_sensor_categories_from_metadata(self, include_organized: bool = True, output_dir: str = "pipeline_output") -> Dict[str, str]:
        metadata_file = self.find_metadata_file(include_organized, output_dir)
        metadata = self._load_metadata_content(metadata_file)

        sensor_categories = metadata.get('sensor_categories')
        if isinstance(sensor_categories, dict) and sensor_categories:
            return {
                str(sensor_id): str(display_name)
                for sensor_id, display_name in sensor_categories.items()
                if sensor_id and display_name
            }

        sensor_file_mapping = metadata.get('sensor_file_mapping', {})
        if not isinstance(sensor_file_mapping, dict):
            return {}

        inferred_categories: Dict[str, str] = {}
        for _, sensor_info in sensor_file_mapping.items():
            sensor_id = sensor_info.get('sensor_id')
            display_name = sensor_info.get('display_name')
            if sensor_id and display_name:
                inferred_categories[str(sensor_id)] = str(display_name)

        return inferred_categories

    @staticmethod
    def _extract_sensor_id_from_filename(filename: str, sensor_ids: List[str]) -> Optional[str]:
        for sensor_id in sensor_ids:
            if sensor_id in filename:
                return sensor_id
        return None

    def _get_sensor_display_names(self, sensor_ids: List[str]) -> Dict[str, str]:
        if not sensor_ids:
            return {}

        try:
            connection_needed = not self.db_client.connection
            if connection_needed:
                self.db_client.connect()

            display_name_map = self.db_client.get_sensor_display_names(sensor_ids)

            if connection_needed:
                self.db_client.disconnect()

            return display_name_map
        except Exception as e:
            self.logger.error(f"sensor display_name 조회 중 오류: {e}")
            return {}

    def find_all_data_files(self, include_organized: bool = True) -> Dict[str, str]:
        """
        모든 데이터 파일 찾기 (원본 디렉토리와 분류된 디렉토리 모두)
        tideup_collect_data 함수의 파일 탐색 로직 참조
        
        Args:
            include_organized: 분류된 디렉토리도 포함할지 여부
            
        Returns:
            파일 키와 경로의 딕셔너리
        """
        
        sensor_categories = self._get_sensor_categories_from_metadata(include_organized)
        sensor_ids = list(sensor_categories.keys())

        pipeline_output = Path("pipeline_output")
        organized_dir = Path("pipeline_output/organized_by_sensor")
        
        saved_files = {}
        # metadata 파일 찾아서 saved_files에 추가
        metadata_file = self.find_metadata_file(include_organized)
        if metadata_file:
            saved_files['metadata'] = str(metadata_file)
            print(f"📄 메타데이터 파일 발견: {metadata_file}")
        else:
            print("⚠️ 메타데이터 파일을 찾을 수 없습니다.")
        
        # 1. 분류된 디렉토리에서 파일 찾기 (우선순위)
        if include_organized and organized_dir.exists():
            for category_dir in organized_dir.iterdir():
                if category_dir.is_dir():
                    for file_path in category_dir.iterdir():
                        if file_path.is_file() and file_path.suffix in ['.json', '.csv']:
                            # tideup_collect_data와 동일한 센서 ID 추출 로직
                            filename = file_path.name
                            sensor_id = self._extract_sensor_id_from_filename(filename, sensor_ids)
                            
                            if sensor_id:
                                # 파일명에서 키 생성 (전처리를 위한 키 형식)
                                if filename.startswith("In_") or filename.startswith("Out_"):
                                    # In_agsmotor_green_bd7d3355-..._ch1_20260316_160853.json
                                    # -> In_agsmotor_green_bd7d3355-..._ch1
                                    parts = filename.split('_')
                                    key_parts = [parts[0], parts[1]]  # In/Out, sensor_type
                                    
                                    # sensor_id 찾기
                                    for i, part in enumerate(parts[2:], 2):
                                        if part in sensor_ids:
                                            key_parts.append(part)  # sensor_id 추가
                                            # 채널 정보 확인
                                            if i + 1 < len(parts) and parts[i + 1].startswith('ch'):
                                                key_parts.append(parts[i + 1])  # 채널 정보 추가
                                            break
                                    
                                    key = '_'.join(key_parts)
                                else:
                                    key = filename.split('.')[0]  # 확장자 제외
                                
                                saved_files[key] = str(file_path)
                                print(f"📁 분류된 파일 발견: {key} -> {file_path}")
        
        # 2. 원본 디렉토리에서 파일 찾기 (보조)
        if pipeline_output.exists():
            for file_path in pipeline_output.iterdir():
                if file_path.is_file() and file_path.suffix in ['.json', '.csv']:
                    filename = file_path.name
                    # 이미 분류된 파일이나 시스템 파일은 건너뛰기
                    if (filename.startswith("metadata_") or 
                        filename.startswith("organizing_") or
                        filename.startswith("processing_")):
                        continue
                    
                    # tideup_collect_data와 동일한 센서 ID 추출 로직
                    sensor_id = self._extract_sensor_id_from_filename(filename, sensor_ids)
                    
                    if sensor_id:
                        # 파일명에서 키 생성
                        if filename.startswith("In_") or filename.startswith("Out_"):
                            parts = filename.split('_')
                            key_parts = [parts[0]]  # In/Out
                            
                            # sensor_type 찾기 (두 단어로 된 센서 타입 처리)
                            if len(parts) >= 3 and parts[1] == 'agsmotor' and len(parts) >= 4 and parts[2] == 'green':
                                key_parts.append('agsmotor_green')  # 두 단어 센서 타입
                                # sensor_id는 그 다음 UUID 부분
                                for i, part in enumerate(parts[3:], 3):
                                    if '-' in part and len(part) > 10:  # UUID 형식 확인
                                        key_parts.append(part)  # sensor_id 추가
                                        # 채널 정보 확인
                                        if i + 1 < len(parts) and parts[i + 1].startswith('ch'):
                                            key_parts.append(parts[i + 1])  # 채널 정보 추가
                                        break
                            else:
                                key_parts.append(parts[1])  # sensor_type (thermohygro, raindrop 등)
                                if len(parts) >= 3:
                                    key_parts.append(parts[2])  # sensor_id
                                    # 채널 정보 확인
                                    if len(parts) >= 4 and parts[3].startswith('ch'):
                                        key_parts.append(parts[3])  # 채널 정보 추가
                            
                            key = '_'.join(key_parts)
                        else:
                            key = filename.split('.')[0]  # 확장자 제외
                        
                        # 중복되지 않으면 추가 (분류된 파일이 우선)
                        if key not in saved_files:
                            saved_files[key] = str(file_path)
                            print(f"📁 원본 파일 발견: {key} -> {file_path}")
        
        print(f"📊 총 {len(saved_files)}개의 데이터 파일을 찾았습니다.")
        
        return saved_files
    
    def find_metadata_file(self, include_organized: bool = True, output_dir: str = "pipeline_output") -> Path:
        """
        가장 최신 메타데이터 파일 찾기
        
        Args:
            include_organized: 분류된 디렉토리도 포함할지 여부
            output_dir: 메타데이터 파일을 찾을 디렉토리 경로
            
        Returns:
            메타데이터 파일 경로
        """
        from pathlib import Path
        
        output_dir = Path(output_dir)
        organized_dir = Path(output_dir) / "organized_by_sensor"
        
        # 메타데이터 파일 찾기 (원본 디렉토리와 분류된 디렉토리 모두 확인)
        metadata_files = []
        
        # 원본 디렉토리에서 메타데이터 파일 찾기
        if output_dir.exists():
            metadata_files.extend(list(output_dir.glob("metadata_*.csv")))
        
        # 분류된 디렉토리에서 메타데이터 파일 찾기
        if include_organized and organized_dir.exists():
            metadata_files.extend(list(organized_dir.glob("metadata_*.csv")))
        
        # 가장 최신 메타데이터 파일 찾기
        if metadata_files:
            return max(metadata_files, key=lambda x: x.stat().st_mtime)
        else:
            return None
    def tideup_collect_data(self, output_dir: str = "pipeline_output"):
        """
        생성 데이터 정리 - 센서 ID별로 폴더 분류
        
        Args:
            output_dir: 데이터가 저장된 디렉토리 경로
        """
        sensor_categories = self._get_sensor_categories_from_metadata(include_organized=True, output_dir=output_dir)
        sensor_ids = list(sensor_categories.keys())

        pipeline_output = Path(output_dir)
        if not pipeline_output.exists():
            print(f"❌ {output_dir} 디렉토리가 존재하지 않습니다.")
            return

        if not sensor_ids:
            print("⚠️ metadata에서 sensor_categories를 찾지 못했습니다.")
            return
        
        # 정리된 파일을 저장할 디렉토리
        organized_dir = pipeline_output / "organized_by_sensor"
        organized_dir.mkdir(exist_ok=True)
        
        print("🔄 데이터 정리 시작...")
        print(f"📁 원본 디렉토리: {pipeline_output}")
        print(f"📁 정리 디렉토리: {organized_dir}")
        
        # 파일 처리 통계
        processed_files = 0
        skipped_files = 0
        created_folders = set()
        
        # 모든 파일 순회
        for file_path in pipeline_output.iterdir():
            # 디렉토리는 건너뛰기
            if file_path.is_dir():
                continue
            
            # 이미 정리된 디렉토리는 건너뛰기
            if file_path.name.startswith("organized_"):
                continue
            
            filename = file_path.name
            
            # 센서 ID 추출 (파일명에서)
            sensor_id = self._extract_sensor_id_from_filename(filename, sensor_ids)
            
            if not sensor_id:
                print(f"⚠️ 센서 ID를 찾을 수 없음: {filename}")
                skipped_files += 1
                continue
            
            # 센서 카테고리 폴더 생성
            category = sensor_categories[sensor_id]
            category_dir = organized_dir / category
            category_dir.mkdir(exist_ok=True)
            created_folders.add(category)
            
            # 파일 이동
            target_path = category_dir / filename
            
            try:
                shutil.move(str(file_path), str(target_path))
                print(f"✅ 이동: {filename} → {category}/{filename}")
                processed_files += 1
            except Exception as e:
                print(f"❌ 이동 실패: {filename} - {e}")
                skipped_files += 1
        
        # 요약 정보 생성
        summary = {
            "processing_time": datetime.now().isoformat(),
            "total_files_processed": processed_files,
            "total_files_skipped": skipped_files,
            "created_folders": sorted(list(created_folders)),
            "sensor_categories": sensor_categories,
            "organized_directory": str(organized_dir)
        }
        
        # 요약 파일 저장
        summary_path = organized_dir / "organizing_summary.csv"
        with open(summary_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=summary.keys())
            writer.writeheader()
            writer.writerow(summary)
        
        print("\n" + "=" * 60)
        print("📊 데이터 정리 완료!")
        print("=" * 60)
        print(f"📁 처리된 파일: {processed_files}개")
        print(f"📁 건너뛴 파일: {skipped_files}개")
        print(f"📁 생성된 폴더: {len(created_folders)}개")
        print(f"\n📋 생성된 폴더 목록:")
        for folder in sorted(created_folders):
            print(f"  • {folder}")
        print(f"\n📄 요약 파일: {summary_path}")
        print("=" * 60)
    
    def run_db_load(
        self, 
        start_time: str,
        end_time: str,
        sensor_with_channels: List[Dict[str, str]] = [],
        site_id: str = "",
        facility_id: str = "",
        grow_name: str = "",
        grow_start_date: str = "",
        requested_columns: List[str] = [],
        config_file: str = "pipeline_config.yaml",
        input_mode = "args",
        output_dir: str = "pipeline_output"):
        """
        파이프라인 실행 - 설정 파일에서 입력을 읽어 쿼리 생성 및 DB 실행
        
        Args:
            site_id: 사이트 ID
            facility_id: 시설 ID
            start_time: 조회 시작 시간
            end_time: 조회 종료 시간
            sensor_with_channels: 센서 ID와 채널 정보 리스트
            grow_name: 재배 이름
            grow_start_date: 재배 시작 날짜
            config_file: 설정 파일 경로
            input_mode: 함수의 입력받는 방식
            
        1. 설정 파일 혹은 함수 파라미터에서 파라미터 읽기
        2. 유효성 검증
        3. 쿼리 생성 및 DB 실행
        4. 결과 출력

        site_id, facility_id, grow_name, grow_start_date에 해당하는 시설의 데이터의 requested_columns를 조회합니다.
        grow_name과 grow_start_date는 재배 정보 테이블에서 조회해야 하나 일단은 결과 컬럼에 그대로 포함합니다.
        """
        self.logger.info("=== 데이터 수집 파이프라인 시작 ===")
        
        try:
            # 1. 입력 방식에 따라 설정 파일 읽기
            if input_mode == "file":
                try:
                    with open(config_file, 'r', encoding='utf-8') as file:
                        config = yaml.safe_load(file)
                except FileNotFoundError:
                    print(f"❌ 설정 파일을 찾을 수 없습니다: {config_file}")
                    print("pipeline_config.yaml 파일을 생성하고 설정을 입력하세요.")
                    return
            elif input_mode == "args":
                # sensor_with_channels에서 센서 ID만 추출
                sensor_ids = [item['sensor_id'] for item in sensor_with_channels]
                config = {
                    "site_id": site_id,
                    "facility_id": facility_id,
                    "sensors": sensor_ids,
                    "sensor_with_channels": sensor_with_channels,
                    "start_time": start_time,
                    "end_time": end_time,
                    "grow_name": grow_name,
                    "grow_start_date": grow_start_date,
                    "requested_columns": requested_columns,
                    "ts_join_mode": "nearest_within_60s",
                    "output_dir": output_dir
                }
            
            # 2. 설정 파라미터 추출
            start_time = config['start_time']
            end_time = config['end_time']
            ts_join_mode = config.get('ts_join_mode', 'nearest_within_60s')
            site_id = config.get('site_id')
            sensor_with_channels = config.get('sensor_with_channels', [])
             
            print(f"\n=== 파라미터 ===")
            print(f"시간 범위: {start_time} ~ {end_time}")
            print(f"조인 모드: {ts_join_mode}")
            if site_id is not None and site_id != "":
                print(f"site_id: {site_id}")
            if facility_id is not None and facility_id != "":
                print(f"facility_id: {facility_id}")
            if sensor_with_channels is not None and sensor_with_channels != []:
                print(f"sensor_with_channels: {sensor_with_channels}")
            
            # 5. 조인 모드 설정
            self.set_ts_join_mode(ts_join_mode)
            
            # 6. 테이블별 쿼리 생성 및 DB 실행 (raw 결과)
            print(f"\n🔄 데이터 수집을 시작합니다...")
            
            # 실행 파라미터 저장 (메타데이터용)
            self._last_start_time = start_time
            self._last_end_time = end_time
            self._last_site_id = site_id

            # list1 = config.get("sensors", [])
            # list2 = self.db_client.get_sensor_ids_specific(site_id, facility_id)
            # print(list1)
            # print(list2)
            # if isinstance(list1, str):
            #     list1 = list1.split(',')
            with self.db_client.get_connection():
                # sensor_with_channels에서 센서 ID와 채널 정보 처리
                sensor_id_list = []
                for sensor_info in sensor_with_channels:
                    sensor_id = sensor_info['sensor_id']
                    channel = sensor_info.get('channel')
                    if channel:
                        # 채널이 있는 경우: sensor_id:channel 형식으로 결합
                        sensor_id_list.append(f"{sensor_id}:{channel}")
                    else:
                        # 채널이 없는 경우: sensor_id만 사용
                        sensor_id_list.append(sensor_id)
                
                # 기존 sensors 목록과 결합
                # config_sensors = config.get("sensors", [])
                if input_mode == "file":
                    config_sensors = config.get("sensors", [])
                else:
                    config_sensors = []
                facility_sensors = self.db_client.get_sensor_ids_specific(site_id, facility_id)
                sensor_id_list = config_sensors + facility_sensors + sensor_id_list

                print(f"site와 facility가 반영된 sensor list: {sensor_id_list}")
                
                # 쿼리 빌더에 센서 정보 전달
                queries_by_table = self.query_builder.build(
                    sensor_ids=sensor_id_list,
                    start_date=start_time,
                    end_date=end_time,
                )

                result_by_sensor: Dict[str, List[Dict[str, Any]]] = {}
                table_queries: Dict[str, str] = {}  # 테이블별 쿼리 저장
                
                # build() 함수는 쿼리 문자열 리스트를 반환하므로 각 쿼리 실행
                for i, query in enumerate(queries_by_table):
                    if isinstance(query, str):
                        # 쿼리에서 sensor_id와 테이블 이름 추출
                        import re
                        table_match = re.search(r'FROM\s+(\w+)', query, re.IGNORECASE)
                        sensor_match = re.search(r"sensor_id\s*=\s*'([^']+)'", query, re.IGNORECASE)
                        channel_match = re.search(r"probe\s*=\s*(\d+)", query, re.IGNORECASE)
                        
                        table_name = table_match.group(1) if table_match else 'unknown'
                        sensor_id = sensor_match.group(1) if sensor_match else 'unknown'
                        channel = channel_match.group(1) if channel_match else None
                        
                        self.logger.info(f"쿼리 실행: table={table_name}, sensor={sensor_id}, channel={channel}")
                        query_result = self.db_client.execute_query(query)
                        
                        # 테이블별 쿼리 저장 (sensor_key와 table_name을 조합)
                        if channel is not None:
                            sensor_key = f"{sensor_id}_ch{channel}"
                        else:
                            sensor_key = sensor_id
                        
                        # 테이블별 쿼리 정보 저장
                        table_key = f"{table_name}_{sensor_key}"
                        table_queries[table_key] = query
                        
                        if sensor_key not in result_by_sensor:
                            result_by_sensor[sensor_key] = []
                        result_by_sensor[sensor_key].extend(query_result)

            # 7. 결과를 파일로 저장
            output_dir = config.get('output_dir', output_dir)
            saved_files, sensor_file_mapping = self.save_results_to_files(result_by_sensor, output_dir, table_queries)
            
            # 8. 결과 요약 출력
            total_rows = sum(len(rows) for rows in result_by_sensor.values())
            print(f"\n✅ 데이터 수집 완료")
            print(f"📊 총 센서: {len(result_by_sensor)}개")
            print(f"📈 총 데이터: {total_rows:,}개 행")
            print(f"📁 출력 디렉토리: {output_dir}/")
            print(f"\n📋 저장된 파일:")
            for sensor_key, file_path in saved_files.items():
                if sensor_key != "metadata":
                    # sensor_file_mapping에서 정보 가져오기
                    if sensor_key in sensor_file_mapping:
                        sensor_info = sensor_file_mapping[sensor_key]
                        sensor_id = sensor_info['sensor_id']
                        channel = sensor_info.get('channel')
                        
                        # result_by_sensor에서 적절한 키로 데이터 찾기
                        if channel is not None:
                            lookup_key = f"{sensor_id}_ch{channel}"
                        else:
                            lookup_key = sensor_id
                        
                        rows_count = len(result_by_sensor.get(lookup_key, []))
                        print(f"  • {sensor_key}: {rows_count}개 행 -> {file_path}")
            print(f"  • 메타데이터: -> {saved_files['metadata']}")
            
            # 9. 다음 단계 안내
            print(f"\n🔄 다음 단계: 학습 데이터 가공 과정에서 이 파일들을 입력으로 사용하세요")
            timestamp = output_dir.split('/')[-1]
            print(f"📁 입력 경로 예시: processing/input/{timestamp}/tableName_{timestamp}.json")
            
            return saved_files
            
        except yaml.YAMLError as e:
            print(f"❌ YAML 파일 파싱 오류: {e}")
        except Exception as e:
            self.logger.error(f"파이프라인 실행 중 오류 발생: {e}")
            print(f"❌ 오류가 발생했습니다: {e}")
        
        print("\n=== 파이프라인 종료 ===")
    
    def save_results_to_files(self, result_by_sensor: Dict[str, List[Dict[str, Any]]], 
                           output_dir: str = "pipeline_output",
                           table_queries: Dict[str, str] = None) -> Tuple[Dict[str, str], Dict[str, Dict[str, str]]]:
        """
        파이프라인 결과를 파일로 저장 (sensor 단위)
        
        Args:
            result_by_sensor: sensor별 결과 데이터
            output_dir: 출력 디렉토리
            table_queries: 테이블별 실행 쿼리
            
        Returns:
            Tuple[저장된 파일 경로 딕셔너리, sensor_file_mapping 딕셔너리]
        """
        # 출력 디렉토리 생성 (부모 디렉토리 포함)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        saved_files = {}
        sensor_file_mapping = {}  # sensor 정보를 저장하기 위한 맵
        # output_dir에 이미 timestamp가 포함되어 있으므로 파일명에는 추가하지 않음
        timestamp = ""

        source_sensor_ids = []
        for sensor_key in result_by_sensor.keys():
            if '_ch' in sensor_key:
                source_sensor_id, _ = sensor_key.split('_ch', 1)
            else:
                source_sensor_id = sensor_key
            source_sensor_ids.append(source_sensor_id)

        sensor_display_names = self._get_sensor_display_names(source_sensor_ids)
        
        for sensor_key, rows in result_by_sensor.items():
            if not rows:
                self.logger.info(f"센서 {sensor_key}: 데이터 없음 (저장 건너뜀)")
                continue
            
            # sensor_key에서 sensor_id와 channel 분리
            if '_ch' in sensor_key:
                sensor_id, channel = sensor_key.split('_ch', 1)
                channel_suffix = f"_ch{channel}"
            else:
                sensor_id = sensor_key
                channel = None
                channel_suffix = ""
            
            # sensor 타입 조회
            sensor_type = self._get_sensor_type(sensor_id)

            # facility 소속 여부 확인
            facility_status = self._check_sensor_has_facility(sensor_id, channel, sensor_type)
            
            # 파일명: facility_status_sensorType_sensorId_channel_timestamp.csv
            filename_csv = f"{facility_status}_{sensor_type}_{sensor_id}{channel_suffix}_{timestamp}.csv"
            file_path_csv = output_path / filename_csv

            
            df = pd.DataFrame(rows)
            df.to_csv(file_path_csv, index=False)
            
            file_key = f"{facility_status}_{sensor_type}_{sensor_id}{channel_suffix}"
            saved_files[file_key] = str(file_path_csv)
            # 데이터에서 site_id와 facility_id 추출
            site_id = None
            facility_id = None
            
            if rows and len(rows) > 0:
                # 첫 번째 행에서 site_id와 facility_id 추출
                first_row = rows[0]
                if 'site_id' in first_row:
                    site_id = first_row['site_id']
                if 'facility_id' in first_row:
                    facility_id = first_row['facility_id']
            
            # sensor 정보 저장
            sensor_file_mapping[file_key] = {
                'sensor_id': sensor_id,
                'display_name': sensor_display_names.get(sensor_id),
                'sensor_type': sensor_type,
                'facility_status': facility_status,
                'site_id': site_id,        # 추가
                'facility_id': facility_id   # 추가
            }
            if channel is not None:
                sensor_file_mapping[file_key]['channel'] = channel
            self.logger.info(f"센서 {sensor_id}{channel_suffix} (type {sensor_type}): {len(rows)}개 행 저장 완료 -> {file_path_csv}")
        
        # 메타데이터 파일 저장 (CSV 형식)
        metadata_file = output_path / f"metadata_{timestamp}.csv"
        
        # 메타데이터를 테이블 형식으로 변환
        metadata_rows = []
        
        # 기본 정보
        metadata_rows.append({
            'key': 'timestamp',
            'value': datetime.now().isoformat()
        })
        metadata_rows.append({
            'key': 'total_sensors',
            'value': len(result_by_sensor)
        })
        metadata_rows.append({
            'key': 'total_rows',
            'value': sum(len(rows) for rows in result_by_sensor.values())
        })
        
        # 설정 정보
        config_info = {
            "start_time": self._last_start_time,
            "end_time": self._last_end_time,
            "site_id": getattr(self, '_last_site_id', None),
            "facility_id": getattr(self, '_last_facility_id', None)
        }
        
        for config_key, config_value in config_info.items():
            metadata_rows.append({
                'key': f'config_{config_key}',
                'value': config_value
            })
        
        # 출력 파일 정보
        for file_key, file_path in saved_files.items():
            metadata_rows.append({
                'key': f'output_file_{file_key}',
                'value': file_path
            })
        
        # sensor_file_mapping 정보 저장 (JSON 문자열로)
        if sensor_file_mapping:
            import json
            sensor_mapping_json = json.dumps(sensor_file_mapping, ensure_ascii=False)
            metadata_rows.append({
                'key': 'sensor_file_mapping',
                'value': sensor_mapping_json
            })

            sensor_categories = {
                sensor_info['sensor_id']: sensor_info['display_name']
                for sensor_info in sensor_file_mapping.values()
                if sensor_info.get('sensor_id') and sensor_info.get('display_name')
            }
            metadata_rows.append({
                'key': 'sensor_categories',
                'value': json.dumps(sensor_categories, ensure_ascii=False)
            })
        
        # table_queries 정보 저장 (JSON 문자열로)
        if table_queries:
            import json
            table_queries_json = json.dumps(table_queries, ensure_ascii=False)
            metadata_rows.append({
                'key': 'table_queries',
                'value': table_queries_json
            })
        
        # 메타데이터 CSV 저장
        metadata_df = pd.DataFrame(metadata_rows)
        metadata_df.to_csv(metadata_file, index=False, encoding='utf-8')

        self.logger.info(f"메타데이터 저장 완료 -> {metadata_file}")
        saved_files["metadata"] = str(metadata_file)

        return saved_files, sensor_file_mapping
    
    def _get_sensor_type(self, sensor_id: str) -> str:
        """
        sensor_id로 sensor_type 조회
        
        Args:
            sensor_id: 센서 ID
            
        Returns:
            sensor_type: 센서 타입
        """
        try:
            # sensors 테이블에서 sensor_type 조회
            query = "SELECT sensor_type FROM sensors WHERE sensor_id = %s"
            
            # DB 연결이 필요한 경우 연결
            connection_needed = not self.db_client.connection
            if connection_needed:
                self.db_client.connect()
            
            result = self.db_client.execute_query(query, (sensor_id,))
            
            # 연결했었다면 연결 해제
            if connection_needed:
                self.db_client.disconnect()
                
            if result:
                return result[0]['sensor_type']
            else:
                return "unknown"
        except Exception as e:
            self.logger.error(f"sensor_type 조회 중 오류 (sensor_id: {sensor_id}): {e}")
            return "unknown"

    def _check_sensor_has_facility(self, sensor_id: str, sensor_channel: str | int, sensor_type: str = None) -> str:
        """
        sensor_id가 facility에 속하는지 여부 확인
        
        Args:
            sensor_id: 센서 ID
            sensor_channel: 센서 채널
            sensor_type: 센서 타입
            
        Returns:
            str: "In" (facility에 속함) 또는 "Out" (facility에 속하지 않음)
        """
        try:
            # sensor_channel이 정수인 경우 문자열로 변환
            if isinstance(sensor_channel, int):
                sensor_channel = str(sensor_channel)

            # sensors 테이블에서 device_id, channel_id 조회 후 facility_devices에서 facility_id 조회
            if sensor_type == "agsmotor_green":
                query = """
                SELECT fc.facility_id
                FROM facility_controls fc
                INNER JOIN sensors s ON fc.device_id = s.device_id AND fc.modbus = s.channel_id
                WHERE s.sensor_id = %s AND fc.payload LIKE %s
                """
                # JSON 형식의 payload에서 채널 찾기: {"8": {{.ratio}}}
                params = (sensor_id, f"%\"{sensor_channel}\"%")
            else:
                query = """
                SELECT fd.facility_id 
                FROM facility_devices fd
                INNER JOIN sensors s ON fd.device_id = s.device_id AND fd.modbus = s.channel_id
                WHERE s.sensor_id = %s
                """
                params = (sensor_id,)
            
            # DB 연결이 필요한 경우 연결
            connection_needed = not self.db_client.connection
            if connection_needed:
                self.db_client.connect()
            
            result = self.db_client.execute_query(query, params)
            
            # 연결했었다면 연결 해제
            if connection_needed:
                self.db_client.disconnect()
                
            if result:
                return "In"
            else:
                return "Out"
        except Exception as e:
            self.logger.error(f"facility 소속 여부 조회 중 오류 (sensor_id: {sensor_id}): {e}")
            return "Out"

    def run_preprocessing(self, saved_files: Dict[str, str], output_dir: str, config: Dict[str, Any]) -> Dict[str, str]:
        return run_pipeline_preprocessing(
            pipeline_instance=self,
            saved_files=saved_files,
            output_dir=output_dir,
            config=config,
            timestamp_tables=TIMESTAMP_TABLES,
        )
        