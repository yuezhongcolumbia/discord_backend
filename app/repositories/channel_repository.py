from sqlalchemy.ext.asyncio import AsyncSession
from app.models.channel import Channel
from uuid import UUID
from sqlalchemy import select


class ChannelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add_channel(self, channel: Channel) -> None:
        self._session.add(channel)

    async def get_channels_by_guild_id(
            self,
            guild_id: UUID,
    ) -> list[Channel]:
        statement = (
            select(Channel)
            .where(Channel.guild_id == guild_id)
            .order_by(
                Channel.created_at,
                Channel.channel_id,
            )
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def get_channel_by_id(
            self,
            channel_id: UUID,
    ) -> Channel | None:
        statement = select(Channel).where(
            Channel.channel_id == channel_id
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def delete_channel(
            self,
            channel: Channel,
    ) -> None:
        await self._session.delete(channel)

