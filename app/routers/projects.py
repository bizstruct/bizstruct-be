from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.dependencies import CurrentUserDep, ProjectServiceDep
from app.core.openapi import error_responses
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_503_SERVICE_UNAVAILABLE,
    ),
)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(status.HTTP_422_UNPROCESSABLE_ENTITY),
    summary="Create a new project",
)
async def create_project(
    data: ProjectCreate,
    current_user: CurrentUserDep,
    service: ProjectServiceDep,
) -> ProjectResponse:
    """
        Creates a new project owned by the authenticated user.
    """
    project = await service.create(user_id=current_user.id, data=data)
    return ProjectResponse.model_validate(project)


@router.get(
    "",
    response_model=list[ProjectResponse],
    status_code=status.HTTP_200_OK,
    summary="List current user's projects",
)
async def list_projects(
    current_user: CurrentUserDep,
    service: ProjectServiceDep,
    skip: Annotated[int, Query(ge=0, description="Offset items")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Max items per page")] = 50,
) -> Sequence[ProjectResponse]:
    """
        Retrieves paginated projects owned exclusively by the authenticated user.
    """
    projects = await service.list_user_projects(
        current_user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
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
) -> ProjectResponse:
    """
        Retrieves a single project by UUID ensuring ownership.
    """
    project = await service.get_by_id(
        project_id=project_id,
        current_user_id=current_user.id,
    )
    return ProjectResponse.model_validate(project)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
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
) -> ProjectResponse:
    """
        Updates mutable project attributes (title only).

        Any attempt to modify immutable fields triggers 422 extra_forbidden.
    """
    project = await service.update(
        project_id=project_id,
        current_user_id=current_user.id,
        data=data,
    )
    return ProjectResponse.model_validate(project)


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

