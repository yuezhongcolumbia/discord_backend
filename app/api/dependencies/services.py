# app/api/dependencies/services.py

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ollama_conversational_assistant import OllamaConversationalAssistant
from app.ai.ollama_text_embedder import OllamaTextEmbedder
from app.api.dependencies.cassandra import get_message_repository
from app.api.dependencies.messaging import get_message_publisher
from app.core.config import settings
from app.db.session import get_db_session
from app.messaging.message_publisher import MessagePublisher
from app.repositories.channel_repository import ChannelRepository
from app.repositories.conversation_playbook_repository import ConversationPlaybookRepository
from app.repositories.direct_message_repository import DirectMessageRepository
from app.repositories.elasticsearch.message_keyword_index_repository import MessageKeywordIndexRepository
from app.repositories.guild_repository import GuildRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.message_search_index_repository import MessageSearchIndexRepository
from app.repositories.conversation_summary_repository import ConversationSummaryRepository
from app.schemas.conversational_assistance import ConversationalAssistanceRequest
from app.services.conversational_assistance_service import ConversationalAssistanceService
from app.services.guild_service import GuildService
from app.services.channel_service import ChannelService
from app.services.message_history_service import MessageHistoryService
from app.services.message_submission_service import MessageSubmissionService
from app.services.authorization_service import AuthorizationService


def get_guild_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GuildService:
    return GuildService(session)

def get_channel_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ChannelService:
    return ChannelService(session)

def get_authorization_service(
    request: Request,
    db_session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
) -> AuthorizationService:
    return AuthorizationService(
        channel_repository=ChannelRepository(
            db_session,
        ),
        direct_message_repository=DirectMessageRepository(
            db_session,
        ),
        redis_client=request.app.state.redis_client,
        cache_ttl_seconds=(
            settings.authorization_cache_ttl_seconds
        ),
    )

def get_message_submission_service(
    db_session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    message_publisher: Annotated[
        MessagePublisher,
        Depends(get_message_publisher),
    ],
    authorization_service: Annotated[
        AuthorizationService,
        Depends(get_authorization_service),
    ],
) -> MessageSubmissionService:
    return MessageSubmissionService(
        channel_repository=ChannelRepository(db_session),
        guild_repository=GuildRepository(db_session),
        authorization_service=authorization_service,
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
    authorization_service: Annotated[
        AuthorizationService,
        Depends(get_authorization_service),
    ],
) -> MessageHistoryService:
    return MessageHistoryService(
        channel_repository=ChannelRepository(db_session),
        guild_repository=GuildRepository(db_session),
        authorization_service=authorization_service,
        message_repository=message_repository,
    )

def get_conversational_assistance_service(
    request: Request,
    db_session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    message_history_service: Annotated[
        MessageHistoryService,
        Depends(get_message_history_service),
    ],
    authorization_service: Annotated[
        AuthorizationService,
        Depends(get_authorization_service),
    ]
) -> ConversationalAssistanceService:
    return ConversationalAssistanceService(
        authorization_service=authorization_service,
        message_history_service=message_history_service,
        message_search_index_repository=MessageSearchIndexRepository(
            db_session,
        ),
        message_keyword_index_repository=MessageKeywordIndexRepository(
            client=request.app.state.elasticsearch_client,
            index_name=settings.elasticsearch_message_index_name,
        ),
        conversation_summary_repository=(
            ConversationSummaryRepository(db_session)
        ),
        playbook_repository=ConversationPlaybookRepository(
            db_session,
        ),
        text_embedder=OllamaTextEmbedder(
            settings.ollama_text_embedding_model_name,
        ),
        conversational_assistant=OllamaConversationalAssistant(
            coaching_model_name=(
                settings.ollama_conversational_assistance_model_name
            ),
        ),
        retrieval_top_k=(
            settings.conversational_assistance_retrieval_top_k
        ),
        fusion_top_k=(
            settings.conversational_assistance_fusion_top_k
        ),
        rrf_rank_constant=(
            settings.conversational_assistance_rrf_rank_constant
        ),
        context_message_limit=(
            settings.conversational_assistance_context_message_limit
        ),
        playbook_limit=(
            settings.conversational_assistance_playbook_limit
        ),
        context_wait_timeout_seconds=(
            settings
            .conversational_assistance_context_wait_timeout_seconds
        ),
    )

