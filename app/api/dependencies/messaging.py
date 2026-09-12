from fastapi import Request

from app.messaging.message_publisher import MessagePublisher


def get_message_publisher(
    request: Request,
) -> MessagePublisher:
    return request.app.state.message_publisher