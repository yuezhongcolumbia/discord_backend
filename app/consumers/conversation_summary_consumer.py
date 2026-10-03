import logging
from uuid import uuid4

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

from app.ai.ollama_conversation_summarizer import (
    OllamaConversationSummarizer,
)
from app.ai.ollama_text_embedder import OllamaTextEmbedder
from app.domain.message import Message
from app.events.message import MessagePersistedEvent
from app.models.channel_type import ChannelType
from app.repositories.channel_repository import ChannelRepository
from app.repositories.conversation_summary_repository import (
    ConversationSummaryRepository,
)
from app.repositories.message_repository import MessageRepository

logger = logging.getLogger(__name__)

# consume message, pinpoint last summary, use it as a cursor to retrive 20 msg since the last summarized one.
# if there is no summary, start at the beginning of the channel and do back fill
# if there is less than 20 msg since the last summarized one, do nothing
# either way we commit offset
# validation error skip and commit
# cassandra we stop the consumer
class ConversationSummaryConsumer:
    def __init__(
        self,
        consumer: Consumer,
        topic: str,
        session_factory: async_sessionmaker[AsyncSession],
        message_repository: MessageRepository,
        summarizer: OllamaConversationSummarizer,
        summary_model_name: str,
        text_embedder: OllamaTextEmbedder,
        poll_timeout_seconds: float,
        window_size: int = 20,
    ) -> None:
        if window_size < 1:
            raise ValueError(
                "Summary window size must be at least one.",
            )

        self._consumer = consumer
        self._topic = topic
        self._session_factory = session_factory
        self._message_repository = message_repository
        self._summarizer = summarizer
        self._summary_model_name = summary_model_name
        self._text_embedder = text_embedder
        self._poll_timeout_seconds = poll_timeout_seconds
        self._window_size = window_size

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
            await self._summarize_channel(message)
            self._commit(record)
        except Exception:
            logger.exception(
                "Conversation summarization failed.",
                extra={
                    "topic": record.topic(),
                    "partition": record.partition(),
                    "offset": record.offset(),
                    "message_id": str(message.message_id),
                    "channel_id": str(message.channel_id),
                },
            )
            raise

    async def _summarize_channel(
        self,
        message: Message,
    ) -> None:
        channel_id = message.channel_id

        async with self._session_factory() as session:
            channel = await ChannelRepository(
                session,
            ).get_channel_by_id(channel_id)

            if (
                channel is None
                or channel.channel_type != ChannelType.DM
            ):
                return

            latest_summary = (
                await ConversationSummaryRepository(
                    session,
                ).get_latest_for_channel(channel_id)
            )

            after_bucket_date = (
                latest_summary.window_end_bucket_date
                if latest_summary is not None
                else None
            )
            after_created_at = (
                latest_summary.window_end_created_at
                if latest_summary is not None
                else None
            )
            after_message_id = (
                latest_summary.window_end_message_id
                if latest_summary is not None
                else None
            )

        while True:
            messages = await run_in_threadpool(
                self._message_repository.get_messages_after,
                channel_id=channel_id,
                after_bucket_date=after_bucket_date,
                after_created_at=after_created_at,
                after_message_id=after_message_id,
                limit=self._window_size,
            )

            if len(messages) < self._window_size:
                return

            summary_content = await self._summarizer.summarize(
                messages,
            )

            embedding = await run_in_threadpool(
                self._text_embedder.embed,
                summary_content,
            )

            window_start = messages[0]
            window_end = messages[-1]
            summary_id = uuid4()

            async with self._session_factory.begin() as session:
                repository = ConversationSummaryRepository(
                    session,
                )

                await repository.upsert(
                    summary_id=summary_id,
                    channel_id=channel_id,
                    summary_content=summary_content,
                    embedding=embedding,
                    source_message_ids=[
                        item.message_id
                        for item in messages
                    ],
                    window_start=window_start,
                    window_end=window_end,
                    summary_model_name=self._summary_model_name,
                )

            # Advance only after the PostgreSQL transaction commits.
            after_bucket_date = window_end.bucket_date
            after_created_at = window_end.created_at
            after_message_id = window_end.message_id

            logger.info(
                "Conversation summary persisted.",
                extra={
                    "channel_id": str(channel_id),
                    "window_end_message_id": str(
                        window_end.message_id,
                    ),
                    "source_message_count": len(messages),
                },
            )

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