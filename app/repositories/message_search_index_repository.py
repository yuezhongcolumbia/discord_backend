from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.message import Message
from app.models.message_search_index import MessageSearchIndex


class MessageSearchIndexRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def upsert(
        self,
        message: Message,
        embedding: Sequence[float],
    ) -> None:
        if message.message_content is None:
            raise ValueError(
                "Cannot index a message without text content.",
            )

        statement = (
            insert(MessageSearchIndex)
            .values(
                message_id=message.message_id,
                channel_id=message.channel_id,
                author_id=message.author_id,
                created_at=message.created_at,
                message_content=message.message_content,
                embedding=list(embedding),
            )
            .on_conflict_do_update(
                index_elements=[
                    MessageSearchIndex.message_id,
                ],
                set_={
                    "channel_id": message.channel_id,
                    "author_id": message.author_id,
                    "created_at": message.created_at,
                    "message_content": message.message_content,
                    "embedding": list(embedding),
                    "indexed_at": func.now(),
                },
            )
        )

        await self._session.execute(statement)

    async def find_similar(
            self,
            channel_id: UUID,
            query_embedding: list[float],
            limit: int,
    ) -> list[MessageSearchIndex]:
        statement = (
            select(MessageSearchIndex)
            .where(
                MessageSearchIndex.channel_id == channel_id,
            )
            .order_by(
                MessageSearchIndex.embedding.cosine_distance(
                    query_embedding,
                ),
                MessageSearchIndex.created_at.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(
            statement,
        )

        return list(result.scalars().all())