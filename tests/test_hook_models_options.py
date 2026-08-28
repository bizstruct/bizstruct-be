"""POST /api/internal/hook — models_options payload validation against
bizstruct_domain.

ModelsOptions is not bilingual (see bizstruct_domain.blocks.models_options)
— plain str fields, no _uk/_en pairs, matching how this block is generated
today (base_system(lang), not bilingual_system()).
"""
from uuid import uuid4

from tests.conftest import INTERNAL_HEADERS


def _option(monetization: str = "subscription", **overrides) -> dict:
    option = {
        "id": str(uuid4()),
        "title": "Subscription · EcoSync",
        "audience": "Sustainability managers at mid-size manufacturers",
        "value_proposition": "Automated CSRD reporting that saves weeks of manual work",
        "description": "A recurring subscription for continuous emissions tracking and automated compliance reports.",
        "monetization": monetization,
        "key_metric": "MRR",
        "time_to_value": "30 minutes to first report",
        "score": 78,
        "score_rationale": "Strong fit: directly addresses the recurring compliance pain with a proven SaaS model.",
    }
    option.update(overrides)
    return option


def _valid_models_options(**overrides) -> dict:
    payload = {
        "options": [
            _option("subscription"),
            _option("transaction_fee"),
            _option("retainer_plus_saas"),
        ],
        "selected_id": None,
    }
    payload.update(overrides)
    return payload


def _hook_body(project_id, data: dict | None, hook_status: str = "success") -> dict:
    return {
        "projectId": str(project_id),
        "block": "models_options",
        "status": hook_status,
        "data": data,
    }


async def test_valid_models_options_hook_succeeds_and_persists(client, project, db_session):
    body = _hook_body(project.id, _valid_models_options())

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 200

    await db_session.refresh(project)
    assert project.models_options is not None
    assert len(project.models_options["options"]) == 3
    assert project.models_options["selected_id"] is None


async def test_wrong_number_of_options_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_models_options(options=[_option("subscription")]))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.models_options is None


async def test_selected_id_not_matching_any_option_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_models_options(selected_id=str(uuid4())))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.models_options is None


async def test_score_out_of_range_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_models_options(options=[
        _option("subscription", score=150),
        _option("transaction_fee"),
        _option("retainer_plus_saas"),
    ]))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.models_options is None


async def test_color_field_rejected_with_422(client, project, db_session):
    """Presentation fields (color, icon, ...) have no place on a domain
    model — see bizstruct-domain's test_no_presentation_fields safeguard."""
    body = _hook_body(project.id, _valid_models_options(options=[
        {**_option("subscription"), "color": "green"},
        _option("transaction_fee"),
        _option("retainer_plus_saas"),
    ]))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.models_options is None


async def test_422_response_body_lists_violations(client, project, db_session):
    body = _hook_body(project.id, _valid_models_options(options=[_option("subscription")]))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, list)
    assert any(err.get("loc") == ["options"] for err in detail)
