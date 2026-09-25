import logging

from confluent_kafka import (
    Consumer,
    KafkaError,
    KafkaException,
    Message as KafkaMessage,
)
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from app.ai.ollama_text_embedder import OllamaTextEmbedder
from app.domain.message import Message
from app.events.message import MessagePersistedEvent
from app.models.channel_type import ChannelType
from app.repositories.channel_repository import ChannelRepository
from app.repositories.message_search_index_repository import (
    MessageSearchIndexRepository,
)

logger = logging.getLogger(__name__)


class MessageSearchIndexConsumer:
    def __init__(
        self,
        consumer: Consumer,
        topic: str,
        session_factory: async_sessionmaker[AsyncSession],
        text_embedder: OllamaTextEmbedder,
        poll_timeout_seconds: float,
    ) -> None:
        self._consumer = consumer
        self._topic = topic
        self._session_factory = session_factory
        self._text_embedder = text_embedder
        self._poll_timeout_seconds = poll_timeout_seconds

    async def run(self) -> None:
        self._consumer.subscribe([self._topic])

        try:
            while True:
                record = self._consumer.poll(
                    timeout=self._poll_timeout_seconds,
                )

                if record is None:
                    continue

                await self._handle_record(record)
        finally:
            self._consumer.close()

    async def _handle_record(
        self,
        record: KafkaMessage,
    ) -> None:
        if record.error() is not None:
            self._raise_if_unexpected_kafka_error(record)
            return

        try:
            message = self._deserialize_message(record)
        except (ValidationError, ValueError):
            logger.exception(
                "Skipping invalid persisted message event.",
                extra={
                    "topic": record.topic(),
                    "partition": record.partition(),
                    "offset": record.offset(),
                },
            )
            self._commit(record)
            return

        try:
            indexed = await self._index_message(message)
            self._commit(record)
        except Exception:
            logger.exception(
                "Message search indexing failed.",
                extra={
                    "topic": record.topic(),
                    "partition": record.partition(),
                    "offset": record.offset(),
                    "message_id": str(message.message_id),
                },
            )
            raise

        if indexed:
            logger.info(
                "Message search index persisted.",
                extra={
                    "message_id": str(message.message_id),
                    "channel_id": str(message.channel_id),
                },
            )

    async def _index_message(
        self,
        message: Message,
    ) -> bool:
        message_content = message.message_content

        if (
            message_content is None
            or not message_content.strip()
        ):
            return False

        async with self._session_factory() as session:
            channel_repository = ChannelRepository(session)

            channel = (
                await channel_repository.get_channel_by_id(
                    message.channel_id,
                )
            )

        if (
            channel is None
            or channel.channel_type != ChannelType.DM
        ):
            return False

        embedding = await run_in_threadpool(
            self._text_embedder.embed,
            message_content,
        )

        async with self._session_factory.begin() as session:
            repository = MessageSearchIndexRepository(session)

            await repository.upsert(
                message=message,
                embedding=embedding,
            )

        return True

    @staticmethod
    def _deserialize_message(
        record: KafkaMessage,
    ) -> Message:
        value = record.value()

        if value is None:
            raise ValueError(
                "Kafka message value must not be null.",
            )

        event = MessagePersistedEvent.model_validate_json(value)

        return event.payload.to_message()

    def _commit(
        self,
        record: KafkaMessage,
    ) -> None:
        self._consumer.commit(
            message=record,
            asynchronous=False,
        )

    @staticmethod
    def _raise_if_unexpected_kafka_error(
        record: KafkaMessage,
    ) -> None:
        error = record.error()

        if (
            error is None
            or error.code() == KafkaError._PARTITION_EOF
        ):
            return

        raise KafkaException(error)