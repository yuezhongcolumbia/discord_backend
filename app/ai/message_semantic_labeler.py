from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from ollama import chat
from pydantic import BaseModel, ConfigDict

from app.domain.message import Message


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class MessageSemanticLabel:
    message_id: UUID
    sentiment: Sentiment
    model_name: str
    labeled_at: datetime


class _SentimentResponse(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    sentiment: Sentiment


class OllamaMessageSemanticLabeler:
    def __init__(
        self,
        model_name: str,
    ) -> None:
        self._model_name = model_name

    def label(
        self,
        message: Message,
    ) -> MessageSemanticLabel:
        response = chat(
            model=self._model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify the sentiment as positive, negative, "
                        "or neutral. Return only valid JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": message.message_content or "",
                },
            ],
            format=_SentimentResponse.model_json_schema(),
            think=False,
            options={
                "temperature": 0,
                "num_predict": 20,
            },
        )

        sentiment_response = _SentimentResponse.model_validate_json(
            response.message.content,
        )

        return MessageSemanticLabel(
            message_id=message.message_id,
            sentiment=sentiment_response.sentiment,
            model_name=self._model_name,
            labeled_at=datetime.now(UTC),
        )