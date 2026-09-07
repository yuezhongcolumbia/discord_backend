from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, model_validator


class MessageCreate(BaseModel):
    message_content: str | None = Field(
        default=None,
        max_length=4000,
    )
    attachment_ids: list[UUID] = Field(
        default_factory=list,
        max_length=10,
    )
    @model_validator(mode="after")
    def validate_content(self) -> "MessageCreate":
        has_text = bool(
            self.message_content
            and self.message_content.strip()
        )
        has_attachments = bool(self.attachment_ids)

        if not has_text and not has_attachments:
            raise ValueError(
                "A message must contain text or at least one attachment"
            )
        return self


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    message_id: UUID
    channel_id: UUID
    author_id: UUID
    message_content: str | None
    attachment_ids: list[UUID]
    created_at: datetime
    edited_at: datetime | None


class MessagePageResponse(BaseModel):
    items: list[MessageResponse]
    next_cursor: str | None