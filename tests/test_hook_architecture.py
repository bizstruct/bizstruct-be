"""POST /api/internal/hook — architecture payload validation against bizstruct_domain."""
import pytest

from tests.conftest import INTERNAL_HEADERS

RATIONALE_UK = "Достатньо довге обґрунтування українською, щоб пройти перевірку мінімальної довжини поля."
RATIONALE_EN = "A rationale long enough in English to satisfy the field's minimum length validation."


def _valid_architecture(**overrides) -> dict:
    payload = dict(
        epicenter="customer_driven",
        epicenter_rationale_uk=RATIONALE_UK,
        epicenter_rationale_en=RATIONALE_EN,
        pattern="free",
        pattern_subtype="freemium",
        pattern_rationale_uk=RATIONALE_UK,
        pattern_rationale_en=RATIONALE_EN,
    )
    payload.update(overrides)
    return payload


def _hook_body(project_id, data: dict | None, hook_status: str = "success") -> dict:
    return {
        "projectId": str(project_id),
        "block": "architecture",
        "status": hook_status,
        "data": data,
    }


async def test_valid_architecture_hook_succeeds_and_persists(client, project_ready_for_architecture, db_session):
    p = project_ready_for_architecture
    body = _hook_body(p.id, _valid_architecture())

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 200

    await db_session.refresh(p)
    assert p.architecture is not None
    assert p.architecture["epicenter"] == "customer_driven"
    assert p.architecture["pattern_subtype"] == "freemium"
    assert p.status == "completed"


async def test_old_epicenter_value_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_architecture(epicenter="competitor_driven"))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.architecture is None


async def test_free_pattern_without_subtype_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_architecture(pattern="free", pattern_subtype=None))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.architecture is None


async def test_long_tail_with_subtype_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_architecture(pattern="long_tail", pattern_subtype="freemium"))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.architecture is None


async def test_valid_free_freemium_accepted(client, project_ready_for_architecture, db_session):
    # Uses project_ready_for_architecture (all other blocks already filled),
    # not the bare `project` fixture: a success hook for the *last* block in
    # BLOCK_CHAIN with earlier blocks still empty hits a pre-existing
    # IndexError in the "enqueue next block" logic (out of scope here — see
    # task summary).
    p = project_ready_for_architecture
    body = _hook_body(p.id, _valid_architecture(pattern="free", pattern_subtype="freemium"))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 200

    await db_session.refresh(p)
    assert p.architecture["pattern"] == "free"
    assert p.architecture["pattern_subtype"] == "freemium"


async def test_422_response_body_lists_violations(client, project):
    body = _hook_body(project.id, _valid_architecture(epicenter="competitor_driven"))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, list)
    assert any(err.get("loc") == ["epicenter"] for err in detail)
