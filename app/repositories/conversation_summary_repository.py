from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.message import Message
from app.models.conversation_summary import ConversationSummary


class ConversationSummaryRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def get_latest_for_channel(
        self,
        channel_id: UUID,
    ) -> ConversationSummary | None:
        statement = (
            select(ConversationSummary)
            .where(
                ConversationSummary.channel_id == channel_id,
            )
            .order_by(
                ConversationSummary.window_end_created_at.desc(),
                ConversationSummary.window_end_message_id.desc(),
            )
            .limit(1)
        )

        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def upsert(
        self,
        summary_id: UUID,
        channel_id: UUID,
        summary_content: str,
        embedding: Sequence[float],
        source_message_ids: Sequence[UUID],
        window_start: Message,
        window_end: Message,
        summary_model_name: str,
    ) -> None:
        if not summary_content.strip():
            raise ValueError(
                "Conversation summary content must not be blank.",
            )

        if (
            window_start.channel_id != channel_id
            or window_end.channel_id != channel_id
        ):
            raise ValueError(
                "Conversation summary window belongs to another channel.",
            )

        statement = (
            insert(ConversationSummary)
            .values(
                summary_id=summary_id,
                channel_id=channel_id,
                summary_content=summary_content,
                embedding=list(embedding),
                source_message_ids=list(source_message_ids),
                window_start_bucket_date=window_start.bucket_date,
                window_start_created_at=window_start.created_at,
                window_start_message_id=window_start.message_id,
                window_end_bucket_date=window_end.bucket_date,
                window_end_created_at=window_end.created_at,
                window_end_message_id=window_end.message_id,
                summary_model_name=summary_model_name,
            )
            .on_conflict_do_update(
                index_elements=[
                    ConversationSummary.channel_id,
                    ConversationSummary.window_end_message_id,
                ],
                set_={
                    "summary_content": summary_content,
                    "embedding": list(embedding),
                    "source_message_ids": list(source_message_ids),
                    "summary_model_name": summary_model_name,
                    "summarized_at": func.now(),
                },
            )
        )

        await self._session.execute(statement)