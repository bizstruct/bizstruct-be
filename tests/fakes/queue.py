class FakeQueue:
    """In-memory QueuePort double: records messages instead of sending them."""

    def __init__(self) -> None:
        self.generation_messages: list[dict] = []
        self.control_messages: list[dict] = []
        self.fail_next_enqueue: bool = False

    async def enqueue_generation(self, **kwargs) -> None:
        if self.fail_next_enqueue:
            self.fail_next_enqueue = False
            raise RuntimeError("simulated queue failure")
        self.generation_messages.append(kwargs)

    async def request_cancellation(self, **kwargs) -> None:
        self.control_messages.append(kwargs)
