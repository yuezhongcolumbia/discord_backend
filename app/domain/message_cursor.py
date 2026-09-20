import base64
import binascii
import json
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MessageCursor:
    bucket_date: date
    created_at: datetime
    message_id: UUID

    def encode(self) -> str:
        payload = {
            "bucket_date": self.bucket_date.isoformat(),
            "created_at": self.created_at.isoformat(),
            "message_id": str(self.message_id),
        }

        encoded = base64.urlsafe_b64encode(
            json.dumps(payload).encode("utf-8")
        )

        return encoded.decode("utf-8").rstrip("=")

    @classmethod
    def decode(cls, cursor: str) -> "MessageCursor":
        try:
            padding = "=" * (-len(cursor) % 4)

            payload = json.loads(
                base64.urlsafe_b64decode(
                    cursor + padding
                ).decode("utf-8")
            )

            return cls(
                bucket_date=date.fromisoformat(
                    payload["bucket_date"]
                ),
                created_at=datetime.fromisoformat(
                    payload["created_at"]
                ),
                message_id=UUID(payload["message_id"]),
            )
        except (
            binascii.Error,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise ValueError("Invalid message cursor") from error