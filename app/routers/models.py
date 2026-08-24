import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Project
from app.schemas import CamelModel
from app.servicebus import enqueue_validate

router = APIRouter(prefix="/api/models", tags=["models"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


class ValidateRequest(CamelModel):
    model_id: str
    title: str
    audience: str
    value_proposition: str
    description: str


@router.post("/{project_id}/validate", status_code=status.HTTP_202_ACCEPTED)
async def validate_model(
    project_id: uuid.UUID,
    body: ValidateRequest,
    background_tasks: BackgroundTasks,
    db: DbDep,
) -> dict[str, str]:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    background_tasks.add_task(
        enqueue_validate,
        str(project_id),
        body.model_id,
        {
            "title": body.title,
            "audience": body.audience,
            "value_proposition": body.value_proposition,
            "description": body.description,
        },
    )
    return {"ok": "1"}
