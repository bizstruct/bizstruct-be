from typing import Protocol

from bizstruct_domain import StageEvent


class EventPort(Protocol):
    """
        Where the orchestrator announces applied transitions to clients.
    """
    async def publish(self, event: StageEvent) -> None:
        """
            Publish one event. Callers publish only after their transaction has
            committed, and never let a failure here undo the transition.
        """
        ...
