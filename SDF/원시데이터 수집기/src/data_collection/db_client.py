# DB 연결 및 쿼리 실행
import psycopg2
import psycopg2.extras
import yaml
import logging
import os
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
from string import Template
from pathlib import Path


class DatabaseClient:
    """데이터베이스 연결 및 데이터 조회를 담당하는 클라이언트 클래스"""
    
    def __init__(self, config_path: str = "config/settings.yaml"):
        """
        데이터베이스 클라이언트 초기화
        
        Args:
            config_path: 설정 파일 경로
        """
        self.config = self._load_config(config_path)
        self.connection = None
        self.logger = self._setup_logger()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """설정 파일 로드 및 환경 변수 치환"""
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                content = file.read()
                # 환경 변수 치환
                template = Template(content)
                substituted_content = template.substitute(os.environ)
                return yaml.safe_load(substituted_content)
        except FileNotFoundError:
            raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"설정 파일 파싱 오류: {e}")
        except KeyError as e:
            raise ValueError(f"환경 변수가 설정되지 않았습니다: {e}")
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            # 로그 폴더 생성
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            # 파일 핸들러
            file_handler = logging.FileHandler(log_dir / "db_client.log", encoding='utf-8')
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.INFO)
            logger.addHandler(file_handler)
            
            # 콘솔 핸들러
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                self.config.get('logging', {}).get('format', 
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            console_handler.setFormatter(console_formatter)
            console_handler.setLevel(logging.INFO)
            logger.addHandler(console_handler)
            
            logger.setLevel(
                getattr(logging, 
                    self.config.get('logging', {}).get('level', 'INFO'))
            )
        return logger
    
    def connect(self) -> None:
        """데이터베이스 연결"""
        try:
            db_config = self.config['database']
            self.connection = psycopg2.connect(
                host=db_config['host'],
                port=db_config['port'],
                user=db_config['username'],
                password=db_config['password'],
                database=db_config['database_name'],
                connect_timeout=10
            )
            self.logger.info("데이터베이스 연결 성공")
        except psycopg2.Error as e:
            self.logger.error(f"데이터베이스 연결 실패: {e}")
            raise
    
    def disconnect(self) -> None:
        """데이터베이스 연결 해제"""
        if self.connection:
            try:
                self.connection.close()
                self.logger.info("데이터베이스 연결 해제")
            except psycopg2.Error as e:
                self.logger.error(f"데이터베이스 연결 해제 중 오류: {e}")
            finally:
                self.connection = None

    def get_sensor_ids_specific(self, site_id: str, facility_id: str) -> List[str]:
        """
        특정 사이트와 시설의 센서 ID 리스트 반환
        
        Args:
            site_id: 사이트 ID
            facility_id: 시설 ID
            
        Returns:
            특정 사이트와 시설의 센서 ID 리스트
        """
        site_id = (site_id or "").strip()
        facility_id = (facility_id or "").strip()

        if site_id == "" and facility_id == "":
            return []

        try:
            sensor_ids: List[str] = []

            if site_id != "" and facility_id == "":
                query_devices = "SELECT device_id FROM site_devices WHERE site_id = %s"
                site_devices = self.execute_query(query_devices, (site_id,))
                device_ids = [row['device_id'] for row in site_devices if row.get('device_id') is not None]

                if not device_ids:
                    return []

                query_site_sensors = "SELECT sensor_id FROM sensors WHERE device_id IN %s"
                result = self.execute_query(query_site_sensors, (tuple(device_ids),))
                sensor_ids.extend([row['sensor_id'] for row in result if row.get('sensor_id')])

            elif site_id == "" and facility_id != "":
                query_facility_sensors = (
                    "SELECT sensor_id FROM sensors "
                    "WHERE (device_id, channel_id) IN "
                    "(SELECT device_id, modbus FROM facility_devices WHERE facility_id = %s)"
                )
                result = self.execute_query(query_facility_sensors, (facility_id,))
                sensor_ids.extend([row['sensor_id'] for row in result if row.get('sensor_id')])

                query_facility_controls = (
                    "SELECT sensor_id, probes FROM sensors "
                    "WHERE (device_id, channel_id) IN "
                    "(SELECT device_id, modbus FROM facility_controls WHERE facility_id = %s)"
                )
                result2 = self.execute_query(query_facility_controls, (facility_id,))
                sensor_ids.extend([
                    f"{row['sensor_id']}:ch{row['probes']}"
                    for row in result2
                    if row.get('sensor_id') and row.get('probes') is not None
                ])

            else:
                query_facility_sensors = (
                    "SELECT sensor_id FROM sensors "
                    "WHERE (device_id, channel_id) IN "
                    "(SELECT device_id, modbus FROM facility_devices WHERE facility_id = %s AND site_id = %s)"
                )
                result = self.execute_query(query_facility_sensors, (facility_id, site_id))
                sensor_ids.extend([row['sensor_id'] for row in result if row.get('sensor_id')])

                query_facility_controls = (
                    "SELECT sensor_id, probes FROM sensors "
                    "WHERE (device_id, channel_id) IN "
                    "(SELECT device_id, modbus FROM facility_controls WHERE facility_id IN "
                    "(SELECT facility_id FROM facilities WHERE facility_id = %s AND site_id = %s))"
                )
                result2 = self.execute_query(query_facility_controls, (facility_id, site_id))
                sensor_ids.extend([
                    f"{row['sensor_id']}:ch{row['probes']}"
                    for row in result2
                    if row.get('sensor_id') and row.get('probes') is not None
                ])

            unique_sensor_ids = list(dict.fromkeys(sensor_ids))
            return unique_sensor_ids
        except Exception as e:
            self.logger.error(f"센서 ID 조회 중 오류 (site_id={site_id}, facility_id={facility_id}): {e}")
            return []

    def execute_sensor_types_query(self, sensor_ids: List[str]) -> List[Dict[str, Any]]:
        """
        sensor_types 테이블 조회
        """
        query = "SELECT sensor_id, sensor_type FROM sensors WHERE sensor_id IN %s"
        return self.execute_query(query, (tuple(sensor_ids),))

    def get_sensor_display_names(self, sensor_ids: List[str]) -> Dict[str, str]:
        """
        sensor_id 목록에 대한 display_name 매핑 반환
        """
        if not sensor_ids:
            return {}

        unique_sensor_ids = list(set(sensor_ids))
        query = "SELECT sensor_id, display_name FROM sensors WHERE sensor_id IN %s"
        result = self.execute_query(query, (tuple(unique_sensor_ids),))

        return {
            row['sensor_id']: row.get('display_name')
            for row in result
            if row.get('sensor_id')
        }
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        쿼리 실행 및 결과 반환
        
        Args:
            query: 실행할 SQL 쿼리
            params: 쿼리 파라미터
            
        Returns:
            쿼리 결과 (디셔너리 리스트)
        """
        if not self.connection:
            raise ConnectionError("데이터베이스에 연결되어 있지 않습니다")
        
        try:
            # 파라미터가 포함된 최종 쿼리 생성 및 로그 기록
            if params:
                # 파라미터를 쿼리에 삽입하여 로깅 (실제 실행과는 별개)
                try:
                    # 안전한 파라미터 치환을 위한 템플릿 사용
                    query_template = Template(query)
                    # %s를 ${param} 형태로 변환
                    safe_query = query.replace('%s', '${param}')
                    formatted_params = []
                    for param in params:
                        if isinstance(param, str):
                            formatted_params.append(f"'{param}'")
                        else:
                            formatted_params.append(str(param))
                    
                    # 파라미터 개수만큼 반복 적용
                    final_query = safe_query
                    for i, formatted_param in enumerate(formatted_params):
                        final_query = final_query.replace('${param}', formatted_param, 1)
                    
                    self.logger.info(f"쿼리 실행: {final_query}")
                except Exception:
                    # 파라미터 치환 실패 시 원본 쿼리와 파라미터 별도 로깅
                    self.logger.info(f"쿼리 실행: {query}")
                    self.logger.info(f"쿼리 파라미터: {params}")
            else:
                self.logger.info(f"쿼리 실행: {query}")
            
            with self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, params)
                result = cursor.fetchall()
                self.logger.info(f"쿼리 실행 성공: {len(result)}개 행 반환")
                return result
        except psycopg2.Error as e:
            self.logger.error(f"쿼리 실행 실패: {e}")
            if params:
                # 오류 시에도 파라미터 포함 쿼리 로깅 시도
                try:
                    query_template = Template(query)
                    safe_query = query.replace('%s', '${param}')
                    formatted_params = []
                    for param in params:
                        if isinstance(param, str):
                            formatted_params.append(f"'{param}'")
                        else:
                            formatted_params.append(str(param))
                    
                    final_query = safe_query
                    for i, formatted_param in enumerate(formatted_params):
                        final_query = final_query.replace('${param}', formatted_param, 1)
                    
                    self.logger.error(f"실패된 쿼리: {final_query}")
                except Exception:
                    self.logger.error(f"실패된 쿼리: {query}")
                    self.logger.error(f"쿼리 파라미터: {params}")
            else:
                self.logger.error(f"실패된 쿼리: {query}")
            raise
    
    @contextmanager
    def get_connection(self):
        """컨텍스트 매니저를 통한 연결 관리"""
        self.connect()
        try:
            yield self
        finally:
            self.disconnect()
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()