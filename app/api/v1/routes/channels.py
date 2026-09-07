from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies.authentication import get_current_user_id
from app.api.dependencies.services import get_channel_service
from app.schemas.channel import ChannelCreate, ChannelResponse,ChannelUpdate
from app.services.channel_service import ChannelService


guild_channels_router = APIRouter(
    prefix="/guilds/{guild_id}/channels",
    tags=["channels"],
)

channel_router = APIRouter(
    prefix="/channels",
    tags=["channels"],
)


@guild_channels_router.post(
    "",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    guild_id: UUID,
    channel_create: ChannelCreate,
    current_user_id: Annotated[
        UUID,
        Depends(get_current_user_id),
    ],
    channel_service: Annotated[
        ChannelService,
        Depends(get_channel_service),
    ],
) -> ChannelResponse:
    channel = await channel_service.create_channel(
        guild_id=guild_id,
        channel_create=channel_create,
        current_user_id=current_user_id,
    )

    return ChannelResponse.model_validate(channel)


@guild_channels_router.get(
    "",
    response_model=list[ChannelResponse],
    status_code=status.HTTP_201_CREATED,
)
async def list_channels(
    guild_id: UUID,
    current_user_id: Annotated[
        UUID,
        Depends(get_current_user_id),
    ],
    channel_service: Annotated[
        ChannelService,
        Depends(get_channel_service),
    ],
) -> list[ChannelResponse]:
    channels = await channel_service.list_channels(
        guild_id=guild_id,
        current_user_id=current_user_id,
    )

    return [
        ChannelResponse.model_validate(channel)
        for channel in channels
    ]

@channel_router.patch(
    "/{channel_id}",
    response_model=ChannelResponse,
    status_code=status.HTTP_200_OK,
)
async def rename_channel(
    channel_id: UUID,
    channel_update: ChannelUpdate,
    current_user_id: Annotated[
        UUID,
        Depends(get_current_user_id),
    ],
    channel_service: Annotated[
        ChannelService,
        Depends(get_channel_service),
    ],
) -> ChannelResponse:
    channel = await channel_service.rename_channel(
        channel_id=channel_id,
        channel_update=channel_update,
        current_user_id=current_user_id,
    )

    return ChannelResponse.model_validate(channel)

@channel_router.delete(
    "/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_channel(
    channel_id: UUID,
    current_user_id: Annotated[
        UUID,
        Depends(get_current_user_id),
    ],
    channel_service: Annotated[
        ChannelService,
        Depends(get_channel_service),
    ],
) -> None:
    await channel_service.delete_channel(
        channel_id=channel_id,
        current_user_id=current_user_id,
    )