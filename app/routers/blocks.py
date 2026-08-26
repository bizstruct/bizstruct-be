import json
import uuid
from typing import Annotated, Any

from bizstruct_domain.blocks.architecture import Architecture
from bizstruct_domain.blocks.empathy_map import EmpathyMap
from bizstruct_domain.blocks.scenario import Scenario
from bizstruct_domain.blocks.pitch import Pitch
from bizstruct_domain.blocks.hypotheses import Hypotheses
from bizstruct_domain.blocks.canvas import Canvas
from bizstruct_domain.blocks.what_if import WhatIf
from bizstruct_domain.enums import CanvasSection
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import ValidationError as DomainValidationError
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Project
from app.schemas import CamelModel

router = APIRouter(prefix="/api", tags=["blocks"])

CANVAS_SECTIONS = {s.value for s in CanvasSection}

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
#
# Canvas (bizstruct_domain.blocks.canvas.Canvas) is the richest CRUD surface
# in the system: add/edit/delete a card, reorder within a section, move a
# card between sections. All five write paths below validate the resulting
# canvas against `Canvas` (not `CanvasGenerated`) before saving — the 2-4
# cards-per-section rule is a generation-time quality bar, not a permanent
# shape restriction on user-edited data (see bizstruct_domain.blocks.canvas's
# module docstring). A user is entitled to add a 5th card or delete down to
# zero.
#
# Known limitation, not fixed here (see task summary): concurrent edits.
# There's no version/ETag on canvas — an optimistic frontend update and an
# in-flight ml hook overwrite can race, and the loser's write is silently
# lost. Out of scope for this task.

def _validate_canvas(data: dict) -> Canvas:
    try:
        return Canvas.model_validate(data)
    except DomainValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=json.loads(e.json()),
        )


def _save_canvas(project: Project, canvas: Canvas) -> dict:
    dumped = canvas.model_dump(mode="json")
    project.canvas = dumped
    flag_modified(project, "canvas")
    return dumped


@router.get("/canvas/{project_id}")
async def get_canvas(project_id: uuid.UUID, db: DbDep) -> dict:
    project = await _get_project_or_404(project_id, db)
    return _block_response(project_id, "canvas", project.canvas)


@router.put("/canvas/{project_id}")
async def update_canvas(project_id: uuid.UUID, body: dict, db: DbDep) -> dict:
    project = await _get_project_or_404(project_id, db)
    validated = _validate_canvas(body)
    _save_canvas(project, validated)
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "canvas", project.canvas)


@router.put("/canvas/{project_id}/{section}")
async def reorder_canvas_section(
    project_id: uuid.UUID,
    section: str,
    db: DbDep,
    body: list[Any] = Body(...),
) -> dict:
    """Replace one section's card list wholesale — the list's order IS the
    cards' display order (see bizstruct_domain.blocks.canvas: no separate
    order/position field), so this doubles as both "reorder within a
    section" and a low-level primitive `move_canvas_card` below builds on."""
    if section not in CANVAS_SECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown section: {section}")
    project = await _get_project_or_404(project_id, db)
    canvas_dict = {**(project.canvas or {}), section: body}
    validated = _validate_canvas(canvas_dict)
    _save_canvas(project, validated)
    await db.commit()
    await db.refresh(project)
    return {"projectId": str(project_id), "section": section, "items": project.canvas[section]}


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
    canvas_dict = project.canvas or {}
    # A user-added card is never AI-generated, regardless of what the
    # request body claims — is_ai_generated always False here.
    item = {**body, "id": str(uuid.uuid4()), "is_ai_generated": False}
    canvas_dict = {**canvas_dict, section: [*canvas_dict.get(section, []), item]}
    validated = _validate_canvas(canvas_dict)
    _save_canvas(project, validated)
    await db.commit()
    await db.refresh(project)
    saved_item = next(it for it in project.canvas[section] if it["id"] == item["id"])
    return {"projectId": str(project_id), "section": section, "item": saved_item}


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
    canvas_dict = project.canvas or {}
    items = list(canvas_dict.get(section, []))
    idx = next((i for i, it in enumerate(items) if it.get("id") == item_id), None)
    if idx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    # Editing a card's content always clears is_ai_generated — the card no
    # longer reflects exactly what the LLM produced, whether or not the
    # request body explicitly touches that field.
    items[idx] = {**items[idx], **body, "is_ai_generated": False}
    canvas_dict = {**canvas_dict, section: items}
    validated = _validate_canvas(canvas_dict)
    _save_canvas(project, validated)
    await db.commit()
    await db.refresh(project)
    saved_item = next(it for it in project.canvas[section] if it["id"] == item_id)
    return {"projectId": str(project_id), "section": section, "item": saved_item}


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
    canvas_dict = project.canvas or {}
    items = canvas_dict.get(section, [])
    canvas_dict = {**canvas_dict, section: [it for it in items if it.get("id") != item_id]}
    # Canvas (not CanvasGenerated) has no per-section minimum, so deleting
    # down to zero cards in a section is valid.
    validated = _validate_canvas(canvas_dict)
    _save_canvas(project, validated)
    await db.commit()


