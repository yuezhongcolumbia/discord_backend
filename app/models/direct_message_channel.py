from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DirectMessageChannel(Base):
    __tablename__ = "direct_message_channels"

    __table_args__ = (
        UniqueConstraint(
            "participant_low_id",
            "participant_high_id",
            name="uq_direct_message_channels_participants",
        ),
        CheckConstraint(
            "participant_low_id < participant_high_id",
            name="ck_direct_message_channels_participant_order",
        ),
    )

    channel_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "channels.channel_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    participant_low_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "users.user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    participant_high_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "users.user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )