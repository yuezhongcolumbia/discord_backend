import asyncio
import logging
import sys

from app.ai.ollama_text_embedder import OllamaTextEmbedder
from app.consumers.message_search_index_consumer import (
    MessageSearchIndexConsumer,
)
from app.core.config import settings
from app.db.elasticsearch import create_elasticsearch_client
from app.db.session import (
    async_session_factory,
    engine,
)
from app.messaging.kafka import (
    create_kafka_message_search_index_consumer,
)
from app.repositories.elasticsearch.message_keyword_index_repository import (
    MessageKeywordIndexRepository,
)


async def main() -> None:
    elasticsearch_client = create_elasticsearch_client()

    try:
        index_exists = await elasticsearch_client.indices.exists(
            index=settings.elasticsearch_message_index_name,
        )

        if not index_exists:
            raise RuntimeError(
                "Elasticsearch message index does not exist. "
                "Create it using the index mapping JSON first.",
            )

        keyword_index_repository = MessageKeywordIndexRepository(
            client=elasticsearch_client,
            index_name=settings.elasticsearch_message_index_name,
        )

        text_embedder = OllamaTextEmbedder(
            model_name=settings.ollama_text_embedding_model_name,
        )

        kafka_consumer = (
            create_kafka_message_search_index_consumer()
        )

        consumer = MessageSearchIndexConsumer(
            consumer=kafka_consumer,
            topic=settings.kafka_message_persisted_topic,
            session_factory=async_session_factory,
            text_embedder=text_embedder,
            keyword_index_repository=keyword_index_repository,
            poll_timeout_seconds=(
                settings.kafka_consumer_poll_timeout_seconds
            ),
        )

        await consumer.run()
    finally:
        try:
            await elasticsearch_client.close()
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