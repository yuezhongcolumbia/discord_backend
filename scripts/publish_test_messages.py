from datetime import UTC, datetime
from itertools import cycle
from uuid import UUID, uuid4

from app.core.config import settings
from app.domain.message import Message
from app.messaging.kafka import create_kafka_producer
from app.messaging.kafka_message_accepted_publisher import (
    KafkaMessageAcceptedPublisher,
)

CHANNEL_ID = UUID("7316013f-90f9-4e25-9d60-4fb61b8a5348")
AUTHOR_ID = UUID("11111111-1111-1111-1111-111111111111")
MESSAGE_COUNT = 100

TEST_MESSAGES = [
    # Positive
    "Thanks for helping me debug that issue. I really appreciate it.",
    "That was a great idea. The new design looks much cleaner.",
    "I am genuinely excited that the deployment finally worked.",
    "You handled that conversation really well.",
    "I had a wonderful time talking with you today.",
    "Congratulations on getting the offer. You earned it.",
    "This made my day so much better.",
    "I am proud of the progress we made this week.",
    "Your explanation was clear and very helpful.",
    "I am relieved that everything turned out okay.",

    # Negative
    "I am frustrated because this bug keeps coming back.",
    "That comment hurt my feelings more than I expected.",
    "I feel overwhelmed and do not know how to fix this.",
    "I am disappointed that nobody replied to my message.",
    "This is exhausting. I need a break from this project.",
    "I am angry that the deadline changed again.",
    "The meeting was a complete waste of time.",
    "I feel ignored when you do not respond.",
    "I am worried that I made the wrong decision.",
    "This situation is making me anxious.",

    # Neutral
    "The meeting starts at 3 PM tomorrow.",
    "I pushed the latest changes to the feature branch.",
    "The database migration completed successfully.",
    "Can you review the pull request when you have time?",
    "I will be offline for about thirty minutes.",
    "The channel has three active members right now.",
    "Please send the document before Friday.",
    "The Kafka topic currently has three partitions.",
    "I updated the configuration value to ten.",
    "The next sprint planning session is on Monday.",
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

    message_contents = cycle(TEST_MESSAGES)

    try:
        for _ in range(MESSAGE_COUNT):
            now = datetime.now(UTC)

            message = Message(
                channel_id=CHANNEL_ID,
                bucket_date=now.date(),
                created_at=now,
                message_id=uuid4(),
                author_id=AUTHOR_ID,
                edited_at=None,
                message_content=next(message_contents),
                attachment_ids=[],
            )

            publisher.publish(message)

        print(f"Published {MESSAGE_COUNT} test messages.")
    finally:
        producer.flush(10)


if __name__ == "__main__":
    main()