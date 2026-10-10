from bizstruct_domain import StageEvent


class FakeEvents:
    """In-memory EventPort double: records the published events."""

    def __init__(self) -> None:
        self.events: list[StageEvent] = []

    async def publish(self, event: StageEvent) -> None:
        self.events.append(event)
