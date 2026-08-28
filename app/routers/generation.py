import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from app.block_chain import BLOCK_CHAIN
from app.database import get_db
from app.models import Project
from app.schemas import CamelModel, ProjectResponse
from app.servicebus import enqueue_block

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generation", tags=["generation"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


class GenerationRequest(CamelModel):
    title: str | None = None
    idea: str | None = None
    translation_key: str | None = None
    # Generation language ("uk"/"en"), fixed for the whole project — set by
    # the client from the user's locale at creation time. Not translation_key
    # (that's an unrelated frontend i18n lookup key for demo project titles).
    language: str = "en"


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def generate_project(
    body: GenerationRequest,
    background_tasks: BackgroundTasks,
    db: DbDep,
) -> ProjectResponse:
    project = Project(
        title=body.title or "Новий проєкт",
        idea=body.idea,
        translation_key=body.translation_key,
        language=body.language,
        status="generating",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    project_id = str(project.id)
    first_block = BLOCK_CHAIN[0]
    background_tasks.add_task(enqueue_block, project_id, first_block, False, project.language)

    logger.info("Project %s created, enqueuing first block %s", project_id, first_block)
    return ProjectResponse.model_validate(project)


@router.post("/{project_id}/regenerate", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_models(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbDep,
) -> dict[str, str]:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    project.models_options = None
    project.status = "generating"
    flag_modified(project, "models_options")
    await db.commit()

    background_tasks.add_task(
        enqueue_block, str(project_id), "models_options", True, project.language
    )
    logger.info("Project %s: regenerating models_options (force=True)", project_id)
    return {"ok": "1"}
