import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from bizstruct_domain import ProjectSnapshot, QueueMessage, Stage, StageEvent, StageResult, StageStatus
from bizstruct_domain import StageRow as WireRow

import app.servicebus as servicebus
from app.core.config import settings
from app.core.security import create_access_token
from app.models import Project, StageRow
from app.pubsub import WebPubSubEvents
from tests.conftest import INTERNAL_HEADERS
from tests.support import artifacts

S = Stage
IDEA = "A platform that connects local farmers with city consumers for weekly fresh produce delivery."


def body(**overrides):
    return {"idea": IDEA, "language": "en", **overrides}


async def create(client, auth_headers, **overrides):
    response = await client.post("/api/generation", json=body(**overrides), headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


def stage_names(project_json) -> list[str]:
    return [r["stage"] for r in project_json["rows"]]


# --- POST /api/generation ------------------------------------------------


async def test_generation_requires_authentication(client):
    assert (await client.post("/api/generation", json=body())).status_code == 401


async def test_generation_creates_the_project_with_a_running_brief_row(client, auth_headers, fake_queue):
    data = await create(client, auth_headers, title="My startup")

    assert data["title"] == "My startup"
    assert data["language"] == "en"
    assert data["enabledOptional"] == [] and data["autoApprove"] is False
    assert data["status"] == "running"
    (brief,) = data["rows"]
    assert brief["stage"] == "brief" and brief["status"] == "running"
    assert brief["instanceIndex"] == 0 and brief["refs"] == {}
    assert brief["attemptId"] and brief["startedAt"] and brief["finishedAt"] is None
    assert brief["artifacts"] == [] and brief["error"] is None and brief["consistency"] is None


async def test_generation_sends_exactly_one_message(client, auth_headers, fake_queue):
    data = await create(client, auth_headers)

    (message,) = fake_queue.messages
    brief = data["rows"][0]
    assert message.project_id == data["id"] and message.language == "en"
    assert [(t.stage_row_id, t.attempt_id) for t in message.targets] == [(brief["id"], brief["attemptId"])]


async def test_generation_creates_rows_for_the_enabled_optional_stages(client, auth_headers, fake_queue):
    data = await create(client, auth_headers, enabledOptional=["environment_scan", "business_case"], autoApprove=True)

    assert data["enabledOptional"] == ["environment_scan", "business_case"] and data["autoApprove"] is True
    assert sorted(stage_names(data)) == ["brief", "business_case", "environment_scan"]
    brief = next(r for r in data["rows"] if r["stage"] == "brief")
    for row in data["rows"]:
        if row["stage"] != "brief":
            assert row["status"] == "pending" and row["refs"] == {"brief": [brief["id"]]}
    assert len(fake_queue.messages) == 1  # only the brief is ready


async def test_generation_uses_a_default_title_in_the_projects_language(client, auth_headers):
    assert (await create(client, auth_headers, language="uk"))["title"] == "Новий проєкт"
    assert (await create(client, auth_headers, language="en"))["title"] == "New project"


async def test_generation_rejects_team_info_and_non_optional_stages(client, auth_headers, fake_queue):
    for stages in (["team_info"], ["pitch"]):
        response = await client.post("/api/generation", json=body(enabledOptional=stages), headers=auth_headers)
        assert response.status_code == 422
    assert fake_queue.messages == []


async def test_generation_validates_the_request(client, auth_headers):
    assert (await client.post("/api/generation", json=body(idea="too short"), headers=auth_headers)).status_code == 422
    assert (await client.post("/api/generation", json=body(language="de"), headers=auth_headers)).status_code == 422
    assert (await client.post("/api/generation", json=body(mode="agent"), headers=auth_headers)).status_code == 422


async def test_generation_publishes_stage_events(client, auth_headers, fake_events):
    data = await create(client, auth_headers)

    assert [(e.stage_row_id, e.status) for e in fake_events.events] == [
        (data["rows"][0]["id"], StageStatus.PENDING),
        (data["rows"][0]["id"], StageStatus.RUNNING),
    ]


# --- GET / list / delete / ownership --------------------------------------


async def test_get_project_returns_camel_case_outer_fields_and_snake_case_domain_models(client, auth_headers):
    created = await create(client, auth_headers)
    brief = created["rows"][0]
    result = artifacts.success(WireRow(id=brief["id"], stage=S.BRIEF, status=StageStatus.RUNNING, attempt_id=brief["attemptId"]), [], project_id=created["id"])
    await client.post("/api/internal/hook", json=result.model_dump(mode="json"), headers=INTERNAL_HEADERS)

    data = (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).json()

    assert {"id", "title", "idea", "language", "enabledOptional", "autoApprove", "status", "rows", "createdAt", "updatedAt"} <= set(data)
    done = next(r for r in data["rows"] if r["stage"] == "brief")
    assert {"instanceIndex", "attemptId", "retryCount", "startedAt", "finishedAt"} <= set(done)
    (artifact,) = done["artifacts"]
    assert set(artifact) == {"id", "type", "data"} and artifact["type"] == "brief"
    assert "customer_segment_candidates" in artifact["data"]  # nested domain model stays snake_case


async def test_get_project_unknown_is_404_and_foreign_is_403(client, auth_headers, other_user):
    created = await create(client, auth_headers)
    stranger = {"Authorization": f"Bearer {create_access_token(other_user.id)}"}

    assert (await client.get(f"/api/projects/{uuid.uuid4()}", headers=auth_headers)).status_code == 404
    assert (await client.get(f"/api/projects/{created['id']}", headers=stranger)).status_code == 403
    assert (await client.get(f"/api/projects/{created['id']}")).status_code == 401


async def test_list_returns_only_own_projects_with_derived_status(client, auth_headers, other_user):
    mine = await create(client, auth_headers)
    stranger = {"Authorization": f"Bearer {create_access_token(other_user.id)}"}
    await create(client, stranger)

    listed = (await client.get("/api/projects", headers=auth_headers)).json()

    assert [p["id"] for p in listed] == [mine["id"]]
    assert listed[0]["status"] == "running" and "rows" not in listed[0]


async def test_delete_removes_the_project_and_its_rows(client, auth_headers, session):
    created = await create(client, auth_headers)

    assert (await client.delete(f"/api/projects/{created['id']}", headers=auth_headers)).status_code == 204

    assert (await session.execute(select(StageRow).where(StageRow.project_id == uuid.UUID(created["id"])))).first() is None
    assert (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).status_code == 404


async def test_patch_title_still_works(client, auth_headers):
    created = await create(client, auth_headers)
    response = await client.patch(f"/api/projects/{created['id']}", json={"title": "Renamed"}, headers=auth_headers)
    assert response.status_code == 200 and response.json()["title"] == "Renamed"


async def test_project_status_failed_after_a_failed_result(client, auth_headers):
    created = await create(client, auth_headers)
    brief = created["rows"][0]
    failed = artifacts.failure(WireRow(id=brief["id"], stage=S.BRIEF, status=StageStatus.RUNNING, attempt_id=brief["attemptId"]), project_id=created["id"])

    assert (await client.post("/api/internal/hook", json=failed.model_dump(mode="json"), headers=INTERNAL_HEADERS)).status_code == 200

    data = (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).json()
    assert data["status"] == "failed"
    assert data["rows"][0]["status"] == "error" and data["rows"][0]["error"]["code"] == "generation_failed"


async def test_reading_a_project_runs_the_watchdog(client, auth_headers, session):
    created = await create(client, auth_headers)
    row = await session.get(StageRow, created["rows"][0]["id"])
    row.started_at = datetime.now(timezone.utc) - timedelta(seconds=settings.stuck_timeout_seconds + 60)
    await session.commit()

    data = (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).json()

    assert data["status"] == "failed"
    assert data["rows"][0]["error"]["code"] == "stuck_timeout"


# --- internal: auth ----------------------------------------------------------


async def test_internal_endpoints_need_the_api_key(client, auth_headers):
    created = await create(client, auth_headers)
    url = f"/api/internal/projects/{created['id']}"

    assert (await client.get(url)).status_code in (401, 422)
    assert (await client.get(url, headers={"x-api-key": "wrong"})).status_code == 401
    assert (await client.post("/api/internal/hook", json={}, headers={"x-api-key": "wrong"})).status_code == 401
    assert (await client.get(url, headers=auth_headers)).status_code in (401, 422)  # a user token is not the key


# --- internal: snapshot --------------------------------------------------------


async def run_through(client, fake_queue, project_id: str, *, segments: int, groups, until: Stage | None = None, auto_pop: bool = True):
    """Answers queued messages with domain-built results until the queue is empty (or `until` is done)."""
    answered: list[str] = []
    while fake_queue.messages:
        message = fake_queue.messages.pop(0)
        target = message.targets[0]
        snap = ProjectSnapshot.model_validate(
            (await client.get(f"/api/internal/projects/{project_id}", params={"row": target.stage_row_id}, headers=INTERNAL_HEADERS)).json()
        )
        row = next(r for r in snap.rows if r.id == target.stage_row_id)
        result = artifacts.success(row, snap.rows, project_id=project_id, segments=segments, groups=groups)
        response = await client.post("/api/internal/hook", json=result.model_dump(mode="json"), headers=INTERNAL_HEADERS)
        assert response.status_code == 200, response.text
        answered.append(row.stage.value)
        if until is not None and row.stage == until:
            break
    return answered


async def test_snapshot_returns_project_fields_and_all_rows_without_row_param(client, auth_headers):
    created = await create(client, auth_headers, enabledOptional=["environment_scan"], language="uk")

    response = await client.get(f"/api/internal/projects/{created['id']}", headers=INTERNAL_HEADERS)

    snapshot = ProjectSnapshot.model_validate(response.json())
    assert snapshot.project_id == created["id"] and snapshot.idea == IDEA and snapshot.language == "uk"
    assert snapshot.enabled_optional == [S.ENVIRONMENT_SCAN]
    assert {r.stage for r in snapshot.rows} == {S.BRIEF, S.ENVIRONMENT_SCAN}
    assert "project_id" in response.json() and "enabled_optional" in response.json()  # snake_case on the wire


async def test_snapshot_with_row_is_that_row_and_the_closure_of_its_refs(client, auth_headers, fake_queue):
    created = await create(client, auth_headers)
    await run_through(client, fake_queue, created["id"], segments=2, groups=((1, 2),), until=S.BRIEF)
    detail = (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).json()
    first_map = next(r for r in detail["rows"] if r["stage"] == "empathy_map" and r["instanceIndex"] == 0)

    snapshot = ProjectSnapshot.model_validate(
        (await client.get(f"/api/internal/projects/{created['id']}", params={"row": first_map["id"]}, headers=INTERNAL_HEADERS)).json()
    )

    assert {r.stage for r in snapshot.rows} == {S.EMPATHY_MAP, S.BRIEF}
    assert {r.id for r in snapshot.rows} == {first_map["id"], first_map["refs"]["brief"][0]}
    assert next(r for r in snapshot.rows if r.stage == S.BRIEF).artifacts  # the closure carries the artifacts


async def test_snapshot_closure_is_transitive(client, auth_headers, fake_queue):
    created = await create(client, auth_headers)
    await run_through(client, fake_queue, created["id"], segments=2, groups=((1, 2),), until=S.IDEATION)
    detail = (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).json()
    patterns = next(r for r in detail["rows"] if r["stage"] == "patterns")

    snapshot = ProjectSnapshot.model_validate(
        (await client.get(f"/api/internal/projects/{created['id']}", params={"row": patterns["id"]}, headers=INTERNAL_HEADERS)).json()
    )

    # patterns -> scenarios, ideations -> empathy maps -> brief
    assert sorted(r.stage.value for r in snapshot.rows) == sorted(
        ["patterns", "customer_scenario", "customer_scenario", "ideation", "ideation", "empathy_map", "empathy_map", "brief"]
    )


async def test_snapshot_unknown_project_or_row_is_404(client, auth_headers):
    created = await create(client, auth_headers)

    assert (await client.get(f"/api/internal/projects/{uuid.uuid4()}", headers=INTERNAL_HEADERS)).status_code == 404
    unknown_row = await client.get(f"/api/internal/projects/{created['id']}", params={"row": "nope"}, headers=INTERNAL_HEADERS)
    assert unknown_row.status_code == 404


# --- internal: hook --------------------------------------------------------------


async def hook(client, result: StageResult):
    return await client.post("/api/internal/hook", json=result.model_dump(mode="json"), headers=INTERNAL_HEADERS)


async def first_brief_result(client, auth_headers, **kwargs):
    created = await create(client, auth_headers, **kwargs)
    brief = created["rows"][0]
    wire = WireRow(id=brief["id"], stage=S.BRIEF, status=StageStatus.RUNNING, attempt_id=brief["attemptId"])
    return created, wire


async def test_hook_applies_a_valid_result(client, auth_headers, fake_queue):
    created, wire = await first_brief_result(client, auth_headers)
    fake_queue.messages.clear()

    response = await hook(client, artifacts.success(wire, [], project_id=created["id"], segments=3, groups=((1, 2, 3),)))

    assert response.status_code == 200 and response.json() == {"status": "applied"}
    data = (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).json()
    assert data["rows"][0]["status"] == "done"
    assert stage_names(data).count("empathy_map") == 3
    assert len(fake_queue.messages) == 3


async def test_hook_unknown_project_and_row_are_404(client, auth_headers):
    created, wire = await first_brief_result(client, auth_headers)
    result = artifacts.success(wire, [], project_id=created["id"])

    assert (await hook(client, result.model_copy(update={"project_id": str(uuid.uuid4())}))).status_code == 404
    assert (await hook(client, result.model_copy(update={"stage_row_id": "nope"}))).status_code == 404


async def test_hook_stale_attempt_is_409(client, auth_headers):
    created, wire = await first_brief_result(client, auth_headers)
    result = artifacts.success(wire, [], project_id=created["id"]).model_copy(update={"attempt_id": "old"})

    assert (await hook(client, result)).status_code == 409


async def test_hook_for_a_row_that_is_not_running_is_409(client, auth_headers):
    created, wire = await first_brief_result(client, auth_headers)
    failed = artifacts.failure(wire, project_id=created["id"])
    await hook(client, failed)

    assert (await hook(client, artifacts.success(wire, [], project_id=created["id"]))).status_code == 409


async def test_hook_duplicate_is_200_and_changes_nothing(client, auth_headers, fake_queue):
    created, wire = await first_brief_result(client, auth_headers)
    result = artifacts.success(wire, [], project_id=created["id"], segments=2, groups=((1, 2),))
    await hook(client, result)
    queued = len(fake_queue.messages)

    response = await hook(client, result)

    assert response.status_code == 200 and response.json() == {"status": "duplicate"}
    assert len(fake_queue.messages) == queued
    data = (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).json()
    assert stage_names(data).count("empathy_map") == 2


async def test_hook_with_invalid_artifacts_is_422_and_marks_the_row_error(client, auth_headers, fake_queue):
    created, wire = await first_brief_result(client, auth_headers)
    good = artifacts.success(wire, [], project_id=created["id"])
    bad = good.model_copy(update={"artifacts": [good.artifacts[0].model_copy(update={"data": {"industry": "x"}})]})
    fake_queue.messages.clear()

    response = await hook(client, bad)

    assert response.status_code == 422 and "brief" in response.json()["detail"]
    data = (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).json()
    assert data["rows"][0]["status"] == "error" and data["rows"][0]["error"]["code"] == "generation_failed"
    assert data["status"] == "failed" and fake_queue.messages == []


async def test_hook_with_a_four_candidate_brief_is_422(client, auth_headers):
    created, wire = await first_brief_result(client, auth_headers)
    good = artifacts.success(wire, [], project_id=created["id"], segments=3)
    data = dict(good.artifacts[0].data, customer_segment_candidates=["a", "b", "c", "d"])

    response = await hook(client, good.model_copy(update={"artifacts": [good.artifacts[0].model_copy(update={"data": data})]}))

    assert response.status_code == 422
    detail = (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).json()
    assert stage_names(detail) == ["brief"]


async def test_hook_with_an_envelope_that_is_not_a_stage_result_is_422(client, auth_headers):
    created, wire = await first_brief_result(client, auth_headers)
    response = await client.post(
        "/api/internal/hook",
        json={"project_id": created["id"], "stage_row_id": wire.id, "attempt_id": wire.attempt_id, "status": "success", "artifacts": []},
        headers=INTERNAL_HEADERS,
    )
    assert response.status_code == 422


async def test_hook_error_level_violation_awaits_a_decision_then_approve_continues(client, auth_headers, fake_queue):
    created, wire = await first_brief_result(client, auth_headers)
    fake_queue.messages.clear()
    await hook(client, artifacts.success(wire, [], project_id=created["id"], consistency=artifacts.error_report()))

    data = (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).json()
    brief = data["rows"][0]
    assert brief["status"] == "awaiting_decision" and brief["consistency"]["violations"][0]["severity"] == "error"
    assert data["status"] == "running" and fake_queue.messages == []

    approved = await client.post(f"/api/projects/{created['id']}/rows/{brief['id']}/approve", headers=auth_headers)

    assert approved.status_code == 200
    assert next(r for r in approved.json()["rows"] if r["stage"] == "brief")["status"] == "done"
    assert len(fake_queue.messages) == 1  # the empathy map


async def test_hook_with_auto_approve_goes_straight_to_done_and_keeps_the_report(client, auth_headers, fake_queue):
    created, wire = await first_brief_result(client, auth_headers, autoApprove=True)
    await hook(client, artifacts.success(wire, [], project_id=created["id"], consistency=artifacts.error_report()))

    brief = (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).json()["rows"][0]

    assert brief["status"] == "done" and brief["consistency"]["violations"]


# --- regenerate / approve endpoints ---------------------------------------------


async def test_regenerate_resets_the_dependents_and_runs_the_row_again(client, auth_headers, fake_queue):
    created, wire = await first_brief_result(client, auth_headers)
    await hook(client, artifacts.success(wire, [], project_id=created["id"], segments=2, groups=((1, 2),)))
    before = (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).json()
    fake_queue.messages.clear()

    response = await client.post(f"/api/projects/{created['id']}/rows/{wire.id}/regenerate", headers=auth_headers)

    assert response.status_code == 200
    after = response.json()
    assert [r["id"] for r in after["rows"]] == [r["id"] for r in before["rows"]]
    assert next(r for r in after["rows"] if r["id"] == wire.id)["status"] == "running"
    assert all(r["status"] == "pending" for r in after["rows"] if r["id"] != wire.id)
    assert fake_queue.row_ids() == [wire.id]


async def test_regenerate_and_approve_conflicts_are_409(client, auth_headers):
    created, wire = await first_brief_result(client, auth_headers)  # the brief is running

    assert (await client.post(f"/api/projects/{created['id']}/rows/{wire.id}/regenerate", headers=auth_headers)).status_code == 409
    assert (await client.post(f"/api/projects/{created['id']}/rows/{wire.id}/approve", headers=auth_headers)).status_code == 409
    assert (await client.post(f"/api/projects/{created['id']}/rows/nope/approve", headers=auth_headers)).status_code == 404


async def test_regenerate_and_approve_are_owner_only(client, auth_headers, other_user):
    created, wire = await first_brief_result(client, auth_headers)
    stranger = {"Authorization": f"Bearer {create_access_token(other_user.id)}"}

    assert (await client.post(f"/api/projects/{created['id']}/rows/{wire.id}/regenerate", headers=stranger)).status_code == 403
    assert (await client.post(f"/api/projects/{created['id']}/rows/{wire.id}/approve", headers=stranger)).status_code == 403


# --- queue failure ------------------------------------------------------------------


async def test_a_queue_failure_leaves_the_row_in_error_queue_unavailable(client, auth_headers, fake_queue):
    fake_queue.fail_next_enqueue = True

    created = await create(client, auth_headers)

    data = (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).json()
    assert data["rows"][0]["error"]["code"] == "queue_unavailable" and data["status"] == "failed"


# --- end to end: a simulated worker answers every message -------------------------------


@pytest.mark.parametrize(
    "segments,groups,canvases",
    [(1, ((1,),), 1), (3, ((1, 2, 3),), 1), (3, ((1, 2), (3,)), 2)],
    ids=["one segment", "three in one group", "split in two"],
)
@pytest.mark.parametrize("enabled", [[], ["environment_scan", "business_case"]], ids=["required only", "with optional"])
async def test_a_simulated_worker_takes_a_project_to_completed(client, auth_headers, fake_queue, segments, groups, canvases, enabled):
    created = await create(client, auth_headers, enabledOptional=enabled)

    answered = await run_through(client, fake_queue, created["id"], segments=segments, groups=groups)

    data = (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).json()
    assert data["status"] == "completed"
    assert all(r["status"] == "done" for r in data["rows"])
    counts = {s: stage_names(data).count(s) for s in set(stage_names(data))}
    assert counts["empathy_map"] == counts["customer_scenario"] == counts["ideation"] == segments
    assert counts["canvas"] == counts["swot_errc_cycle"] == counts["storytelling"] == counts["future_scenario"] == counts["pitch"] == canvases
    assert counts["brief"] == counts["patterns"] == 1
    assert len(answered) == len(data["rows"])  # every row was sent exactly once
    assert len(set(answered)) == len(set(counts))


async def test_the_worker_receives_each_row_exactly_once(client, auth_headers, fake_queue):
    created = await create(client, auth_headers)
    sent: list[str] = []
    while fake_queue.messages:
        message = fake_queue.messages.pop(0)
        target = message.targets[0]
        sent.append(target.stage_row_id)
        snap = ProjectSnapshot.model_validate(
            (await client.get(f"/api/internal/projects/{created['id']}", params={"row": target.stage_row_id}, headers=INTERNAL_HEADERS)).json()
        )
        row = next(r for r in snap.rows if r.id == target.stage_row_id)
        await hook(client, artifacts.success(row, snap.rows, project_id=created["id"], segments=3, groups=((1, 2), (3,))))

    detail = (await client.get(f"/api/projects/{created['id']}", headers=auth_headers)).json()
    assert detail["status"] == "completed"
    assert len(sent) == len(set(sent)) == len(detail["rows"])


# --- adapters ---------------------------------------------------------------------------


async def test_service_bus_queue_sends_the_message_json_through_the_sender(monkeypatch):
    sent: list[str] = []
    monkeypatch.setattr(servicebus, "_send_to_queue", sent.append)
    monkeypatch.setattr(settings, "service_bus_connection_string", "Endpoint=sb://x/;SharedAccessKey=k")
    message = QueueMessage.model_validate(
        {"project_id": "p", "language": "en", "targets": [{"stage_row_id": "r", "stage": "brief", "attempt_id": "a"}]}
    )

    await servicebus.ServiceBusQueue().enqueue(message)

    assert [QueueMessage.model_validate_json(body) for body in sent] == [message]


async def test_service_bus_queue_is_a_noop_without_a_connection_string(monkeypatch):
    sent: list[str] = []
    monkeypatch.setattr(servicebus, "_send_to_queue", sent.append)
    monkeypatch.setattr(settings, "service_bus_connection_string", None)
    message = QueueMessage.model_validate(
        {"project_id": "p", "language": "en", "targets": [{"stage_row_id": "r", "stage": "brief", "attempt_id": "a"}]}
    )

    await servicebus.ServiceBusQueue().enqueue(message)

    assert sent == []


async def test_web_pubsub_events_are_a_noop_without_a_connection_string(monkeypatch):
    monkeypatch.setattr(settings, "azure_web_pubsub_connection_string", "")
    await WebPubSubEvents().publish(StageEvent(project_id="p", stage_row_id="r", stage=S.BRIEF, status=StageStatus.DONE))
