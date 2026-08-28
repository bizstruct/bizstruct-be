"""POST /api/internal/hook — empathy_map payload validation against bizstruct_domain."""
from tests.conftest import INTERNAL_HEADERS


def _item(i: int, text: str | None = None) -> dict:
    return {"id": i, "text": text or f"Sufficiently long English text number {i}"}


def _valid_empathy_map(**overrides) -> dict:
    section = [_item(1), _item(2), _item(3)]
    payload = {s: list(section) for s in ("says", "thinks", "does", "feels", "pains", "gains")}
    payload.update(overrides)
    return payload


def _hook_body(project_id, data: dict | None, hook_status: str = "success") -> dict:
    return {
        "projectId": str(project_id),
        "block": "empathy_map",
        "status": hook_status,
        "data": data,
    }


async def test_valid_empathy_map_hook_succeeds_and_persists(client, project, db_session):
    body = _hook_body(project.id, _valid_empathy_map())

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 200

    await db_session.refresh(project)
    assert project.empathy_map is not None
    assert len(project.empathy_map["says"]) == 3


async def test_too_few_items_in_section_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_empathy_map(says=[_item(1), _item(2)]))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.empathy_map is None


async def test_short_item_text_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_empathy_map(pains=[_item(1, text="No"), _item(2), _item(3)]))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.empathy_map is None


async def test_missing_section_rejected_with_422(client, project, db_session):
    payload = _valid_empathy_map()
    del payload["gains"]
    body = _hook_body(project.id, payload)

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.empathy_map is None


async def test_422_response_body_lists_violations(client, project, db_session):
    body = _hook_body(project.id, _valid_empathy_map(says=[_item(1), _item(2)]))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, list)
    assert any(err.get("loc") == ["says"] for err in detail)
