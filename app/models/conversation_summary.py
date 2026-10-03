from datetime import date, datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    DateTime,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConversationSummary(Base):
    """
    Asynchronous long-term memory projection of a DM message window.

    Cassandra remains the authoritative message store.
    """

    __tablename__ = "conversation_summaries"

    __table_args__ = (
        UniqueConstraint(
            "channel_id",
            "window_end_message_id",
            name=(
                "uq_conversation_summaries_"
                "channel_window_end_message_id"
            ),
        ),
        Index(
            "ix_conversation_summaries_channel_window_end",
            "channel_id",
            "window_end_created_at",
            "window_end_message_id",
        ),
    )

    summary_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
    )

    channel_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )

    summary_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    embedding: Mapped[list[float]] = mapped_column(
        Vector(768),
        nullable=False,
    )

    # Provenance for debugging and future retrieval experiments.
    source_message_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PostgreSQLUUID(as_uuid=True)),
        nullable=False,
    )

    window_start_bucket_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    window_start_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    window_start_message_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )

    window_end_bucket_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    window_end_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    window_end_message_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )

    summary_model_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    summarized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )