from uuid import UUID


class ConversationContextCatchingUpError(Exception):
    def __init__(
        self,
        channel_id: UUID,
    ) -> None:
        self.channel_id = channel_id

        super().__init__(
            "Conversation context is still catching up.",
        )