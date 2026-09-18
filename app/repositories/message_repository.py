from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from cassandra.cluster import Session as CassandraSession
from cassandra.query import (
    BatchStatement,
    BatchType,
    PreparedStatement,
)
from cassandra.util import Date as CassandraDate

from app.domain.message import Message


class MessageRepository:
    def __init__(
        self,
        session: CassandraSession,
    ) -> None:
        self._session = session

        # ---------- Write statements ----------

        self._insert_message: PreparedStatement = (
            self._session.prepare(
                """
                INSERT INTO messages_by_channel_bucket (
                    channel_id,
                    bucket_date,
                    created_at,
                    message_id,
                    author_id,
                    edited_at,
                    message_content,
                    attachment_ids
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
            )
        )

        self._insert_bucket: PreparedStatement = (
            self._session.prepare(
                """
                INSERT INTO message_buckets_by_channel (
                    channel_id,
                    bucket_date
                )
                VALUES (?, ?)
                """
            )
        )

        self._update_message_sentiment: PreparedStatement = (
            self._session.prepare(
                """
                UPDATE messages_by_channel_bucket
                SET
                    sentiment = ?,
                    sentiment_labeled_at = ?,
                    sentiment_model_name = ?,
                    sentiment_prompt_version = ?
                WHERE channel_id = ?
                  AND bucket_date = ?
                  AND created_at = ?
                  AND message_id = ?
                """
            )
        )

        # ---------- Read statements ----------

        self._select_latest_bucket: PreparedStatement = (
            self._session.prepare(
                """
                SELECT bucket_date
                FROM message_buckets_by_channel
                WHERE channel_id = ?
                LIMIT 1
                """
            )
        )

        self._select_previous_bucket: PreparedStatement = (
            self._session.prepare(
                """
                SELECT bucket_date
                FROM message_buckets_by_channel
                WHERE channel_id = ?
                  AND bucket_date < ?
                LIMIT 1
                """
            )
        )

        self._select_messages: PreparedStatement = (
            self._session.prepare(
                """
                SELECT
                    channel_id,
                    bucket_date,
                    created_at,
                    message_id,
                    author_id,
                    edited_at,
                    sentiment,
                    sentiment_labeled_at,
                    sentiment_model_name,
                    sentiment_prompt_version,
                    message_content,
                    attachment_ids
                FROM messages_by_channel_bucket
                WHERE channel_id = ?
                  AND bucket_date = ?
                LIMIT ?
                """
            )
        )

        self._select_messages_before: PreparedStatement = (
            self._session.prepare(
                """
                SELECT
                    channel_id,
                    bucket_date,
                    created_at,
                    message_id,
                    author_id,
                    edited_at,
                    sentiment,
                    sentiment_labeled_at,
                    sentiment_model_name,
                    sentiment_prompt_version,
                    message_content,
                    attachment_ids
                FROM messages_by_channel_bucket
                WHERE channel_id = ?
                  AND bucket_date = ?
                  AND (created_at, message_id) < (?, ?)
                LIMIT ?
                """
            )
        )

    def save(
        self,
        message: Message,
    ) -> Message:
        batch = BatchStatement(
            batch_type=BatchType.LOGGED,
        )

        batch.add(
            self._insert_message,
            (
                message.channel_id,
                message.bucket_date,
                message.created_at,
                message.message_id,
                message.author_id,
                message.edited_at,
                message.message_content,
                message.attachment_ids,
            ),
        )

        batch.add(
            self._insert_bucket,
            (
                message.channel_id,
                message.bucket_date,
            ),
        )

        self._session.execute(batch)

        return message

    def update_sentiments(
            self,
            messages: list[Message],
    ) -> None:
        futures = [
            self._session.execute_async(
                self._update_message_sentiment,
                (
                    message.sentiment,
                    message.sentiment_labeled_at,
                    message.sentiment_model_name,
                    message.sentiment_prompt_version,
                    message.channel_id,
                    message.bucket_date,
                    message.created_at,
                    message.message_id,
                ),
            )
            for message in messages
        ]

        for future in futures:
            future.result()

    def get_latest_bucket(
        self,
        channel_id: UUID,
    ) -> date | None:
        result = self._session.execute(
            self._select_latest_bucket,
            (channel_id,),
        )

        row = result.one()

        if row is None:
            return None

        return self._to_python_date(row.bucket_date)

    def get_previous_bucket(
        self,
        channel_id: UUID,
        before_bucket_date: date,
    ) -> date | None:
        result = self._session.execute(
            self._select_previous_bucket,
            (
                channel_id,
                before_bucket_date,
            ),
        )

        row = result.one()

        if row is None:
            return None

        return self._to_python_date(row.bucket_date)

    def get_messages(
        self,
        channel_id: UUID,
        bucket_date: date,
        limit: int,
    ) -> list[Message]:
        result = self._session.execute(
            self._select_messages,
            (
                channel_id,
                bucket_date,
                limit,
            ),
        )

        return [
            self._row_to_message(row)
            for row in result
        ]

    def get_messages_before(
        self,
        channel_id: UUID,
        bucket_date: date,
        before_created_at: datetime,
        before_message_id: UUID,
        limit: int,
    ) -> list[Message]:
        result = self._session.execute(
            self._select_messages_before,
            (
                channel_id,
                bucket_date,
                before_created_at,
                before_message_id,
                limit,
            ),
        )

        return [
            self._row_to_message(row)
            for row in result
        ]

    @classmethod
    def _row_to_message(
        cls,
        row: Any,
    ) -> Message:
        return Message(
            channel_id=row.channel_id,
            bucket_date=cls._to_python_date(
                row.bucket_date,
            ),
            created_at=cls._to_utc_datetime(
                row.created_at,
            ),
            message_id=row.message_id,
            author_id=row.author_id,
            edited_at=(
                cls._to_utc_datetime(row.edited_at)
                if row.edited_at is not None
                else None
            ),
            sentiment=row.sentiment,
            sentiment_labeled_at=(
                cls._to_utc_datetime(row.sentiment_labeled_at)
                if row.sentiment_labeled_at is not None
                else None
            ),
            sentiment_model_name=row.sentiment_model_name,
            sentiment_prompt_version=row.sentiment_prompt_version,
            message_content=row.message_content,
            attachment_ids=list(
                row.attachment_ids or [],
            ),
        )

    @staticmethod
    def _to_python_date(
        value: date | CassandraDate,
    ) -> date:
        if isinstance(value, date):
            return value

        return value.date()

    @staticmethod
    def _to_utc_datetime(
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)