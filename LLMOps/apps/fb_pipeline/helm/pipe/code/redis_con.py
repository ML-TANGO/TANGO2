
import redis
import settings

redis_client = None

def get_redis_client(retry_attempts=5, role : str = 'master'):
    global redis_client
    # print(type(redis_client))
    if redis_client is not None:
        return redis_client
    # redis_client = None
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