class MoveCanvasItemRequest(CamelModel):
    to_section: str
    to_index: int | None = None


@router.patch("/canvas/{project_id}/{section}/{item_id}/move")
async def move_canvas_item(
    project_id: uuid.UUID,
    section: str,
    item_id: str,
    body: MoveCanvasItemRequest,
    db: DbDep,
) -> dict:
    """Move a card from `section` into `body.to_section`, at `body.to_index`
    (appended to the end if omitted) — the drag&drop-between-sections case
    B3 calls out, which the section-scoped endpoints above can't express
    atomically on their own."""
    if section not in CANVAS_SECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown section: {section}")
    if body.to_section not in CANVAS_SECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown section: {body.to_section}")

    project = await _get_project_or_404(project_id, db)
    canvas_dict = project.canvas or {}
    from_items = list(canvas_dict.get(section, []))
    idx = next((i for i, it in enumerate(from_items) if it.get("id") == item_id), None)
    if idx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    item = from_items.pop(idx)

    if section == body.to_section:
        to_items = from_items
    else:
        to_items = list(canvas_dict.get(body.to_section, []))
    insert_at = len(to_items) if body.to_index is None else max(0, min(body.to_index, len(to_items)))
    to_items.insert(insert_at, item)

    canvas_dict = {**canvas_dict, section: from_items, body.to_section: to_items}
    validated = _validate_canvas(canvas_dict)
    _save_canvas(project, validated)
    await db.commit()
    await db.refresh(project)
    return {
        "projectId": str(project_id),
        "fromSection": section,
        "toSection": body.to_section,
        "item": item,
    }


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
#
# WhatIf (bizstruct_domain.blocks.what_if.WhatIf) is 3 ERRC alternatives, at
# most one `applied`. Unlike every other block above, "applying" here isn't
# just a status flip on this block's own data — it's a write to the
# project's Canvas too (see B2 of the what_if task): eliminate removes a
# card, reduce/raise rewrites one, create adds one. So this is the one
# place in this file where an endpoint under /what-if also mutates
# project.canvas, via the same `_validate_canvas`/`_save_canvas` helpers
# canvas's own endpoints use above.
#
# Rollback: each applied alternative carries a `canvas_snapshot_before` —
# the full Canvas as it was immediately before this alternative was
# applied. This is the simplest of the two options the task named (a
# snapshot-per-alternative vs. a separate canvas-version table): no new
# table/migration, and "undo the one alternative currently in effect" is
# the only rollback case that exists (at most one alternative is ever
# applied at a time), so a full version history isn't needed. The tradeoff
# is that this only supports undoing the CURRENT apply, not an arbitrary
# point in canvas history — acceptable since full canvas versioning
# (If-Match) is explicitly out of scope for this task.
#
# `canvas_snapshot_before` is intentionally NOT part of the
# bizstruct_domain.blocks.what_if.WhatIfAlternative model — it's a
# bizstruct-be persistence/rollback implementation detail, not domain data
# every consumer needs to reason about. It's stripped before validating
# against WhatIf and merged back in before saving (_validate_what_if /
# _save_what_if below), so the domain model stays pure while bizstruct-fe
# still gets it directly on the alternative it belongs to.

