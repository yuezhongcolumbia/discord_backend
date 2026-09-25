"""add message search indexes

Revision ID: f389eeb9f076
Revises: 2445936d1380
Create Date: 2026-09-22 13:20:52.722744
"""

from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa


revision: str = "f389eeb9f076"
down_revision: Union[str, Sequence[str], None] = "2445936d1380"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_search_indexes",
        sa.Column(
            "message_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "channel_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "message_content",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "embedding",
            Vector(768),
            nullable=False,
        ),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "message_id",
            name=op.f("pk_message_search_indexes"),
        ),
    )

    op.create_index(
        "ix_message_search_indexes_channel_created_at",
        "message_search_indexes",
        ["channel_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_message_search_indexes_channel_created_at",
        table_name="message_search_indexes",
    )

    op.drop_table("message_search_indexes")