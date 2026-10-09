from redis.asyncio import Redis

from app.core.config import settings


def create_redis_client() -> Redis:
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=(
            settings.redis_socket_connect_timeout_seconds
        ),
        socket_timeout=(
            settings.redis_socket_timeout_seconds
        ),
    )