def _validate_what_if(data: dict) -> tuple[WhatIf, dict[str, dict]]:
    alternatives = data.get("alternatives", []) if isinstance(data, dict) else []
    snapshots: dict[str, dict] = {}
    stripped = []
    for alt in alternatives:
        alt = dict(alt)
        snapshot = alt.pop("canvas_snapshot_before", None)
        if snapshot is not None and alt.get("id") is not None:
            snapshots[str(alt["id"])] = snapshot
        stripped.append(alt)
    try:
        validated = WhatIf.model_validate({"alternatives": stripped})
    except DomainValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=json.loads(e.json()),
        )
    return validated, snapshots


def _save_what_if(project: Project, validated: WhatIf, snapshots: dict[str, dict]) -> dict:
    dumped = validated.model_dump(mode="json")
    for alt in dumped["alternatives"]:
        snapshot = snapshots.get(alt["id"])
        if snapshot is not None:
            alt["canvas_snapshot_before"] = snapshot
    project.what_if = dumped
    flag_modified(project, "what_if")
    return dumped


def _find_alternative(alternatives: list[dict], alternative_id: uuid.UUID) -> tuple[int, dict]:
    target = str(alternative_id)
    idx = next((i for i, a in enumerate(alternatives) if a.get("id") == target), None)
    if idx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alternative not found")
    return idx, alternatives[idx]


# Applying/reverting an alternative is a canvas write, same as canvas's own
# CRUD endpoints above — and same as those, this file does NOT enforce the
# project.status == "generating" edit-lock server-side (that's a frontend-
# only UI guard; full If-Match versioning is out of scope for this task).
# Adding server-side enforcement only for apply/revert and not for
# update_canvas_item etc. would be a new inconsistency, not a fix — left as
# the same documented gap the rest of this file already has.


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
    validated, snapshots = _validate_what_if(body)
    _save_what_if(project, validated, snapshots)
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "whatIf", project.what_if)


@router.patch("/what-if/{project_id}/{alternative_id}")
async def update_what_if_alternative(
    project_id: uuid.UUID,
    alternative_id: uuid.UUID,
    body: dict,
    db: DbDep,
) -> dict:
    """Edit an alternative's own fields (title/premise/moves/expected_impact
    — anything but `status`). `status` is exclusively managed by the apply/
    revert endpoints below, since a bare status flip here used to be exactly
    the "applied means nothing" bug this task fixes (B2) — allowing it back
    in through PATCH would just reopen it."""
    if "status" in body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status cannot be set via PATCH — use the apply/revert endpoints",
        )
    project = await _get_project_or_404(project_id, db)
    what_if = project.what_if or {"alternatives": []}
    alternatives = list(what_if.get("alternatives", []))
    idx, alt = _find_alternative(alternatives, alternative_id)
    alternatives[idx] = {**alt, **body, "id": alt["id"]}
    validated, snapshots = _validate_what_if({"alternatives": alternatives})
    _save_what_if(project, validated, snapshots)
    await db.commit()
    await db.refresh(project)
    return _block_response(project_id, "whatIf", project.what_if)


