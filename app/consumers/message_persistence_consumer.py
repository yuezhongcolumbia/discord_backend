import logging
from dataclasses import dataclass
from time import monotonic

from confluent_kafka import (
    Consumer,
    KafkaError,
    KafkaException,
    Message as KafkaMessage,
    TopicPartition,
)
from pydantic import ValidationError

from app.domain.message import Message
from app.events.message import MessageAcceptedPayload
from app.repositories.message_repository import MessageRepository

logger = logging.getLogger(__name__)


@dataclass
class _RetryState:
    record: KafkaMessage
    message: Message
    partition: TopicPartition
    attempt: int
    retry_at: float


class MessagePersistenceConsumer:
    def __init__(
        self,
        consumer: Consumer,
        topic: str,
        message_repository: MessageRepository,
        poll_timeout_seconds: float,
        retry_initial_backoff_seconds: float,
        retry_max_backoff_seconds: float,
        retry_max_attempts: int,
    ) -> None:
        self._consumer = consumer
        self._topic = topic
        self._message_repository = message_repository
        self._poll_timeout_seconds = poll_timeout_seconds
        self._retry_initial_backoff_seconds = retry_initial_backoff_seconds
        self._retry_max_backoff_seconds = retry_max_backoff_seconds
        self._retry_max_attempts = retry_max_attempts
        self._retries: list[_RetryState] = []

    def run(self) -> None:
        self._consumer.subscribe(
            [self._topic],
            on_assign=self._on_assign,
            on_revoke=self._on_revoke,
        )

        try:
            while True:
                self._retry_due_records()

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

        partition = TopicPartition(
            record.topic(),
            record.partition(),
        )

        if any(
            retry.partition == partition
            for retry in self._retries
        ):
            logger.warning(
                "Received a record from a paused partition.",
            )
            return

        # A deserialization error causes skipping the msg, commiting to offset
        # DLQ in the future will better handle this
        try:
            message = self._deserialize_message(record)
        except (ValidationError, ValueError):
            logger.exception(
                "Skipping invalid message event.",
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

        try:
            self._persist_and_commit(
                record=record,
                message=message,
            )
        except Exception:
            logger.exception(
                "Message persistence failed; pausing partition for retry.",
            )
            self._pause_for_retry(
                record=record,
                message=message,
                partition=partition,
            )
    # 1.skip future retry attempt
    # 2. try persist/commit offset again
    #     if fails calculate future commit time
    #             if exceed attempt limit, it raise unhandled exception, the consumer will shutdown
    #     else delete the retryState, resume partition
    def _retry_due_records(self) -> None:
        now = monotonic()

        for retry in list(self._retries):
            if retry.retry_at > now:
                continue

            try:
                self._persist_and_commit(
                    record=retry.record,
                    message=retry.message,
                )
            except Exception:
                retry.attempt += 1

                if retry.attempt >= self._retry_max_attempts:
                    logger.exception(
                        "Message persistence reached the retry limit.",
                    )
                    raise

                retry.retry_at = monotonic() + self._retry_delay(
                    retry.attempt,
                )

                logger.exception(
                    "Message persistence retry failed.",
                )
            else:
                self._consumer.resume([retry.partition])
                self._retries.remove(retry)

                logger.info(
                    "Message persistence retry succeeded.",
                )

    def _persist_and_commit(
        self,
        record: KafkaMessage,
        message: Message,
    ) -> None:
        self._message_repository.save(message)

        self._consumer.commit(
            message=record,
            asynchronous=False,
        )

    def _deserialize_message(
            self,
            record: KafkaMessage,
    ) -> Message:
        value = record.value()
        if value is None:
            raise ValueError("Kafka message value must not be null.")

        payload = MessageAcceptedPayload.model_validate_json(value)

        return payload.to_message()

    def _pause_for_retry(
        self,
        record: KafkaMessage,
        message: Message,
        partition: TopicPartition,
    ) -> None:
        self._consumer.pause([partition])

        self._retries.append(
            _RetryState(
                record=record,
                message=message,
                partition=partition,
                attempt=1,
                retry_at=monotonic() + self._retry_delay(1),
            )
        )

    def _retry_delay(
        self,
        attempt: int,
    ) -> float:
        return min(
            self._retry_initial_backoff_seconds * (2 ** (attempt - 1)),
            self._retry_max_backoff_seconds,
        )

    def _on_assign(
        self,
        consumer: Consumer,
        partitions: list[TopicPartition],
    ) -> None:
        consumer.assign(partitions)

    def _on_revoke(
        self,
        consumer: Consumer,
        partitions: list[TopicPartition],
    ) -> None:
        self._retries = [
            retry
            for retry in self._retries
            if retry.partition not in partitions
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