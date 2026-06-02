import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Project

router = APIRouter(prefix="/api", tags=["blocks"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


async def _get_project_or_404(project_id: uuid.UUID, db: AsyncSession) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _resolve_locale(data: Any, locale: str) -> Any:
    """If data is stored as {uk: ..., en: ...}, return the requested locale slice."""
    if isinstance(data, dict) and locale in data:
        return data[locale]
    return data


def _block_response(project_id: uuid.UUID, field: str, value: Any) -> dict:
    return {"projectId": str(project_id), field: value}


@router.get("/empathy-map/{project_id}")
async def get_empathy_map(
    project_id: uuid.UUID,
    db: DbDep,
    locale: str = Query(default="uk"),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    data = _resolve_locale(project.empathy_map, locale)
    return _block_response(project_id, "empathyMap", data)


@router.get("/hypotheses/{project_id}")
async def get_hypotheses(
    project_id: uuid.UUID,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)
    return _block_response(project_id, "hypotheses", project.hypotheses)


@router.get("/pitch/{project_id}")
async def get_pitch(
    project_id: uuid.UUID,
    db: DbDep,
    locale: str = Query(default="uk"),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    data = _resolve_locale(project.pitch, locale)
    return _block_response(project_id, "pitch", data)


@router.get("/scenario/{project_id}")
async def get_scenario(
    project_id: uuid.UUID,
    db: DbDep,
    locale: str = Query(default="uk"),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    data = _resolve_locale(project.scenario, locale)
    return _block_response(project_id, "scenario", data)


@router.get("/what-if/{project_id}")
async def get_what_if(
    project_id: uuid.UUID,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)
    return _block_response(project_id, "whatIf", project.what_if)


@router.get("/architecture/{project_id}")
async def get_architecture(
    project_id: uuid.UUID,
    db: DbDep,
    locale: str = Query(default="uk"),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    data = _resolve_locale(project.architecture, locale)
    return _block_response(project_id, "architecture", data)
