from utils import settings, redis_key

import redis, uuid, asyncio, random, hashlib, time, threading, logging

import redis.asyncio as aioredis

#TODO
#database 선택은 추후 정책 정해지면 추가

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

sync_redis_client = None  # 동기 클라이언트
async_redis_client = None  # 비동기 클라이언트
redis_health_status = {"connected": False, "last_check": 0}
redis_health_check_interval = 30  # 30초마다 헬스체크

def is_redis_connected(client=None):
    """Redis 연결 상태를 확인하는 함수"""
    if client is None:
        client = sync_redis_client
    
    if client is None:
        return False
    
    try:
        client.ping()
        return True
    except Exception as e:
        logging.error(f"Redis 연결 확인 실패: {e}")
        return False

def reset_redis_client():
    """Redis 클라이언트를 초기화하는 함수"""
    global sync_redis_client
    if sync_redis_client:
        try:
            sync_redis_client.close()
        except:
            pass
    sync_redis_client = None

def get_redis_client(retry_attempts=5, role : str = 'master'):
    global sync_redis_client, redis_health_status
    
    # 기존 클라이언트가 있고 연결이 정상이면 반환
    if sync_redis_client is not None and is_redis_connected(sync_redis_client):
        redis_health_status["connected"] = True
        redis_health_status["last_check"] = time.time()
        return sync_redis_client
    
    # 연결이 끊어졌거나 없으면 새로 연결
    if sync_redis_client is not None:
        logging.warning("Redis 연결이 끊어져 재연결을 시도합니다.")
        reset_redis_client()
    
    attempt = 0
    while attempt < retry_attempts:
        try:
            if settings.JF_REDIS_CLUSTER_ENABLED:
                sync_redis_client = redis.RedisCluster(
                    host=settings.JF_REDIS_CLUSTER_DNS,
                    port=settings.JF_REDIS_PROT,
                    password=settings.JF_REDIS_PASSWORD,
                    socket_connect_timeout=0.1,
                    max_connections=500,
                    decode_responses=True
                )
            else:
                host = settings.JF_REDIS_MASTER_DNS if role == 'master' else settings.JF_REDIS_SLAVES_DNS
                sync_redis_client = redis.StrictRedis(
                    host=host, 
                    port=settings.JF_REDIS_PROT, 
                    db=0, 
                    password=settings.JF_REDIS_PASSWORD, 
                    socket_connect_timeout=0.1,
                    decode_responses=True
                )
            
            # 연결 테스트
            sync_redis_client.ping()
            redis_health_status["connected"] = True
            redis_health_status["last_check"] = time.time()
            logging.info(f"Redis 연결 성공 (시도 {attempt + 1}/{retry_attempts})")
            return sync_redis_client
            
        except Exception as e:
            attempt += 1
            redis_health_status["connected"] = False
            logging.error(f"Redis 연결 시도 {attempt} 실패: {str(e)}")
            if attempt < retry_attempts:
                time.sleep(min(attempt * 2, 10))  # 지수 백오프, 최대 10초
    
    redis_health_status["connected"] = False
    raise Exception(f"Redis 연결 실패: {retry_attempts}번 시도 후 포기")

async def get_redis_client_async(retry_attempts=5, role: str = 'master'):
    global async_redis_client
    if async_redis_client is not None:
        return async_redis_client
    
    attempt = 0

    while attempt < retry_attempts:
        try:
            if settings.JF_REDIS_CLUSTER_ENABLED:
                # Redis 클라이언트 생성
                async_redis_client = aioredis.RedisCluster(
                    host=settings.JF_REDIS_CLUSTER_DNS,
                    port=settings.JF_REDIS_PROT,
                    password=settings.JF_REDIS_PASSWORD,
                    decode_responses=True,
                    socket_connect_timeout=0.1,
                    max_connections=500  # 최대 10개의 연결을 유지하는 연결 풀
                )
                await async_redis_client.ping()
                return async_redis_client
            else:
                # 비클러스터 환경에서의 Redis 클라이언트 생성, 연결 풀 설정
                host = settings.JF_REDIS_MASTER_DNS if role == 'master' else settings.JF_REDIS_SLAVES_DNS
                async_redis_client = aioredis.Redis(
                    host=host, 
                    port=settings.JF_REDIS_PROT, 
                    db=0, 
                    password=settings.JF_REDIS_PASSWORD, 
                    decode_responses=True,
                    # max_connections=60  # 최대 10개의 연결을 유지하는 연결 풀
                )
                return async_redis_client
        except Exception as e:
            attempt += 1
            print(f"Redis 연결 시도 {attempt} 실패: {str(e)}.")

    print(f"{retry_attempts}번 재시도 후 Redis 연결에 실패했습니다.")
    return None  # 모든 시도가 실패한 경우 None 반환

