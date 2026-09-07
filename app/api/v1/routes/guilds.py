from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status, Response


from app.api.dependencies.authentication import get_current_user_id
from app.api.dependencies.services import get_guild_service
from app.schemas.guild import GuildCreate, GuildResponse, GuildMembershipResponse
from app.services.guild_service import GuildService


router = APIRouter(
    prefix="/guilds",
    tags=["guilds"],
)


@router.post(
    "",
    response_model=GuildResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_guild(
    guild_create: GuildCreate,
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    guild_service: Annotated[GuildService, Depends(get_guild_service)],
) -> GuildResponse:

    guild = await guild_service.create_guild(
        guild_create=guild_create,
        owner_id=current_user_id,
    )

    return GuildResponse.model_validate(guild)



@router.put(
    "/{guild_id}/members/me",
    response_model=GuildMembershipResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_201_CREATED: {
            "model": GuildMembershipResponse,
            "description": "The membership was created.",
        },
    },
)
async def join_guild(
    guild_id: UUID,
    response: Response,
    current_user_id: Annotated[
        UUID,
        Depends(get_current_user_id),
    ],
    guild_service: Annotated[
        GuildService,
        Depends(get_guild_service),
    ],
) -> GuildMembershipResponse:
    membership, created = await guild_service.join_guild(
        guild_id=guild_id,
        user_id=current_user_id,
    )
    response.status_code = (
        status.HTTP_201_CREATED
        if created
        else status.HTTP_200_OK
    )
    return GuildMembershipResponse.model_validate(membership)


@router.delete(
    "/{guild_id}/members/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def leave_guild(
    guild_id: UUID,
    current_user_id: Annotated[
        UUID,
        Depends(get_current_user_id),
    ],
    guild_service: Annotated[
        GuildService,
        Depends(get_guild_service),
    ],
) -> None:
    await guild_service.leave_guild(
        guild_id=guild_id,
        user_id=current_user_id,
    )