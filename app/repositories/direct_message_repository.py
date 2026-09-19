from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.direct_message_channel import (
    DirectMessageChannel,
)


class DirectMessageRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def get_channel_id_by_participants(
            self,
            participant_a_id: UUID,
            participant_b_id: UUID,
    ) -> UUID | None:
        participant_low_id, participant_high_id = sorted(
            (participant_a_id, participant_b_id),
        )

        statement = select(
            DirectMessageChannel.channel_id,
        ).where(
            DirectMessageChannel.participant_low_id
            == participant_low_id,
            DirectMessageChannel.participant_high_id
            == participant_high_id,
        )

        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def is_participant(
        self,
        channel_id: UUID,
        user_id: UUID,
    ) -> bool:
        statement = select(
            DirectMessageChannel.channel_id,
        ).where(
            DirectMessageChannel.channel_id == channel_id,
            or_(
                DirectMessageChannel.participant_low_id
                == user_id,
                DirectMessageChannel.participant_high_id
                == user_id,
            ),
        )

        result = await self._session.execute(statement)

        return result.scalar_one_or_none() is not None

    def add(
        self,
        channel_id: UUID,
        participant_a_id: UUID,
        participant_b_id: UUID,
    ) -> DirectMessageChannel:
        participant_low_id, participant_high_id = sorted(
            (participant_a_id, participant_b_id),
        )

        direct_message_channel = DirectMessageChannel(
            channel_id=channel_id,
            participant_low_id=participant_low_id,
            participant_high_id=participant_high_id,
        )

        self._session.add(direct_message_channel)

        return direct_message_channel