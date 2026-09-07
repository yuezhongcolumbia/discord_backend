from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from app.exceptions.channel import ChannelNotFoundError
from app.exceptions.guild import GuildNotFoundError, OwnerCannotLeaveGuildError, GuildOwnerRequiredError, \
    GuildMembershipRequiredError
from app.exceptions.message import InvalidMessageCursorError


async def handle_guild_not_found(
    _request: Request,
    exception: GuildNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": str(exception),
        },
    )

async def handle_owner_cannot_leave_guild(
    _request: Request,
    exception: OwnerCannotLeaveGuildError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": str(exception),
        },
    )
async def handle_guild_owner_required(
    _request: Request,
    exception: GuildOwnerRequiredError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exception)},
    )

async def handle_guild_membership_required(
    _request: Request,
    exception: GuildMembershipRequiredError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exception)},
    )

async def handle_channel_not_found(
    _request: Request,
    exception: ChannelNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exception)},
    )

async def handle_invalid_message_cursor(
    request: Request,
    exception: InvalidMessageCursorError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": str(exception),
        },
    )




def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        GuildNotFoundError,
        handle_guild_not_found,
    )
    app.add_exception_handler(
        OwnerCannotLeaveGuildError,
        handle_owner_cannot_leave_guild,
    )
    app.add_exception_handler(
        GuildOwnerRequiredError,
        handle_guild_owner_required,
    )
    app.add_exception_handler(
        GuildMembershipRequiredError,
        handle_guild_membership_required,
    )
    app.add_exception_handler(
        ChannelNotFoundError,
        handle_channel_not_found,
    )
    app.add_exception_handler(
        InvalidMessageCursorError,
        handle_invalid_message_cursor
    )