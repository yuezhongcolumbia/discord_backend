import logging
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.exceptions.channel import ChannelNotFoundError
from app.models.channel_type import ChannelType
from app.repositories.channel_repository import ChannelRepository
from app.repositories.direct_message_repository import (
    DirectMessageRepository,
)

logger = logging.getLogger(__name__)


class AuthorizationService:
    def __init__(
        self,
        channel_repository: ChannelRepository,
        direct_message_repository: DirectMessageRepository,
        redis_client: Redis,
        cache_ttl_seconds: int,
    ) -> None:
        if cache_ttl_seconds < 1:
            raise ValueError(
                "Authorization cache TTL must be positive.",
            )

        self._channel_repository = channel_repository
        self._direct_message_repository = direct_message_repository
        self._redis_client = redis_client
        self._cache_ttl_seconds = cache_ttl_seconds

    async def require_dm_access(
        self,
        channel_id: UUID,
        user_id: UUID,
    ) -> None:
        cache_key = (
            f"authz:dm-access:{channel_id}:{user_id}"
        )

        cached_access = await self._read_cache(cache_key)

        if cached_access == "allow":
            return

        if cached_access == "deny":
            raise ChannelNotFoundError(channel_id)

        allowed = await self._has_dm_access(
            channel_id=channel_id,
            user_id=user_id,
        )

        await self._write_cache(
            cache_key=cache_key,
            allowed=allowed,
        )

        if not allowed:
            raise ChannelNotFoundError(channel_id)

    async def _has_dm_access(
        self,
        channel_id: UUID,
        user_id: UUID,
    ) -> bool:
        channel = (
            await self._channel_repository.get_channel_by_id(
                channel_id,
            )
        )

        if (
            channel is None
            or channel.channel_type != ChannelType.DM
        ):
            return False

        return (
            await self._direct_message_repository.is_participant(
                channel_id=channel_id,
                user_id=user_id,
            )
        )

    async def _read_cache(
        self,
        cache_key: str,
    ) -> str | None:
        try:
            return await self._redis_client.get(cache_key)
        except RedisError:
            logger.warning(
                "Authorization cache read failed; "
                "falling back to PostgreSQL.",
                exc_info=True,
            )
            return None

    async def _write_cache(
        self,
        cache_key: str,
        allowed: bool,
    ) -> None:
        try:
            await self._redis_client.set(
                name=cache_key,
                value="allow" if allowed else "deny",
                ex=self._cache_ttl_seconds,
            )
        except RedisError:
            logger.warning(
                "Authorization cache write failed.",
                exc_info=True,
            )

    async def invalidate_dm_access(
            self,
            channel_id: UUID,
            participant_a_id: UUID,
            participant_b_id: UUID,
    ) -> None:
        cache_keys = [
            f"authz:dm-access:{channel_id}:{participant_a_id}",
            f"authz:dm-access:{channel_id}:{participant_b_id}",
        ]

        try:
            await self._redis_client.delete(*cache_keys)
        except RedisError:
            logger.warning(
                "DM authorization cache invalidation failed.",
                extra={
                    "channel_id": str(channel_id),
                },
                exc_info=True,
            )