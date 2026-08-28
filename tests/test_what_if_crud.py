"""What-If CRUD + apply/revert.

Bodies use snake_case field names, like canvas's own CRUD endpoints (see
test_canvas_crud.py) — validated directly against
bizstruct_domain.blocks.what_if.WhatIf, which has no camelCase
alias_generator of its own.
"""
_EMPTY_SECTIONS = {
    "key_activities": [], "key_resources": [], "value_propositions": [],
    "customer_relationships": [], "channels": [], "customer_segments": [],
    "cost_structure": [], "revenue_streams": [],
}


def _move(action: str = "eliminate", section: str = "key_partners", target: str = "First partner card", **overrides) -> dict:
    move = {
        "action": action,
        "target_section": section,
        "target": target,
        "rationale": "Rationale for this move, long enough to pass validation.",
    }
    if action in ("reduce", "raise"):
        move.setdefault("new_text", "Regional logistics partner, smaller contract")
    move.update(overrides)
    return move


def _alternative(alt_id: str, status: str = "draft", moves: list[dict] | None = None) -> dict:
    return {
        "id": alt_id,
        "title": "Direct delivery",
        "premise": "Remove logistics intermediaries.",
        "moves": moves or [_move("eliminate"), _move("reduce"), _move("raise")],
        "expected_impact": "Lower delivery cost.",
        "status": status,
    }


def _three_alternatives(overrides: dict[int, dict] | None = None) -> list[dict]:
    ids = [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
        "33333333-3333-3333-3333-333333333333",
    ]
    alts = [_alternative(i) for i in ids]
    for idx, patch in (overrides or {}).items():
        alts[idx] = {**alts[idx], **patch}
    return alts


