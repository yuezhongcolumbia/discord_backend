from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.guild import (
    GuildNotFoundError,
    GuildOwnerRequiredError, GuildMembershipRequiredError,
)
from app.models.channel import Channel
from app.repositories.channel_repository import ChannelRepository
from app.repositories.guild_repository import GuildRepository
from app.schemas.channel import ChannelCreate
from app.exceptions.channel import ChannelNotFoundError
from app.schemas.channel import ChannelCreate, ChannelUpdate


class ChannelService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._channel_repository = ChannelRepository(session)
        self._guild_repository = GuildRepository(session)

    async def create_channel(
        self,
        guild_id: UUID,
        channel_create: ChannelCreate,
        current_user_id: UUID,
    ) -> Channel:
        async with self._session.begin():
            guild = await self._guild_repository.get_guild_by_id(guild_id)
            if guild is None:
                raise GuildNotFoundError(guild_id)
            if guild.owner_id != current_user_id:
                raise GuildOwnerRequiredError(guild_id)
            channel = Channel(
                guild_id=guild_id,
                channel_name=channel_create.name,
                channel_type=channel_create.channel_type,
            )
            self._channel_repository.add_channel(channel)
            await self._session.flush()
        return channel

    async def list_channels(
            self,
            guild_id: UUID,
            current_user_id: UUID,
    ) -> list[Channel]:
        async with self._session.begin():
            guild = await self._guild_repository.get_guild_by_id(guild_id)

            if guild is None:
                raise GuildNotFoundError(guild_id)

            membership = await self._guild_repository.get_membership(
                guild_id=guild_id,
                user_id=current_user_id,
            )

            if membership is None:
                raise GuildMembershipRequiredError(guild_id)

            channels = (
                await self._channel_repository.get_channels_by_guild_id(
                    guild_id
                )
            )

        return channels

    async def rename_channel(
            self,
            channel_id: UUID,
            channel_update: ChannelUpdate,
            current_user_id: UUID,
    ) -> Channel:
        async with self._session.begin():
            channel = await self._channel_repository.get_channel_by_id(
                channel_id
            )

            if channel is None:
                raise ChannelNotFoundError(channel_id)

            guild = await self._guild_repository.get_guild_by_id(
                channel.guild_id
            )

            if guild is None:
                raise GuildNotFoundError(channel.guild_id)

            if guild.owner_id != current_user_id:
                raise GuildOwnerRequiredError(channel.guild_id)

            channel.channel_name = channel_update.name

            await self._session.flush()

        return channel

    async def delete_channel(
            self,
            channel_id: UUID,
            current_user_id: UUID,
    ) -> None:
        async with self._session.begin():
            channel = await self._channel_repository.get_channel_by_id(
                channel_id
            )

            if channel is None:
                return

            guild = await self._guild_repository.get_guild_by_id(
                channel.guild_id
            )

            if guild is None:
                raise GuildNotFoundError(channel.guild_id)

            if guild.owner_id != current_user_id:
                raise GuildOwnerRequiredError(channel.guild_id)

            await self._channel_repository.delete_channel(channel)