from uuid import UUID
from sqlalchemy.dialects.postgresql import insert

from app.models.guild_role import GuildRole
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.guild import Guild
from app.models.guild_membership import GuildMembership


class GuildRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add_guild(self, guild: Guild) -> None:
        self._session.add(guild)

    async def get_guild_by_id(self, guild_id: UUID) -> Guild | None:
        return await self._session.get(Guild, guild_id)

    def add_membership(self, membership: GuildMembership) -> None:
        self._session.add(membership)

    async def get_membership(
        self,
        guild_id: UUID,
        user_id: UUID,
    ) -> GuildMembership | None:
        return await self._session.get(
            GuildMembership,
            (guild_id, user_id),
        )

    async def delete_membership(
        self,
        membership: GuildMembership,
    ) -> None:
        await self._session.delete(membership)

    async def add_membership_if_absent(
            self,
            guild_id: UUID,
            user_id: UUID,
            role: GuildRole,
    ) ->tuple[GuildMembership, bool]:
        statement = (
            insert(GuildMembership)
            .values(
                guild_id=guild_id,
                user_id=user_id,
                role=role,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    GuildMembership.guild_id,
                    GuildMembership.user_id,
                ],
            )
            .returning(GuildMembership)
        )

        result = await self._session.execute(statement)
        created_membership = result.scalar_one_or_none()

        if created_membership is not None:
            return created_membership, True

        existing_membership = await self.get_membership(
            guild_id=guild_id,
            user_id=user_id,
        )

        if existing_membership is None:
            raise RuntimeError(
                "Membership was not created and could not be retrieved."
            )

        return existing_membership, False