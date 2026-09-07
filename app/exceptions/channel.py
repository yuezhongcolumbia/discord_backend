from uuid import UUID

class ChannelNotFoundError(Exception):
    def __init__(self, channel_id: UUID) -> None:
        self.channel_id = channel_id
        super().__init__(f"Channel {channel_id} was not found.")