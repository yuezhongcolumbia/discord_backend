class InvalidMessageCursorError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid message cursor.")