def redis_health_monitor():
    """Redis 연결 상태를 주기적으로 모니터링하는 함수 (Kubernetes probe 기반)"""
    global redis_health_status, redis_health_check_interval
    
    while True:
        try:
            current_time = time.time()
            
            # 주기적으로 헬스체크 수행
            if current_time - redis_health_status.get("last_check", 0) > redis_health_check_interval:
                logging.info("Redis 헬스체크 시작...")
                
                if is_redis_connected():
                    if not redis_health_status["connected"]:
                        logging.info("Redis 연결 복구됨")
                    redis_health_status["connected"] = True
                else:
                    if redis_health_status["connected"]:
                        logging.warning("Redis 연결 끊어짐 감지 - Kubernetes probe가 처리합니다")
                    redis_health_status["connected"] = False
                    
                    # 간단한 재연결 시도 (1회만, Kubernetes가 실패시 pod 재시작 처리)
                    try:
                        logging.info("Redis 재연결 시도 (1회)...")
                        get_redis_client(retry_attempts=1)
                        logging.info("Redis 재연결 성공")
                    except Exception as e:
                        logging.warning(f"Redis 재연결 실패: {e} - Kubernetes probe에서 pod 재시작 처리")
                
                redis_health_status["last_check"] = current_time
            
            time.sleep(10)  # 10초마다 체크
            
        except Exception as e:
            logging.error(f"Redis 헬스 모니터 오류: {e}")
            time.sleep(30)  # 오류 발생시 30초 대기

def start_redis_health_monitor():
    """Redis 헬스 모니터 스레드를 시작하는 함수"""
    monitor_thread = threading.Thread(target=redis_health_monitor, daemon=True)
    monitor_thread.start()
    logging.info("Redis 헬스 모니터 시작됨")

def get_redis_health_status():
    """Redis 연결 상태를 반환하는 함수"""
    return redis_health_status.copy()

def get_safe_redis_client():
    """안전한 Redis 클라이언트 획득"""
    try:
        return get_redis_client()
    except Exception as e:
        logging.error(f"Redis 클라이언트 획득 실패: {e}")
        return None

class RedisQueue:
    def __init__(self, redis_client, key : str):
        """
        큐를 초기화합니다.

        :param name: 큐 이름
        :param namespace: 네임스페이스 (기본값: 'queue')
        :param redis_kwargs: Redis 연결 매개변수
        """
        self.__db = redis_client
        self.key = key

    def _ensure_connection(self):
        """Redis 연결 상태를 확인하고 필요시 재연결"""
        if not is_redis_connected(self.__db):
            logging.warning(f"RedisQueue[{self.key}]: Redis 연결 끊어짐, 재연결 시도")
            try:
                self.__db = get_redis_client()
                logging.info(f"RedisQueue[{self.key}]: Redis 재연결 성공")
            except Exception as e:
                logging.error(f"RedisQueue[{self.key}]: Redis 재연결 실패: {e}")
                raise

    def _execute_with_retry(self, operation, *args, **kwargs):
        """Redis 명령을 재시도와 함께 실행 (Kubernetes probe 기반)"""
        max_retries = 1  # Kubernetes probe에 의존하여 재시도 횟수 줄임
        for attempt in range(max_retries + 1):
            try:
                return operation(*args, **kwargs)
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
                if attempt < max_retries:
                    logging.warning(f"RedisQueue[{self.key}]: 연결 오류 (시도 {attempt + 1}/{max_retries + 1}), 재시도...")
                    self._ensure_connection()
                    continue
                else:
                    logging.warning(f"RedisQueue[{self.key}]: Redis 연결 실패 - Kubernetes probe에서 pod 재시작 처리: {e}")
                    raise
            except Exception as e:
                logging.error(f"RedisQueue[{self.key}]: Redis 작업 실패: {e}")
                raise

    def qsize(self):
        """큐의 크기를 반환합니다."""
        return self._execute_with_retry(self.__db.llen, self.key)

    def is_empty(self):
        """큐가 비어 있는지 확인합니다."""
        return self.qsize() == 0

    def rput(self, item):
        """큐에 항목을 추가합니다.(right push)"""
        return self._execute_with_retry(self.__db.rpush, self.key, item)
    
    def lput(self, item):
        """큐 앞쪽에 항목을 추가합니다.(left push)"""
        return self._execute_with_retry(self.__db.lpush, self.key, item)

    def pop(self, block=True, timeout=None):
        """
        큐에서 항목을 가져옵니다.

        :param block: True이면 항목이 있을 때까지 대기합니다.
        :param timeout: 블록 모드에서의 타임아웃 (초 단위)
        """
        if block:
            item = self._execute_with_retry(self.__db.blpop, self.key, timeout=timeout)
            if item:
                item = item[1]  # item은 ('key', 'value') 형태의 튜플이므로 value만 추출
        else:
            item = self._execute_with_retry(self.__db.lpop, self.key)  # lpop은 단일 값을 반환
        return item

    def pop_nowait(self):
        """큐에서 항목을 대기 없이 가져옵니다."""
        return self.pop(block=False)
    
    def fetch_queue_items(self, start_index : int = 0, end_index :int = -1):
        """큐에서 항목을 읽어 옵니다."""
        return self._execute_with_retry(self.__db.lrange, self.key, start_index, end_index)


