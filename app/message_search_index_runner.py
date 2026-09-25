import asyncio
import logging
import sys

from app.ai.ollama_text_embedder import OllamaTextEmbedder
from app.consumers.message_search_index_consumer import (
    MessageSearchIndexConsumer,
)
from app.core.config import settings
from app.db.session import (
    async_session_factory,
    engine,
)
from app.messaging.kafka import (
    create_kafka_message_search_index_consumer,
)


async def main() -> None:
    kafka_consumer = (
        create_kafka_message_search_index_consumer()
    )

    text_embedder = OllamaTextEmbedder(
        model_name=settings.ollama_text_embedding_model_name,
    )

    consumer = MessageSearchIndexConsumer(
        consumer=kafka_consumer,
        topic=settings.kafka_message_persisted_topic,
        session_factory=async_session_factory,
        text_embedder=text_embedder,
        poll_timeout_seconds=(
            settings.kafka_consumer_poll_timeout_seconds
        ),
    )

    try:
        await consumer.run()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(
            asyncio.WindowsSelectorEventLoopPolicy(),
        )

    asyncio.run(main())