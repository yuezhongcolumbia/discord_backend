import logging

from app.consumers.message_persistence_consumer import (
    MessagePersistenceConsumer,
)
from app.core.config import settings
from app.db.cassandra import cassandra_client
from app.messaging.kafka import create_kafka_message_persistence_consumer
from app.repositories.message_repository import MessageRepository


def main() -> None:
    cassandra_client.connect()

    try:
        kafka_consumer = create_kafka_message_persistence_consumer()

        message_repository = MessageRepository(
            session=cassandra_client.get_session(),
        )

        consumer = MessagePersistenceConsumer(
            consumer=kafka_consumer,
            topic=settings.kafka_message_accepted_topic,
            message_repository=message_repository,
            poll_timeout_seconds=(
                settings.kafka_consumer_poll_timeout_seconds
            ),
            retry_initial_backoff_seconds=(
                settings.kafka_consumer_retry_initial_backoff_seconds
            ),
            retry_max_backoff_seconds=(
                settings.kafka_consumer_retry_max_backoff_seconds
            ),
            retry_max_attempts=settings.kafka_consumer_retry_max_attempts,
        )

        consumer.run()
    finally:
        cassandra_client.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    main()