async def delete_workspace_streams_cluster(workspace_id, client=sync_redis_client):
    pattern = f"workspace:{workspace_id}:*"

    # 모든 노드에서 검색 후 삭제
    for node in await client.get_nodes():
        cursor = "0"
        while True:
            cursor, keys = await client.scan(cursor=cursor, match=pattern, count=100, node=node)
            if keys:
                await client.delete(*keys)
                print(f"✅ {len(keys)}개의 스트림 삭제됨: {keys} (노드: {node})")
            if cursor == "0":
                break



def add_data_to_stream_sync(stream_key: str, data: dict, client=sync_redis_client):
    """
    Redis Stream에 data 추가가
    :param stream_prefix: 스트림 키 접두사 (예: 'mystream')
    :param data: 추가할 데이터 (dict)
    :param client: Redis 연결 객체
    """
    message_id = client.xadd(stream_key, data)
    print(f"✅ 데이터 추가됨: {stream_key} -> {message_id}")
    return message_id

async def add_data_to_stream(stream_key: str, data: dict, client):
    """
    Redis Stream에 data 추가가
    :param stream_key: 스트림 키 접두사 (예: 'mystream')
    :param data: 추가할 데이터 (dict)
    :param client: Redis 연결 객체
    """
    message_id = await client.xadd(stream_key, data)
    print(f"✅ 데이터 추가됨: {stream_key} -> {message_id}")
    return message_id

def create_consumer_group_sync(stream_key: str, group_name: str, client=sync_redis_client):
    """
    특정 스트림에 대한 컨슈머 그룹을 생성하는 함수
    :param stream_key: 스트림 키 (예: 'mystream-1')
    :param group_name: 컨슈머 그룹 이름 (예: 'group1')
    :param client: Redis 연결 객체
    """
    try:
        client.xgroup_create(stream_key, group_name, id="0", mkstream=True)
        print(f"✅ 컨슈머 그룹 생성됨: {group_name} @ {stream_key}")
    except redis.exceptions.ResponseError:
        print(f"⚠️ 이미 존재하는 컨슈머 그룹: {group_name} @ {stream_key}")

async def create_consumer_group(stream_key: str, group_name: str, client=sync_redis_client):
    """
    특정 스트림에 대한 컨슈머 그룹을 생성하는 함수
    :param stream_key: 스트림 키 (예: 'mystream-1')
    :param group_name: 컨슈머 그룹 이름 (예: 'group1')
    :param client: Redis 연결 객체
    """
    try:
        await client.xgroup_create(stream_key, group_name, id="0", mkstream=True)
        print(f"✅ 컨슈머 그룹 생성됨: {group_name} @ {stream_key}")
    except redis.exceptions.ResponseError:
        print(f"⚠️ 이미 존재하는 컨슈머 그룹: {group_name} @ {stream_key}")


def read_from_stream_sync(stream_key: str, count: int = 1, client=sync_redis_client):
    """
    여러 개의 스트림에서 메시지를 읽는 함수
    :param stream_keys: 스트림 키 리스트 (예: ['mystream-1', 'mystream-2'])
    :param count: 최대 읽을 메시지 수
    :param client: Redis 연결 객체
    """
    try:
        messages = client.xread({stream_key : "0"}, count=count)
        return messages
    except redis.exceptions.ResponseError:
        print(f"⚠️ 존재하지 않는 스트림 : {stream_key} ")

