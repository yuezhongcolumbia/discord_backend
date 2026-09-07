from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.channel_type import ChannelType


class Channel(Base):
    __tablename__ = "channels"

    channel_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    guild_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("guilds.guild_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    channel_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    channel_type: Mapped[ChannelType] = mapped_column(
        SqlEnum(
            ChannelType,
            name="channel_type",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        nullable=False,
        default=ChannelType.TEXT,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )