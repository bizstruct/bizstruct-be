import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Project

router = APIRouter(prefix="/api", tags=["blocks"])

CANVAS_SECTIONS = {
    "key_partners", "key_activities", "key_resources", "value_propositions",
    "customer_relationships", "channels", "customer_segments",
    "cost_structure", "revenue_streams",
}

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


def _merge_locale(existing: Any, locale: str | None, body: Any) -> Any:
    """
    If locale is given — patch only that slice inside {uk:…, en:…}.
    If no locale — replace the whole value.
    """
    if locale and isinstance(existing, dict):
        return {**existing, locale: body}
    if locale:
        return {locale: body}
    return body


# ── Canvas ───────────────────────────────────────────────────────────────────

@router.get("/canvas/{project_id}")
async def get_canvas(project_id: uuid.UUID, db: DbDep) -> dict:
    project = await _get_project_or_404(project_id, db)
    return _block_response(project_id, "canvasData", project.canvas_data)


@router.put("/canvas/{project_id}")
async def update_canvas(project_id: uuid.UUID, body: dict, db: DbDep) -> dict:
    project = await _get_project_or_404(project_id, db)
    project.canvas_data = body
    flag_modified(project, "canvas_data")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "canvasData", project.canvas_data)


@router.put("/canvas/{project_id}/{section}")
async def reorder_canvas_section(
    project_id: uuid.UUID,
    section: str,
    db: DbDep,
    body: list[Any] = Body(...),
) -> dict:
    if section not in CANVAS_SECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown section: {section}")
    project = await _get_project_or_404(project_id, db)
    canvas = {**(project.canvas_data or {}), section: body}
    project.canvas_data = canvas
    flag_modified(project, "canvas_data")
    await db.commit()
    await db.refresh(project)
    return {"projectId": str(project_id), "section": section, "items": body}


@router.post("/canvas/{project_id}/{section}", status_code=status.HTTP_201_CREATED)
async def add_canvas_item(
    project_id: uuid.UUID,
    section: str,
    body: dict,
    db: DbDep,
) -> dict:
    if section not in CANVAS_SECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown section: {section}")
    project = await _get_project_or_404(project_id, db)
    canvas = project.canvas_data or {}
    item = {"id": str(uuid.uuid4()), "is_ai_generated": False, **body}
    canvas[section] = [*canvas.get(section, []), item]
    project.canvas_data = canvas
    flag_modified(project, "canvas_data")
    await db.commit()
    await db.refresh(project)
    return {"projectId": str(project_id), "section": section, "item": item}


@router.patch("/canvas/{project_id}/{section}/{item_id}")
async def update_canvas_item(
    project_id: uuid.UUID,
    section: str,
    item_id: str,
    body: dict,
    db: DbDep,
) -> dict:
    if section not in CANVAS_SECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown section: {section}")
    project = await _get_project_or_404(project_id, db)
    canvas = project.canvas_data or {}
    items = canvas.get(section, [])
    idx = next((i for i, it in enumerate(items) if it.get("id") == item_id), None)
    if idx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    items[idx] = {**items[idx], **body}
    canvas[section] = items
    project.canvas_data = canvas
    flag_modified(project, "canvas_data")
    await db.commit()
    await db.refresh(project)
    return {"projectId": str(project_id), "section": section, "item": items[idx]}


@router.delete("/canvas/{project_id}/{section}/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_canvas_item(
    project_id: uuid.UUID,
    section: str,
    item_id: str,
    db: DbDep,
) -> None:
    if section not in CANVAS_SECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown section: {section}")
    project = await _get_project_or_404(project_id, db)
    canvas = project.canvas_data or {}
    items = canvas.get(section, [])
    canvas[section] = [it for it in items if it.get("id") != item_id]
    project.canvas_data = canvas
    flag_modified(project, "canvas_data")
    await db.commit()


# ── Empathy Map ───────────────────────────────────────────────────────────────

