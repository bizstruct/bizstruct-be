from typing import Protocol

from uuid import UUID


class QueuePort(Protocol):
    """
        Where the orchestrator sends stage-execution signals to the worker.
    """
    async def enqueue_generation(
        self,
        *,
        project_id: UUID,
        stage_type: str,
        language: str,
        force: bool = False,
        comment: str | None = None,
    ) -> None:
        """
            Enqueue one stage for the worker to process.

            Callers must call this only after their own transaction has
            committed — a message sent for a stage row that isn't visible
            yet to the worker's own connection would send it chasing state
            that doesn't exist.
        """
        ...

    async def request_cancellation(
        self,
        *,
        project_id: UUID,
        stage_type: str,
    ) -> None:
        """
            Ask the worker to interrupt this stage if it is currently running.

            Best-effort: the backend's own state change is the source of
            truth; a late or missed message here changes nothing.
        """
        ...

