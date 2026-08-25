"""POST /api/internal/hook — scenario payload validation against bizstruct_domain."""
from tests.conftest import INTERNAL_HEADERS

_STEPS = [
    ("context", "calendar"),
    ("goal", "target"),
    ("action", "zap"),
    ("result", "check-circle"),
    ("impact", "trending-up"),
]


def _timeline(steps=_STEPS) -> list[dict]:
    return [
        {
            "step_type": step_type,
            "icon_key": icon_key,
            "text_uk": f"Достатньо довгий текст кроку {step_type} українською",
            "text_en": f"A sufficiently long step text for {step_type} in English",
        }
        for step_type, icon_key in steps
    ]


def _valid_scenario(**overrides) -> dict:
    payload = {
        "persona": {
            "name_uk": "Дмитро Петренко",
            "name_en": "Dmytro Petrenko",
            "role_uk": "EHS Director",
            "role_en": "EHS Director",
            "pain_point_uk": "Щорічний аудит коштує €52k і займає 3 тижні підготовки",
            "pain_point_en": "The annual audit costs €52k and takes 3 weeks to prepare",
        },
        "timeline": _timeline(),
        "metrics": {
            "before": {"value_uk": "€52k", "value_en": "€52k", "label_uk": "Вартість аудиту", "label_en": "Audit cost"},
            "after": {"value_uk": "€6k", "value_en": "€6k", "label_uk": "Вартість моніторингу", "label_en": "Monitoring cost"},
        },
    }
    payload.update(overrides)
    return payload


def _hook_body(project_id, data: dict | None, hook_status: str = "success") -> dict:
    return {
        "projectId": str(project_id),
        "block": "scenario",
        "status": hook_status,
        "data": data,
    }


async def test_valid_scenario_hook_succeeds_and_persists(client, project, db_session):
    body = _hook_body(project.id, _valid_scenario())

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 200

    await db_session.refresh(project)
    assert project.scenario is not None
    assert len(project.scenario["timeline"]) == 5
    assert "highlight" not in project.scenario["timeline"][0]


async def test_wrong_step_order_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_scenario(timeline=_timeline(list(reversed(_STEPS)))))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.scenario is None


async def test_too_few_timeline_steps_rejected_with_422(client, project, db_session):
    body = _hook_body(project.id, _valid_scenario(timeline=_timeline(_STEPS[:4])))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.scenario is None


async def test_highlight_field_rejected_with_422(client, project, db_session):
    """highlight is presentation logic, not part of the domain model — the
    hook must reject it rather than silently drop or persist it."""
    steps = _timeline()
    steps[0]["highlight"] = False
    body = _hook_body(project.id, _valid_scenario(timeline=steps))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422

    await db_session.refresh(project)
    assert project.scenario is None


async def test_422_response_body_lists_violations(client, project, db_session):
    body = _hook_body(project.id, _valid_scenario(timeline=_timeline(_STEPS[:4])))

    resp = await client.post("/api/internal/hook", json=body, headers=INTERNAL_HEADERS)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, list)
    assert any(err.get("loc") == ["timeline"] for err in detail)
