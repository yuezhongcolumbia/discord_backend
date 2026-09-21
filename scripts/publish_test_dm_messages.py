from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.core.config import settings
from app.domain.message import Message
from app.messaging.kafka import create_kafka_producer
from app.messaging.kafka_message_accepted_publisher import (
    KafkaMessageAcceptedPublisher,
)


CHANNEL_ID = UUID("db7b99f3-d039-4e2b-9a54-e221ac82bfd4")

AUTHOR_A_ID = UUID("11111111-1111-1111-1111-111111111111")
AUTHOR_B_ID = UUID("22222222-2222-2222-2222-222222222222")

TEST_MESSAGES: list[tuple[UUID, str]] = [
    (
        AUTHOR_A_ID,
        "Hey, are we still on for dinner Thursday? "
        "I just want to plan my week.",
    ),
    (
        AUTHOR_B_ID,
        "I think so. This week has been messy, but I should know "
        "more after tomorrow's release.",
    ),
    (
        AUTHOR_A_ID,
        "No problem. I know work has been intense lately.",
    ),
    (
        AUTHOR_B_ID,
        "Thank you. I have been looking forward to seeing you, "
        "I just do not want to promise something and cancel again.",
    ),
    (
        AUTHOR_A_ID,
        "I appreciate that. I guess I felt a little disappointed "
        "because the last two plans changed at the last minute.",
    ),
    (
        AUTHOR_B_ID,
        "That is fair. I am sorry about that. I was dealing with "
        "production issues and did not handle the communication well.",
    ),
    (
        AUTHOR_A_ID,
        "I do not need you to be available all the time. It would "
        "just help if you told me earlier when things are uncertain.",
    ),
    (
        AUTHOR_B_ID,
        "You are right. I thought I was keeping you updated, but I "
        "can see why it felt like you were waiting around for me.",
    ),
    (
        AUTHOR_A_ID,
        "Maybe I am overthinking it. I do not want this to become "
        "a bigger issue than it is.",
    ),
    (
        AUTHOR_B_ID,
        "You are not overthinking it. I care about this, and I do "
        "not want you to feel like an afterthought.",
    ),
    (
        AUTHOR_A_ID,
        "That means a lot. I think I just needed to hear that "
        "instead of guessing what was going on.",
    ),
    (
        AUTHOR_B_ID,
        "I am in the middle of a production call now, but can we "
        "talk properly tonight? I will message you when I am free.",
    ),
]


def main() -> None:
    producer = create_kafka_producer()

    publisher = KafkaMessageAcceptedPublisher(
        producer=producer,
        topic=settings.kafka_message_accepted_topic,
        publish_wait_timeout_seconds=(
            settings.kafka_publish_wait_timeout_seconds
        ),
    )

    conversation_started_at = (
        datetime.now(UTC).replace(microsecond=0)
        - timedelta(minutes=len(TEST_MESSAGES))
    )

    try:
        for index, (
            author_id,
            message_content,
        ) in enumerate(TEST_MESSAGES):
            created_at = (
                conversation_started_at
                + timedelta(minutes=index)
            )

            message = Message(
                channel_id=CHANNEL_ID,
                bucket_date=created_at.date(),
                created_at=created_at,
                message_id=uuid4(),
                author_id=author_id,
                edited_at=None,
                message_content=message_content,
                attachment_ids=[],
            )

            publisher.publish(message)

        print(
            f"Published {len(TEST_MESSAGES)} test messages.",
        )
    finally:
        producer.flush(10)


if __name__ == "__main__":
    main()