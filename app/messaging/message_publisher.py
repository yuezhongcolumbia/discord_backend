# app/messaging/message_publisher.py

from typing import Protocol

from app.domain.message import Message


class MessagePublisher(Protocol):
    def publish(self, message: Message) -> None:
        ...
