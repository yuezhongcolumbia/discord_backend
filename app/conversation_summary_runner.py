import asyncio
import logging
import sys

from app.ai.ollama_conversation_summarizer import (
    OllamaConversationSummarizer,
)
from app.ai.ollama_text_embedder import OllamaTextEmbedder
from app.consumers.conversation_summary_consumer import (
    ConversationSummaryConsumer,
)
from app.core.config import settings
from app.db.cassandra import cassandra_client
from app.db.session import (
    async_session_factory,
    engine,
)
from app.messaging.kafka import (
    create_kafka_conversation_summary_consumer,
)
from app.repositories.message_repository import MessageRepository


async def main() -> None:
    try:
        cassandra_client.connect()

        message_repository = MessageRepository(
            session=cassandra_client.get_session(),
        )

        summarizer = OllamaConversationSummarizer(
            model_name=(
                settings.ollama_conversation_summary_model_name
            ),
        )

        text_embedder = OllamaTextEmbedder(
            model_name=settings.ollama_text_embedding_model_name,
        )

        kafka_consumer = (
            create_kafka_conversation_summary_consumer()
        )

        try:
            consumer = ConversationSummaryConsumer(
                consumer=kafka_consumer,
                topic=settings.kafka_message_persisted_topic,
                session_factory=async_session_factory,
                message_repository=message_repository,
                summarizer=summarizer,
                summary_model_name=(
                    settings.ollama_conversation_summary_model_name
                ),
                text_embedder=text_embedder,
                poll_timeout_seconds=(
                    settings.kafka_consumer_poll_timeout_seconds
                ),
                window_size=(
                    settings.conversation_summary_window_size
                ),
            )
        except Exception:
            kafka_consumer.close()
            raise

        # Consumer.run() closes the Kafka consumer on exit.
        await consumer.run()
    finally:
        try:
            cassandra_client.close()
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