def read_from_streams_sync(stream_keys: list, count: int = 1, client=sync_redis_client):
    """
    여러 개의 스트림에서 메시지를 읽는 함수
    :param stream_keys: 스트림 키 리스트 (예: ['mystream-1', 'mystream-2'])
    :param count: 최대 읽을 메시지 수
    :param client: Redis 연결 객체
    """
    stream_dict = {key: "0" for key in stream_keys}  # 처음부터 읽기
    messages = client.xread(stream_dict, count=count)
    return messages


def read_from_consumer_group_sync(stream_key: str, group_name: str, consumer_name: str, count: int = 1, client=sync_redis_client):
    """
    특정 컨슈머 그룹에서 메시지를 읽는 함수
    :param stream_key: 스트림 키
    :param group_name: 컨슈머 그룹 이름
    :param consumer_name: 개별 컨슈머 이름
    :param count: 최대 읽을 메시지 수
    :param client: Redis 연결 객체
    """
    try:
        messages = client.xreadgroup(group_name, consumer_name, {stream_key: ">"}, count=count)
        return messages
    except redis.exceptions.ResponseError as e:
        print(f"⚠️ 컨슈머 그룹 오류: {e}")
        return []


def acknowledge_message_sync(stream_key: str, group_name: str, message_id: str, client=sync_redis_client):
    """
    컨슈머 그룹에서 특정 메시지를 처리 완료(Ack)로 표시하는 함수
    :param stream_key: 스트림 키
    :param group_name: 컨슈머 그룹 이름
    :param message_id: 처리 완료할 메시지 ID
    :param client: Redis 연결 객체
    """
    client.xack(stream_key, group_name, message_id)
    print(f"✅ 메시지 {message_id} 처리 완료 (Ack)")

def delete_message_sync(stream_key: str, message_id: str, client=sync_redis_client):
    """
    컨슈머 그룹에서 특정 메시지를 처리 완료(Ack)로 표시하는 함수
    :param stream_key: 스트림 키
    :param group_name: 컨슈머 그룹 이름
    :param message_id: 처리 완료할 메시지 ID
    :param client: Redis 연결 객체
    """
    client.xdel(stream_key, message_id)
    print(f"✅ 메시지 {message_id} 삭제 완료 (Del)")


def list_pending_messages_sync(stream_key: str, group_name: str, client=sync_redis_client):
    """
    컨슈머 그룹에서 처리되지 않은 메시지 확인
    :param stream_key: 스트림 키
    :param group_name: 컨슈머 그룹 이름
    :param client: Redis 연결 객체
    """
    pending_info = client.xpending(stream_key, group_name)
    print(f"⚠️ 미처리 메시지: {pending_info}")
    return pending_info


async def delete_consumer_group(stream_key: str, group_name: str, client=sync_redis_client):
    """
    특정 스트림의 컨슈머 그룹을 삭제하는 함수
    :param stream_key: 스트림 키
    :param group_name: 컨슈머 그룹 이름
    :param client: Redis 연결 객체
    """
    try:
        result = await client.xgroup_destroy(stream_key, group_name)
        if result:
            print(f"✅ 컨슈머 그룹 삭제됨: {group_name} @ {stream_key}")
        else:
            print(f"⚠️ 컨슈머 그룹이 존재하지 않음: {group_name} @ {stream_key}")
    except redis.exceptions.ResponseError as e:
        print(f"⚠️ 오류 발생: {e}")


async def delete_consumer(stream_key: str, group_name: str, consumer_name: str, client=sync_redis_client):
    """
    특정 컨슈머 그룹에서 컨슈머를 삭제하는 함수
    :param stream_key: 스트림 키
    :param group_name: 컨슈머 그룹 이름
    :param consumer_name: 삭제할 컨슈머 이름
    :param client: Redis 연결 객체
    """
    result = await client.xgroup_delconsumer(stream_key, group_name, consumer_name)
    if result > 0:
        print(f"✅ 컨슈머 삭제됨: {consumer_name} @ {group_name} ({result} 메시지 영향받음)")
    else:
        print(f"⚠️ 컨슈머가 존재하지 않음: {consumer_name} @ {group_name}")