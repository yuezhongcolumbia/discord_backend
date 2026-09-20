from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_playbook import (
    ConversationPlaybook,
)


class ConversationPlaybookRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    def add(
        self,
        playbook: ConversationPlaybook,
    ) -> None:
        self._session.add(playbook)

    async def find_similar(
        self,
        query_embedding: list[float],
        limit: int,
    ) -> list[ConversationPlaybook]:
        statement = (
            select(ConversationPlaybook)
            .order_by(
                ConversationPlaybook.embedding.cosine_distance(
                    query_embedding,
                )
            )
            .limit(limit)
        )

        result = await self._session.execute(statement)

        return list(result.scalars().all())