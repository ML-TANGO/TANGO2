from confluent_kafka.admin import AdminClient, NewTopic, NewPartitions
from confluent_kafka import KafkaException

class KafkaAdminUtils:
    def __init__(self, conf):
        self.admin_client = AdminClient(conf)

    def list_topics(self):
        """List all topics in the Kafka cluster."""
        try:
            metadata = self.admin_client.list_topics(timeout=10)
            return metadata.topics.keys()
        except KafkaException as e:
            raise RuntimeError(f"Failed to list topics: {e}")

    def create_topic(self, topic_name, num_partitions, replication_factor=1):
        """Create a new topic with the specified number of partitions and replication factor."""
        topic = NewTopic(topic=topic_name, num_partitions=num_partitions, replication_factor=replication_factor)
        try:
            fs = self.admin_client.create_topics([topic])
            for topic, f in fs.items():
                try:
                    f.result()  # Wait for operation to finish
                    print(f"✅ Topic '{topic}' created successfully.")
                except Exception as e:
                    print(f"❌ Failed to create topic '{topic}': {e}")
        except KafkaException as e:
            raise RuntimeError(f"Failed to create topic: {e}")

    def delete_topic(self, topic_name):
        """Delete an existing topic."""
        try:
            fs = self.admin_client.delete_topics([topic_name], operation_timeout=30)
            for topic, f in fs.items():
                try:
                    f.result()  # Wait for operation to finish
                    print(f"✅ Topic '{topic}' deleted successfully.")
                except Exception as e:
                    print(f"❌ Failed to delete topic '{topic}': {e}")
        except KafkaException as e:
            raise RuntimeError(f"Failed to delete topic: {e}")

    def increase_partitions(self, topic_name, num_partitions):
        """Increase the number of partitions for an existing topic."""
        try:
            fs = self.admin_client.create_partitions({topic_name: NewPartitions(num_partitions)})
            for topic, f in fs.items():
                try:
                    f.result()  # Wait for operation to finish
                    print(f"✅ Partitions for topic '{topic}' increased successfully.")
                except Exception as e:
                    print(f"❌ Failed to increase partitions for topic '{topic}': {e}")
        except KafkaException as e:
            raise RuntimeError(f"Failed to increase partitions: {e}")

# Example usage:
# conf = {'bootstrap.servers': 'localhost:9092'}
# kafka_admin = KafkaAdminUtils(conf)
# print(kafka_admin.list_topics())
# kafka_admin.create_topic('new_topic', num_partitions=3)
# kafka_admin.delete_topic('old_topic')
# kafka_admin.increase_partitions('existing_topic', num_partitions=5)