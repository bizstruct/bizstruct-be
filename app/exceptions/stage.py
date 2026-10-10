from uuid import UUID

from .base import AppException, EntityNotFoundError


class StageRowNotFound(EntityNotFoundError):
    code: str = "stage_row_not_found"

    def __init__(self, project_id: UUID, row_id: str) -> None:
        # Skips EntityNotFoundError.__init__ on purpose: it takes one identifier,
        # and a row is only meaningful together with its project.
        AppException.__init__(self, f"Stage row '{row_id}' not found for project '{project_id}'")


class StageConflictError(AppException):
    """
        Base for requests that conflict with the current state of a row (HTTP 409).
    """

    code: str = "stage_conflict"


class InvalidStageTransition(StageConflictError):
    code: str = "invalid_stage_transition"

    def __init__(self, current: str, target: str) -> None:
        message = f"Cannot transition stage from '{current}' to '{target}'"
        super().__init__(message)


class StaleAttempt(StageConflictError):
    code: str = "stale_attempt"

    def __init__(self, row_id: str, status: str) -> None:
        message = f"Stage row '{row_id}' is '{status}' or belongs to another attempt; the result was not applied"
        super().__init__(message)


class StageActionNotAllowed(StageConflictError):
    code: str = "stage_action_not_allowed"

    def __init__(self, action: str, row_id: str, status: str) -> None:
        message = f"Cannot {action} stage row '{row_id}' while it is '{status}'"
        super().__init__(message)
