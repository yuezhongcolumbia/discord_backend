from uuid import UUID

from fastapi.concurrency import run_in_threadpool

from app.core.message_cursor import MessageCursor
from app.domain.message import Message
from app.domain.message_page import MessagePage
from app.exceptions.channel import ChannelNotFoundError
from app.exceptions.guild import (
    GuildMembershipRequiredError,
)
from app.exceptions.message import (
    InvalidMessageCursorError,
)
from app.models.channel_type import ChannelType
from app.repositories.channel_repository import (
    ChannelRepository,
)
from app.repositories.direct_message_repository import (
    DirectMessageRepository,
)
from app.repositories.guild_repository import (
    GuildRepository,
)
from app.repositories.message_repository import (
    MessageRepository,
)


class MessageHistoryService:
    def __init__(
        self,
        channel_repository: ChannelRepository,
        guild_repository: GuildRepository,
        direct_message_repository: DirectMessageRepository,
        message_repository: MessageRepository,
    ) -> None:
        self._channel_repository = channel_repository
        self._guild_repository = guild_repository
        self._direct_message_repository = (
            direct_message_repository
        )
        self._message_repository = message_repository

    async def _validate_channel_access(
        self,
        channel_id: UUID,
        user_id: UUID,
    ) -> None:
        channel = (
            await self._channel_repository.get_channel_by_id(
                channel_id,
            )
        )
        if channel is None:
            raise ChannelNotFoundError(channel_id)
        if channel.channel_type == ChannelType.DM:
            is_participant = (
                await self._direct_message_repository
                .is_participant(
                    channel_id=channel_id,
                    user_id=user_id,
                )
            )
            if not is_participant:
                raise ChannelNotFoundError(channel_id)
            return

        if channel.guild_id is None:
            raise ChannelNotFoundError(channel_id)

        membership = (
            await self._guild_repository.get_membership(
                guild_id=channel.guild_id,
                user_id=user_id,
            )
        )

        if membership is None:
            raise GuildMembershipRequiredError(
                channel.guild_id,
            )

    async def list_messages(
        self,
        channel_id: UUID,
        current_user_id: UUID,
        limit: int,
        cursor: str | None,
    ) -> MessagePage:
        # 1. Authorize access through PostgreSQL.
        await self._validate_channel_access(
            channel_id=channel_id,
            user_id=current_user_id,
        )

        # 2. Decode the client's starting position.
        message_cursor = self._decode_cursor(
            cursor,
        )

        # 3. Execute the synchronous Cassandra queries
        # in a worker thread.
        messages = await run_in_threadpool(
            self._collect_messages,
            channel_id,
            limit,
            message_cursor,
        )

        # 4. The extra message proves another page exists.
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

        # A first-page request starts at the latest bucket.
        # A later request starts at the cursor's bucket.
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
                bucket_messages = (
                    self._message_repository
                    .get_messages_before(
                        channel_id=channel_id,
                        bucket_date=current_bucket,
                        before_created_at=(
                            message_cursor.created_at
                        ),
                        before_message_id=(
                            message_cursor.message_id
                        ),
                        limit=remaining,
                    )
                )

                # The cursor boundary applies only to
                # the bucket containing the cursor.
                message_cursor = None
            else:
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
                    self._message_repository
                    .get_previous_bucket(
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