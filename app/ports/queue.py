from typing import Protocol

from bizstruct_domain import QueueMessage


class QueuePort(Protocol):
    """
        Where the orchestrator sends stage-execution signals to the worker.
    """
    async def enqueue(self, message: QueueMessage) -> None:
        """
            Enqueue one message for the worker to process. The pipeline sends
            exactly one `RowTarget` per message (ADR-0011 Q5).

            Callers must call this only after their own transaction has
            committed — a message sent for a row that isn't visible
            yet to the worker's own connection would send it chasing state
            that doesn't exist.
        """
        ...

    async def request_cancellation(
        self,
        *,
        project_id: str,
        stage_row_id: str,
    ) -> None:
        """
            Ask the worker to interrupt this row if it is currently running.

            Best-effort: the backend's own state change is the source of
            truth; a late or missed message here changes nothing. ADR-0011
            has no cancellation message, so the Service Bus adapter only logs
            it until the contract gets one.
        """
        ...
