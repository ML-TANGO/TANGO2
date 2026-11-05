from confluent_kafka import Producer
from aiokafka import AIOKafkaProducer
import asyncio

class KafkaProducer:
    def __init__(self, config):
        self.producer = Producer(config)

    def delivery_report(self, err, msg):
        if err is not None:
            print(f"Delivery failed for record {msg.key()}: {err}")
        else:
            print(f"Record successfully produced to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")

    def produce(self, topic, value, key = None):
        try:
            self.producer.produce(topic, key=key, value=value, callback=self.delivery_report)
            self.producer.flush()
        except Exception as e:
            print(f"Failed to produce message: {e}")


class AsyncKafkaProducer:
    def __init__(self, config):
        self.producer = AIOKafkaProducer(**config)

    async def produce_async(self, topic, key, value):
        try:
            await self.producer.start()
            await self.producer.send_and_wait(topic, key=key.encode(), value=value.encode())
        except Exception as e:
            print(f"Failed to produce message: {e}")
        finally:
            await self.producer.stop()
