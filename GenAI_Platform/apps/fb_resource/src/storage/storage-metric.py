import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
import subprocess
import time
import logging
import signal
import threading
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from prometheus_client import start_http_server, Gauge, Info, Counter

import traceback
from utils.settings import LLM_USED

from utils.msa_db import db_workspace as ws_db
from utils.msa_db import db_storage as storage_db
from utils.msa_db import db_dataset as dataset_db
from utils.msa_db import db_prepro as prepro_db
from utils.msa_db import db_project as project_db
from utils.llm_db import db_model

from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('storage_metric.log')
    ]
)
logger = logging.getLogger(__name__)

# 상수 정의
class StoragePaths:
    MAIN_STORAGE_PATH = "/jf-data/main/{WORKSPACE_NAME}"
    PROJECT_PATH = MAIN_STORAGE_PATH + "/projects/{PROJECT_NAME}"
    MODEL_PATH = MAIN_STORAGE_PATH + "/models/{MODEL_NAME}"
    PREPRO_PATH = MAIN_STORAGE_PATH + "/preprocessings/{PREPRO_NAME}"
    DATA_STORAGE_PATH = "/jf-data/data/{WORKSPACE_NAME}"
    DATASET_PATH = DATA_STORAGE_PATH + "/{ACCESS}/{DATASET_NAME}"

class MetricNames:
    WORKSPACE_USAGE = 'workspace_usage_bytes'
    DATASET_USAGE = 'dataset_usage_bytes'
    PROJECT_USAGE = 'project_usage_bytes'
    MODEL_USAGE = 'model_usage_bytes'
    PREPRO_USAGE = 'prepro_usage_bytes'

# 장애복구 관련 상수
class RecoveryConfig:
    MAX_RETRY_ATTEMPTS = 3
    INITIAL_RETRY_DELAY = 1  # 초
    MAX_RETRY_DELAY = 60     # 초
    BACKOFF_MULTIPLIER = 2
    HEALTH_CHECK_INTERVAL = 30  # 초
    CONSECUTIVE_FAILURE_THRESHOLD = 5
    GRACEFUL_SHUTDOWN_TIMEOUT = 10  # 초

class ServiceStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    SHUTTING_DOWN = "shutting_down"

# Prometheus 메트릭 정의
WORKSPACE_USAGE = Gauge(
    MetricNames.WORKSPACE_USAGE, 
    'Workspace used storage in bytes', 
    ['name', 'type', 'storage']
)
DATASET_USAGE = Gauge(
    MetricNames.DATASET_USAGE, 
    'Dataset used storage in bytes',
    ['name', 'workspace', 'storage', 'type']
)
PROJECT_USAGE = Gauge(
    MetricNames.PROJECT_USAGE, 
    'Project used storage in bytes',
    ['name', 'workspace', 'storage', 'type']
)
MODEL_USAGE = Gauge(
    MetricNames.MODEL_USAGE, 
    'Model used storage in bytes',
    ['name', 'workspace', 'storage', 'type']
)
PREPRO_USAGE = Gauge(
    MetricNames.PREPRO_USAGE, 
    'Preprocessing used storage in bytes',
    ['name', 'workspace', 'storage', 'type']
)

# 장애복구 관련 메트릭
RETRY_COUNTER = Counter('storage_metric_retries_total', 'Total number of retry attempts', ['operation'])
FAILURE_COUNTER = Counter('storage_metric_failures_total', 'Total number of failures', ['operation'])
HEALTH_STATUS = Gauge('storage_metric_health_status', 'Current health status', ['status'])
COLLECTION_DURATION = Gauge('storage_metric_collection_duration_seconds', 'Time taken for metric collection')

