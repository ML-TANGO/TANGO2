import asyncio
import logging
from typing import List, Dict
from utils import topic_key, settings, redis_key, mongodb_key
from utils.redis import get_redis_client_async
from utils.mongodb import mongodb_conn
from datetime import datetime
import time
import random
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
import threading

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from confluent_kafka.admin import AdminClient, NewPartitions, NewTopic
import json

logger = logging.getLogger("alert-server")
logging.basicConfig(level=logging.INFO)

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.max_retries = 5
        self.base_delay = 1  # 초기 지연 시간 (초)
        self.max_delay = 30  # 최대 지연 시간 (초)
        self.kafka_healthy = False

    async def connect_with_retry(self, connect_func, *args, **kwargs):
        retry_count = 0
        while True:
            try:
                result = await connect_func(*args, **kwargs)
                self.kafka_healthy = True
                return result
            except Exception as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"최대 재시도 횟수 초과: {str(e)}")
                    self.kafka_healthy = False
                    raise

                # 지수 백오프 계산 (jitter 추가)
                delay = min(self.base_delay * (2 ** (retry_count - 1)), self.max_delay)
                jitter = random.uniform(0, 0.1 * delay)
                total_delay = delay + jitter

                logger.warning(f"연결 실패, {total_delay:.2f}초 후 재시도 ({retry_count}/{self.max_retries}): {str(e)}")
                await asyncio.sleep(total_delay)

    async def get_redis_client(self):
        return await self.connect_with_retry(get_redis_client_async)

    async def create_kafka_consumer(self, topics, group_id):
        async def _create_consumer():
            consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=settings.JF_KAFKA_DNS,
                value_deserializer=lambda m: m.decode('utf-8'),
                group_id=group_id
            )
            await consumer.start()
            return consumer
        return await self.connect_with_retry(_create_consumer)

connection_manager = ConnectionManager()

@app.get("/health")
async def health_check():
    """Health check endpoint for probes"""
    return JSONResponse(
        content={"status": "healthy", "kafka_healthy": connection_manager.kafka_healthy},
        status_code=200
    )

