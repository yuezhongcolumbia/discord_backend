from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.concurrency import run_in_threadpool

from app.core.message_cursor import MessageCursor
from app.domain.message import Message
from app.domain.message_page import MessagePage
from app.exceptions.channel import ChannelNotFoundError
from app.exceptions.guild import GuildMembershipRequiredError
from app.exceptions.message import InvalidMessageCursorError
from app.repositories.channel_repository import ChannelRepository
from app.repositories.guild_repository import GuildRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.message import MessageCreate


class MessageService:
    def __init__(
        self,
        channel_repository: ChannelRepository,
        guild_repository: GuildRepository,
        message_repository: MessageRepository,
    ) -> None:
        self._channel_repository = channel_repository
        self._guild_repository = guild_repository
        self._message_repository = message_repository

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
            self._message_repository.save,
            message,
        )

        return message

    async def list_messages(
            self,
            channel_id: UUID,
            current_user_id: UUID,
            limit: int,
            cursor: str | None,
    ) -> MessagePage:
        # Block 1: authorization through PostgreSQL.
        await self._validate_channel_access(
            channel_id=channel_id,
            user_id=current_user_id,
        )

        # Block 2: decode the client's starting position.
        message_cursor = self._decode_cursor(cursor)

        # Block 3: Cassandra driver calls are synchronous, so execute
        # the entire multi-query pagination operation in one worker thread.
        messages = await run_in_threadpool(
            self._collect_messages,
            channel_id,
            limit,
            message_cursor,
        )

        # Block 4: the extra message proves another page exists.
        has_more = len(messages) > limit
        items = messages[:limit]

        next_cursor = None

        if has_more:
            last_message = items[-1]

            next_cursor = MessageCursor(
                bucket_date=last_message.bucket_date,
                created_at=last_message.created_at,
                message_id=last_message.message_id,
            ).encode()

        return MessagePage(
            items=items,
            next_cursor=next_cursor,
        )

    def _collect_messages(
            self,
            channel_id: UUID,
            limit: int,
            message_cursor: MessageCursor | None,
    ) -> list[Message]:
        target_size = limit + 1
        messages: list[Message] = []

        # First request starts at the newest active bucket.
        # Later requests start at the bucket contained in the cursor.
        if message_cursor is None:
            current_bucket = (
                self._message_repository.get_latest_bucket(
                    channel_id=channel_id,
                )
            )
        else:
            current_bucket = message_cursor.bucket_date

        while (
                current_bucket is not None
                and len(messages) < target_size
        ):
            remaining = target_size - len(messages)

            if message_cursor is not None:
                # Continue strictly after/older than the cursor.
                bucket_messages = (
                    self._message_repository.get_messages_before(
                        channel_id=channel_id,
                        bucket_date=current_bucket,
                        before_created_at=message_cursor.created_at,
                        before_message_id=message_cursor.message_id,
                        limit=remaining,
                    )
                )

                # The cursor boundary applies only to its own bucket.
                message_cursor = None
            else:
                # An older bucket is read from its newest message.
                bucket_messages = (
                    self._message_repository.get_messages(
                        channel_id=channel_id,
                        bucket_date=current_bucket,
                        limit=remaining,
                    )
                )

            messages.extend(bucket_messages)

            if len(messages) < target_size:
                current_bucket = (
                    self._message_repository.get_previous_bucket(
                        channel_id=channel_id,
                        before_bucket_date=current_bucket,
                    )
                )

        return messages

    @staticmethod
    def _decode_cursor(
            cursor: str | None,
    ) -> MessageCursor | None:
        if cursor is None:
            return None

        try:
            return MessageCursor.decode(cursor)
        except ValueError as exception:
            raise InvalidMessageCursorError() from exception