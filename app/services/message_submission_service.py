from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.concurrency import run_in_threadpool

from app.domain.message import Message
from app.exceptions.channel import ChannelNotFoundError
from app.exceptions.guild import GuildMembershipRequiredError
from app.messaging.message_publisher import MessagePublisher
from app.repositories.channel_repository import ChannelRepository
from app.repositories.guild_repository import GuildRepository
from app.schemas.message import MessageCreate


class MessageSubmissionService:
    def __init__(
        self,
        channel_repository: ChannelRepository,
        guild_repository: GuildRepository,
        message_publisher: MessagePublisher,
    ) -> None:
        self._channel_repository = channel_repository
        self._guild_repository = guild_repository
        self._message_publisher = message_publisher

    async def create_message(
        self,
        channel_id: UUID,
        author_id: UUID,
        message_create: MessageCreate,
    ) -> Message:
        await self._validate_channel_access(
            channel_id=channel_id,
            user_id=author_id,
        )

        now = datetime.now(UTC)
        now = now.replace(
            microsecond=(now.microsecond // 1000) * 1000,
        )

        message = Message(
            channel_id=channel_id,
            bucket_date=now.date(),
            created_at=now,
            message_id=uuid4(),
            author_id=author_id,
            edited_at=None,
            message_content=message_create.message_content,
            attachment_ids=message_create.attachment_ids,
        )

        await run_in_threadpool(
            self._message_publisher.publish,
            message,
        )

        return message

    async def _validate_channel_access(
        self,
        channel_id: UUID,
        user_id: UUID,
    ) -> None:
        channel = await self._channel_repository.get_channel_by_id(channel_id)
        if channel is None:
            raise ChannelNotFoundError(channel_id)

        membership = await self._guild_repository.get_membership(
            guild_id=channel.guild_id,
            user_id=user_id,
        )
        if membership is None:
            raise GuildMembershipRequiredError(channel.guild_id)