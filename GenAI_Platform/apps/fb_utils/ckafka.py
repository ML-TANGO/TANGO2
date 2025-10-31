from confluent_kafka import Producer
from confluent_kafka import Consumer, KafkaError, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic

class KafkaAdmin:
    def __init__(self, bootstrap_servers):
        self.bootstrap_servers = bootstrap_servers
        self.conf = {
            'bootstrap.servers' : self.bootstrap_servers,
        }
        self.admin_client = AdminClient(self.conf)

    def get_topics(self):
        return list(self.admin_client.list_topics(timeout=10).topics.keys())

    def delete_topics(self, topics: list):
        fs = self.admin_client.delete_topics(topics, operation_timeout=30)

        for topic, f in fs.items():
            try:
                f.result()  # The result itself is None
                print(f"Topic {topic} deleted")
            except Exception as e:
                print(f"Failed to delete topic {topic}: {e}")

    def create_topic(self, topic, partition: int, replication_factor:int=1):
        self.admin_client.create_topics([
            NewTopic(topic, num_partitions=partition, replication_factor=replication_factor)
        ])

class KafkaProducer:
    def __init__(self, bootstrap_servers):
        self.bootstrap_servers = bootstrap_servers
        self.conf = {
            'bootstrap.servers' : self.bootstrap_servers,
        }
        self.producer = Producer(self.conf)


    def produce(self, topic, key=None,value=None, partition=None):
        def acked(err, msg):
            if err is not None:
                print("Failed to deliver message: %s: %s" % (str(msg), str(err)))
            else:
                print("Message produced: %s" % (str(msg)))

        if partition is not None:
            self.producer.produce(topic, key=key, value=value, partition=partition, callback=acked)
        else:
            # partition이 None 일때 파라미터로 들어가면 에러발생
            self.producer.produce(topic, key=key, value=value, callback=acked)
        self.producer.poll(1)

class KafkaConsumer:
    def __init__(self, bootstrap_servers, group_id):
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.conf = {
            'bootstrap.servers' : self.bootstrap_servers,
            'group.id' : self.group_id,
            'auto.offset.reset': 'earliest'  # 처음부터 메시지 소비
        }
        self.consumer = Consumer(self.conf)
        self.running = True

    def subscribe(self, topics: list):
        try:
            self.consumer.subscribe(topics)

            while self.running:
                msg = self.consumer.poll(timeout=1)
                if msg is None: continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        # End of partition event
                        sys.stderr.write('%% %s [%d] reached end at offset %d\n' %
                                         (msg.topic(), msg.partition(), msg.offset()))
                    elif msg.error():
                        raise KafkaException(msg.error())
                else:
                    print(f"key: {msg.key()}, val: {msg.value()}, partition: {msg.partition()}")
        finally:
            self.consumer.close()

import os
bs=os.environ['JF_KAFKA_DNS']
# 통합 서버 세팅 (namespace: kafka, svc name: kafka)
bs = "kafka.kafka.svc.cluster.local:9092"
kafka_producer = KafkaProducer(bootstrap_servers=bs)
kafka_admin = KafkaAdmin(bootstrap_servers=bs)
