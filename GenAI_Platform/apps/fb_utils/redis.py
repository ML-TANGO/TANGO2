from utils import settings, redis_key

import redis, uuid, asyncio

import redis.asyncio as aioredis

#TODO
#database 선택은 추후 정책 정해지면 추가

def get_redis_client(retry_attempts=5, role : str = 'master'):
    redis_client = None
    attempt = 0
    while attempt < retry_attempts:
        try:
            if settings.JF_REDIS_CLUSTER_ENABLED:
                redis_client = redis.RedisCluster(
                    host=settings.JF_REDIS_CLUSTER_DNS,
                    port=settings.JF_REDIS_PROT,
                    password=settings.JF_REDIS_PASSWORD,
                    socket_connect_timeout=0.1,
                    max_connections=500,
                    decode_responses=True
                )
                return redis_client
            else:
                host = settings.JF_REDIS_MASTER_DNS if role == 'master' else settings.JF_REDIS_SLAVES_DNS
                return redis.StrictRedis(
                    host=host,
                    port=settings.JF_REDIS_PROT,
                    db=0,
                    password=settings.JF_REDIS_PASSWORD,
                    socket_connect_timeout=0.1,
                    # max_connections=60,
                    decode_responses=True
                    )
        except Exception as e:
            import sys
            attempt += 1
            print(f"Redis 연결 시도 {attempt} 실패: {str(e)}.", file=sys.stderr)
    raise Exception("Redis 연결 실패")

async def get_redis_client_async(retry_attempts=5, role: str = 'master'):
    redis_client = None
    attempt = 0

    while attempt < retry_attempts:
        try:
            if settings.JF_REDIS_CLUSTER_ENABLED:
                # Redis 클라이언트 생성
                redis_client = aioredis.RedisCluster(
                    host=settings.JF_REDIS_CLUSTER_DNS,
                    port=settings.JF_REDIS_PROT,
                    password=settings.JF_REDIS_PASSWORD,
                    decode_responses=True,
                    socket_connect_timeout=0.1,
                    max_connections=500  # 최대 10개의 연결을 유지하는 연결 풀
                )
                await redis_client.ping()
                return redis_client
            else:
                # 비클러스터 환경에서의 Redis 클라이언트 생성, 연결 풀 설정
                host = settings.JF_REDIS_MASTER_DNS if role == 'master' else settings.JF_REDIS_SLAVES_DNS
                redis_client = aioredis.Redis(
                    host=host,
                    port=settings.JF_REDIS_PROT,
                    db=0,
                    password=settings.JF_REDIS_PASSWORD,
                    decode_responses=True,
                    # max_connections=60  # 최대 10개의 연결을 유지하는 연결 풀
                )
                return redis_client
        except Exception as e:
            attempt += 1
            print(f"Redis 연결 시도 {attempt} 실패: {str(e)}.")

    print(f"{retry_attempts}번 재시도 후 Redis 연결에 실패했습니다.")
    return None  # 모든 시도가 실패한 경우 None 반환



# async def get_redis_client_async(role: str = 'master'):
#     if settings.JF_REDIS_CLUSTER_ENABLED:
#         # Redis 클러스터용 클라이언트 생성, 연결 풀 설정
#         redis_client = aioredis.RedisCluster(
#             host=settings.JF_REDIS_CLUSTER_DNS,
#             port=settings.JF_REDIS_PROT,
#             password=settings.JF_REDIS_PASSWORD,
#             decode_responses=True,
#             socket_connect_timeout=0.1,
#             max_connections=60  # 최대 10개의 연결을 유지하는 연결 풀
#         )
#         await redis_client.initialize()  # 클러스터 초기화
#         return redis_client
#     else:
#         # 비클러스터 환경에서의 Redis 클라이언트 생성, 연결 풀 설정
#         host = settings.JF_REDIS_MASTER_DNS if role == 'master' else settings.JF_REDIS_SLAVES_DNS
#         redis_client = aioredis.Redis(
#             host=host,
#             port=settings.JF_REDIS_PROT,
#             db=0,
#             password=settings.JF_REDIS_PASSWORD,
#             decode_responses=True,
#             max_connections=60  # 최대 10개의 연결을 유지하는 연결 풀
#         )
#         return redis_client

def redis_hgetall_sync(redis_con = None , key = None):
    if redis_con is None:
        redis_con = get_redis_client(role="slave")
    try:
        data = redis_con.hgetall(key)
    finally:
        redis_con.close()
    return data

def redis_set_sync(redis_con = None ,key = None, data = None):
    if redis_con is None:
        redis_con = get_redis_client(role="slave")
    try:
        data = redis_con.set(key, data)
    finally:
        redis_con.close()
    return data

def redis_hset_sync(redis_con = None, main_key = None, sub_key = None, data = None):
    if redis_con is None:
        redis_con = get_redis_client(role="slave")
    try:
        data = redis_con.hset(main_key, sub_key, data)
    finally:
        redis_con.close()
    return data

