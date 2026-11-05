import asyncio
import logging
import random
import time
from utils.redis import get_redis_client_async, get_redis_client

logger = logging.getLogger("connection-manager")

class ConnectionManager:
    def __init__(self):
        self.max_retries = 5
        self.base_delay = 1
        self.max_delay = 30
        self.redis_healthy = False
        self.last_redis_client = None
        self.last_async_redis_client = None

    async def connect_with_retry(self, connect_func, *args, **kwargs):
        retry_count = 0
        while True:
            try:
                result = await connect_func(*args, **kwargs)
                self.redis_healthy = True
                return result
            except Exception as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"최대 재시도 횟수 초과: {str(e)}")
                    self.redis_healthy = False
                    raise

                delay = min(self.base_delay * (2 ** (retry_count - 1)), self.max_delay)
                jitter = random.uniform(0, 0.1 * delay)
                total_delay = delay + jitter

                logger.warning(f"Redis 연결 실패, {total_delay:.2f}초 후 재시도 ({retry_count}/{self.max_retries}): {str(e)}")
                await asyncio.sleep(total_delay)

    def connect_with_retry_sync(self, connect_func, *args, **kwargs):
        retry_count = 0
        while True:
            try:
                result = connect_func(*args, **kwargs)
                self.redis_healthy = True
                return result
            except Exception as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"최대 재시도 횟수 초과: {str(e)}")
                    self.redis_healthy = False
                    raise

                delay = min(self.base_delay * (2 ** (retry_count - 1)), self.max_delay)
                jitter = random.uniform(0, 0.1 * delay)
                total_delay = delay + jitter

                logger.warning(f"Redis 연결 실패, {total_delay:.2f}초 후 재시도 ({retry_count}/{self.max_retries}): {str(e)}")
                time.sleep(total_delay)

    async def get_redis_client(self):
        """비동기 Redis 클라이언트 반환"""
        try:
            client = await self.connect_with_retry(get_redis_client_async)
            self.last_async_redis_client = client
            return client
        except Exception as e:
            logger.error(f"Redis 비동기 클라이언트 연결 실패: {e}")
            # 기존 클라이언트가 있다면 재사용 시도
            if self.last_async_redis_client:
                logger.info("기존 비동기 Redis 클라이언트 재사용 시도")
                return self.last_async_redis_client
            raise

    def get_redis_client_sync(self):
        """동기 Redis 클라이언트 반환"""
        try:
            client = self.connect_with_retry_sync(get_redis_client)
            self.last_redis_client = client
            return client
        except Exception as e:
            logger.error(f"Redis 동기 클라이언트 연결 실패: {e}")
            # 기존 클라이언트가 있다면 재사용 시도
            if self.last_redis_client:
                logger.info("기존 동기 Redis 클라이언트 재사용 시도")
                return self.last_redis_client
            raise

# 전역 인스턴스
connection_manager = ConnectionManager() 