import asyncio
from time import monotonic
from uuid import UUID

from fastapi.concurrency import run_in_threadpool

from app.ai.ollama_conversational_assistant import (
    OllamaConversationalAssistant,
)
from app.services.authorization_service import AuthorizationService
from app.ai.ollama_text_embedder import OllamaTextEmbedder
from app.domain.message import Message
from app.domain.message_cursor import MessageCursor
from app.exceptions.channel import ChannelNotFoundError
from app.exceptions.conversational_assistance import (
    ConversationContextCatchingUpError,
)
from app.exceptions.message import InvalidMessageCursorError
from app.models.channel_type import ChannelType
from app.models.conversation_playbook import ConversationPlaybook
from app.models.conversation_summary import ConversationSummary
from app.models.message_search_index import MessageSearchIndex
from app.observability.langfuse_client import create_langfuse_client
from app.repositories.channel_repository import ChannelRepository
from app.repositories.conversation_playbook_repository import (
    ConversationPlaybookRepository,
)
from app.repositories.conversation_summary_repository import (
    ConversationSummaryRepository,
)
from app.repositories.direct_message_repository import (
    DirectMessageRepository,
)
from app.repositories.elasticsearch.message_keyword_index_repository import (
    MessageKeywordIndexRepository,
    MessageKeywordSearchResult,
)
from app.repositories.message_search_index_repository import (
    MessageSearchIndexRepository,
)
from app.schemas.conversational_assistance import (
    ConversationalAssistanceRequest,
    ConversationalAssistanceResponse,
)
from app.services.message_history_service import MessageHistoryService


