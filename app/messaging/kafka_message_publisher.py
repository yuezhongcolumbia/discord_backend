from threading import Event
from time import monotonic

from confluent_kafka import KafkaError, KafkaException, Message as KafkaMessage, Producer

from app.domain.message import Message
from app.events.message import MessageAcceptedPayload
from app.exceptions.kafka import KafkaPublishError
from app.messaging.message_publisher import MessagePublisher


class KafkaMessagePublisher(MessagePublisher):
    def __init__(
        self,
        producer: Producer,
        topic: str,
        publish_wait_timeout_seconds: float,
    ) -> None:
        self._producer = producer
        self._topic = topic
        self._publish_wait_timeout_seconds = publish_wait_timeout_seconds

    def publish(self, message: Message) -> None:
        payload = MessageAcceptedPayload.from_message(message)
        delivery_completed = Event()
        delivery_error: KafkaError | None = None

        # callback function to detect delivery error
        def on_delivery(
                error: KafkaError | None,
                _kafka_message: KafkaMessage,
        ) -> None:
            nonlocal delivery_error

            delivery_error = error
            delivery_completed.set()

        # publishing message event
        try:
            self._producer.produce(
                topic=self._topic,
                key=str(message.channel_id).encode("utf-8"),
                value=payload.model_dump_json().encode("utf-8"),
                on_delivery=on_delivery,
            )
        except BufferError as error:
            raise KafkaPublishError(
                "Kafka producer queue is full."
            ) from error

        # keep polling until either success or timeout
        deadline = monotonic() + self._publish_wait_timeout_seconds
        while not delivery_completed.is_set():
            remaining_seconds = deadline - monotonic()
            if remaining_seconds <= 0:
                raise KafkaPublishError(
                    "Timed out while waiting for Kafka message delivery confirmation."
                )

            self._producer.poll(timeout=min(remaining_seconds, 0.1))

        if delivery_error is not None:
            delivery_exception = KafkaException(delivery_error)
            raise KafkaPublishError(
                "Kafka message delivery failed."
            ) from delivery_exception