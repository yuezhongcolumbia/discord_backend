from fastapi import APIRouter

from app.api.v1.routes import guilds
from app.api.v1.routes.channels import (
    channel_router,
    guild_channels_router,
    dm_channels_router
)
from app.api.v1.routes.messages import router as messages_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.conversational_assistance import router as conversational_assistance_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(guilds.router)
api_router.include_router( guild_channels_router)
api_router.include_router( dm_channels_router)
api_router.include_router( channel_router)
api_router.include_router( messages_router)
api_router.include_router( conversational_assistance_router)
