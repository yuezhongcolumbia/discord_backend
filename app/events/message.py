from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain.message import Message


class MessageAcceptedPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    message_id: UUID
    channel_id: UUID
    bucket_date: date
    created_at: datetime
    author_id: UUID
    edited_at: datetime | None
    message_content: str | None
    attachment_ids: list[UUID]

    @classmethod
    def from_message(
        cls,
        message: Message,
    ) -> "MessageAcceptedPayload":
        return cls(
            message_id=message.message_id,
            channel_id=message.channel_id,
            bucket_date=message.bucket_date,
            created_at=message.created_at,
            author_id=message.author_id,
            edited_at=message.edited_at,
            message_content=message.message_content,
            attachment_ids=message.attachment_ids,
        )

    def to_message(self) -> Message:
        return Message(
            message_id=self.message_id,
            channel_id=self.channel_id,
            bucket_date=self.bucket_date,
            created_at=self.created_at,
            author_id=self.author_id,
            edited_at=self.edited_at,
            message_content=self.message_content,
            attachment_ids=self.attachment_ids,
        )


class MessageAcceptedEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    event_type: Literal["message.accepted"] = "message.accepted"
    event_version: Literal[1] = 1
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    payload: MessageAcceptedPayload

    @classmethod
    def from_message(
        cls,
        message: Message,
    ) -> "MessageAcceptedEvent":
        return cls(
            payload=MessageAcceptedPayload.from_message(message),
        )