@router.get("/empathy-map/{project_id}")
async def get_empathy_map(
    project_id: uuid.UUID,
    db: DbDep,
    locale: str = Query(default="uk"),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    return _block_response(project_id, "empathyMap", _resolve_locale(project.empathy_map, locale))


@router.put("/empathy-map/{project_id}")
async def update_empathy_map(
    project_id: uuid.UUID,
    body: dict,
    db: DbDep,
    locale: str = Query(default=None),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    project.empathy_map = _merge_locale(project.empathy_map, locale, body)
    flag_modified(project, "empathy_map")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "empathyMap", _resolve_locale(project.empathy_map, locale or "uk"))


# ── Hypotheses ────────────────────────────────────────────────────────────────

@router.get("/hypotheses/{project_id}")
async def get_hypotheses(
    project_id: uuid.UUID,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)
    return _block_response(project_id, "hypotheses", project.hypotheses)


@router.put("/hypotheses/{project_id}")
async def update_hypotheses(
    project_id: uuid.UUID,
    db: DbDep,
    body: list[Any] = Body(...),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    project.hypotheses = body
    flag_modified(project, "hypotheses")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "hypotheses", project.hypotheses)


@router.patch("/hypotheses/{project_id}")
async def patch_hypotheses(
    project_id: uuid.UUID,
    db: DbDep,
    body: list[Any] | dict[str, Any] = Body(...),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    items = body.get("hypotheses", body) if isinstance(body, dict) else body
    project.hypotheses = items
    flag_modified(project, "hypotheses")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "hypotheses", project.hypotheses)


# ── Pitch ─────────────────────────────────────────────────────────────────────

@router.get("/pitch/{project_id}")
async def get_pitch(
    project_id: uuid.UUID,
    db: DbDep,
    locale: str = Query(default="uk"),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    return _block_response(project_id, "pitch", _resolve_locale(project.pitch, locale))


@router.put("/pitch/{project_id}")
async def update_pitch(
    project_id: uuid.UUID,
    body: dict,
    db: DbDep,
    locale: str = Query(default=None),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    project.pitch = _merge_locale(project.pitch, locale, body)
    flag_modified(project, "pitch")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "pitch", _resolve_locale(project.pitch, locale or "uk"))


@router.patch("/pitch/{project_id}/{pitch_type}/{slide_type}")
async def update_pitch_slide(
    project_id: uuid.UUID,
    pitch_type: str,
    slide_type: str,
    body: dict,
    db: DbDep,
    locale: str = Query(default="uk"),
) -> dict:
    if pitch_type not in ("investor", "client"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="pitch_type must be 'investor' or 'client'")

    project = await _get_project_or_404(project_id, db)
    pitch = project.pitch or {}
    locale_data = pitch.get(locale, {})
    slides = locale_data.get(pitch_type, [])

    idx = next((i for i, s in enumerate(slides) if s.get("type") == slide_type), None)
    if idx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Slide '{slide_type}' not found in {pitch_type} pitch")

    slides[idx] = {**slides[idx], **{k: v for k, v in body.items() if k in ("headline", "content")}}
    locale_data[pitch_type] = slides
    project.pitch = {**pitch, locale: locale_data}
    flag_modified(project, "pitch")
    await db.commit()
    await db.refresh(project)
    return {"projectId": str(project_id), "pitchType": pitch_type, "slide": slides[idx]}


# ── Scenario ──────────────────────────────────────────────────────────────────

@router.get("/scenario/{project_id}")
async def get_scenario(
    project_id: uuid.UUID,
    db: DbDep,
    locale: str = Query(default="uk"),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    return _block_response(project_id, "scenario", _resolve_locale(project.scenario, locale))


@router.put("/scenario/{project_id}")
async def update_scenario(
    project_id: uuid.UUID,
    body: dict,
    db: DbDep,
    locale: str = Query(default=None),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    project.scenario = _merge_locale(project.scenario, locale, body)
    flag_modified(project, "scenario")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "scenario", _resolve_locale(project.scenario, locale or "uk"))


# ── What-If ───────────────────────────────────────────────────────────────────

@router.get("/what-if/{project_id}")
async def get_what_if(
    project_id: uuid.UUID,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)
    return _block_response(project_id, "whatIf", project.what_if)


@router.put("/what-if/{project_id}")
async def update_what_if(
    project_id: uuid.UUID,
    body: dict,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)
    project.what_if = body
    flag_modified(project, "what_if")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "whatIf", project.what_if)


@router.patch("/what-if/{project_id}/{scenario_id}")
async def update_what_if_scenario(
    project_id: uuid.UUID,
    scenario_id: str,
    body: dict,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)

    what_if = project.what_if or {"scenarios": []}
    scenarios = what_if.get("scenarios", [])

    idx = next((i for i, s in enumerate(scenarios) if s.get("id") == scenario_id), None)
    if idx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")

    if body.get("status") == "applied":
        for s in scenarios:
            s["status"] = "draft"

    scenarios[idx] = {**scenarios[idx], **body}
    project.what_if = {**what_if, "scenarios": scenarios}
    flag_modified(project, "what_if")

    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "whatIf", project.what_if)


# ── Architecture ──────────────────────────────────────────────────────────────

@router.get("/architecture/{project_id}")
async def get_architecture(
    project_id: uuid.UUID,
    db: DbDep,
    locale: str = Query(default="uk"),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    return _block_response(project_id, "architecture", _resolve_locale(project.architecture, locale))


@router.put("/architecture/{project_id}")
async def update_architecture(
    project_id: uuid.UUID,
    body: dict,
    db: DbDep,
    locale: str = Query(default=None),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    project.architecture = _merge_locale(project.architecture, locale, body)
    flag_modified(project, "architecture")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "architecture", _resolve_locale(project.architecture, locale or "uk"))


@router.patch("/architecture/{project_id}/epicenter")
async def update_architecture_epicenter(
    project_id: uuid.UUID,
    body: dict,
    db: DbDep,
    locale: str = Query(default="uk"),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    arch = project.architecture or {}
    locale_data = arch.get(locale, {})
    locale_data["epicenter"] = {**locale_data.get("epicenter", {}), **body}
    project.architecture = {**arch, locale: locale_data}
    flag_modified(project, "architecture")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "architecture", _resolve_locale(project.architecture, locale))


@router.patch("/architecture/{project_id}/pattern")
async def update_architecture_pattern(
    project_id: uuid.UUID,
    body: dict,
    db: DbDep,
    locale: str = Query(default="uk"),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    arch = project.architecture or {}
    locale_data = arch.get(locale, {})
    locale_data["pattern"] = {**locale_data.get("pattern", {}), **body}
    project.architecture = {**arch, locale: locale_data}
    flag_modified(project, "architecture")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "architecture", _resolve_locale(project.architecture, locale))
