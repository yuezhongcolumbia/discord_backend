from confluent_kafka import Producer

from app.domain.message import Message
from app.events.message import MessageAcceptedPayload
from app.messaging.message_publisher import MessagePublisher


class KafkaMessagePublisher(MessagePublisher):
    def __init__(
        self,
        producer: Producer,
        topic: str,
    ) -> None:
        self._producer = producer
        self._topic = topic

    def publish(self, message: Message) -> None:
        payload = MessageAcceptedPayload.from_message(message)

        self._producer.produce(
            topic=self._topic,
            key=str(message.channel_id).encode("utf-8"),
            value=payload.model_dump_json().encode("utf-8"),
        )