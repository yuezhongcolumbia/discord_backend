from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query

from app.api.dependencies.authentication import get_current_user_id
from app.api.dependencies.services import get_message_service
from app.schemas.message import MessageCreate, MessageResponse, MessagePageResponse
from app.services.message_service import MessageService


router = APIRouter(
    prefix="/channels/{channel_id}/messages",
    tags=["messages"],
)


@router.post(
    "",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_message(
    channel_id: UUID,
    message_create: MessageCreate,
    current_user_id: Annotated[
        UUID,
        Depends(get_current_user_id),
    ],
    message_service: Annotated[
        MessageService,
        Depends(get_message_service),
    ],
) -> MessageResponse:
    message = await message_service.create_message(
        channel_id=channel_id,
        author_id=current_user_id,
        message_create=message_create,
    )

    return MessageResponse.model_validate(message)



@router.get(
    "",
    response_model=MessagePageResponse,
    status_code=status.HTTP_200_OK,
)
async def list_messages(
    channel_id: UUID,
    current_user_id: Annotated[
        UUID,
        Depends(get_current_user_id),
    ],
    message_service: Annotated[
        MessageService,
        Depends(get_message_service),
    ],
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
    cursor: Annotated[
        str | None,
        Query(),
    ] = None,
) -> MessagePageResponse:
    page = await message_service.list_messages(
        channel_id=channel_id,
        current_user_id=current_user_id,
        limit=limit,
        cursor=cursor,
    )
    return MessagePageResponse(
        items=[
            MessageResponse.model_validate(message)
            for message in page.items
        ],
        next_cursor=page.next_cursor,
    )