import json
import uuid
from typing import Annotated, Any

from bizstruct_domain.blocks.architecture import Architecture
from bizstruct_domain.blocks.empathy_map import EmpathyMap
from bizstruct_domain.blocks.scenario import Scenario
from bizstruct_domain.blocks.pitch import Pitch
from bizstruct_domain.blocks.hypotheses import Hypotheses
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import ValidationError as DomainValidationError
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
#
# EmpathyMap (bizstruct_domain.blocks.empathy_map.EmpathyMap) stores both
# languages inline per item (text_uk/text_en) — like architecture, unlike the
# {uk: {...}, en: {...}} wrapper the other blocks below still use. So these
# endpoints don't take a `locale` query param and always validate writes
# against the domain model before saving.

def _validate_empathy_map(data: dict) -> EmpathyMap:
    try:
        return EmpathyMap.model_validate(data)
    except DomainValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=json.loads(e.json()),
        )


@router.get("/empathy-map/{project_id}")
async def get_empathy_map(
    project_id: uuid.UUID,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)
    return _block_response(project_id, "empathyMap", project.empathy_map)


@router.put("/empathy-map/{project_id}")
async def update_empathy_map(
    project_id: uuid.UUID,
    body: dict,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)
    validated = _validate_empathy_map(body)
    project.empathy_map = validated.model_dump(mode="json")
    flag_modified(project, "empathy_map")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "empathyMap", project.empathy_map)


# ── Hypotheses ────────────────────────────────────────────────────────────────

# Hypotheses (bizstruct_domain.blocks.hypotheses.Hypotheses) wraps its list
# in a `hypotheses` field. Previously this repo stored/returned a bare list
# here — a real mismatch with the ML hook, which already sent (and this
# column already got, via internal.py) the wrapped {"hypotheses": [...]}
# shape; PATCH's `body.get("hypotheses", body)` fallback was working around
# exactly that inconsistency. GET/PUT/PATCH now all consistently
# store/return {"hypotheses": [...]}, validated against the domain model
# (minimum 5, D/V/F category coverage, id pattern, falsifiable-text length).

def _validate_hypotheses(data: list | dict) -> Hypotheses:
    payload = data if isinstance(data, dict) else {"hypotheses": data}
    try:
        return Hypotheses.model_validate(payload)
    except DomainValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=json.loads(e.json()),
        )


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
    body: list[Any] | dict[str, Any] = Body(...),
) -> dict:
    project = await _get_project_or_404(project_id, db)
    validated = _validate_hypotheses(body)
    project.hypotheses = validated.model_dump(mode="json")
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
    validated = _validate_hypotheses(body)
    project.hypotheses = validated.model_dump(mode="json")
    flag_modified(project, "hypotheses")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "hypotheses", project.hypotheses)


# ── Pitch ─────────────────────────────────────────────────────────────────────
#
# Pitch (bizstruct_domain.blocks.pitch.Pitch) stores both languages inline
# per slide (headline_uk/headline_en, content_uk/content_en) — like
# architecture/empathy_map/scenario, unlike hypotheses below. So these
# endpoints don't take a `locale` query param and always validate writes
# against the domain model before saving. The audience is `customer`, not
# `client` (bizstruct-be previously used `client` here while bizstruct-fe
# already used `customer` — this settles the drift on `customer`, matching
# bizstruct_domain.enums.PitchAudience).

def _validate_pitch(data: dict) -> Pitch:
    try:
        return Pitch.model_validate(data)
    except DomainValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=json.loads(e.json()),
        )


@router.get("/pitch/{project_id}")
async def get_pitch(
    project_id: uuid.UUID,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)
    return _block_response(project_id, "pitch", project.pitch)


@router.put("/pitch/{project_id}")
async def update_pitch(
    project_id: uuid.UUID,
    body: dict,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)
    validated = _validate_pitch(body)
    project.pitch = validated.model_dump(mode="json")
    flag_modified(project, "pitch")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "pitch", project.pitch)