@router.post("/what-if/{project_id}/{alternative_id}/apply")
async def apply_what_if_alternative(
    project_id: uuid.UUID,
    alternative_id: uuid.UUID,
    db: DbDep,
) -> dict:
    """Apply an ERRC alternative: mutate the canvas per its moves, mark it
    `applied` (and every other alternative `draft`), save the pre-apply
    canvas as this alternative's rollback snapshot.

    Move -> canvas mapping (see bizstruct_domain.blocks.what_if.ERRCMove):
    - eliminate: remove the card in target_section whose text == move.target
    - reduce/raise: rewrite that card's text to move.new_text
    - create: append a new card with text == move.target

    Matching is an exact text match on the move's `target` against current
    canvas card text — not a fuzzy/best-effort match. If any move's target
    can't be matched (the canvas changed since this alternative was
    generated, or the LLM's target text drifted from the actual card), the
    whole apply is rejected with 422 and the full list of unresolved moves,
    rather than silently applying the moves that DID match and dropping the
    rest — see the what_if task's B2 for why silent best-effort was
    explicitly ruled out.
    """
    project = await _get_project_or_404(project_id, db)

    what_if = project.what_if or {"alternatives": []}
    alternatives = list(what_if.get("alternatives", []))
    idx, alt = _find_alternative(alternatives, alternative_id)
    if alt.get("status") == "applied":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Alternative is already applied")

    canvas = _validate_canvas(project.canvas or {})
    canvas_snapshot = canvas.model_dump(mode="json")
    sections: dict[str, list[dict]] = {k: list(v) for k, v in canvas_snapshot.items()}

    unresolved: list[dict] = []
    for move in alt.get("moves", []):
        section = move["target_section"]
        cards = sections.get(section, [])
        action = move["action"]

        if action == "eliminate":
            match = next((c for c in cards if c["text"] == move["target"]), None)
            if match is None:
                unresolved.append(move)
                continue
            sections[section] = [c for c in cards if c["id"] != match["id"]]
        elif action in ("reduce", "raise"):
            match_idx = next((i for i, c in enumerate(cards) if c["text"] == move["target"]), None)
            if match_idx is None:
                unresolved.append(move)
                continue
            cards[match_idx] = {**cards[match_idx], "text": move["new_text"], "is_ai_generated": True}
        elif action == "create":
            cards.append({"id": str(uuid.uuid4()), "text": move["target"], "is_ai_generated": True})
        else:
            unresolved.append(move)

    if unresolved:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Could not match every move to an existing canvas card. "
                "No changes were applied.",
                "unresolvedMoves": unresolved,
            },
        )

    validated_canvas = _validate_canvas({**(project.canvas or {}), **sections})
    _save_canvas(project, validated_canvas)

    for i, a in enumerate(alternatives):
        if i == idx:
            alternatives[i] = {**a, "status": "applied", "canvas_snapshot_before": canvas_snapshot}
        elif a.get("status") == "applied":
            alternatives[i] = {**a, "status": "draft"}

    validated_wi, snapshots = _validate_what_if({"alternatives": alternatives})
    _save_what_if(project, validated_wi, snapshots)

    await db.commit()
    await db.refresh(project)
    return {"projectId": str(project_id), "whatIf": project.what_if, "canvas": project.canvas}


@router.post("/what-if/{project_id}/{alternative_id}/revert")
async def revert_what_if_alternative(
    project_id: uuid.UUID,
    alternative_id: uuid.UUID,
    db: DbDep,
) -> dict:
    """Undo an applied alternative: restore the canvas to its
    `canvas_snapshot_before`, set the alternative back to `draft`."""
    project = await _get_project_or_404(project_id, db)

    what_if = project.what_if or {"alternatives": []}
    alternatives = list(what_if.get("alternatives", []))
    idx, alt = _find_alternative(alternatives, alternative_id)
    if alt.get("status") != "applied":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Alternative is not applied")
    snapshot = alt.get("canvas_snapshot_before")
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No canvas snapshot recorded for this alternative — cannot revert",
        )

    validated_canvas = _validate_canvas(snapshot)
    _save_canvas(project, validated_canvas)

    alternatives[idx] = {k: v for k, v in alt.items() if k != "canvas_snapshot_before"}
    alternatives[idx]["status"] = "draft"

    validated_wi, snapshots = _validate_what_if({"alternatives": alternatives})
    _save_what_if(project, validated_wi, snapshots)

    await db.commit()
    await db.refresh(project)
    return {"projectId": str(project_id), "whatIf": project.what_if, "canvas": project.canvas}


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
