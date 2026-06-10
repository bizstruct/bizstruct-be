import logging
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Project
from app.pubsub import send_block_ready, send_generation_complete, get_negotiate_url
from app.schemas import CamelModel, ProjectResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["internal"])

DbDep = Annotated[AsyncSession, Depends(get_db)]

BLOCK_FIELDS: frozenset[str] = frozenset({
    "models_options",
    "canvas_data",
    "empathy_map",
    "hypotheses",
    "pitch",
    "scenario",
    "what_if",
    "architecture",
})


async def verify_internal_key(x_api_key: Annotated[str, Header()]) -> None:
    if x_api_key != settings.internal_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


InternalAuth = Annotated[None, Depends(verify_internal_key)]


class HookRequest(CamelModel):
    project_id: uuid.UUID
    block: str
    status: Literal["success", "failed"]
    data: dict[str, Any] | list[Any] | None = None
    error: str | None = None


class NegotiateResponse(CamelModel):
    url: str


@router.get("/negotiate", response_model=NegotiateResponse, tags=["pubsub"])
async def negotiate(project_id: uuid.UUID = Query(...)) -> NegotiateResponse:
    """Return Azure Web PubSub client access URL for the given project group."""
    if not settings.azure_web_pubsub_connection_string:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PubSub not configured",
        )
    url = get_negotiate_url(str(project_id))
    return NegotiateResponse(url=url)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project_internal(
    project_id: uuid.UUID,
    _: InternalAuth,
    db: DbDep,
) -> ProjectResponse:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.post("/hook", status_code=status.HTTP_200_OK)
async def ml_hook(
    body: HookRequest,
    _: InternalAuth,
    db: DbDep,
) -> dict[str, str]:
    if body.block not in BLOCK_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown block: {body.block}",
        )

    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    project_id_str = str(body.project_id)

    if body.status == "success":
        setattr(project, body.block, body.data)
        flag_modified(project, body.block)

        all_filled = all(getattr(project, field) is not None for field in BLOCK_FIELDS)
        if all_filled:
            project.status = "completed"
            logger.info("Project %s completed", project.id)

        await db.commit()
        send_block_ready(project_id_str, body.block, "success")
        if all_filled:
            send_generation_complete(project_id_str, "completed")

    else:
        project.status = "failed"
        logger.warning("Block %s failed for project %s: %s", body.block, project.id, body.error)
        await db.commit()
        send_block_ready(project_id_str, body.block, "failed")
        send_generation_complete(project_id_str, "failed")

    return {"ok": "1"}
