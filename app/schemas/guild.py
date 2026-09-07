from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.guild_role import GuildRole


class GuildCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()

        return value


class GuildResponse(BaseModel):
    guild_id: UUID
    name: str = Field(validation_alias="guild_name")
    owner_id: UUID
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class GuildMembershipResponse(BaseModel):
    guild_id: UUID
    user_id: UUID
    role: GuildRole
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)