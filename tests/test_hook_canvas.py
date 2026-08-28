"""POST /api/internal/hook — canvas payload validation against
bizstruct_domain.

Validated against CanvasGenerated (2-4 cards/section) here — this is
generation output, not a CRUD edit. See test_canvas_crud.py for the looser
Canvas bound CRUD writes are held to instead.
"""
from uuid import uuid4

from tests.conftest import INTERNAL_HEADERS

_SECTIONS = (
    "key_partners", "key_activities", "key_resources", "value_propositions",
    "customer_relationships", "channels", "customer_segments",
    "cost_structure", "revenue_streams",
)


def _card(text: str = "A generated canvas card", **overrides) -> dict:
    card = {"id": str(uuid4()), "text": text, "is_ai_generated": True}
    card.update(overrides)
    return card


def _valid_canvas(cards_per_section: int = 2, **overrides) -> dict:
    payload = {section: [_card() for _ in range(cards_per_section)] for section in _SECTIONS}
    payload.update(overrides)
    return payload


def _hook_body(project_id, data: dict | None, hook_status: str = "success") -> dict:
    return {
        "projectId": str(project_id),
        "block": "canvas",
        "status": hook_status,
        "data": data,
    }


async def test_valid_canvas_hook_succeeds_and_persists(client, project, db_session):
    body = _hook_body(project.id, _valid_canvas())

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 200

    await db_session.refresh(project)
    assert project.canvas is not None
    assert len(project.canvas["key_partners"]) == 2


async def test_too_few_cards_in_a_section_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_canvas(key_partners=[_card()]))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.canvas is None


async def test_too_many_cards_in_a_section_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_canvas(revenue_streams=[_card(), _card(), _card(), _card(), _card()]))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.canvas is None


async def test_short_card_text_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_canvas(channels=[_card("Ads"), _card()]))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.canvas is None


async def test_color_field_rejected_with_422(client, project, db_session):
    """Presentation fields have no place on a domain model — see
    bizstruct-domain's test_no_presentation_fields safeguard."""
    body = _hook_body(project.id, _valid_canvas(key_partners=[_card(color="teal"), _card()]))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.canvas is None


async def test_422_response_body_lists_violations(client, project, db_session):
    body = _hook_body(project.id, _valid_canvas(key_partners=[_card()]))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, list)
    assert any(err.get("loc") == ["key_partners"] for err in detail)
