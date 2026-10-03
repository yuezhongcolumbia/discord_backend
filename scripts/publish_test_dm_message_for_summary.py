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

# Topics intentionally cross summary-window boundaries.
# Messages include tentative plans, corrections, and unresolved questions.
TEST_MESSAGES: list[tuple[UUID, str]] = [
    (
        AUTHOR_A_ID,
        "Hey",
    ),
    (
        AUTHOR_B_ID,
        "Heyyy. Give me a second, I just spilled coffee on my desk.",
    ),
    (
        AUTHOR_A_ID,
        "lol. Important question: did the laptop survive?",
    ),
    (
        AUTHOR_B_ID,
        "Yes. My dignity did not. Anyway, are we still trying to run "
        "the community workshop next Saturday?",
    ),
    (
        AUTHOR_A_ID,
        "Yep. I was thinking Riverside, maybe 2 to 4. "
        "Just a suggestion though; I have not booked anything.",
    ),
    (
        AUTHOR_B_ID,
        "Hmm. Riverside is $120 and our entire budget is $150. "
        "If equipment costs extra, that gets tight. "
        "Let me ask what is included before we commit.",
    ),
    (
        AUTHOR_A_ID,
        "Makes sense.",
    ),
    (
        AUTHOR_B_ID,
        "Also, how many people signed up? Last time I checked it was nine.",
    ),
    (
        AUTHOR_A_ID,
        "18 now, but six have not confirmed. I would not treat "
        "all 18 as definite attendees yet.",
    ),
    (
        AUTHOR_B_ID,
        "Oh wow. Okay, I will chase confirmations. Gently. "
        "Not the terrifying spreadsheet email I sent last time.",
    ),
    (
        AUTHOR_A_ID,
        "That email had three exclamation marks in the subject lol.",
    ),
    (
        AUTHOR_B_ID,
        "It was a passionate spreadsheet.",
    ),
    (
        AUTHOR_A_ID,
        "I might be able to borrow a projector from work. "
        "I need approval first, so please do not promise people "
        "we have one yet.",
    ),
    (
        AUTHOR_B_ID,
        "Got it. By the way, did you finish the mystery novel?",
    ),
    (
        AUTHOR_A_ID,
        "Nope. Halfway through. If you spoil it, I am cancelling "
        "our friendship, not the workshop.",
    ),
    (
        AUTHOR_B_ID,
        "Haha okay. Riverside replied: Saturday afternoon is taken. "
        "They offered Sunday morning, but I have a family thing Sunday.",
    ),
    (
        AUTHOR_A_ID,
        "Ah, annoying. Then Riverside is out. "
        "The library has a free room Saturday from 3 to 5, "
        "but it only fits 12.",
    ),
    (
        AUTHOR_B_ID,
        "Could we do two sessions?",
    ),
    (
        AUTHOR_A_ID,
        "Maybe, but let us wait for confirmations. Two sessions "
        "would mean changing the content and staying longer. "
        "I do not want us announcing that before we know we need it.",
    ),
    (
        AUTHOR_B_ID,
        "Fair. I will wait.",
    ),
    (
        AUTHOR_A_ID,
        "Also I got approval for the work projector! "
        "So that part is sorted for now.",
    ),
    (
        AUTHOR_B_ID,
        "Nice. Can you send the slides Thursday evening? "
        "I want some time to review them.",
    ),
    (
        AUTHOR_A_ID,
        "Uh, Thursday is release day. Friday at noon is the earliest "
        "I can actually commit to. I could send an unfinished outline "
        "Thursday, but it would not be the final slides.",
    ),
    (
        AUTHOR_B_ID,
        "Wait, I thought you said Thursday last week?",
    ),
    (
        AUTHOR_A_ID,
        "I said I would try. Looking back, that was vague. "
        "Sorry, I should have made the difference clearer. "
        "Can we use Friday noon as the confirmed deadline?",
    ),
    (
        AUTHOR_B_ID,
        "Yeah, that works. I was worried I would get them Friday night "
        "and have no time. Noon is fine. I can review by 6.",
    ),
    (
        AUTHOR_A_ID,
        "Deal. Friday noon from me, review by Friday at 6 from you.",
    ),
    (
        AUTHOR_B_ID,
        "Exactly.",
    ),
    (
        AUTHOR_A_ID,
        "Unrelated: that coffee place is criminally expensive.",
    ),
    (
        AUTHOR_B_ID,
        "Right?? $7 and they spelled my name as Brian. "
        "My name is not even close to Brian.",
    ),
    (
        AUTHOR_A_ID,
        "Anyway, confirmations came in. We are down to 11. "
        "The other seven withdrew or said they cannot attend.",
    ),
    (
        AUTHOR_B_ID,
        "Okay, one session fits then. I will reserve the library "
        "Saturday from 3 to 5.",
    ),
    (
        AUTHOR_A_ID,
        "Yes please. One session, not two.",
    ),
    (
        AUTHOR_B_ID,
        "Booked! They have a screen, but no speakers. "
        "And we must be completely out by 5, not just finish "
        "talking at 5.",
    ),
    (
        AUTHOR_A_ID,
        "I can bring my little speaker. It is enough for speech. "
        "Nobody should expect a concert.",
    ),
    (
        AUTHOR_B_ID,
        "Tragic. I had prepared a 40-minute drum solo.",
    ),
    (
        AUTHOR_A_ID,
        "Denied.",
    ),
    (
        AUTHOR_B_ID,
        "One actual issue: I need to leave at 4:30 for a family "
        "appointment. I can help set up and run registration, "
        "but I cannot stay for cleanup.",
    ),
    (
        AUTHOR_A_ID,
        "Okay, I can take the last half hour and cleanup. "
        "Let us stop presenting at 4:45 so we have 15 minutes "
        "to pack up.",
    ),
    (
        AUTHOR_B_ID,
        "Thank you. I will give you the attendance list before "
        "I leave. Could we meet at 2:30 to set up?",
    ),
    (
        AUTHOR_A_ID,
        "Probably. Let me check my train before I confirm 2:30.",
    ),
    (
        AUTHOR_B_ID,
        "Sure.",
    ),
    (
        AUTHOR_A_ID,
        "The bakery across the street has a $60 minimum for group "
        "orders. I was about to reserve a table for snacks afterward. "
        "Want me to pay the deposit?",
    ),
    (
        AUTHOR_B_ID,
        "Hmm, please hold off. I am not comfortable spending shared "
        "money before both of us agree. Also, I will already have "
        "left, so I cannot join the snacks.",
    ),
    (
        AUTHOR_A_ID,
        "Ah right, forgot about 4:30. Nothing paid or reserved yet. "
        "I will ask whether people even want snacks.",
    ),
    (
        AUTHOR_B_ID,
        "Thanks. I am not against snacks, just surprise expenses.",
    ),
    (
        AUTHOR_A_ID,
        "Understood. We will agree before spending shared money.",
    ),
    (
        AUTHOR_B_ID,
        "Also my car will not start. Great timing 🙃 "
        "I am taking the train Saturday, so I cannot transport equipment.",
    ),
    (
        AUTHOR_A_ID,
        "Oof. I can carry the speaker. But work just withdrew approval "
        "for the projector because another team needs it. "
        "I know I said it was sorted; that has changed.",
    ),
    (
        AUTHOR_B_ID,
        "Ugh. Okay. The library mentioned they lend projectors. "
        "Let me call before we start buying anything.",
    ),
    (
        AUTHOR_A_ID,
        "Please do. I do not want to buy a projector for one afternoon.",
    ),
    (
        AUTHOR_B_ID,
        "Good news: their projector is free and now reserved for us. "
        "They said it takes HDMI. They did not confirm whether "
        "they have a USB-C adapter.",
    ),
    (
        AUTHOR_A_ID,
        "My laptop needs USB-C to HDMI. I think I own an adapter, "
        "but I need to check my bag tonight.",
    ),
    (
        AUTHOR_B_ID,
        "Okay, that is still open then. Please let me know by Friday "
        "at 6 so we have time to borrow one if needed.",
    ),
    (
        AUTHOR_A_ID,
        "Will do. Seven people want snacks, but honestly it seems "
        "simpler if everyone buys their own. No group order?",
    ),
    (
        AUTHOR_B_ID,
        "Agreed. No group order, no deposit, no shared snack expense.",
    ),
    (
        AUTHOR_A_ID,
        "Checked the train. I can be there at 2:40, not 2:30. "
        "Is 20 minutes enough for setup?",
    ),
    (
        AUTHOR_B_ID,
        "Yes. I will arrive at 2:30 and start arranging chairs. "
        "You arrive at 2:40 with the speaker.",
    ),
    (
        AUTHOR_A_ID,
        "Final recap: Saturday, library, 3 to 5, 11 attendees, one "
        "session. Slides Friday noon, your review by 6. You arrive "
        "2:30 and leave 4:30; I arrive 2:40, finish presenting 4:45, "
        "and clean up by 5. Library projector, my speaker, everyone "
        "buys their own snacks. Adapter is the only unresolved item.",
    ),
    (
        AUTHOR_B_ID,
        "Yep, confirmed. And no spoilers about the novel. "
        "I am only on chapter four now.",
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

    # Start yesterday at 23:50 UTC to exercise cross-bucket retrieval.
    conversation_started_at = (
        datetime.now(UTC).replace(
            hour=23,
            minute=50,
            second=0,
            microsecond=0,
        )
        - timedelta(days=1)
    )

    published_count = 0

    try:
        for index, (author_id, content) in enumerate(TEST_MESSAGES):
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
                message_content=content,
                attachment_ids=[],
            )

            publisher.publish(message)
            published_count += 1

            print(
                f"{index + 1:02d}. "
                f"message_id={message.message_id} | "
                f"author_id={message.author_id} | "
                f"bucket_date={message.bucket_date} | "
                f"created_at={message.created_at.isoformat()} | "
                f"content={content}"
            )

        print(f"Published {published_count} test messages.")
    finally:
        producer.flush(10)


if __name__ == "__main__":
    main()