@router.patch("/pitch/{project_id}/{pitch_type}/{slide_type}")
async def update_pitch_slide(
    project_id: uuid.UUID,
    pitch_type: str,
    slide_type: str,
    body: dict,
    db: DbDep,
) -> dict:
    if pitch_type not in ("investor", "customer"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="pitch_type must be 'investor' or 'customer'")

    project = await _get_project_or_404(project_id, db)
    pitch = project.pitch or {}
    slides = list(pitch.get(pitch_type, []))

    idx = next((i for i, s in enumerate(slides) if s.get("type") == slide_type), None)
    if idx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Slide '{slide_type}' not found in {pitch_type} pitch")

    allowed_fields = ("headline_uk", "headline_en", "content_uk", "content_en")
    slides[idx] = {**slides[idx], **{k: v for k, v in body.items() if k in allowed_fields}}
    merged = {**pitch, pitch_type: slides}
    validated = _validate_pitch(merged)
    project.pitch = validated.model_dump(mode="json")
    flag_modified(project, "pitch")
    await db.commit()
    await db.refresh(project)
    updated_slide = next(s for s in project.pitch[pitch_type] if s["type"] == slide_type)
    return {"projectId": str(project_id), "pitchType": pitch_type, "slide": updated_slide}


# ── Scenario ──────────────────────────────────────────────────────────────────
#
# Scenario (bizstruct_domain.blocks.scenario.Scenario) stores both languages
# inline per field (text_uk/text_en etc.) — like architecture and
# empathy_map, unlike pitch/hypotheses below. So these endpoints don't take
# a `locale` query param and always validate writes against the domain
# model before saving.

def _validate_scenario(data: dict) -> Scenario:
    try:
        return Scenario.model_validate(data)
    except DomainValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=json.loads(e.json()),
        )


@router.get("/scenario/{project_id}")
async def get_scenario(
    project_id: uuid.UUID,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)
    return _block_response(project_id, "scenario", project.scenario)


@router.put("/scenario/{project_id}")
async def update_scenario(
    project_id: uuid.UUID,
    body: dict,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)
    validated = _validate_scenario(body)
    project.scenario = validated.model_dump(mode="json")
    flag_modified(project, "scenario")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "scenario", project.scenario)


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
#
# Architecture (bizstruct_domain.blocks.architecture.Architecture) is a flat
# model with both languages inline (epicenter_rationale_uk/_en etc.) — unlike
# every other block here it is NOT stored as {uk: {...}, en: {...}}. So,
# unlike the sibling blocks above, these endpoints don't take a `locale`
# query param and always validate writes against the domain model before
# saving (partial PATCHes included — a merge that leaves the object in an
# invalid state, e.g. pattern=free with no pattern_subtype, is rejected
# rather than silently persisted).

def _validate_architecture(data: dict) -> Architecture:
    try:
        return Architecture.model_validate(data)
    except DomainValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=json.loads(e.json()),
        )


@router.get("/architecture/{project_id}")
async def get_architecture(
    project_id: uuid.UUID,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)
    return _block_response(project_id, "architecture", project.architecture)


@router.put("/architecture/{project_id}")
async def update_architecture(
    project_id: uuid.UUID,
    body: dict,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)
    validated = _validate_architecture(body)
    project.architecture = validated.model_dump(mode="json")
    flag_modified(project, "architecture")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "architecture", project.architecture)


@router.patch("/architecture/{project_id}/epicenter")
async def update_architecture_epicenter(
    project_id: uuid.UUID,
    body: dict,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)
    merged = {**(project.architecture or {}), **body}
    validated = _validate_architecture(merged)
    project.architecture = validated.model_dump(mode="json")
    flag_modified(project, "architecture")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "architecture", project.architecture)


@router.patch("/architecture/{project_id}/pattern")
async def update_architecture_pattern(
    project_id: uuid.UUID,
    body: dict,
    db: DbDep,
) -> dict:
    project = await _get_project_or_404(project_id, db)
    merged = {**(project.architecture or {}), **body}
    validated = _validate_architecture(merged)
    project.architecture = validated.model_dump(mode="json")
    flag_modified(project, "architecture")
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "architecture", project.architecture)
