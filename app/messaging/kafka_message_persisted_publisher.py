from datetime import UTC, datetime

from confluent_kafka import Producer

from app.domain.message import Message
from app.events.message import MessagePersistedEvent
from app.messaging.kafka_record_publisher import KafkaRecordPublisher
from app.messaging.message_publisher import MessagePublisher


class KafkaMessagePersistedPublisher(MessagePublisher):
    def __init__(
        self,
        producer: Producer,
        topic: str,
        publish_wait_timeout_seconds: float,
    ) -> None:
        self._record_publisher = KafkaRecordPublisher(
            producer=producer,
            topic=topic,
            publish_wait_timeout_seconds=(
                publish_wait_timeout_seconds
            ),
        )

    def publish(
        self,
        message: Message,
    ) -> None:
        event = MessagePersistedEvent.from_message(
            message=message,
            persisted_at=datetime.now(UTC),
        )

        self._record_publisher.publish(
            key=str(message.channel_id).encode("utf-8"),
            value=event.model_dump_json().encode("utf-8"),
        )