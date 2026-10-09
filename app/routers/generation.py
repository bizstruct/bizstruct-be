from fastapi import APIRouter, status

from app.core.dependencies import CurrentUserDep, OrchestratorDep, ProjectServiceDep, StageServiceDep
from app.core.openapi import error_responses
from app.schemas.project import GenerationRequest, ProjectDetail

router = APIRouter(
    prefix="/generation",
    tags=["generation"],
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_503_SERVICE_UNAVAILABLE,
    ),
)


@router.post(
    "",
    response_model=ProjectDetail,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(status.HTTP_422_UNPROCESSABLE_ENTITY),
    summary="Create a project and start its generation",
)
async def generate_project(
    data: GenerationRequest,
    current_user: CurrentUserDep,
    service: ProjectServiceDep,
    stage_service: StageServiceDep,
    orchestrator: OrchestratorDep,
) -> ProjectDetail:
    """
        Creates a project owned by the authenticated user with its first rows
        (the brief and the enabled optional stages), starts whatever is ready
        and returns the project. The rest of the pipeline advances on its own
        as results arrive.
    """
    project = await service.create(user_id=current_user.id, data=data)
    await orchestrator.start(project)
    rows = await stage_service.get_rows(project.id)
    statuses = await service.statuses([project])
    return ProjectDetail.build(project, statuses[project.id], rows)
