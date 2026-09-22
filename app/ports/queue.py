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

