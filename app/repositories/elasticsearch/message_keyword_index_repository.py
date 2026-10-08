from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from elasticsearch import AsyncElasticsearch

from app.domain.message import Message


@dataclass(frozen=True)
class MessageKeywordSearchResult:
    message_id: UUID
    channel_id: UUID
    author_id: UUID
    created_at: datetime
    message_content: str
    score: float


class MessageKeywordIndexRepository:
    def __init__(
        self,
        client: AsyncElasticsearch,
        index_name: str,
    ) -> None:
        self._client = client
        self._index_name = index_name

    async def upsert(
        self,
        message: Message,
    ) -> None:
        content = message.message_content

        if content is None or not content.strip():
            raise ValueError(
                "Cannot index a message without text content.",
            )

        await self._client.index(
            index=self._index_name,
            id=str(message.message_id),
            document={
                "message_id": str(message.message_id),
                "channel_id": str(message.channel_id),
                "author_id": str(message.author_id),
                "created_at": message.created_at.isoformat(),
                "message_content": content,
            },
        )

    async def find_by_keywords(
        self,
        channel_id: UUID,
        query: str,
        limit: int,
    ) -> list[MessageKeywordSearchResult]:
        if limit < 1:
            raise ValueError(
                "Search limit must be at least one.",
            )

        if not query.strip():
            return []

        response = await self._client.search(
            index=self._index_name,
            size=limit,
            allow_partial_search_results=False,
            query={
                "bool": {
                    "filter": [
                        {
                            "term": {
                                "channel_id": str(channel_id),
                            },
                        },
                    ],
                    "must": [
                        {
                            "match": {
                                "message_content": {
                                    "query": query,
                                    "operator": "or",
                                },
                            },
                        },
                    ],
                },
            },
            sort=[
                {"_score": "desc"},
                {"created_at": "desc"},
                {"message_id": "asc"},
            ],
        )

        return [
            MessageKeywordSearchResult(
                message_id=UUID(hit["_source"]["message_id"]),
                channel_id=UUID(hit["_source"]["channel_id"]),
                author_id=UUID(hit["_source"]["author_id"]),
                created_at=datetime.fromisoformat(
                    hit["_source"]["created_at"],
                ),
                message_content=hit["_source"]["message_content"],
                score=float(hit["_score"]),
            )
            for hit in response["hits"]["hits"]
        ]