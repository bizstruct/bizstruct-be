"""Canvas CRUD endpoints — the richest CRUD surface in the system.

All five write operations (add, edit, delete, reorder within a section,
move between sections) are covered, plus the domain-validation and
is_ai_generated-reset invariants from B1/B3.

Bodies use snake_case field names throughout: unlike the CamelModel-based
endpoints elsewhere in this repo, these PUT/POST/PATCH bodies are validated
directly against bizstruct_domain.blocks.canvas.Canvas, which (like
architecture/empathy_map/scenario/pitch) has no camelCase alias_generator
of its own.
"""
_EMPTY_SECTIONS = {
    "key_activities": [], "key_resources": [], "value_propositions": [],
    "customer_relationships": [], "channels": [], "customer_segments": [],
    "cost_structure": [], "revenue_streams": [],
}


async def _seed_canvas(client, project_id):
    body = {
        "key_partners": [{"id": "11111111-1111-1111-1111-111111111111", "text": "First partner card", "is_ai_generated": True}],
        **_EMPTY_SECTIONS,
    }
    resp = await client.put(f"/api/canvas/{project_id}", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_get_canvas_null_for_new_project(client, project):
    resp = await client.get(f"/api/canvas/{project.id}")
    assert resp.status_code == 200
    assert resp.json()["canvas"] is None


async def test_put_canvas_validates_and_persists(client, project):
    data = await _seed_canvas(client, project.id)
    assert len(data["canvas"]["key_partners"]) == 1


async def test_put_canvas_rejects_short_card_text(client, project):
    resp = await client.put(f"/api/canvas/{project.id}", json={
        "key_partners": [{"id": "22222222-2222-2222-2222-222222222222", "text": "Ads", "is_ai_generated": True}],
        **_EMPTY_SECTIONS,
    })
    assert resp.status_code == 422


async def test_add_card_sets_is_ai_generated_false(client, project):
    await _seed_canvas(client, project.id)
    resp = await client.post(
        f"/api/canvas/{project.id}/key_activities",
        json={"text": "A user-added activity card", "is_ai_generated": True},
    )
    assert resp.status_code == 201, resp.text
    item = resp.json()["item"]
    assert item["is_ai_generated"] is False  # forced False regardless of what the request claims
    assert item["text"] == "A user-added activity card"


async def test_add_card_unknown_section_rejected(client, project):
    resp = await client.post(f"/api/canvas/{project.id}/not_a_section", json={"text": "Doesn't matter here"})
    assert resp.status_code == 400


async def test_edit_card_resets_is_ai_generated(client, project):
    data = await _seed_canvas(client, project.id)
    card_id = data["canvas"]["key_partners"][0]["id"]
    assert data["canvas"]["key_partners"][0]["is_ai_generated"] is True

    resp = await client.patch(
        f"/api/canvas/{project.id}/key_partners/{card_id}",
        json={"text": "An edited partner card"},
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["item"]
    assert item["text"] == "An edited partner card"
    assert item["is_ai_generated"] is False  # editing an AI-generated card clears the flag


async def test_edit_nonexistent_card_404(client, project):
    await _seed_canvas(client, project.id)
    resp = await client.patch(
        f"/api/canvas/{project.id}/key_partners/does-not-exist",
        json={"text": "Doesn't matter"},
    )
    assert resp.status_code == 404


async def test_delete_card(client, project):
    data = await _seed_canvas(client, project.id)
    card_id = data["canvas"]["key_partners"][0]["id"]

    resp = await client.delete(f"/api/canvas/{project.id}/key_partners/{card_id}")
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/canvas/{project.id}")
    assert get_resp.json()["canvas"]["key_partners"] == []


async def test_reorder_section(client, project):
    resp = await client.put(f"/api/canvas/{project.id}", json={
        "key_partners": [
            {"id": "33333333-3333-3333-3333-333333333333", "text": "First partner card here", "is_ai_generated": True},
            {"id": "44444444-4444-4444-4444-444444444444", "text": "Second partner card here", "is_ai_generated": True},
        ],
        **_EMPTY_SECTIONS,
    })
    assert resp.status_code == 200
    canvas = resp.json()["canvas"]
    first_id, second_id = canvas["key_partners"][0]["id"], canvas["key_partners"][1]["id"]

    # Reverse the order
    reorder_body = [
        {"id": second_id, "text": "Second partner card here", "is_ai_generated": True},
        {"id": first_id, "text": "First partner card here", "is_ai_generated": True},
    ]
    resp = await client.put(f"/api/canvas/{project.id}/key_partners", json=reorder_body)
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert [it["id"] for it in items] == [second_id, first_id]


async def test_move_card_between_sections(client, project):
    data = await _seed_canvas(client, project.id)
    card_id = data["canvas"]["key_partners"][0]["id"]

    resp = await client.patch(
        f"/api/canvas/{project.id}/key_partners/{card_id}/move",
        json={"toSection": "key_activities"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fromSection"] == "key_partners"
    assert body["toSection"] == "key_activities"

    get_resp = await client.get(f"/api/canvas/{project.id}")
    canvas = get_resp.json()["canvas"]
    assert canvas["key_partners"] == []
    assert len(canvas["key_activities"]) == 1
    assert canvas["key_activities"][0]["id"] == card_id


async def test_move_card_to_unknown_section_rejected(client, project):
    data = await _seed_canvas(client, project.id)
    card_id = data["canvas"]["key_partners"][0]["id"]

    resp = await client.patch(
        f"/api/canvas/{project.id}/key_partners/{card_id}/move",
        json={"toSection": "not_a_section"},
    )
    assert resp.status_code == 400


async def test_more_than_four_cards_in_a_section_allowed_via_crud(client, project):
    """The 2-4 bound is generation-only — CRUD may exceed it."""
    for i in range(5):
        resp = await client.post(
            f"/api/canvas/{project.id}/key_resources",
            json={"text": f"A CRUD-added resource card {i}"},
        )
        assert resp.status_code == 201, resp.text

    get_resp = await client.get(f"/api/canvas/{project.id}")
    assert len(get_resp.json()["canvas"]["key_resources"]) == 5
