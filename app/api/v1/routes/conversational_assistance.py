from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies.authentication import (
    get_current_user_id,
)
from app.api.dependencies.services import (
    get_conversational_assistance_service,
)
from app.schemas.conversational_assistance import (
    ConversationalAssistanceRequest,
    ConversationalAssistanceResponse,
)
from app.services.conversational_assistance_service import (
    ConversationalAssistanceService,
)


router = APIRouter(
    prefix="/channels/{channel_id}/conversational-assistance",
    tags=["conversational assistance"],
)


@router.post(
    "",
    response_model=ConversationalAssistanceResponse,
    status_code=status.HTTP_200_OK,
)
async def generate_conversational_assistance(
    channel_id: UUID,
    request: ConversationalAssistanceRequest,
    current_user_id: Annotated[
        UUID,
        Depends(get_current_user_id),
    ],
    conversational_assistance_service: Annotated[
        ConversationalAssistanceService,
        Depends(get_conversational_assistance_service),
    ],
) -> ConversationalAssistanceResponse:
    return await conversational_assistance_service.assist(
        channel_id=channel_id,
        current_user_id=current_user_id,
        request=request,
    )