@dataclass
class StorageInfo:
    """스토리지 정보를 담는 데이터 클래스"""
    id: int
    name: str
    mountpoint: str
    ip: Optional[str] = None
    storage_type: Optional[str] = None  # 'nfs', 'hostpath', 'local' 등
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # 추가 필드들을 위한 catch-all 필드
    _extra_fields: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """초기화 후 추가 필드 처리"""
        # dataclass에서 정의되지 않은 필드들을 _extra_fields에 저장
        pass
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StorageInfo':
        """딕셔너리에서 StorageInfo 객체 생성"""
        # 정의된 필드들만 추출
        defined_fields = {
            'id': data.get('id'),
            'name': data.get('name'),
            'mountpoint': data.get('mountpoint'),
            'ip': data.get('ip'),
            'storage_type': data.get('storage_type'),
            'created_at': data.get('created_at'),
            'updated_at': data.get('updated_at')
        }
        
        # 필수 필드 검증 (IP는 선택적)
        required_fields = ['id', 'name', 'mountpoint']
        for field in required_fields:
            if defined_fields[field] is None:
                raise ValueError(f"Required field '{field}' is missing in storage data")
        
        return cls(**defined_fields)
    
    def is_local_storage(self) -> bool:
        """로컬 스토리지인지 확인"""
        is_local = (not self.ip or self.ip.strip() == '' or 
                   self.storage_type in ['hostpath', 'local', 'emptyDir'])
        
        logger.debug(f"Storage '{self.name}' type check: IP='{self.ip}', storage_type='{self.storage_type}' -> is_local={is_local}")
        return is_local
    
    def is_remote_storage(self) -> bool:
        """원격 스토리지인지 확인"""
        return not self.is_local_storage()

    def _build_storage_path(self, base_path: str) -> str:
        """
        스토리지 타입에 따른 경로를 생성합니다.
        
        Args:
            base_path: 기본 경로
            
        Returns:
            실제 스토리지 경로
        """
        if self.is_local_storage():
            # 로컬 스토리지의 경우 mountpoint를 기준으로 경로 생성
            if self.mountpoint and self.mountpoint != '/':
                # mountpoint가 루트가 아닌 경우, base_path에서 mountpoint 부분을 교체
                if base_path.startswith('/jf-data'):
                    # /jf-data로 시작하는 경로를 mountpoint 기준으로 변경
                    relative_path = base_path.replace('/jf-data', '')
                    full_path = os.path.join(self.mountpoint, relative_path.lstrip('/'))
                    logger.debug(f"Hostpath storage path mapping: {base_path} -> {full_path}")
                    return full_path
                else:
                    # 기타 경로는 mountpoint와 결합
                    full_path = os.path.join(self.mountpoint, base_path.lstrip('/'))
                    logger.debug(f"Hostpath storage path mapping: {base_path} -> {full_path}")
                    return full_path
            else:
                # mountpoint가 루트인 경우 기본 경로 사용
                logger.debug(f"Hostpath storage using default path: {base_path}")
                return base_path
        else:
            # 원격 스토리지의 경우 기본 경로 사용 (NFS 마운트된 것으로 가정)
            logger.debug(f"NFS storage using default path: {base_path}")
            return base_path

@dataclass
class WorkspaceInfo:
    """워크스페이스 정보를 담는 데이터 클래스"""
    id: int
    name: str
    data_storage_id: int
    main_storage_id: int
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # 추가 필드들을 위한 catch-all 필드
    _extra_fields: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """초기화 후 추가 필드 처리"""
        # dataclass에서 정의되지 않은 필드들을 _extra_fields에 저장
        pass
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkspaceInfo':
        """딕셔너리에서 WorkspaceInfo 객체 생성"""
        # 정의된 필드들만 추출
        defined_fields = {
            'id': data.get('id'),
            'name': data.get('name'),
            'data_storage_id': data.get('data_storage_id'),
            'main_storage_id': data.get('main_storage_id'),
            'description': data.get('description'),
            'created_at': data.get('created_at'),
            'updated_at': data.get('updated_at')
        }
        
        # 필수 필드 검증
        required_fields = ['id', 'name', 'data_storage_id', 'main_storage_id']
        for field in required_fields:
            if defined_fields[field] is None:
                raise ValueError(f"Required field '{field}' is missing in workspace data")
        
        return cls(**defined_fields)

