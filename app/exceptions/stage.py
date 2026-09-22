from uuid import UUID

from .base import AppException


class StageNotFound(AppException):
    code: str = "stage_not_found"

    def __init__(self, project_id: UUID, stage_type: str) -> None:
        message = f"Stage '{stage_type}' not found for project '{project_id}'"
        super().__init__(message)


class InvalidStageTransition(AppException):
    code: str = "invalid_stage_transition"

    def __init__(self, current: str, target: str) -> None:
        message = f"Cannot transition stage from '{current}' to '{target}'"
        super().__init__(message)


class StagesAlreadyExist(AppException):
    code: str = "stages_already_exist"

    def __init__(self, project_id: UUID) -> None:
        message = f"Stages already exist for project '{project_id}'"
        super().__init__(message)
