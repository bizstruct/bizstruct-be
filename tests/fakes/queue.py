from bizstruct_domain import QueueMessage


class FakeQueue:
    """In-memory QueuePort double: records messages instead of sending them."""

    def __init__(self) -> None:
        self.messages: list[QueueMessage] = []
        self.control_messages: list[dict] = []
        self.fail_next_enqueue: bool = False

    async def enqueue(self, message: QueueMessage) -> None:
        if self.fail_next_enqueue:
            self.fail_next_enqueue = False
            raise RuntimeError("simulated queue failure")
        self.messages.append(message)

    async def request_cancellation(self, **kwargs) -> None:
        self.control_messages.append(kwargs)

    def row_ids(self) -> list[str]:
        return [m.targets[0].stage_row_id for m in self.messages]
