import logging
from dataclasses import dataclass, replace
from time import monotonic

from confluent_kafka import (
    Consumer,
    KafkaError,
    KafkaException,
    Message as KafkaMessage,
    TopicPartition,
)
from pydantic import ValidationError

from app.ai.message_semantic_labeler import (
    OllamaMessageSemanticLabeler,
)
from app.domain.message import Message
from app.events.message import MessagePersistedEvent
from app.repositories.message_repository import MessageRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _PendingSemanticUpdate:
    record: KafkaMessage
    message: Message



# 1. Invalid event:
#    Flush pending labels, commit their offsets,
#    then skip and commit the invalid record.
#
# 2. Valid event:
#    Call the LLM and add the labeled message to the buffer.
#
# 3. Flush:
#    When the buffer is full or due(_flush_interval_seconds), update labels to Cassandra.
#    Commit offsets only after the write succeeds.
#
# 4. LLM or Cassandra failure:
#    Do not commit the failed record.
#    Stop the worker; Kafka replays it after restart.
class MessageSemanticConsumer:
    def __init__(
        self,
        consumer: Consumer,
        topic: str,
        message_repository: MessageRepository,
        labeler: OllamaMessageSemanticLabeler,
        poll_timeout_seconds: float,
        batch_size: int,
        flush_interval_seconds: float,
        prompt_version: str,
    ) -> None:
        self._consumer = consumer
        self._topic = topic
        self._message_repository = message_repository
        self._labeler = labeler
        self._poll_timeout_seconds = poll_timeout_seconds
        self._batch_size = batch_size
        self._flush_interval_seconds = flush_interval_seconds
        self._prompt_version = prompt_version
        self._pending: list[_PendingSemanticUpdate] = []
        self._last_flush_at = monotonic()

    def run(self) -> None:
        self._consumer.subscribe(
            [self._topic],
            on_assign=self._on_assign,
            on_revoke=self._on_revoke,
        )

        try:
            while True:
                if self._is_flush_due():
                    self._flush_pending()

                record = self._consumer.poll(
                    timeout=self._poll_timeout_seconds,
                )
                if record is None:
                    continue

                self._handle_record(record)
        finally:
            try:
                self._flush_pending()
            finally:
                self._consumer.close()

    def _handle_record(
        self,
        record: KafkaMessage,
    ) -> None:
        if record.error() is not None:
            self._raise_if_unexpected_kafka_error(record)
            return

        try:
            event = self._deserialize_event(record)
        except (ValidationError, ValueError):
            logger.exception(
                "Skipping invalid persisted message event.",
                extra={
                    "topic": record.topic(),
                    "partition": record.partition(),
                    "offset": record.offset(),
                },
            )
            self._flush_pending()

            self._consumer.commit(
                message=record,
                asynchronous=False,
            )
            return

        message = event.payload.to_message()

        try:
            label = self._labeler.label(message)
        except Exception:
            logger.exception(
                "Message semantic labeling failed.",
                extra={
                    "message_id": str(message.message_id),
                    "topic": record.topic(),
                    "partition": record.partition(),
                    "offset": record.offset(),
                },
            )
            raise

        labeled_message = replace(
            message,
            sentiment=label.sentiment.value,
            sentiment_labeled_at=label.labeled_at,
            sentiment_model_name=label.model_name,
            sentiment_prompt_version=self._prompt_version,
        )

        self._pending.append(
            _PendingSemanticUpdate(
                record=record,
                message=labeled_message,
            ),
        )

        logger.info(
            "Message semantic labeling succeeded: "
            "message_id=%s sentiment=%s model=%s",
            label.message_id,
            label.sentiment.value,
            label.model_name,
        )

        if self._is_flush_due():
            self._flush_pending()

    def _flush_pending(self) -> None:
        if not self._pending:
            return

        messages = [
            pending.message
            for pending in self._pending
        ]

        self._message_repository.update_sentiments(messages)

        self._consumer.commit(
            offsets=self._offsets_to_commit(),
            asynchronous=False,
        )

        logger.info(
            "Persisted %s message sentiments.",
            len(self._pending),
        )

        self._pending.clear()
        self._last_flush_at = monotonic()

    def _is_flush_due(self) -> bool:
        if not self._pending:
            return False

        if len(self._pending) >= self._batch_size:
            return True

        return (
            monotonic() - self._last_flush_at
            >= self._flush_interval_seconds
        )

    def _offsets_to_commit(self) -> list[TopicPartition]:
        offsets: dict[tuple[str, int], int] = {}

        for pending in self._pending:
            record = pending.record
            partition_key = (
                record.topic(),
                record.partition(),
            )
            next_offset = record.offset() + 1

            offsets[partition_key] = max(
                offsets.get(partition_key, 0),
                next_offset,
            )

        return [
            TopicPartition(
                topic,
                partition,
                offset,
            )
            for (topic, partition), offset in offsets.items()
        ]

    @staticmethod
    def _deserialize_event(
        record: KafkaMessage,
    ) -> MessagePersistedEvent:
        value = record.value()
        if value is None:
            raise ValueError("Kafka message value must not be null.")

        return MessagePersistedEvent.model_validate_json(value)

    @staticmethod
    def _on_assign(
        consumer: Consumer,
        partitions: list[TopicPartition],
    ) -> None:
        consumer.assign(partitions)

    def _on_revoke(
        self,
        consumer: Consumer,
        partitions: list[TopicPartition],
    ) -> None:
        revoked_partitions = {
            (partition.topic, partition.partition)
            for partition in partitions
        }
        self._pending = [
            pending
            for pending in self._pending
            if (
                pending.record.topic(),
                pending.record.partition(),
            )
            not in revoked_partitions
        ]

        consumer.unassign()

    @staticmethod
    def _raise_if_unexpected_kafka_error(
        record: KafkaMessage,
    ) -> None:
        error = record.error()
        if error is None or error.code() == KafkaError._PARTITION_EOF:
            return

        raise KafkaException(error)