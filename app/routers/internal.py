from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse

from bizstruct_domain import ProjectSnapshot, Stage, StageResult

from app.core.config import settings
from app.core.dependencies import OrchestratorDep, DbSession, StageServiceDep
from app.core.openapi import error_responses
from app.exceptions.base import EntityNotFoundError
from app.exceptions.stage import StageRowNotFound
from app.models.project import Project
from app.schemas.common import ErrorResponse
from app.services.stage import to_wire_row

router = APIRouter(prefix="/internal", tags=["internal"])


async def verify_internal_key(x_api_key: Annotated[str, Header()]) -> None:
    if x_api_key != settings.internal_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


InternalAuth = Annotated[None, Depends(verify_internal_key)]


@router.get(
    "/projects/{project_id}",
    response_model=ProjectSnapshot,
    responses=error_responses(status.HTTP_401_UNAUTHORIZED, status.HTTP_404_NOT_FOUND),
    summary="Snapshot of a project for the worker",
)
async def get_snapshot(
    project_id: UUID,
    _: InternalAuth,
    session: DbSession,
    stage_service: StageServiceDep,
    row: Annotated[str | None, Query(description="Only this row and the transitive closure of its refs")] = None,
) -> ProjectSnapshot:
    """
        The project fields plus its rows. With `row`, only that row and the
        transitive closure of its `refs` (ADR-0011 Q3). Snake_case domain models.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise EntityNotFoundError(entity_name="Project", identifier=str(project_id))

    wire_rows = [to_wire_row(r) for r in await stage_service.get_rows(project_id)]
    if row is not None:
        by_id = {r.id: r for r in wire_rows}
        if row not in by_id:
            raise StageRowNotFound(project_id, row)
        closure: set[str] = set()
        frontier = [row]
        while frontier:
            current = frontier.pop()
            if current in closure or current not in by_id:
                continue
            closure.add(current)
            for ids in by_id[current].refs.values():
                frontier.extend(ids)
        wire_rows = [r for r in wire_rows if r.id in closure]

    return ProjectSnapshot(
        project_id=str(project.id),
        idea=project.idea,
        language=project.language.value,
        enabled_optional=[Stage(value) for value in project.enabled_optional],
        rows=wire_rows,
    )


@router.post(
    "/hook",
    status_code=status.HTTP_200_OK,
    responses={
        **error_responses(
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_409_CONFLICT,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
    },
    summary="Receive the result of a row from the worker",
)
async def stage_hook(
    result: StageResult,
    _: InternalAuth,
    orchestrator: OrchestratorDep,
) -> JSONResponse:
    """
        Applies a StageResult (ADR-0011 Q9): 200 applied or duplicate, 404 unknown
        project or row, 409 stale attempt or the row is no longer running, 422 the
        artifacts fail their schema (the row is moved to ERROR as generation_failed).
    """
    outcome = await orchestrator.apply_result(result.project_id, result)
    if outcome.kind == "invalid":
        payload = ErrorResponse(detail="; ".join(outcome.problems)).model_dump()
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": outcome.kind})