def redis_hget_sync(redis_con = None , main_key = None, sub_key = None):
    if redis_con is None:
        redis_con = get_redis_client(role="slave")
    try:
        data = redis_con.hget(main_key, sub_key)
    finally:
        redis_con.close()
    return data

def redis_hdel_sync(redis_con = None , main_key = None, sub_key = None):
    if redis_con is None:
        redis_con = get_redis_client(role="slave")
    try:
        data = redis_con.hdel(main_key, sub_key)
    finally:
        redis_con.close()
    return data

def redis_get_sync(redis_con = None , key = None):
    if redis_con is None:
        redis_con = get_redis_client(role="slave")
    try:
        data = redis_con.get(key)
    finally:
        redis_con.close()
    return data

def redis_delete_sync(redis_con = None , key = None):
    if redis_con is None:
        redis_con = get_redis_client(role="slave")
    try:
        data = redis_con.delete(key)
    finally:
        redis_con.close()
    return data




async def redis_hdel(redis_con = None , main_key = None, sub_key = None):
    if redis_con is None:
        redis_con = await get_redis_client_async(role="slave")
    try:
        data = await redis_con.hdel(main_key, sub_key)
    finally:
        await redis_con.close()
    return data

async def redis_hgetall(redis_con = None , key = None):
    if redis_con is None:
        redis_con = await get_redis_client_async(role="slave")
    try:
        data = await redis_con.hgetall(key)
    finally:
        await redis_con.close()
    return data

async def redis_hget(redis_con = None, main_key = None, sub_key = None):
    if redis_con is None:
        redis_con = await get_redis_client_async(role="slave")
    try:
        data = await redis_con.hget(main_key, sub_key)
    finally:
        await redis_con.close()
    return data

async def redis_get(redis_con = None , key = None):
    if redis_con is None:
        redis_con = await get_redis_client_async(role="slave")
    try:
        data = await redis_con.get(key)
    finally:
        await redis_con.close()
    return data

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

    def qsize(self):
        """큐의 크기를 반환합니다."""
        return self.__db.llen(self.key)

    def is_empty(self):
        """큐가 비어 있는지 확인합니다."""
        return self.qsize() == 0

    def rput(self, item):
        """큐에 항목을 추가합니다.(right push)"""
        self.__db.rpush(self.key, item)

    def lput(self, item):
        """큐 앞쪽에 항목을 추가합니다.(left push)"""
        self.__db.lpush(self.key, item)

    def pop(self, block=True, timeout=None):
        """
        큐에서 항목을 가져옵니다.

        :param block: True이면 항목이 있을 때까지 대기합니다.
        :param timeout: 블록 모드에서의 타임아웃 (초 단위)
        """
        if block:
            item = self.__db.blpop(self.key, timeout=timeout)
            if item:
                item = item[1]  # item은 ('key', 'value') 형태의 튜플이므로 value만 추출
        else:
            item = self.__db.lpop(self.key)  # lpop은 단일 값을 반환
        return item

    def pop_nowait(self):
        """큐에서 항목을 대기 없이 가져옵니다."""
        return self.pop(block=False)

    def fetch_queue_items(self, start_index : int = 0, end_index :int = -1):
        """큐에서 항목을 읽어 옵니다."""
        return self.__db.lrange(self.key, start_index, end_index)

class RedisLock:
    def __init__(self, redis_client, lock_key, lock_expire=10):
        self.redis_client = redis_client
        self.lock_key = lock_key
        self.lock_expire = lock_expire
        self.lock_value = str(uuid.uuid4())

    def acquire_lock(self):
        """
        Acquire a lock with a unique value and expiration time.
        """
        # Try to acquire the lock
        result = self.redis_client.set(self.lock_key, self.lock_value, nx=True, ex=self.lock_expire)
        return result is not None

    def release_lock(self):
        """
        Release the lock only if it is still held by the current owner using a Lua script.
        """
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = self.redis_client.eval(lua_script, 1, self.lock_key, self.lock_value)
        if result == 1:
            return True
        else:
            import sys
            # Additional debugging information
            current_value = self.redis_client.get(self.lock_key)
            if current_value is not None:
                current_value = current_value.decode('utf-8')
            print(f"Failed to release lock. Current value: {current_value}, Lock value: {self.lock_value}", file=sys.stderr)
            return False

    # def extend_lock(self, additional_time):
    #     """
    #     Extend the lock expiration time if it is still held by the current owner using a Lua script.
    #     """
    #     lua_script = """
    #     if redis.call("get", KEYS[1]) == ARGV[1] then
    #         return redis.call("expire", KEYS[1], ARGV[2])
    #     else
    #         return 0
    #     end
    #     """
    #     result = self.redis_client.eval(lua_script, 1, self.lock_key, self.lock_value, additional_time)
    #     return result == 1