async def _seed_canvas(client, project_id):
    body = {
        "key_partners": [{"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "text": "First partner card", "is_ai_generated": True}],
        **_EMPTY_SECTIONS,
    }
    resp = await client.put(f"/api/canvas/{project_id}", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["canvas"]


async def _seed_what_if(client, project_id, alternatives=None):
    resp = await client.put(f"/api/what-if/{project_id}", json={"alternatives": alternatives or _three_alternatives()})
    assert resp.status_code == 200, resp.text
    return resp.json()["whatIf"]


async def test_get_what_if_null_for_new_project(client, project):
    resp = await client.get(f"/api/what-if/{project.id}")
    assert resp.status_code == 200
    assert resp.json()["whatIf"] is None


async def test_put_what_if_validates_and_persists(client, project):
    what_if = await _seed_what_if(client, project.id)
    assert len(what_if["alternatives"]) == 3


async def test_put_what_if_rejects_all_create_moves(client, project):
    alts = _three_alternatives({0: {"moves": [_move("create", target="A brand new card")] * 3}})
    resp = await client.put(f"/api/what-if/{project.id}", json={"alternatives": alts})
    assert resp.status_code == 422


async def test_patch_alternative_cannot_set_status(client, project):
    await _seed_what_if(client, project.id)
    resp = await client.patch(
        f"/api/what-if/{project.id}/11111111-1111-1111-1111-111111111111",
        json={"status": "applied"},
    )
    assert resp.status_code == 400


async def test_patch_alternative_edits_premise(client, project):
    await _seed_what_if(client, project.id)
    resp = await client.patch(
        f"/api/what-if/{project.id}/11111111-1111-1111-1111-111111111111",
        json={"premise": "An updated premise long enough to pass validation."},
    )
    assert resp.status_code == 200, resp.text
    alt = next(a for a in resp.json()["whatIf"]["alternatives"] if a["id"] == "11111111-1111-1111-1111-111111111111")
    assert alt["premise"] == "An updated premise long enough to pass validation."


async def test_apply_eliminates_reduces_and_creates_cards(client, project):
    """eliminate the first seeded card, raise (rewrite) the second, create a
    new one in a different section — 3 distinct actions, all resolvable."""
    await _seed_canvas_with_two_cards(client, project.id)
    alts = _three_alternatives({0: {"moves": [
        _move("eliminate", target="First partner card"),
        _move("raise", target="Second partner card", new_text="Second partner card, strengthened"),
        _move("create", "key_activities", "A brand new activity card"),
    ]}})
    await _seed_what_if(client, project.id, alts)

    resp = await client.post(f"/api/what-if/{project.id}/11111111-1111-1111-1111-111111111111/apply")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    canvas = body["canvas"]
    assert [c["text"] for c in canvas["key_partners"]] == ["Second partner card, strengthened"]
    assert len(canvas["key_activities"]) == 1
    assert canvas["key_activities"][0]["text"] == "A brand new activity card"

    what_if = body["whatIf"]
    applied = next(a for a in what_if["alternatives"] if a["id"] == "11111111-1111-1111-1111-111111111111")
    assert applied["status"] == "applied"
    assert applied["canvas_snapshot_before"] is not None
    others = [a for a in what_if["alternatives"] if a["id"] != "11111111-1111-1111-1111-111111111111"]
    assert all(a["status"] == "draft" for a in others)


async def _seed_canvas_with_two_cards(client, project_id):
    body = {
        "key_partners": [
            {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "text": "First partner card", "is_ai_generated": True},
            {"id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "text": "Second partner card", "is_ai_generated": True},
        ],
        **_EMPTY_SECTIONS,
    }
    resp = await client.put(f"/api/canvas/{project_id}", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["canvas"]


async def test_apply_unresolved_target_rejected_with_422_and_no_changes(client, project):
    await _seed_canvas(client, project.id)
    alts = _three_alternatives({0: {"moves": [
        _move("eliminate", target="A card that does not exist on the canvas"),
        _move("create", "key_activities", "A brand new activity card"),
        _move("raise", "key_resources", target="Also does not exist", new_text="n/a"),
    ]}})
    await _seed_what_if(client, project.id, alts)

    resp = await client.post(f"/api/what-if/{project.id}/11111111-1111-1111-1111-111111111111/apply")
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert len(detail["unresolvedMoves"]) == 2

    canvas_resp = await client.get(f"/api/canvas/{project.id}")
    assert len(canvas_resp.json()["canvas"]["key_partners"]) == 1  # untouched


async def test_apply_already_applied_rejected_with_409(client, project):
    await _seed_canvas_with_two_cards(client, project.id)
    alts = _three_alternatives({0: {"moves": [
        _move("eliminate", target="First partner card"),
        _move("raise", target="Second partner card", new_text="Strengthened"),
        _move("create", "key_activities", "A brand new activity card"),
    ]}})
    await _seed_what_if(client, project.id, alts)
    resp = await client.post(f"/api/what-if/{project.id}/11111111-1111-1111-1111-111111111111/apply")
    assert resp.status_code == 200, resp.text

    resp2 = await client.post(f"/api/what-if/{project.id}/11111111-1111-1111-1111-111111111111/apply")
    assert resp2.status_code == 409


async def test_apply_unknown_alternative_404(client, project):
    await _seed_canvas(client, project.id)
    await _seed_what_if(client, project.id)
    resp = await client.post(f"/api/what-if/{project.id}/99999999-9999-9999-9999-999999999999/apply")
    assert resp.status_code == 404


async def test_revert_restores_canvas_and_status(client, project):
    await _seed_canvas_with_two_cards(client, project.id)
    alts = _three_alternatives({0: {"moves": [
        _move("eliminate", target="First partner card"),
        _move("raise", target="Second partner card", new_text="Strengthened"),
        _move("create", "key_activities", "A brand new activity card"),
    ]}})
    await _seed_what_if(client, project.id, alts)
    apply_resp = await client.post(f"/api/what-if/{project.id}/11111111-1111-1111-1111-111111111111/apply")
    assert apply_resp.status_code == 200

    revert_resp = await client.post(f"/api/what-if/{project.id}/11111111-1111-1111-1111-111111111111/revert")
    assert revert_resp.status_code == 200, revert_resp.text
    canvas = revert_resp.json()["canvas"]
    texts = {c["text"] for c in canvas["key_partners"]}
    assert texts == {"First partner card", "Second partner card"}
    assert canvas["key_activities"] == []

    what_if = revert_resp.json()["whatIf"]
    reverted = next(a for a in what_if["alternatives"] if a["id"] == "11111111-1111-1111-1111-111111111111")
    assert reverted["status"] == "draft"
    assert "canvas_snapshot_before" not in reverted or reverted.get("canvas_snapshot_before") is None


async def test_revert_not_applied_rejected_with_409(client, project):
    await _seed_canvas(client, project.id)
    await _seed_what_if(client, project.id)
    resp = await client.post(f"/api/what-if/{project.id}/11111111-1111-1111-1111-111111111111/revert")
    assert resp.status_code == 409
