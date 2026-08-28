"""POST /api/internal/hook — what_if payload validation against
bizstruct_domain.

Validated against WhatIfGenerated (every alternative status=draft) here —
this is generation output. See test_what_if_crud.py for apply/revert, which
is where an alternative actually becomes `applied`.
"""
from uuid import uuid4

from tests.conftest import INTERNAL_HEADERS


def _move(action: str = "eliminate", **overrides) -> dict:
    move = {
        "action": action,
        "target_section": "key_partners",
        "target": "Third-party logistics partner",
        "rationale": "Rationale for this move, long enough to pass validation.",
    }
    if action in ("reduce", "raise"):
        move["new_text"] = "Regional logistics partner, smaller contract"
    move.update(overrides)
    return move


def _alternative(status: str = "draft", **overrides) -> dict:
    alt = {
        "id": str(uuid4()),
        "title": "Direct delivery",
        "premise": "Remove logistics intermediaries.",
        "moves": [_move("eliminate"), _move("reduce"), _move("raise")],
        "expected_impact": "Lower delivery cost.",
        "status": status,
    }
    alt.update(overrides)
    return alt


def _valid_what_if(**overrides) -> dict:
    payload = {"alternatives": [_alternative() for _ in range(3)]}
    payload.update(overrides)
    return payload


def _hook_body(project_id, data: dict | None, hook_status: str = "success") -> dict:
    return {
        "projectId": str(project_id),
        "block": "what_if",
        "status": hook_status,
        "data": data,
    }


async def test_valid_what_if_hook_succeeds_and_persists(client, project, db_session):
    body = _hook_body(project.id, _valid_what_if())

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 200

    await db_session.refresh(project)
    assert project.what_if is not None
    assert len(project.what_if["alternatives"]) == 3
    assert all(a["status"] == "draft" for a in project.what_if["alternatives"])


async def test_applied_status_rejected_with_422(client, project, db_session):
    """WhatIfGenerated forbids status=applied — applying is a user decision
    made after generation, not something generation output may claim."""
    alts = [_alternative(), _alternative(), _alternative(status="applied")]
    body = _hook_body(project.id, _valid_what_if(alternatives=alts))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.what_if is None


async def test_all_create_moves_rejected_with_422(client, project, db_session):
    alts = [
        _alternative(moves=[_move("create", target="A brand new card")] * 3),
        _alternative(),
        _alternative(),
    ]
    body = _hook_body(project.id, _valid_what_if(alternatives=alts))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.what_if is None


async def test_reduce_move_missing_new_text_rejected_with_422(client, project, db_session):
    bad_move = _move("reduce")
    del bad_move["new_text"]
    alts = [_alternative(moves=[_move("eliminate"), bad_move, _move("raise")]), _alternative(), _alternative()]
    body = _hook_body(project.id, _valid_what_if(alternatives=alts))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.what_if is None


async def test_only_two_alternatives_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, {"alternatives": [_alternative(), _alternative()]})

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.what_if is None


async def test_icon_field_rejected_with_422(client, project, db_session):
    """Presentation fields have no place on a domain model — see
    bizstruct-domain's test_no_presentation_fields safeguard."""
    bad_move = _move("eliminate")
    bad_move["icon"] = "coins"
    alts = [_alternative(moves=[bad_move, _move("reduce"), _move("raise")]), _alternative(), _alternative()]
    body = _hook_body(project.id, _valid_what_if(alternatives=alts))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.what_if is None
