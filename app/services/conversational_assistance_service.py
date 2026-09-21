import asyncio
from time import monotonic
from uuid import UUID

from fastapi.concurrency import run_in_threadpool

from app.ai.ollama_conversational_assistant import (
    OllamaConversationalAssistant,
)
from app.ai.ollama_text_embedder import OllamaTextEmbedder
from app.domain.message_cursor import MessageCursor
from app.domain.message import Message
from app.exceptions.channel import ChannelNotFoundError
from app.exceptions.conversational_assistance import (
    ConversationContextCatchingUpError,
)
from app.exceptions.message import InvalidMessageCursorError
from app.models.channel_type import ChannelType
from app.repositories.channel_repository import ChannelRepository
from app.repositories.conversation_playbook_repository import (
    ConversationPlaybookRepository,
)
from app.repositories.direct_message_repository import (
    DirectMessageRepository,
)
from app.schemas.conversational_assistance import (
    ConversationalAssistanceRequest,
    ConversationalAssistanceResponse,
)
from app.services.message_history_service import (
    MessageHistoryService,
)


class ConversationalAssistanceService:
    # Loads verified DM context, retrieves relevant playbooks,
    # and generates structured conversational assistance.
    def __init__(
        self,
        channel_repository: ChannelRepository,
        direct_message_repository: DirectMessageRepository,
        message_history_service: MessageHistoryService,
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
        # 1. Load recent DM messages after verifying the client cursor.
        # 2. Embed the draft and context to retrieve relevant playbooks.
        # 3. Send the draft, context, and playbooks to Qwen for assistance.
        messages = await self.get_context_messages(
            channel_id=channel_id,
            current_user_id=current_user_id,
            context_through_cursor=(
                request.context_through_cursor
            ),
        )

        retrieval_query = self._build_retrieval_query(
            draft=request.draft,
            messages=messages,
        )

        query_embedding = await run_in_threadpool(
            self._text_embedder.embed,
            retrieval_query,
        )

        playbooks = await self._playbook_repository.find_similar(
            query_embedding=query_embedding,
            limit=self._playbook_limit,
        )

        return await run_in_threadpool(
            self._conversational_assistant.assist,
            draft=request.draft,
            messages=messages,
            playbooks=playbooks,
            current_user_id=current_user_id,
        )

    async def get_context_messages(
        self,
        channel_id: UUID,
        current_user_id: UUID,
        context_through_cursor: str,
    ) -> list[Message]:
        await self._validate_dm_access(
            channel_id=channel_id,
            user_id=current_user_id,
        )

        expected_cursor = self._decode_cursor(
            context_through_cursor,
        )

        deadline = (
            monotonic()
            + self._context_wait_timeout_seconds
        )

        while True:
            messages = (
                await self._message_history_service
                .get_recent_messages(
                    channel_id=channel_id,
                    current_user_id=current_user_id,
                    limit=self._context_message_limit,
                )
            )

            if self._contains_cursor(
                messages=messages,
                expected_cursor=expected_cursor,
            ):
                return messages

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
    def _contains_cursor(
        messages: list[Message],
        expected_cursor: MessageCursor,
    ) -> bool:
        return any(
            message.bucket_date == expected_cursor.bucket_date
            and message.created_at == expected_cursor.created_at
            and message.message_id == expected_cursor.message_id
            for message in messages
        )

    @staticmethod
    def _build_retrieval_query(
        draft: str,
        messages: list[Message],
    ) -> str:
        conversation_context = "\n".join(
            message.message_content or "[attachment only]"
            for message in messages
        )

        return (
            f"Draft:\n{draft}\n\n"
            f"Recent conversation:\n{conversation_context}"
        )