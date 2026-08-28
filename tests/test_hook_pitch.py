"""POST /api/internal/hook — pitch payload validation against bizstruct_domain."""
from tests.conftest import INTERNAL_HEADERS

_INVESTOR_TYPES = ["hook", "problem", "solution", "traction", "ask"]
_CUSTOMER_TYPES = ["opening", "empathy", "transformation", "social_proof", "invitation"]


def _slide(slide_type: str) -> dict:
    return {
        "type": slide_type,
        "headline": f"Headline {slide_type}",
        "content": f"Sufficiently long slide content for {slide_type} in English",
    }


def _deck(types: list[str]) -> list[dict]:
    return [_slide(t) for t in types]


def _valid_pitch(**overrides) -> dict:
    payload = {"investor": _deck(_INVESTOR_TYPES), "customer": _deck(_CUSTOMER_TYPES)}
    payload.update(overrides)
    return payload


def _hook_body(project_id, data: dict | None, hook_status: str = "success") -> dict:
    return {
        "projectId": str(project_id),
        "block": "pitch",
        "status": hook_status,
        "data": data,
    }


async def test_valid_pitch_hook_succeeds_and_persists(client, project, db_session):
    body = _hook_body(project.id, _valid_pitch())

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 200

    await db_session.refresh(project)
    assert project.pitch is not None
    assert len(project.pitch["investor"]) == 5
    assert len(project.pitch["customer"]) == 5


async def test_client_field_rejected_with_422(client, project, db_session):
    """The audience field is `customer`, not `client` — a payload using the
    old name must be rejected, not silently accepted."""
    payload = _valid_pitch()
    payload["client"] = payload.pop("customer")
    body = _hook_body(project.id, payload)

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.pitch is None


async def test_wrong_investor_order_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_pitch(investor=_deck(list(reversed(_INVESTOR_TYPES)))))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.pitch is None


async def test_too_few_customer_slides_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_pitch(customer=_deck(_CUSTOMER_TYPES[:4])))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.pitch is None


async def test_422_response_body_lists_violations(client, project, db_session):
    body = _hook_body(project.id, _valid_pitch(investor=_deck(_INVESTOR_TYPES[:4])))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, list)
    assert any(err.get("loc") == ["investor"] for err in detail)
