"""add conversation summaries

Revision ID: <keep generated revision id>
Revises: f389eeb9f076
Create Date: <keep generated date>
"""

from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "<keep generated revision id>"
down_revision: Union[str, Sequence[str], None] = "f389eeb9f076"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_summaries",
        sa.Column(
            "summary_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "channel_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "summary_content",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "embedding",
            Vector(768),
            nullable=False,
        ),
        sa.Column(
            "source_message_ids",
            postgresql.ARRAY(sa.UUID()),
            nullable=False,
        ),
        sa.Column(
            "window_start_bucket_date",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "window_start_created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "window_start_message_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "window_end_bucket_date",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "window_end_created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "window_end_message_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "summary_model_name",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "summarized_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "summary_id",
            name=op.f("pk_conversation_summaries"),
        ),
        sa.UniqueConstraint(
            "channel_id",
            "window_end_message_id",
            name=(
                "uq_conversation_summaries_"
                "channel_window_end_message_id"
            ),
        ),
    )

    op.create_index(
        "ix_conversation_summaries_channel_window_end",
        "conversation_summaries",
        [
            "channel_id",
            "window_end_created_at",
            "window_end_message_id",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_summaries_channel_window_end",
        table_name="conversation_summaries",
    )

    op.drop_table("conversation_summaries")