"""GET /api/projects/{id} and /api/internal/projects/{id} type architecture via Architecture."""
from tests.conftest import INTERNAL_HEADERS
from tests.test_hook_architecture import _valid_architecture, _hook_body


async def test_project_response_serializes_architecture_block(client, project_ready_for_architecture, db_session):
    # project_ready_for_architecture, not the bare `project` fixture: see the
    # comment on test_valid_free_freemium_accepted in test_hook_architecture.py.
    p = project_ready_for_architecture
    body = _hook_body(p.id, _valid_architecture())
    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 200

    resp = await client.get(f"/api/projects/{p.id}")
    assert resp.status_code == 200
    arch = resp.json()["architecture"]
    assert arch["epicenter"] == "customer_driven"
    assert arch["pattern_subtype"] == "freemium"
    # Nested Architecture model has no camelCase alias generator of its own —
    # fields stay snake_case even though the rest of ProjectResponse is camelCase.
    assert "epicenter_rationale_uk" in arch


async def test_project_with_no_architecture_yet_returns_null(client, project):
    resp = await client.get(f"/api/projects/{project.id}")
    assert resp.status_code == 200
    assert resp.json()["architecture"] is None
