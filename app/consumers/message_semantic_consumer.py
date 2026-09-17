import logging

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
from app.events.message import MessagePersistedEvent

logger = logging.getLogger(__name__)


class MessageSemanticConsumer:
    def __init__(
        self,
        consumer: Consumer,
        topic: str,
        labeler: OllamaMessageSemanticLabeler,
        poll_timeout_seconds: float,
    ) -> None:
        self._consumer = consumer
        self._topic = topic
        self._labeler = labeler
        self._poll_timeout_seconds = poll_timeout_seconds

    def run(self) -> None:
        self._consumer.subscribe(
            [self._topic],
            on_assign=self._on_assign,
        )

        try:
            while True:
                record = self._consumer.poll(
                    timeout=self._poll_timeout_seconds,
                )
                if record is None:
                    continue

                self._handle_record(record)
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

        logger.info(
            "Message semantic labeling succeeded: "
            "message_id=%s sentiment=%s model=%s "
            "persisted_at=%s labeled_at=%s",
            label.message_id,
            label.sentiment.value,
            label.model_name,
            event.occurred_at.isoformat(),
            label.labeled_at.isoformat(),
        )

        self._consumer.commit(
            message=record,
            asynchronous=False,
        )

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

    @staticmethod
    def _raise_if_unexpected_kafka_error(
        record: KafkaMessage,
    ) -> None:
        error = record.error()
        if error is None or error.code() == KafkaError._PARTITION_EOF:
            return

        raise KafkaException(error)