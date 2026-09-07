from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.guild import Guild
from app.models.guild_membership import GuildMembership
from app.models.guild_role import GuildRole
from app.repositories.guild_repository import GuildRepository
from app.schemas.guild import GuildCreate
from app.exceptions.guild import (
    GuildNotFoundError,
    OwnerCannotLeaveGuildError,
)


class GuildService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._guild_repository = GuildRepository(session)

    async def create_guild(
        self,
        guild_create: GuildCreate,
        owner_id: UUID,
    ) -> Guild:
        guild = Guild(
            guild_name=guild_create.name,
            owner_id=owner_id,
        )

        async with self._session.begin():
            self._guild_repository.add_guild(guild)

            await self._session.flush()

            owner_membership = GuildMembership(
                guild_id=guild.guild_id,
                user_id=owner_id,
                role=GuildRole.OWNER,
            )

            self._guild_repository.add_membership(owner_membership)

        return guild


    async def join_guild(
            self,
            guild_id: UUID,
            user_id: UUID,
    ) -> tuple[GuildMembership, bool]:
        async with self._session.begin():
            guild = await self._guild_repository.get_guild_by_id(
                guild_id
            )

            if guild is None:
                raise GuildNotFoundError(guild_id)

            membership, created = (
                await self._guild_repository.add_membership_if_absent(
                    guild_id=guild_id,
                    user_id=user_id,
                    role=GuildRole.MEMBER,
                )
            )
        return membership, created

    async def leave_guild(
            self,
            guild_id: UUID,
            user_id: UUID,
    ) -> None:
        async with self._session.begin():
            guild = await self._guild_repository.get_guild_by_id(
                guild_id
            )
            if guild is None:
                raise GuildNotFoundError(guild_id)
            if guild.owner_id == user_id:
                raise OwnerCannotLeaveGuildError(guild_id)
            membership = await self._guild_repository.get_membership(
                guild_id=guild_id,
                user_id=user_id,
            )
            if membership is None:
                return
            await self._guild_repository.delete_membership(
                membership
            )