@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint"""
    return JSONResponse(
        content={"status": "ready", "kafka_healthy": connection_manager.kafka_healthy},
        status_code=200
    )

# 토픽이 있는지 검사
async def check_topic():
    try:
        conf = {
            'bootstrap.servers': settings.JF_KAFKA_DNS
        }
        a = AdminClient(conf)
        topic_metadata = a.list_topics(timeout=10)
        not_found_topics = []
        for topic in topic_key.ALERT_TOPICS:
            if topic not in topic_metadata.topics:
                logger.error(f"❌ Topic '{topic}' not found.")
                not_found_topics.append(topic)
            else:
                logger.info(f"✅ Topic '{topic}' found.")
        connection_manager.kafka_healthy = True
        return not_found_topics
    except Exception as e:
        logger.error(f"Kafka 연결 실패: {str(e)}")
        connection_manager.kafka_healthy = False
        return []

# 없는 토픽 생성
async def create_topic(topics: List[str] = topic_key.ALERT_TOPICS):
    if not topics:
        logger.info("✅ All topics are already created.")
        return
    try:
        conf = {
            'bootstrap.servers': settings.JF_KAFKA_DNS
        }
        a = AdminClient(conf)
        new_topics = [topic for topic in topics if topic not in a.list_topics().topics]
        if new_topics:
            fs = a.create_topics([NewTopic(topic=topic, num_partitions=3, replication_factor=1) for topic in new_topics])
            for topic, f in fs.items():
                try:
                    f.result()
                    logger.info(f"✅ Topic '{topic}' created successfully.")
                except Exception as e:
                    logger.error(f"❌ Failed to create topic '{topic}': {e}")
        else:
            logger.info("✅ All topics are already created.")
        connection_manager.kafka_healthy = True
    except Exception as e:
        logger.error(f"토픽 생성 실패: {str(e)}")
        connection_manager.kafka_healthy = False

# 토픽의 파티션 개수 늘리기
def increase_partition():
    conf = {
        'bootstrap.servers': settings.JF_KAFKA_DNS
    }
    a = AdminClient(conf)
    new_partition_count = 3
    new_partitions = [NewPartitions(topic=topic, new_total_count=new_partition_count) for topic in topic_key.ALERT_TOPICS]
    fs = a.create_partitions(new_partitions)
    for topic, f in fs.items():
        try:
            f.result()
            logger.info(f"✅ Partitions for topic '{topic}' increased successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to increase partitions for topic '{topic}': {e}")


async def send_alert(user_id: str, alert: dict, redis_client = None):
    try:
        if not redis_client:
            redis_client = await connection_manager.get_redis_client()
        key = redis_key.USER_ALERT_CHANNEL.format(user_id)
        await redis_client.xadd(key, alert)
        logger.info(f"🔔 Alert sent to {key}")
        logger.info(f"🔔 Alert data: {alert}")
    except Exception as e:
        logger.error(f"Alert 전송 실패: {str(e)}")
        raise

async def save_alert_to_mongodb(alert: dict):
    with mongodb_conn(database_name=mongodb_key.DATABASE, collection_name=mongodb_key.NOTIFICATION_COLLECTION) as collection:
        alert["create_datetime"] = datetime.now()
        collection.insert_one(alert)
    logging.info(f"✅ Alert saved to MongoDB")
    return True

async def alert_consume():
    while True:
        try:
            consumer = await connection_manager.create_kafka_consumer(
                topic_key.ALERT_TOPICS,
                "mlops-alert-group"
            )
            logger.info("🔔 Alert consumer started")
            
            while True:
                try:
                    async for msg in consumer:
                        try:
                            data = json.loads(msg.value)
                            user_id = data.get("user_id")
                            if user_id:
                                await send_alert(user_id, data)
                                await save_alert_to_mongodb(data)
                        except Exception as e:
                            logger.error(f"메시지 처리 중 오류: {str(e)}")
                except Exception as e:
                    logger.error(f"Consumer 루프 중 오류: {str(e)}")
                    break
        except Exception as e:
            logger.error(f"Consumer 시작 중 오류: {str(e)}")
            await asyncio.sleep(5)  # 심각한 오류 시 잠시 대기
        finally:
            try:
                await consumer.stop()
            except:
                pass

async def user_alert_log_delete(user_id: int):
    try:
        with mongodb_conn(database_name=mongodb_key.DATABASE, collection_name=mongodb_key.NOTIFICATION_COLLECTION) as collection:
            collection.delete_many({"user_id": user_id})
            logging.info(f"✅ Alert logs deleted for user {user_id}")
            return True
    except Exception as e:
        logging.error(f"❌ Error deleting alert logs for user {user_id}: {e}")
        return False
    except:
        logging.error(f"❌ Error deleting alert logs for user {user_id}: Unknown error")
        return False


async def user_delete_consume():
    while True:
        try:
            consumer = await connection_manager.create_kafka_consumer(
                [topic_key.USER_DELETE_TOPIC],
                "my-group"
            )
            logger.info("🔔 User delete consumer started")
            
            while True:
                try:
                    async for msg in consumer:
                        try:
                            data = json.loads(msg.value)
                            user_id = data.get("user_id")
                            if user_id:
                                await user_alert_log_delete(user_id)
                                redis_client = await connection_manager.get_redis_client()
                                key = redis_key.USER_ALERT_CHANNEL.format(user_id)
                                await redis_client.delete(key)
                                logger.info(f"✅ Redis stream deleted for user {user_id}")
                        except Exception as e:
                            logger.error(f"메시지 처리 중 오류: {str(e)}")
                except Exception as e:
                    logger.error(f"Consumer 루프 중 오류: {str(e)}")
                    break
        except Exception as e:
            logger.error(f"Consumer 시작 중 오류: {str(e)}")
            await asyncio.sleep(5)  # 심각한 오류 시 잠시 대기
        finally:
            try:
                await consumer.stop()
            except:
                pass

async def main():
    # 초기화 시 Kafka 연결 체크 (실패해도 계속 진행)
    logger.info("🚀 Starting alert management service...")
    not_found_topics = await check_topic()
    if not_found_topics:
        await create_topic(not_found_topics)
    
    await asyncio.gather(
        alert_consume(),
        user_delete_consume()
    )

def run_fastapi():
    """FastAPI 서버를 별도 스레드에서 실행"""
    import logging
    
    # Health check 경로에 대한 로그를 필터링하는 커스텀 필터
    class HealthCheckFilter:
        def filter(self, record):
            return not ('/health' in record.getMessage() or '/ready' in record.getMessage())
    
    # uvicorn access logger에 필터 추가
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.addFilter(HealthCheckFilter())
    
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    # FastAPI 서버를 백그라운드에서 시작
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    
    # 메인 애플리케이션 실행
    asyncio.run(main())