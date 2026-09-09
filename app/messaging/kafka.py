from confluent_kafka import Producer

from app.core.config import settings


def create_kafka_producer() -> Producer:
    return Producer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "enable.idempotence": True,
            "acks": "all",
        }
    )