class ServiceHealth:
    """서비스 상태 정보"""
    status: ServiceStatus = ServiceStatus.STARTING
    last_successful_collection: Optional[datetime] = None
    consecutive_failures: int = 0
    total_failures: int = 0
    total_retries: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    
    def update_status(self, success: bool):
        """상태 업데이트"""
        if success:
            self.consecutive_failures = 0
            self.last_successful_collection = datetime.now()
            if self.status == ServiceStatus.UNHEALTHY:
                self.status = ServiceStatus.DEGRADED
            elif self.status == ServiceStatus.DEGRADED:
                self.status = ServiceStatus.HEALTHY
        else:
            self.consecutive_failures += 1
            self.total_failures += 1
            if self.consecutive_failures >= RecoveryConfig.CONSECUTIVE_FAILURE_THRESHOLD:
                self.status = ServiceStatus.UNHEALTHY
            elif self.status == ServiceStatus.HEALTHY:
                self.status = ServiceStatus.DEGRADED

class RetryHandler:
    """재시도 처리기"""
    
    @staticmethod
    def exponential_backoff_delay(attempt: int) -> float:
        """지수 백오프 지연 시간 계산"""
        delay = RecoveryConfig.INITIAL_RETRY_DELAY * (RecoveryConfig.BACKOFF_MULTIPLIER ** (attempt - 1))
        return min(delay, RecoveryConfig.MAX_RETRY_DELAY)
    
    @staticmethod
    def retry_with_backoff(func: Callable, *args, **kwargs) -> Any:
        """백오프 전략을 사용한 재시도"""
        last_exception = None
        
        for attempt in range(1, RecoveryConfig.MAX_RETRY_ATTEMPTS + 1):
            try:
                result = func(*args, **kwargs)
                if attempt > 1:
                    logger.info(f"Operation succeeded after {attempt} attempts")
                return result
                
            except Exception as e:
                last_exception = e
                RETRY_COUNTER.labels(operation=func.__name__).inc()
                
                if attempt < RecoveryConfig.MAX_RETRY_ATTEMPTS:
                    delay = RetryHandler.exponential_backoff_delay(attempt)
                    logger.warning(f"Attempt {attempt} failed for {func.__name__}: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {RecoveryConfig.MAX_RETRY_ATTEMPTS} attempts failed for {func.__name__}: {e}")
                    FAILURE_COUNTER.labels(operation=func.__name__).inc()
        
        raise last_exception

class HealthChecker:
    """헬스체크 처리기"""
    
    def __init__(self, collector: 'StorageMetricCollector'):
        self.collector = collector
        self.health_thread = None
        self.stop_event = threading.Event()
    
    def start_health_check(self):
        """헬스체크 스레드 시작"""
        self.health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self.health_thread.start()
        logger.info("Health check thread started")
    
    def stop_health_check(self):
        """헬스체크 스레드 중지"""
        self.stop_event.set()
        if self.health_thread and self.health_thread.is_alive():
            self.health_thread.join(timeout=5)
        logger.info("Health check thread stopped")
    
    def _health_check_loop(self):
        """헬스체크 루프"""
        while not self.stop_event.is_set():
            try:
                self._perform_health_check()
                time.sleep(RecoveryConfig.HEALTH_CHECK_INTERVAL)
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                time.sleep(5)
    
    def _perform_health_check(self):
        """헬스체크 수행"""
        try:
            # 기본적인 시스템 리소스 체크
            self._check_system_resources()
            
            # 데이터베이스 연결 체크
            self._check_database_connection()
            
            # 스토리지 접근성 체크
            self._check_storage_accessibility()
            
            logger.debug("Health check passed")
            
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            self.collector.health.update_status(False)
    
    def _check_system_resources(self):
        """시스템 리소스 체크"""
        # 메모리 사용량 체크
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
                # 간단한 메모리 체크 (90% 이상 사용 시 경고)
                pass
        except Exception as e:
            logger.warning(f"Memory check failed: {e}")
    
    def _check_database_connection(self):
        """데이터베이스 연결 체크"""
        try:
            # 간단한 DB 쿼리로 연결 확인
            ws_db.get_workspace_list()
        except Exception as e:
            raise Exception(f"Database connection failed: {e}")
    
    def _check_storage_accessibility(self):
        """스토리지 접근성 체크"""
        try:
            # 기본 경로 접근성 체크
            test_path = "/jf-data"
            if not os.path.exists(test_path):
                raise Exception(f"Storage path {test_path} not accessible")
        except Exception as e:
            raise Exception(f"Storage accessibility check failed: {e}")

