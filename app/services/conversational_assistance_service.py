
import asyncio
from time import monotonic
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from langchain_core.tools import BaseTool, tool
from pydantic import Field

from app.ai.ollama_conversational_assistant import (
    OllamaConversationalAssistant,
)
from app.ai.ollama_text_embedder import OllamaTextEmbedder
from app.domain.message import Message
from app.domain.message_cursor import MessageCursor
from app.exceptions.channel import ChannelNotFoundError
from app.exceptions.conversational_assistance import (
    ConversationContextCatchingUpError,
)
from app.exceptions.message import InvalidMessageCursorError
from app.models import MessageSearchIndex
from app.models.channel_type import ChannelType
from app.repositories.channel_repository import ChannelRepository
from app.repositories.conversation_playbook_repository import (
    ConversationPlaybookRepository,
)
from app.repositories.direct_message_repository import (
    DirectMessageRepository,
)
from app.repositories.message_search_index_repository import (
    MessageSearchIndexRepository,
)
from app.schemas.conversational_assistance import (
    ConversationalAssistanceRequest,
    ConversationalAssistanceResponse,
)
from app.services.message_history_service import (
    MessageHistoryService,
)

# 1. Verifies that the user can access the requested DM channel.
# 2. Waits until Cassandra contains the cursor watermark.
# 3. Creates two server-scoped message retrieval tools:
#    - get_recent_messages reads the newest messages before the cursor.
#    - search_messages embeds an LLM-generated query and searches
#      relevant earlier messages before the cursor.
#    - Both tools use the verified channel, user, and cursor internally;
#      the LLM cannot change their scope.
#    - Both share one message-id collection to deduplicate results and
#      cap the total retrieved context size.
# 4. Retrieves draft-relevant playbooks and runs the assistant.

class ConversationalAssistanceService:

    def __init__(
        self,
        channel_repository: ChannelRepository,
        direct_message_repository: DirectMessageRepository,
        message_history_service: MessageHistoryService,
        message_search_index_repository: MessageSearchIndexRepository,
        playbook_repository: ConversationPlaybookRepository,
        text_embedder: OllamaTextEmbedder,
        conversational_assistant: OllamaConversationalAssistant,
        context_message_limit: int,
        playbook_limit: int,
        context_wait_timeout_seconds: float,
    ) -> None:
        self._channel_repository = channel_repository
        self._direct_message_repository = (
            direct_message_repository
        )
        self._message_history_service = (
            message_history_service
        )
        self._message_search_index_repository = (
            message_search_index_repository
        )
        self._playbook_repository = playbook_repository
        self._text_embedder = text_embedder
        self._conversational_assistant = (
            conversational_assistant
        )
        self._context_message_limit = context_message_limit
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
        await self._validate_dm_access(
            channel_id=channel_id,
            user_id=current_user_id,
        )

        context_cursor = self._decode_cursor(
            request.context_through_cursor,
        )

        await self._wait_for_context_cursor(
            channel_id=channel_id,
            context_cursor=context_cursor,
        )

        playbooks = await self._find_draft_playbooks(
            draft=request.draft,
        )
        message_tools, retrieved_message_ids = (
            self._create_message_tools(
                channel_id=channel_id,
                current_user_id=current_user_id,
            )
        )

        return await self._conversational_assistant.assist(
            draft=request.draft,
            playbooks=playbooks,
            message_tools=message_tools,
            retrieved_message_ids=retrieved_message_ids,
        )

    async def _find_draft_playbooks(
        self,
        draft: str,
    ) -> list:
        draft_embedding = await run_in_threadpool(
            self._text_embedder.embed,
            draft,
        )

        return await self._playbook_repository.find_similar(
            query_embedding=draft_embedding,
            limit=self._playbook_limit,
        )

    def _create_message_tools(
            self,
            channel_id: UUID,
            current_user_id: UUID,
    ) -> tuple[list[BaseTool], set[UUID]]:
        retrieved_message_ids: set[UUID] = set()

        max_messages_per_tool_call = 3

        def remaining_context_limit() -> int:
            return (
                    self._context_message_limit
                    - len(retrieved_message_ids)
            )

        @tool
        async def get_recent_messages() -> str:
            """Retrieve recent messages in this conversation."""

            remaining = remaining_context_limit()

            if remaining <= 0:
                return "Context limit reached."

            messages = (
                await self._message_history_service
                .get_recent_messages(
                    channel_id=channel_id,
                    limit=min(
                        max_messages_per_tool_call,
                        remaining,
                    ),
                )
            )

            new_messages = [
                message
                for message in messages
                if message.message_id not in retrieved_message_ids
            ]

            retrieved_message_ids.update(
                message.message_id
                for message in new_messages
            )

            return self._format_recent_messages(
                new_messages,
                current_user_id,
            )

        @tool
        async def search_messages(
                query: str = Field(
                    min_length=1,
                    max_length=500,
                    description=(
                            "Semantic search query for relevant earlier "
                            "conversation messages."
                    ),
                ),
        ) -> str:
            """Search relevant earlier messages in this conversation."""

            remaining = remaining_context_limit()

            if remaining <= 0:
                return "Context limit reached."

            query_embedding = await run_in_threadpool(
                self._text_embedder.embed,
                query,
            )

            messages = (
                await self._message_search_index_repository
                .find_similar(
                    channel_id=channel_id,
                    query_embedding=query_embedding,
                    limit=min(
                        max_messages_per_tool_call,
                        remaining,
                    ),
                )
            )

            new_messages = [
                message
                for message in messages
                if message.message_id not in retrieved_message_ids
            ]

            retrieved_message_ids.update(
                message.message_id
                for message in new_messages
            )

            return self._format_search_index_messages(
                new_messages,
                current_user_id,
            )

        return [
            get_recent_messages,
            search_messages,
        ], retrieved_message_ids

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

    async def _validate_dm_access(
        self,
        channel_id: UUID,
        user_id: UUID,
    ) -> None:
        channel = (
            await self._channel_repository.get_channel_by_id(
                channel_id,
            )
        )

        if (
            channel is None
            or channel.channel_type != ChannelType.DM
        ):
            raise ChannelNotFoundError(channel_id)

        is_participant = (
            await self._direct_message_repository.is_participant(
                channel_id=channel_id,
                user_id=user_id,
            )
        )

        if not is_participant:
            raise ChannelNotFoundError(channel_id)

    @staticmethod
    def _decode_cursor(
        encoded_cursor: str,
    ) -> MessageCursor:
        try:
            return MessageCursor.decode(encoded_cursor)
        except ValueError as exception:
            raise InvalidMessageCursorError() from exception

    @staticmethod
    def _format_recent_messages(
            messages: list[Message],
            current_user_id: UUID,
    ) -> str:
        if not messages:
            return "No messages found."

        return "\n".join(
            (
                f"{message.message_id} | "
                f"{'You' if message.author_id == current_user_id else 'Other person'}: "
                f"{message.message_content or '[attachment only]'}"
            )
            for message in messages
        )

    @staticmethod
    def _format_search_index_messages(
            messages: list[MessageSearchIndex],
            current_user_id: UUID,
    ) -> str:
        if not messages:
            return "No messages found."

        return "\n".join(
            (
                f"{message.message_id} | "
                f"{'You' if message.author_id == current_user_id else 'Other person'}: "
                f"{message.message_content}"
            )
            for message in messages
        )