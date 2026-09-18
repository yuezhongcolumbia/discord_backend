import logging

from app.ai.message_semantic_labeler import (
    OllamaMessageSemanticLabeler,
)
from app.consumers.message_semantic_consumer import (
    MessageSemanticConsumer,
)
from app.core.config import settings
from app.db.cassandra import cassandra_client
from app.messaging.kafka import (
    create_kafka_message_semantic_consumer,
)
from app.repositories.message_repository import MessageRepository


def main() -> None:
    cassandra_client.connect()

    try:
        kafka_consumer = (
            create_kafka_message_semantic_consumer()
        )

        message_repository = MessageRepository(
            session=cassandra_client.get_session(),
        )

        labeler = OllamaMessageSemanticLabeler(
            model_name=settings.ollama_message_semantic_model_name,
        )

        consumer = MessageSemanticConsumer(
            consumer=kafka_consumer,
            topic=settings.kafka_message_persisted_topic,
            message_repository=message_repository,
            labeler=labeler,
            poll_timeout_seconds=(
                settings.kafka_consumer_poll_timeout_seconds
            ),
            batch_size=(
                settings.kafka_message_semantic_batch_size
            ),
            flush_interval_seconds=(
                settings.kafka_message_semantic_flush_interval_seconds
            ),
            prompt_version=(
                settings.message_semantic_prompt_version
            ),
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