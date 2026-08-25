"""POST /api/internal/hook — hypotheses payload validation against bizstruct_domain."""
from tests.conftest import INTERNAL_HEADERS


def _h(i: int, category: str, quadrant: str, text: str | None = None) -> dict:
    return {
        "id": f"H{i}.1",
        "text": text or "A placeholder falsifiable claim involving a specific 10% metric",
        "category": category,
        "quadrant": quadrant,
    }


def _valid_hypotheses(**overrides) -> dict:
    payload = {
        "hypotheses": [
            _h(1, "desirability", "q1"),
            _h(2, "viability", "q2"),
            _h(3, "feasibility", "q3"),
            _h(4, "desirability", "q4"),
            _h(5, "viability", "q1"),
        ]
    }
    payload.update(overrides)
    return payload


def _hook_body(project_id, data: dict | None, hook_status: str = "success") -> dict:
    return {
        "projectId": str(project_id),
        "block": "hypotheses",
        "status": hook_status,
        "data": data,
    }


async def test_valid_hypotheses_hook_succeeds_and_persists(client, project, db_session):
    body = _hook_body(project.id, _valid_hypotheses())

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 200

    await db_session.refresh(project)
    assert project.hypotheses is not None
    assert len(project.hypotheses["hypotheses"]) == 5


async def test_too_few_hypotheses_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_hypotheses(hypotheses=[_h(1, "desirability", "q1")]))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.hypotheses is None


async def test_missing_category_coverage_rejected_with_422(client, project, db_session):
    only_desirability = [_h(i, "desirability", "q1") for i in range(1, 6)]
    body = _hook_body(project.id, _valid_hypotheses(hypotheses=only_desirability))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.hypotheses is None


async def test_capitalized_category_rejected_with_422(client, project, db_session):
    """Category values are lowercase (desirability/viability/feasibility) —
    the old capitalized form must be rejected, not silently accepted."""
    body = _hook_body(project.id, _valid_hypotheses(hypotheses=[_h(1, "Desirability", "q1")] + _valid_hypotheses()["hypotheses"][1:]))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.hypotheses is None


async def test_422_response_body_lists_violations(client, project, db_session):
    body = _hook_body(project.id, _valid_hypotheses(hypotheses=[_h(1, "desirability", "q1")]))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, list)
    assert any(err.get("loc") == ["hypotheses"] for err in detail)
