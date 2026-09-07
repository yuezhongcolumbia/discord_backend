from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.guild_role import GuildRole


class GuildMembership(Base):
    __tablename__ = "guild_memberships"

    guild_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("guilds.guild_id", ondelete="CASCADE"),
        primary_key=True,
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )

    role: Mapped[GuildRole] = mapped_column(
        SqlEnum(
            GuildRole,
            name="guild_role",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        nullable=False,
        default=GuildRole.MEMBER,
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )