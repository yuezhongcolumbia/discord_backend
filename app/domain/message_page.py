from dataclasses import dataclass

from app.domain.message import Message


@dataclass(frozen=True, slots=True)
class MessagePage:
    items: list[Message]
    next_cursor: str | None