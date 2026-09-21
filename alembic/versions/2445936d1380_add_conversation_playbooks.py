"""add conversation playbooks

Revision ID: 2445936d1380
Revises: 329f30dafa88
Create Date: 2026-09-20 11:49:29.241110
"""

from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa


revision: str = "2445936d1380"
down_revision: Union[str, Sequence[str], None] = "329f30dafa88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE EXTENSION IF NOT EXISTS vector
        """
    )

    op.create_table(
        "conversation_playbooks",
        sa.Column(
            "playbook_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "embedding",
            Vector(768),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "playbook_id",
            name=op.f("pk_conversation_playbooks"),
        ),
    )


def downgrade() -> None:
    op.drop_table("conversation_playbooks")