class ConversationalAssistanceService:
    def __init__(
        self,
        authorization_service: AuthorizationService,
        message_history_service: MessageHistoryService,
        message_search_index_repository: MessageSearchIndexRepository,
        message_keyword_index_repository: MessageKeywordIndexRepository,
        conversation_summary_repository: ConversationSummaryRepository,
        playbook_repository: ConversationPlaybookRepository,
        text_embedder: OllamaTextEmbedder,
        conversational_assistant: OllamaConversationalAssistant,
        context_message_limit: int,
        retrieval_top_k: int,
        fusion_top_k: int,
        rrf_rank_constant: int,
        playbook_limit: int,
        context_wait_timeout_seconds: float,
    ) -> None:
        if retrieval_top_k < 1:
            raise ValueError(
                "Retrieval top K must be at least one.",
            )

        if fusion_top_k < 1:
            raise ValueError(
                "Fusion top K must be at least one.",
            )

        if rrf_rank_constant < 1:
            raise ValueError(
                "RRF rank constant must be at least one.",
            )

        if context_message_limit < 1:
            raise ValueError(
                "Context message limit must be at least one.",
            )

        self._authorization_service = authorization_service
        self._message_history_service = message_history_service
        self._message_search_index_repository = (
            message_search_index_repository
        )
        self._message_keyword_index_repository = (
            message_keyword_index_repository
        )
        self._conversation_summary_repository = (
            conversation_summary_repository
        )
        self._playbook_repository = playbook_repository
        self._text_embedder = text_embedder
        self._conversational_assistant = conversational_assistant
        self._context_message_limit = context_message_limit
        self._retrieval_top_k = retrieval_top_k
        self._fusion_top_k = fusion_top_k
        self._rrf_rank_constant = rrf_rank_constant
        self._playbook_limit = playbook_limit
        self._context_wait_timeout_seconds = (
            context_wait_timeout_seconds
        )

    async def assist(
        self,
        channel_id: UUID,
        current_user_id: UUID,
        request: ConversationalAssistanceRequest,
    ) -> ConversationalAssistanceResponse:
        await self._authorization_service.require_dm_access(
            channel_id=channel_id,
            user_id=current_user_id,
        )

        context_cursor = self._decode_cursor(
            request.context_through_cursor,
        )

        # The cursor is a persistence watermark, not a retrieval bound.
        await self._wait_for_context_cursor(
            channel_id=channel_id,
            context_cursor=context_cursor,
        )

        langfuse = create_langfuse_client()

        with langfuse.start_as_current_observation(
            as_type="span",
            name="conversational-assistance",
            input={
                "draft": request.draft,
                "channel_id": str(channel_id),
                "current_user_id": str(current_user_id),
            },
            metadata={
                "retrieval_mode": "fixed_pipeline",
                "fusion_method": "rrf",
                "retrieval_top_k": self._retrieval_top_k,
                "fusion_top_k": self._fusion_top_k,
                "rrf_rank_constant": self._rrf_rank_constant,
                "context_message_limit": self._context_message_limit,
            },
        ) as span:
            draft_embedding = await run_in_threadpool(
                self._text_embedder.embed,
                request.draft,
            )

            playbooks = await self._find_draft_playbooks(
                draft_embedding=draft_embedding,
            )

            (
                recent_messages,
                semantic_messages,
                keyword_messages,
                summaries,
            ) = await self._retrieve_context(
                channel_id=channel_id,
                draft=request.draft,
                draft_embedding=draft_embedding,
            )

            fused_messages = self._fuse_messages(
                semantic_messages=semantic_messages,
                keyword_messages=keyword_messages,
                limit=self._fusion_top_k,
                rank_constant=self._rrf_rank_constant,
            )

            messages_by_id: dict[
                UUID,
                Message | MessageSearchIndex | MessageKeywordSearchResult,
            ] = {}

            # Prioritize fused historical evidence, then add recent context.
            for message in [*fused_messages, *recent_messages]:
                messages_by_id.setdefault(
                    message.message_id,
                    message,
                )

            selected_messages = list(messages_by_id.values())[
                :self._context_message_limit
            ]

            # Present selected messages chronologically after selection.
            selected_messages.sort(
                key=lambda message: (
                    message.created_at,
                    message.message_id,
                ),
            )

            retrieval_output = {
                "retrieval_operation_count": 4,
                "recent_message_ids": [
                    str(message.message_id)
                    for message in recent_messages
                ],
                "semantic_message_ids": [
                    str(message.message_id)
                    for message in semantic_messages
                ],
                "keyword_message_ids": [
                    str(message.message_id)
                    for message in keyword_messages
                ],
                "fused_message_ids": [
                    str(message.message_id)
                    for message in fused_messages
                ],
                "retrieved_message_count": len(selected_messages),
                "retrieved_message_ids": [
                    str(message.message_id)
                    for message in selected_messages
                ],
                "retrieved_summary_count": len(summaries),
                "retrieved_summary_ids": [
                    str(summary.summary_id)
                    for summary in summaries
                ],
            }

            # Keep retrieval results if coaching subsequently fails.
            span.update(output=retrieval_output)

            response = await self._conversational_assistant.assist(
                draft=request.draft,
                playbooks=playbooks,
                message_context=self._format_messages(
                    messages=selected_messages,
                    current_user_id=current_user_id,
                ),
                summary_context=self._format_summaries(summaries),
                current_user_id=str(current_user_id),
            )

            span.update(
                output={
                    **retrieval_output,
                    "risk_level": response.risk_level.value,
                    "concern_count": len(response.concerns),
                    "option_count": len(response.options),
                },
            )

            return response

    async def _find_draft_playbooks(
        self,
        draft_embedding: list[float],
    ) -> list[ConversationPlaybook]:
        return await self._playbook_repository.find_similar(
            query_embedding=draft_embedding,
            limit=self._playbook_limit,
        )

    async def _find_draft_summaries(
        self,
        channel_id: UUID,
        draft_embedding: list[float],
        limit: int,
    ) -> list[ConversationSummary]:
        return await self._conversation_summary_repository.find_similar(
            channel_id=channel_id,
            query_embedding=draft_embedding,
            limit=limit,
        )

    async def _retrieve_context(
        self,
        channel_id: UUID,
        draft: str,
        draft_embedding: list[float],
    ) -> tuple[
        list[Message],
        list[MessageSearchIndex],
        list[MessageKeywordSearchResult],
        list[ConversationSummary],
    ]:
        langfuse = create_langfuse_client()

        with langfuse.start_as_current_observation(
            as_type="tool",
            name="get_recent_messages",
            input={
                "channel_id": str(channel_id),
                "top_k": self._retrieval_top_k,
            },
        ) as observation:
            recent_messages = (
                await self._message_history_service.get_recent_messages(
                    channel_id=channel_id,
                    limit=self._retrieval_top_k,
                )
            )

            observation.update(
                output={
                    "message_count": len(recent_messages),
                    "message_ids": [
                        str(message.message_id)
                        for message in recent_messages
                    ],
                },
            )

        # Run PostgreSQL searches sequentially: they share an AsyncSession.
        with langfuse.start_as_current_observation(
            as_type="tool",
            name="search_messages",
            input={
                "channel_id": str(channel_id),
                "top_k": self._retrieval_top_k,
                "query_source": "draft",
            },
        ) as observation:
            semantic_messages = (
                await self._message_search_index_repository.find_similar(
                    channel_id=channel_id,
                    query_embedding=draft_embedding,
                    limit=self._retrieval_top_k,
                )
            )

            observation.update(
                output={
                    "message_count": len(semantic_messages),
                    "message_ids": [
                        str(message.message_id)
                        for message in semantic_messages
                    ],
                },
            )

        with langfuse.start_as_current_observation(
            as_type="tool",
            name="search_messages_by_keywords",
            input={
                "channel_id": str(channel_id),
                "top_k": self._retrieval_top_k,
                "query_source": "draft",
            },
        ) as observation:
            keyword_messages = (
                await self._message_keyword_index_repository.find_by_keywords(
                    channel_id=channel_id,
                    query=draft,
                    limit=self._retrieval_top_k,
                )
            )

            observation.update(
                output={
                    "message_count": len(keyword_messages),
                    "message_ids": [
                        str(message.message_id)
                        for message in keyword_messages
                    ],
                },
            )

        with langfuse.start_as_current_observation(
            as_type="tool",
            name="search_summaries",
            input={
                "channel_id": str(channel_id),
                "top_k": self._retrieval_top_k,
                "query_source": "draft",
            },
        ) as observation:
            summaries = await self._find_draft_summaries(
                channel_id=channel_id,
                draft_embedding=draft_embedding,
                limit=self._retrieval_top_k,
            )

            observation.update(
                output={
                    "summary_count": len(summaries),
                    "summary_ids": [
                        str(summary.summary_id)
                        for summary in summaries
                    ],
                },
            )

        return (
            recent_messages,
            semantic_messages,
            keyword_messages,
            summaries,
        )

    @staticmethod
    def _fuse_messages(
        semantic_messages: list[MessageSearchIndex],
        keyword_messages: list[MessageKeywordSearchResult],
        limit: int,
        rank_constant: int,
    ) -> list[MessageSearchIndex | MessageKeywordSearchResult]:
        scores: dict[UUID, float] = {}
        messages_by_id: dict[
            UUID,
            MessageSearchIndex | MessageKeywordSearchResult,
        ] = {}

        for ranked_messages in (
            semantic_messages,
            keyword_messages,
        ):
            for rank, message in enumerate(
                ranked_messages,
                start=1,
            ):
                message_id = message.message_id

                messages_by_id.setdefault(
                    message_id,
                    message,
                )

                scores[message_id] = (
                    scores.get(message_id, 0.0)
                    + 1.0 / (rank_constant + rank)
                )

        ranked_ids = sorted(
            scores,
            key=lambda message_id: (
                -scores[message_id],
                str(message_id),
            ),
        )

        return [
            messages_by_id[message_id]
            for message_id in ranked_ids[:limit]
        ]

    async def _wait_for_context_cursor(
        self,
        channel_id: UUID,
        context_cursor: MessageCursor,
    ) -> None:
        deadline = (
            monotonic()
            + self._context_wait_timeout_seconds
        )

        while True:
            cursor_exists = (
                await self._message_history_service.contains_cursor(
                    channel_id=channel_id,
                    context_cursor=context_cursor,
                )
            )

            if cursor_exists:
                return

            remaining_seconds = deadline - monotonic()

            if remaining_seconds <= 0:
                raise ConversationContextCatchingUpError(
                    channel_id,
                )

            await asyncio.sleep(
                min(0.1, remaining_seconds),
            )


    @staticmethod
    def _decode_cursor(
        encoded_cursor: str,
    ) -> MessageCursor:
        try:
            return MessageCursor.decode(encoded_cursor)
        except ValueError as exception:
            raise InvalidMessageCursorError() from exception

    @staticmethod
    def _format_messages(
        messages: list[
            Message | MessageSearchIndex | MessageKeywordSearchResult
        ],
        current_user_id: UUID,
    ) -> str:
        if not messages:
            return "No messages found."

        return "\n".join(
            (
                f"{message.message_id} | "
                f"{message.created_at.isoformat()} | "
                f"{'You' if message.author_id == current_user_id else 'Other person'}: "
                f"{message.message_content or '[attachment only]'}"
            )
            for message in messages
        )

    @staticmethod
    def _format_summaries(
        summaries: list[ConversationSummary],
    ) -> str:
        if not summaries:
            return "No historical summaries found."

        return "\n\n".join(
            (
                f"summary_id={summary.summary_id}\n"
                f"Window: {summary.window_start_created_at.isoformat()}"
                f" through {summary.window_end_created_at.isoformat()}\n"
                f"{summary.summary_content}"
            )
            for summary in summaries
        )