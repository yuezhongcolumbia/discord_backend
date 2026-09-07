from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.channel_type import ChannelType


ChannelName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
    ),
]


class ChannelCreate(BaseModel):
    name: ChannelName
    channel_type: ChannelType = ChannelType.TEXT


class ChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    channel_id: UUID
    guild_id: UUID
    name: str = Field(validation_alias="channel_name")
    channel_type: ChannelType
    created_at: datetime

class ChannelUpdate(BaseModel):
    name: ChannelName