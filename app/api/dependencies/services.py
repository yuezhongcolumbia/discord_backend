# app/api/dependencies/services.py

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.cassandra import get_message_repository
from app.api.dependencies.messaging import get_message_publisher
from app.db.session import get_db_session
from app.messaging.message_publisher import MessagePublisher
from app.repositories.channel_repository import ChannelRepository
from app.repositories.direct_message_repository import DirectMessageRepository
from app.repositories.guild_repository import GuildRepository
from app.repositories.message_repository import MessageRepository
from app.services.conversational_assistance_service import ConversationalAssistanceService
from app.services.guild_service import GuildService
from app.services.channel_service import ChannelService
from app.services.message_history_service import MessageHistoryService
from app.services.message_submission_service import MessageSubmissionService


def get_guild_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GuildService:
    return GuildService(session)

def get_channel_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ChannelService:
    return ChannelService(session)

# def get_message_service(
#     db_session: Annotated[
#         AsyncSession,
#         Depends(get_db_session),
#     ],
#     message_repository: Annotated[
#         MessageRepository,
#         Depends(get_message_repository),
#     ],
#     message_publisher: Annotated[
#         MessagePublisher,
#         Depends(get_message_publisher),
#     ]
# ) -> MessageService:
#     return MessageService(
#         channel_repository=ChannelRepository(db_session),
#         guild_repository=GuildRepository(db_session),
#         message_repository=message_repository,
#         message_publisher=message_publisher,
#     )
def get_message_submission_service(
    db_session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    message_publisher: Annotated[
        MessagePublisher,
        Depends(get_message_publisher),
    ],
) -> MessageSubmissionService:
    return MessageSubmissionService(
        channel_repository=ChannelRepository(db_session),
        guild_repository=GuildRepository(db_session),
        direct_message_repository=DirectMessageRepository(
            db_session,
        ),
        message_publisher=message_publisher,
    )


def get_message_history_service(
    db_session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    message_repository: Annotated[
        MessageRepository,
        Depends(get_message_repository),
    ],
) -> MessageHistoryService:
    return MessageHistoryService(
        channel_repository=ChannelRepository(db_session),
        guild_repository=GuildRepository(db_session),
        direct_message_repository=DirectMessageRepository(
            db_session,
        ),
        message_repository=message_repository,
    )

def get_conversational_assistance_service(
    db_session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    message_history_service: Annotated[
        MessageHistoryService,
        Depends(get_message_history_service),
    ],
) -> ConversationalAssistanceService:
    return ConversationalAssistanceService(
        channel_repository=ChannelRepository(db_session),
        direct_message_repository=DirectMessageRepository(
            db_session,
        ),
        message_history_service=message_history_service,
        context_message_limit=(
            settings.conversational_assistance_context_message_limit
        ),
        context_wait_timeout_seconds=(
            settings
            .conversational_assistance_context_wait_timeout_seconds
        ),
    )