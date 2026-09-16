from threading import Event
from time import monotonic

from confluent_kafka import (
    KafkaError,
    KafkaException,
    Message as KafkaMessage,
    Producer,
)

from app.exceptions.kafka import KafkaPublishError


class KafkaRecordPublisher:
    def __init__(
        self,
        producer: Producer,
        topic: str,
        publish_wait_timeout_seconds: float,
    ) -> None:
        self._producer = producer
        self._topic = topic
        self._publish_wait_timeout_seconds = (
            publish_wait_timeout_seconds
        )

    def publish(
        self,
        key: bytes,
        value: bytes,
    ) -> None:
        delivery_completed = Event()
        delivery_error: KafkaError | None = None

        def on_delivery(
            error: KafkaError | None,
            _kafka_message: KafkaMessage,
        ) -> None:
            nonlocal delivery_error

            delivery_error = error
            delivery_completed.set()

        try:
            self._producer.produce(
                topic=self._topic,
                key=key,
                value=value,
                on_delivery=on_delivery,
            )
        except BufferError as error:
            raise KafkaPublishError(
                "Kafka producer queue is full.",
            ) from error

        deadline = monotonic() + self._publish_wait_timeout_seconds

        while not delivery_completed.is_set():
            remaining_seconds = deadline - monotonic()

            if remaining_seconds <= 0:
                raise KafkaPublishError(
                    "Timed out while waiting for Kafka message "
                    "delivery confirmation.",
                )

            self._producer.poll(
                timeout=min(remaining_seconds, 0.1),
            )

        if delivery_error is not None:
            raise KafkaPublishError(
                "Kafka message delivery failed.",
            ) from KafkaException(delivery_error)