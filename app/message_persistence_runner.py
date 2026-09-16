import logging

from app.consumers.message_persistence_consumer import (
    MessagePersistenceConsumer,
)
from app.core.config import settings
from app.db.cassandra import cassandra_client
from app.messaging.kafka import (
    create_kafka_message_persistence_consumer,
    create_kafka_producer,
)
from app.messaging.kafka_message_persisted_publisher import (
    KafkaMessagePersistedPublisher,
)
from app.repositories.message_repository import MessageRepository


def main() -> None:
    cassandra_client.connect()

    try:
        kafka_producer = create_kafka_producer()

        try:
            kafka_consumer = (
                create_kafka_message_persistence_consumer()
            )

            message_repository = MessageRepository(
                session=cassandra_client.get_session(),
            )

            message_persisted_publisher = (
                KafkaMessagePersistedPublisher(
                    producer=kafka_producer,
                    topic=settings.kafka_message_persisted_topic,
                    publish_wait_timeout_seconds=(
                        settings.kafka_publish_wait_timeout_seconds
                    ),
                )
            )

            consumer = MessagePersistenceConsumer(
                consumer=kafka_consumer,
                topic=settings.kafka_message_accepted_topic,
                message_repository=message_repository,
                message_persisted_publisher=(
                    message_persisted_publisher
                ),
                poll_timeout_seconds=(
                    settings.kafka_consumer_poll_timeout_seconds
                ),
                retry_initial_backoff_seconds=(
                    settings.kafka_consumer_retry_initial_backoff_seconds
                ),
                retry_max_backoff_seconds=(
                    settings.kafka_consumer_retry_max_backoff_seconds
                ),
                retry_max_attempts=(
                    settings.kafka_consumer_retry_max_attempts
                ),
            )

            consumer.run()
        finally:
            kafka_producer.flush(10)
    finally:
        cassandra_client.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    main()