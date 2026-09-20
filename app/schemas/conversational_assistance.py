from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ConversationRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConversationalAssistanceRequest(BaseModel):
    draft: str = Field(
        min_length=1,
        max_length=4_000,
    )
    context_through_cursor: str = Field(
        min_length=1,
    )


class ConversationalAssistanceOption(BaseModel):
    label: str
    draft: str


class ConversationalAssistanceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    risk_level: ConversationRiskLevel
    risk_reason: str
    concerns: list[str]
    options: list[ConversationalAssistanceOption]