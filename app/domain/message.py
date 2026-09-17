from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Message:
    channel_id: UUID
    bucket_date: date
    created_at: datetime
    message_id: UUID
    author_id: UUID
    message_content: str | None
    attachment_ids: list[UUID]
    edited_at: datetime | None = None
    sentiment: str | None = None
    sentiment_labeled_at: datetime | None = None
    sentiment_model_name: str | None = None
    sentiment_prompt_version: str | None = None