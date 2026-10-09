from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.dependencies import CurrentUserDep, OrchestratorDep, ProjectServiceDep, StageServiceDep
from app.core.openapi import error_responses
from app.models.project import Project
from app.schemas.project import ProjectDetail, ProjectSummary, ProjectUpdate
from app.services.project import ProjectService
from app.services.stage import StageService

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_503_SERVICE_UNAVAILABLE,
    ),
)


@router.get(
    "",
    response_model=list[ProjectSummary],
    status_code=status.HTTP_200_OK,
    summary="List current user's projects",
)
async def list_projects(
    current_user: CurrentUserDep,
    service: ProjectServiceDep,
    orchestrator: OrchestratorDep,
    skip: Annotated[int, Query(ge=0, description="Offset items")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Max items per page")] = 50,
) -> Sequence[ProjectSummary]:
    """
        Retrieves paginated projects owned exclusively by the authenticated user.
    """
    projects = await service.list_user_projects(
        current_user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    await orchestrator.expire_stuck([p.id for p in projects])
    statuses = await service.statuses(projects)
    return [ProjectSummary.build(p, statuses[p.id]) for p in projects]


@router.get(
    "/{project_id}",
    response_model=ProjectDetail,
    status_code=status.HTTP_200_OK,
    responses=error_responses(
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
    summary="Get project details by ID",
)
async def get_project(
    project_id: UUID,
    current_user: CurrentUserDep,
    service: ProjectServiceDep,
    stage_service: StageServiceDep,
    orchestrator: OrchestratorDep,
) -> ProjectDetail:
    """
        Retrieves a single project with its rows by UUID, ensuring ownership.

        Reading also runs the lazy watchdog: a row running for longer than the
        stuck timeout becomes an error first.
    """
    project = await service.get_by_id(
        project_id=project_id,
        current_user_id=current_user.id,
    )
    await orchestrator.expire_stuck([project.id])
    return await _detail(service, stage_service, project)


@router.patch(
    "/{project_id}",
    response_model=ProjectSummary,
    status_code=status.HTTP_200_OK,
    responses=error_responses(
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    ),
    summary="Update project title",
)
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    current_user: CurrentUserDep,
    service: ProjectServiceDep,
) -> ProjectSummary:
    """
        Updates mutable project attributes (title only).

        Any attempt to modify immutable fields triggers 422 extra_forbidden.
    """
    project = await service.update(
        project_id=project_id,
        current_user_id=current_user.id,
        data=data,
    )
    statuses = await service.statuses([project])
    return ProjectSummary.build(project, statuses[project.id])


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
    summary="Delete a project",
)
async def delete_project(
    project_id: UUID,
    current_user: CurrentUserDep,
    service: ProjectServiceDep,
) -> None:
    """
        Deletes a project owned by the current user.
    """
    await service.delete(
        project_id=project_id,
        current_user_id=current_user.id,
    )



@router.post(
    "/{project_id}/rows/{row_id}/regenerate",
    response_model=ProjectDetail,
    status_code=status.HTTP_200_OK,
    responses=error_responses(
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
    ),
    summary="Regenerate a row and everything that depends on it",
)
async def regenerate_row(
    project_id: UUID,
    row_id: str,
    current_user: CurrentUserDep,
    service: ProjectServiceDep,
    stage_service: StageServiceDep,
    orchestrator: OrchestratorDep,
) -> ProjectDetail:
    """
        Puts the row and every dependent row back to pending (artifacts cleared,
        row ids kept) and starts whatever is ready. 409 if the row's status does
        not allow regeneration.
    """
    project = await service.get_by_id(project_id=project_id, current_user_id=current_user.id)
    await orchestrator.regenerate(project.id, row_id)
    return await _detail(service, stage_service, project)


@router.post(
    "/{project_id}/rows/{row_id}/approve",
    response_model=ProjectDetail,
    status_code=status.HTTP_200_OK,
    responses=error_responses(
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
    ),
    summary="Approve a row that awaits a decision",
)
async def approve_row(
    project_id: UUID,
    row_id: str,
    current_user: CurrentUserDep,
    service: ProjectServiceDep,
    stage_service: StageServiceDep,
    orchestrator: OrchestratorDep,
) -> ProjectDetail:
    """
        Moves a row awaiting a decision to done, keeping its consistency report,
        and continues the pipeline. 409 if the row is not awaiting a decision.
    """
    project = await service.get_by_id(project_id=project_id, current_user_id=current_user.id)
    await orchestrator.approve(project.id, row_id)
    return await _detail(service, stage_service, project)


async def _detail(service: ProjectService, stage_service: StageService, project: Project) -> ProjectDetail:
    rows = await stage_service.get_rows(project.id)
    statuses = await service.statuses([project])
    return ProjectDetail.build(project, statuses[project.id], rows)
