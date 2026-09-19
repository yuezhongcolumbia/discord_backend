from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from langfuse import Langfuse
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
        langfuse_client: Langfuse | None = None,
    ) -> None:
        self._model_name = model_name
        self._langfuse_client = langfuse_client

    def label(
        self,
        message: Message,
    ) -> MessageSemanticLabel:
        if self._langfuse_client is None:
            return self._label(message)

        with self._langfuse_client.start_as_current_observation(
            as_type="generation",
            name="message-sentiment-labeling",
            model=self._model_name,
            input={
                "message_id": str(message.message_id),
                "message_content": message.message_content,
            },
            metadata={
                "provider": "ollama",
                "temperature": 0,
                "num_predict": 20,
                "thinking_enabled": False,
            },
        ) as generation:
            semantic_label = self._label(message)

            generation.update(
                output={
                    "sentiment": semantic_label.sentiment.value,
                },
            )

            return semantic_label

    def _label(
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