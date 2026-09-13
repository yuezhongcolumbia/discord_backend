from confluent_kafka import Producer, Consumer

from app.core.config import settings


def create_kafka_producer() -> Producer:
    return Producer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "enable.idempotence": True,
            "acks": "all",
            "delivery.timeout.ms": settings.kafka_delivery_timeout_ms,
        }
    )

def create_kafka_message_persistence_consumer() -> Consumer:
    return Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_message_persistence_group_id,
            "enable.auto.commit": False,
            "auto.offset.reset": settings.kafka_consumer_auto_offset_reset,
            "allow.auto.create.topics": False,
        }
    )