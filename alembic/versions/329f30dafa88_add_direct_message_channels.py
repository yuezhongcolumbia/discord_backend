"""add direct message channels

Revision ID: 329f30dafa88
Revises: 56e1899223f9
Create Date: 2026-09-19 14:36:43.333107
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "329f30dafa88"
down_revision: Union[str, Sequence[str], None] = "56e1899223f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "direct_message_channels",
        sa.Column(
            "channel_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "participant_low_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "participant_high_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "participant_low_id < participant_high_id",
            name=op.f(
                "ck_direct_message_channels_"
                "ck_direct_message_channels_participant_order"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["channels.channel_id"],
            name=op.f(
                "fk_direct_message_channels_channel_id_channels"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_high_id"],
            ["users.user_id"],
            name=op.f(
                "fk_direct_message_channels_"
                "participant_high_id_users"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["participant_low_id"],
            ["users.user_id"],
            name=op.f(
                "fk_direct_message_channels_"
                "participant_low_id_users"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "channel_id",
            name=op.f(
                "pk_direct_message_channels"
            ),
        ),
        sa.UniqueConstraint(
            "participant_low_id",
            "participant_high_id",
            name="uq_direct_message_channels_participants",
        ),
    )

    op.alter_column(
        "channels",
        "guild_id",
        existing_type=sa.UUID(),
        nullable=True,
    )

    op.alter_column(
        "channels",
        "channel_name",
        existing_type=sa.VARCHAR(length=100),
        nullable=True,
    )

    op.drop_constraint(
        op.f("ck_channels_channel_type"),
        "channels",
        type_="check",
    )

    op.create_check_constraint(
        op.f("ck_channels_ck_channels_type_fields"),
        "channels",
        """
        (
            channel_type = 'text'
            AND guild_id IS NOT NULL
            AND channel_name IS NOT NULL
        )
        OR
        (
            channel_type = 'dm'
            AND guild_id IS NULL
            AND channel_name IS NULL
        )
        """,
    )


def downgrade() -> None:
    op.drop_table("direct_message_channels")

    # Old schema cannot represent DM channels.
    op.execute(
        """
        DELETE FROM channels
        WHERE channel_type = 'dm'
        """
    )

    op.drop_constraint(
        op.f("ck_channels_ck_channels_type_fields"),
        "channels",
        type_="check",
    )

    op.create_check_constraint(
        op.f("ck_channels_channel_type"),
        "channels",
        "channel_type::text = 'text'::text",
    )

    op.alter_column(
        "channels",
        "channel_name",
        existing_type=sa.VARCHAR(length=100),
        nullable=False,
    )

    op.alter_column(
        "channels",
        "guild_id",
        existing_type=sa.UUID(),
        nullable=False,
    )