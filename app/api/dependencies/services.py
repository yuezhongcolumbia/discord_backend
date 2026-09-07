# app/api/dependencies/services.py

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.cassandra import get_message_repository
from app.db.session import get_db_session
from app.repositories.channel_repository import ChannelRepository
from app.repositories.guild_repository import GuildRepository
from app.repositories.message_repository import MessageRepository
from app.services.guild_service import GuildService
from app.services.channel_service import ChannelService
from app.services.message_service import MessageService


def get_guild_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GuildService:
    return GuildService(session)

def get_channel_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ChannelService:
    return ChannelService(session)

def get_message_service(
    db_session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    message_repository: Annotated[
        MessageRepository,
        Depends(get_message_repository),
    ],
) -> MessageService:
    return MessageService(
        channel_repository=ChannelRepository(db_session),
        guild_repository=GuildRepository(db_session),
        message_repository=message_repository,
    )