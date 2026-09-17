import logging

from app.ai.message_semantic_labeler import (
    OllamaMessageSemanticLabeler,
)
from app.consumers.message_semantic_consumer import (
    MessageSemanticConsumer,
)
from app.core.config import settings
from app.messaging.kafka import (
    create_kafka_message_semantic_consumer,
)


def main() -> None:
    kafka_consumer = create_kafka_message_semantic_consumer()

    labeler = OllamaMessageSemanticLabeler(
        model_name=settings.ollama_message_semantic_model_name,
    )

    consumer = MessageSemanticConsumer(
        consumer=kafka_consumer,
        topic=settings.kafka_message_persisted_topic,
        labeler=labeler,
        poll_timeout_seconds=(
            settings.kafka_consumer_poll_timeout_seconds
        ),
    )

    consumer.run()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    main()