class StorageMetricCollector:
    """스토리지 메트릭 수집기 클래스"""
    
    def __init__(self):
        self.storage_id = os.getenv("STORAGE_ID")
        if not self.storage_id:
            raise ValueError("STORAGE_ID environment variable is required")
        
        self.health = ServiceHealth()
        self.health_checker = HealthChecker(self)
        self.shutdown_event = threading.Event()
        
        # 시그널 핸들러 등록
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        logger.info(f"Storage metric collector initialized with storage_id: {self.storage_id}")
    
    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_event.set()
    
    def start(self):
        """서비스 시작"""
        try:
            self.health.status = ServiceStatus.STARTING
            self.health_checker.start_health_check()
            
            # Prometheus HTTP 서버 시작
            start_http_server(8000)
            logger.info("Prometheus HTTP server started on port 8000")
            
            self.health.status = ServiceStatus.HEALTHY
            logger.info("Storage metric collector started successfully")
            
        except Exception as e:
            self.health.status = ServiceStatus.UNHEALTHY
            logger.error(f"Failed to start storage metric collector: {e}")
            raise
    
    def stop(self):
        """서비스 중지"""
        try:
            logger.info("Stopping storage metric collector...")
            self.health.status = ServiceStatus.SHUTTING_DOWN
            
            self.shutdown_event.set()
            self.health_checker.stop_health_check()
            
            logger.info("Storage metric collector stopped successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def get_disk_usage(self, storage_info: StorageInfo, path: str) -> Optional[int]:
        """
        디스크 사용량을 조회합니다.
        
        Args:
            storage_info: 스토리지 정보 객체
            path: 조회할 경로
            
        Returns:
            사용량 (바이트) 또는 None (실패 시)
        """
        def _get_disk_usage_internal():
            logger.debug(f"Getting disk usage for path: {path}")
            
            # 스토리지 타입에 따른 로깅
            if storage_info.is_local_storage():
                logger.debug(f"Processing hostpath/local storage: {path} (mountpoint: {storage_info.mountpoint})")
            else:
                logger.debug(f"Processing NFS/remote storage: {path} (IP: {storage_info.ip}, mountpoint: {storage_info.mountpoint})")
            
            # Pod 환경에서는 경로 존재 여부를 확인하지 않고 바로 du 명령 실행
            result = subprocess.run(
                ['du', '-sb', path], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True,
                # timeout=30
            )
            
            if result.returncode == 0:
                usage = int(result.stdout.split('\t')[0])
                logger.debug(f"Disk usage for {path}: {usage} bytes")
                return usage
            else:
                raise Exception(f"du command failed: {result.stderr}")
        
        try:
            return RetryHandler.retry_with_backoff(_get_disk_usage_internal)
        except Exception as e:
            logger.error(f"Failed to get disk usage for {path} after retries: {e}")
            return None
    
    def set_metric_safely(self, metric: Gauge, labels: Dict[str, str], value: int) -> None:
        """
        메트릭을 안전하게 설정합니다.
        
        Args:
            metric: 설정할 Prometheus 메트릭
            labels: 메트릭 라벨
            value: 설정할 값
        """
        try:
            metric.labels(**labels).set(value)
            logger.debug(f"Set metric {metric._name} with labels {labels} to {value}")
        except Exception as e:
            logger.error(f"Failed to set metric {metric._name} with labels {labels}: {e}")
            raise
    
    def set_data_storage_usage(self, ws_info: WorkspaceInfo) -> None:
        """데이터 스토리지 사용량을 설정합니다."""
        try:
            logger.info(f"Setting data storage usage for workspace: {ws_info.name}")
            
            # 스토리지 정보 조회
            data_storage_info = storage_db.get_storage(storage_id=ws_info.data_storage_id)
            if not data_storage_info:
                logger.error(f"Storage not found for ID: {ws_info.data_storage_id}")
                return
            
            storage_info = StorageInfo.from_dict(data_storage_info)
            
            # 워크스페이스 데이터 경로 사용량
            ws_data_path = StoragePaths.DATA_STORAGE_PATH.format(WORKSPACE_NAME=ws_info.name)
            actual_ws_data_path = storage_info._build_storage_path(ws_data_path)
            ws_data_usage = self.get_disk_usage(storage_info, actual_ws_data_path)
            
            self.set_metric_safely(
                WORKSPACE_USAGE,
                {'name': ws_info.name, 'type': 'data', 'storage': storage_info.name},
                ws_data_usage or 0
            )
            
            # 데이터셋 사용량
            dataset_list = dataset_db.get_dataset_list(workspace_id=ws_info.id)
            for dataset in dataset_list:
                dataset_path = StoragePaths.DATASET_PATH.format(
                    WORKSPACE_NAME=ws_info.name,
                    ACCESS=dataset['access'],
                    DATASET_NAME=dataset['dataset_name']
                )
                actual_dataset_path = storage_info._build_storage_path(dataset_path)
                dataset_usage = self.get_disk_usage(storage_info, actual_dataset_path)
                
                self.set_metric_safely(
                    DATASET_USAGE,
                    {
                        'name': dataset['dataset_name'],
                        'type': 'data',
                        'workspace': ws_info.name,
                        'storage': storage_info.name
                    },
                    dataset_usage or 0
                )
                
        except Exception as e:
            logger.error(f"Error setting data storage usage for workspace {ws_info.name}: {e}")
            logger.debug(traceback.format_exc())
            raise
    
    def set_main_storage_usage(self, ws_info: WorkspaceInfo) -> None:
        """메인 스토리지 사용량을 설정합니다."""
        try:
            logger.info(f"Setting main storage usage for workspace: {ws_info.name}")
            
            # 스토리지 정보 조회
            main_storage_info = storage_db.get_storage(storage_id=ws_info.main_storage_id)
            if not main_storage_info:
                logger.error(f"Storage not found for ID: {ws_info.main_storage_id}")
                return
            
            storage_info = StorageInfo.from_dict(main_storage_info)
            
            # 워크스페이스 메인 경로 사용량
            ws_main_path = StoragePaths.MAIN_STORAGE_PATH.format(WORKSPACE_NAME=ws_info.name)
            actual_ws_main_path = storage_info._build_storage_path(ws_main_path)
            ws_main_usage = self.get_disk_usage(storage_info, actual_ws_main_path)
            
            self.set_metric_safely(
                WORKSPACE_USAGE,
                {'name': ws_info.name, 'type': 'main', 'storage': storage_info.name},
                ws_main_usage or 0
            )
            
            # 프로젝트 사용량
            project_list = project_db.get_project_list(workspace_id=ws_info.id)
            for project in project_list:
                project_path = StoragePaths.PROJECT_PATH.format(
                    WORKSPACE_NAME=ws_info.name,
                    PROJECT_NAME=project['name']
                )
                actual_project_path = storage_info._build_storage_path(project_path)
                project_usage = self.get_disk_usage(storage_info, actual_project_path)
                
                self.set_metric_safely(
                    PROJECT_USAGE,
                    {
                        'name': project['name'],
                        'type': 'main',
                        'workspace': ws_info.name,
                        'storage': storage_info.name
                    },
                    project_usage or 0
                )
            
            # 전처리 사용량
            prepro_list = prepro_db.get_preprocessing_list_sync(workspace_id=ws_info.id)
            for prepro in prepro_list:
                prepro_path = StoragePaths.PREPRO_PATH.format(
                    WORKSPACE_NAME=ws_info.name,
                    PREPRO_NAME=prepro['name']
                )
                actual_prepro_path = storage_info._build_storage_path(prepro_path)
                prepro_usage = self.get_disk_usage(storage_info, actual_prepro_path)
                
                self.set_metric_safely(
                    PREPRO_USAGE,
                    {
                        'name': prepro['name'],
                        'type': 'main',
                        'workspace': ws_info.name,
                        'storage': storage_info.name
                    },
                    prepro_usage or 0
                )
            
            # 모델 사용량 (LLM 사용 시)
            if LLM_USED:
                self._set_model_usage(ws_info, storage_info)
                
        except Exception as e:
            logger.error(f"Error setting main storage usage for workspace {ws_info.name}: {e}")
            logger.debug(traceback.format_exc())
            raise
    
    def _set_model_usage(self, ws_info: WorkspaceInfo, storage_info: StorageInfo) -> None:
        """모델 사용량을 설정합니다."""
        try:
            model_list = db_model.get_models_sync(workspace_id=ws_info.id)
            if not model_list:
                return
                
            for model in model_list:
                model_path = StoragePaths.MODEL_PATH.format(
                    WORKSPACE_NAME=ws_info.name,
                    MODEL_NAME=model['name']
                )
                actual_model_path = storage_info._build_storage_path(model_path)
                
                model_usage = None
                if os.path.exists(actual_model_path):
                    model_usage = self.get_disk_usage(storage_info, actual_model_path)
                
                self.set_metric_safely(
                    MODEL_USAGE,
                    {
                        'name': model['name'],
                        'type': 'main',
                        'workspace': ws_info.name,
                        'storage': storage_info.name
                    },
                    model_usage or 0
                )
                
        except Exception as e:
            logger.error(f"Error setting model usage for workspace {ws_info.name}: {e}")
            logger.debug(traceback.format_exc())
            raise
    
    def collect_metrics(self) -> None:
        """모든 메트릭을 수집합니다."""
        start_time = time.time()
        success = False
        
        try:
            logger.info("Starting metric collection cycle")
            
            ws_list = ws_db.get_workspace_list()
            if not ws_list:
                logger.warning("No workspaces found")
                return
            
            logger.info(f"Found {len(ws_list)} workspaces")
            
            for ws in ws_list:
                try:
                    ws_info = WorkspaceInfo.from_dict(ws)
                    
                    # 데이터 스토리지 처리
                    if ws_info.data_storage_id == int(self.storage_id):
                        self.set_data_storage_usage(ws_info)
                    
                    # 메인 스토리지 처리
                    if ws_info.main_storage_id == int(self.storage_id):
                        self.set_main_storage_usage(ws_info)
                        
                except Exception as e:
                    logger.error(f"Error processing workspace {ws.get('name', 'unknown')}: {e}")
                    logger.debug(traceback.format_exc())
                    continue
            
            success = True
            logger.info("Metric collection cycle completed successfully")
            
        except Exception as e:
            logger.error(f"Error in metric collection: {e}")
            logger.debug(traceback.format_exc())
        finally:
            # 메트릭 업데이트
            duration = time.time() - start_time
            COLLECTION_DURATION.set(duration)
            
            # 헬스 상태 업데이트
            self.health.update_status(success)
            HEALTH_STATUS.labels(status=self.health.status.value).set(1)
            
            # 다른 상태는 0으로 설정
            for status in ServiceStatus:
                if status != self.health.status:
                    HEALTH_STATUS.labels(status=status.value).set(0)
    
    def run(self):
        """메인 실행 루프"""
        try:
            self.start()
            
            while not self.shutdown_event.is_set():
                try:
                    self.collect_metrics()
                    
                    # 헬스 상태에 따른 대기 시간 조정
                    if self.health.status == ServiceStatus.UNHEALTHY:
                        wait_time = 30  # 비정상 상태일 때 더 긴 대기
                    elif self.health.status == ServiceStatus.DEGRADED:
                        wait_time = 15  # 성능 저하 상태일 때 중간 대기
                    else:
                        wait_time = 5   # 정상 상태일 때 기본 대기
                    
                    self.shutdown_event.wait(wait_time)
                    
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    logger.debug(traceback.format_exc())
                    self.shutdown_event.wait(5)
                    
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            logger.debug(traceback.format_exc())
            raise
        finally:
            self.stop()

def main():
    """메인 함수"""
    collector = None
    try:
        collector = StorageMetricCollector()
        collector.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.debug(traceback.format_exc())
        sys.exit(1)
    finally:
        if collector:
            collector.stop()

if __name__ == '__main__':
    main()


