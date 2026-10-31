import asyncio
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from bizstruct_domain import Stage, StageErrorCode, StageFailure, StageStatus

from app.exceptions.base import EntityNotFoundError
from app.exceptions.stage import StageActionNotAllowed, StageRowNotFound, StaleAttempt
from app.services.orchestrator import GenerationOrchestrator
from app.services.stage import StageService
from tests.fakes.queue import FakeQueue
from tests.support import artifacts
from tests.test_stage_service import FAILURE, chain_specs, spec, walk_to_done

S = Stage


@pytest_asyncio.fixture
def stage_service(session):
    return StageService(session)


@pytest_asyncio.fixture
def orchestrator(session, stage_service, fake_queue, fake_events):
    return GenerationOrchestrator(session, stage_service, fake_queue, fake_events)


async def start(orchestrator, project):
    """Creates the first rows through the orchestrator, as POST /api/generation does."""
    await orchestrator.start(project)


# --- start -------------------------------------------------------------------


async def test_start_creates_the_brief_row_and_runs_it(orchestrator, stage_service, project, fake_queue):
    await start(orchestrator, project)

    (brief,) = await stage_service.get_rows(project.id)
    assert brief.stage == S.BRIEF and brief.refs == {}
    assert brief.status == StageStatus.RUNNING
    assert brief.attempt_id is not None and brief.started_at is not None


async def test_start_sends_exactly_one_message_for_the_brief(orchestrator, stage_service, project, fake_queue):
    await start(orchestrator, project)

    (brief,) = await stage_service.get_rows(project.id)
    (message,) = fake_queue.messages
    assert message.project_id == str(project.id)
    assert message.language == "en"
    assert len(message.targets) == 1
    target = message.targets[0]
    assert (target.stage_row_id, target.stage, target.attempt_id) == (brief.id, S.BRIEF, brief.attempt_id)


async def test_start_creates_rows_for_enabled_optional_stages_only(orchestrator, stage_service, project, fake_queue):
    project.enabled_optional = ["environment_scan"]

    await start(orchestrator, project)

    rows = await stage_service.get_rows(project.id)
    assert {r.stage for r in rows} == {S.BRIEF, S.ENVIRONMENT_SCAN}
    scan = next(r for r in rows if r.stage == S.ENVIRONMENT_SCAN)
    assert scan.status == StageStatus.PENDING  # waits for the brief
    assert len(fake_queue.messages) == 1


async def test_start_commits_before_sending(orchestrator, stage_service, project, session_factory):
    seen: list[StageStatus] = []

    class CheckingQueue(FakeQueue):
        async def enqueue(self, message):
            async with session_factory() as other:
                row = await StageService(other).get_row(project.id, message.targets[0].stage_row_id)
                seen.append(row.status)
            await super().enqueue(message)

    checking = GenerationOrchestrator(orchestrator.session, stage_service, CheckingQueue())
    await checking.start(project)

    assert seen == [StageStatus.RUNNING]


async def test_start_publishes_events_for_the_new_and_started_rows(orchestrator, project, fake_events):
    await start(orchestrator, project)

    assert [(e.stage, e.status) for e in fake_events.events] == [(S.BRIEF, StageStatus.PENDING), (S.BRIEF, StageStatus.RUNNING)]
    assert all(e.project_id == str(project.id) for e in fake_events.events)


async def test_queue_failure_compensates_with_queue_unavailable(orchestrator, stage_service, project, fake_queue, session_factory):
    fake_queue.fail_next_enqueue = True

    await start(orchestrator, project)

    assert fake_queue.messages == []
    async with session_factory() as other:
        (brief,) = await StageService(other).get_rows(project.id)
    assert brief.status == StageStatus.ERROR
    assert brief.error["code"] == StageErrorCode.QUEUE_UNAVAILABLE


async def test_queue_failure_after_the_row_left_running_does_not_touch_it(stage_service, project, session_factory, session):
    """Something else (the watchdog, a cancel) moved the row on while enqueueing failed: leave it alone."""

    class MovesRowThenFails(FakeQueue):
        async def enqueue(self, message):
            async with session_factory() as other:
                other_service = StageService(other)
                row = await other_service.get_row(project.id, message.targets[0].stage_row_id, lock=True)
                await other_service.transition(row, StageStatus.ERROR, failure=FAILURE)
                await other.commit()
            raise RuntimeError("simulated queue failure")

    orchestrator = GenerationOrchestrator(session, stage_service, MovesRowThenFails())

    await orchestrator.start(project)  # must not raise

    async with session_factory() as other:
        (brief,) = await StageService(other).get_rows(project.id)
    assert brief.status == StageStatus.ERROR
    assert brief.error["code"] == StageErrorCode.GENERATION_FAILED  # the other writer's failure, not queue_unavailable


# --- advance -----------------------------------------------------------------


async def test_advance_twice_starts_nothing_the_second_time(orchestrator, project, fake_queue):
    await start(orchestrator, project)
    await orchestrator.advance(project.id)

    assert len(fake_queue.messages) == 1


async def test_advance_starts_every_ready_row_once_with_one_message_each(orchestrator, stage_service, project, session, fake_queue):
    project.enabled_optional = ["environment_scan"]
    await stage_service.create_rows(project.id, chain_specs())
    await walk_to_done(stage_service, project.id, "brief")
    await session.commit()

    await orchestrator.advance(project.id)

    # both maps and the enabled environment scan are ready; nothing else is
    assert sorted(fake_queue.row_ids()) == ["em0", "em1", "scan"]
    await orchestrator.advance(project.id)
    assert len(fake_queue.messages) == 3


async def test_advance_never_starts_a_disabled_optional_row(orchestrator, stage_service, project, session, fake_queue):
    await stage_service.create_rows(project.id, chain_specs())
    await walk_to_done(stage_service, project.id, "brief")
    await session.commit()

    await orchestrator.advance(project.id)

    assert sorted(fake_queue.row_ids()) == ["em0", "em1"]


async def test_advance_unknown_project_raises_not_found(orchestrator):
    import uuid

    with pytest.raises(EntityNotFoundError):
        await orchestrator.advance(uuid.uuid4())


async def test_advance_serializes_concurrent_calls_for_the_same_project(stage_service, project, session, session_factory, fake_queue):
    """Two advance() calls racing on the same project must not both start the brief."""
    await stage_service.create_rows(project.id, [spec("brief", S.BRIEF)])
    await session.commit()

    async def run_advance():
        async with session_factory() as own_session:
            await GenerationOrchestrator(own_session, StageService(own_session), fake_queue).advance(project.id)

    await asyncio.gather(run_advance(), run_advance())

    assert fake_queue.row_ids() == ["brief"]


# --- fail -------------------------------------------------------------------


async def test_fail_moves_the_row_to_error_with_the_failure(orchestrator, stage_service, project):
    await start(orchestrator, project)
    (brief,) = await stage_service.get_rows(project.id)

    await orchestrator.fail(project.id, brief.id, FAILURE)

    assert brief.status == StageStatus.ERROR
    assert brief.error == {"code": "generation_failed", "message": "boom"}


async def test_fail_does_not_touch_the_queue_or_other_rows(orchestrator, stage_service, project, session, fake_queue):
    await stage_service.create_rows(project.id, chain_specs())
    brief = await stage_service.get_row(project.id, "brief")
    await stage_service.transition(brief, StageStatus.RUNNING)
    await session.commit()

    await orchestrator.fail(project.id, "brief", FAILURE)

    assert fake_queue.messages == [] and fake_queue.control_messages == []
    assert (await stage_service.get_row(project.id, "em0")).status == StageStatus.PENDING


async def test_fail_unknown_row_raises_not_found(orchestrator, project):
    with pytest.raises(StageRowNotFound):
        await orchestrator.fail(project.id, "nope", FAILURE)


# --- cancel -----------------------------------------------------------------


async def test_cancel_moves_active_rows_to_error_and_sends_control_messages(orchestrator, stage_service, project, session, fake_queue):
    await stage_service.create_rows(project.id, chain_specs())
    await stage_service.transition(await stage_service.get_row(project.id, "brief"), StageStatus.RUNNING)
    em0 = await stage_service.get_row(project.id, "em0")
    await stage_service.transition(em0, StageStatus.RUNNING)
    await stage_service.transition(em0, StageStatus.CONSISTENCY_CHECK)
    # needs_retry is not "active": nothing runs for it and the domain has no needs_retry -> error edge (D26).
    em1 = await stage_service.get_row(project.id, "em1")
    await stage_service.transition(em1, StageStatus.RUNNING)
    await stage_service.transition(em1, StageStatus.CONSISTENCY_CHECK)
    await stage_service.transition(em1, StageStatus.NEEDS_RETRY)
    await session.commit()

    canceled = await orchestrator.cancel(project.id)

    assert {r.id for r in canceled} == {"brief", "em0"}
    assert all(r.error["code"] == StageErrorCode.CANCELED_BY_USER for r in canceled)
    assert {m["stage_row_id"] for m in fake_queue.control_messages} == {"brief", "em0"}
    assert em1.status == StageStatus.NEEDS_RETRY


async def test_cancel_commits_before_sending_control_messages(orchestrator, stage_service, project, session, session_factory):
    await stage_service.create_rows(project.id, [spec("brief", S.BRIEF)])
    await stage_service.transition(await stage_service.get_row(project.id, "brief"), StageStatus.RUNNING)
    await session.commit()

    class AssertCommittedQueue(FakeQueue):
        async def request_cancellation(self, **kwargs):
            async with session_factory() as verify:
                assert (await StageService(verify).get_row(project.id, kwargs["stage_row_id"])).status == StageStatus.ERROR
            await super().request_cancellation(**kwargs)

    queue = AssertCommittedQueue()
    await GenerationOrchestrator(session, stage_service, queue).cancel(project.id)
    assert len(queue.control_messages) == 1


async def test_cancel_with_nothing_active_is_a_noop(orchestrator, stage_service, project, session, fake_queue):
    await stage_service.create_rows(project.id, chain_specs())
    await session.commit()

    assert await orchestrator.cancel(project.id) == []
    assert fake_queue.control_messages == []


# --- apply_result --------------------------------------------------------------


async def brief_result(orchestrator, stage_service, project, **kwargs):
    await start(orchestrator, project)
    (brief,) = await stage_service.get_rows(project.id)
    return brief, artifacts.success(
        stage_row_to_wire(brief), [stage_row_to_wire(brief)], project_id=str(project.id), segments=kwargs.pop("segments", 1), **kwargs
    )


def stage_row_to_wire(row):
    from app.services.stage import to_wire_row

    return to_wire_row(row)


async def test_a_successful_brief_result_is_stored_and_the_row_becomes_done(orchestrator, stage_service, project):
    brief, result = await brief_result(orchestrator, stage_service, project)

    outcome = await orchestrator.apply_result(project.id, result)

    assert outcome.kind == "applied"
    assert brief.status == StageStatus.DONE
    assert [a["type"] for a in brief.artifacts] == ["brief"]
    assert brief.finished_at is not None


def with_project_title(result, title):
    for artifact in result.artifacts:
        if artifact.type == "brief":
            artifact.data["project_title"] = title
    return result


async def test_a_default_project_name_is_replaced_by_the_brief_title(orchestrator, stage_service, project, session):
    project.title = "New project"
    brief, result = await brief_result(orchestrator, stage_service, project)

    await orchestrator.apply_result(project.id, with_project_title(result, "  Reminders for auto repair shops  "))

    await session.refresh(project)
    assert project.title == "Reminders for auto repair shops"


async def test_a_name_the_user_chose_is_kept(orchestrator, stage_service, project, session):
    assert project.title == "Test"  # not a default name
    brief, result = await brief_result(orchestrator, stage_service, project)

    await orchestrator.apply_result(project.id, with_project_title(result, "Reminders for auto repair shops"))

    await session.refresh(project)
    assert project.title == "Test"


async def test_a_brief_without_a_title_leaves_the_default_name(orchestrator, stage_service, project, session):
    project.title = "Новий проєкт"
    brief, result = await brief_result(orchestrator, stage_service, project)

    await orchestrator.apply_result(project.id, result)

    await session.refresh(project)
    assert project.title == "Новий проєкт"


async def test_the_consistency_check_step_is_applied_in_order(orchestrator, stage_service, project, fake_events):
    brief, result = await brief_result(orchestrator, stage_service, project)
    fake_events.events.clear()

    await orchestrator.apply_result(project.id, result)

    brief_statuses = [e.status for e in fake_events.events if e.stage_row_id == brief.id]
    assert brief_statuses == [StageStatus.CONSISTENCY_CHECK, StageStatus.DONE]


async def test_a_brief_result_creates_the_next_rows_and_starts_the_ready_ones_once(orchestrator, stage_service, project, fake_queue):
    brief, result = await brief_result(orchestrator, stage_service, project, segments=3, groups=((1, 2, 3),))
    fake_queue.messages.clear()

    await orchestrator.apply_result(project.id, result)

    rows = await stage_service.get_rows(project.id)
    maps = [r for r in rows if r.stage == S.EMPATHY_MAP]
    assert len(maps) == 3 and all(m.status == StageStatus.RUNNING for m in maps)
    assert sorted(fake_queue.row_ids()) == sorted(m.id for m in maps)
    assert all(len(m.targets) == 1 for m in fake_queue.messages)
    # the others wait for their inputs
    assert all(r.status == StageStatus.PENDING for r in rows if r.stage in (S.CUSTOMER_SCENARIO, S.IDEATION, S.PATTERNS))


async def test_new_rows_are_announced_as_pending_before_their_own_start(orchestrator, stage_service, project, fake_events):
    brief, result = await brief_result(orchestrator, stage_service, project, segments=2, groups=((1, 2),))
    fake_events.events.clear()

    await orchestrator.apply_result(project.id, result)

    pending = [e for e in fake_events.events if e.status == StageStatus.PENDING]
    created = {r.id for r in await stage_service.get_rows(project.id)} - {brief.id}
    assert {e.stage_row_id for e in pending} == created


async def test_a_duplicate_of_an_applied_result_changes_nothing(orchestrator, stage_service, project, fake_queue):
    brief, result = await brief_result(orchestrator, stage_service, project, segments=2, groups=((1, 2),))
    await orchestrator.apply_result(project.id, result)
    rows_before = len(await stage_service.get_rows(project.id))
    messages_before = len(fake_queue.messages)

    outcome = await orchestrator.apply_result(project.id, result)

    assert outcome.kind == "duplicate"
    assert len(await stage_service.get_rows(project.id)) == rows_before
    assert len(fake_queue.messages) == messages_before


async def test_a_stale_attempt_is_rejected(orchestrator, stage_service, project):
    brief, result = await brief_result(orchestrator, stage_service, project)
    stale = result.model_copy(update={"attempt_id": "an-older-attempt"})

    with pytest.raises(StaleAttempt):
        await orchestrator.apply_result(project.id, stale)

    assert brief.status == StageStatus.RUNNING


async def test_a_result_for_a_row_that_is_not_running_is_rejected(orchestrator, stage_service, project, session):
    brief, result = await brief_result(orchestrator, stage_service, project)
    await orchestrator.fail(project.id, brief.id, FAILURE)

    with pytest.raises(StaleAttempt):
        await orchestrator.apply_result(project.id, result)


async def test_a_result_for_an_unknown_row_or_project_is_not_found(orchestrator, stage_service, project):
    brief, result = await brief_result(orchestrator, stage_service, project)

    with pytest.raises(StageRowNotFound):
        await orchestrator.apply_result(project.id, result.model_copy(update={"stage_row_id": "nope"}))
    with pytest.raises(EntityNotFoundError):
        await orchestrator.apply_result("00000000-0000-0000-0000-000000000000", result)
    with pytest.raises(EntityNotFoundError):
        await orchestrator.apply_result("not-a-uuid", result)


async def test_invalid_artifacts_put_the_row_in_error_and_report_the_problems(orchestrator, stage_service, project):
    brief, result = await brief_result(orchestrator, stage_service, project)
    broken = result.model_copy(update={"artifacts": [result.artifacts[0].model_copy(update={"data": {"industry": "only"}})]})

    outcome = await orchestrator.apply_result(project.id, broken)

    assert outcome.kind == "invalid" and outcome.problems
    assert brief.status == StageStatus.ERROR
    assert brief.error["code"] == StageErrorCode.GENERATION_FAILED
    assert brief.artifacts == []


async def test_a_failed_result_moves_the_row_to_error_with_the_failure(orchestrator, stage_service, project, fake_queue):
    brief, _ = await brief_result(orchestrator, stage_service, project)
    failed = artifacts.failure(stage_row_to_wire(brief), project_id=str(project.id), code=StageErrorCode.CHECK_FAILED)

    outcome = await orchestrator.apply_result(project.id, failed)

    assert outcome.kind == "applied"
    assert brief.status == StageStatus.ERROR
    assert brief.error == {"code": "check_failed", "message": "The model failed."}
    assert len(fake_queue.messages) == 1  # nothing new started


async def test_an_error_level_violation_awaits_a_decision_and_blocks_the_next_rows(orchestrator, stage_service, project, fake_queue):
    brief, result = await brief_result(orchestrator, stage_service, project)
    result = result.model_copy(update={"consistency": artifacts.error_report()})
    fake_queue.messages.clear()

    await orchestrator.apply_result(project.id, result)

    assert brief.status == StageStatus.AWAITING_DECISION
    assert brief.consistency["violations"][0]["severity"] == "error"
    assert fake_queue.messages == []
    assert [r.stage for r in await stage_service.get_rows(project.id)] == [S.BRIEF]


async def test_auto_approve_applies_the_approval_at_once_and_keeps_the_report(orchestrator, stage_service, project, fake_queue):
    project.auto_approve = True
    brief, result = await brief_result(orchestrator, stage_service, project)
    result = result.model_copy(update={"consistency": artifacts.error_report()})

    await orchestrator.apply_result(project.id, result)

    assert brief.status == StageStatus.DONE
    assert brief.approved_at is not None
    assert brief.consistency["violations"][0]["severity"] == "error"
    assert {r.stage for r in await stage_service.get_rows(project.id)} >= {S.EMPATHY_MAP}


async def test_a_warning_does_not_block_done(orchestrator, stage_service, project):
    brief, result = await brief_result(orchestrator, stage_service, project)

    await orchestrator.apply_result(project.id, result.model_copy(update={"consistency": artifacts.warning_report()}))

    assert brief.status == StageStatus.DONE and brief.approved_at is None


# --- approve -------------------------------------------------------------------


async def test_approve_moves_an_awaiting_row_to_done_and_continues(orchestrator, stage_service, project, fake_queue):
    brief, result = await brief_result(orchestrator, stage_service, project)
    await orchestrator.apply_result(project.id, result.model_copy(update={"consistency": artifacts.error_report()}))

    await orchestrator.approve(project.id, brief.id)

    assert brief.status == StageStatus.DONE and brief.approved_at is not None
    assert brief.consistency is not None
    assert any(r.stage == S.EMPATHY_MAP and r.status == StageStatus.RUNNING for r in await stage_service.get_rows(project.id))


async def test_approve_on_a_row_that_is_not_awaiting_is_refused(orchestrator, stage_service, project):
    brief, _ = await brief_result(orchestrator, stage_service, project)

    with pytest.raises(StageActionNotAllowed):
        await orchestrator.approve(project.id, brief.id)


# --- regenerate ------------------------------------------------------------------


async def finished_brief_and_maps(orchestrator, stage_service, project, fake_queue):
    brief, result = await brief_result(orchestrator, stage_service, project, segments=2, groups=((1, 2),))
    await orchestrator.apply_result(project.id, result)
    return brief, [r for r in await stage_service.get_rows(project.id) if r.stage == S.EMPATHY_MAP]


async def test_regenerate_resets_the_row_and_its_dependents_and_keeps_row_ids(orchestrator, stage_service, project, fake_queue):
    brief, maps = await finished_brief_and_maps(orchestrator, stage_service, project, fake_queue)
    ids_before = {r.id for r in await stage_service.get_rows(project.id)}
    old_attempt = brief.attempt_id
    fake_queue.messages.clear()

    await orchestrator.regenerate(project.id, brief.id)

    rows = await stage_service.get_rows(project.id)
    assert {r.id for r in rows} == ids_before  # no row created or removed
    assert brief.status == StageStatus.RUNNING and brief.attempt_id != old_attempt
    assert brief.artifacts == []
    assert all(r.status == StageStatus.PENDING and r.artifacts == [] for r in rows if r.stage != S.BRIEF)
    assert fake_queue.row_ids() == [brief.id]


async def test_regenerate_an_error_row_is_a_retry(orchestrator, stage_service, project, fake_queue):
    brief, _ = await brief_result(orchestrator, stage_service, project)
    await orchestrator.fail(project.id, brief.id, FAILURE)
    fake_queue.messages.clear()

    await orchestrator.regenerate(project.id, brief.id)

    assert brief.status == StageStatus.RUNNING and brief.error is None
    assert fake_queue.row_ids() == [brief.id]


async def test_regenerate_a_running_row_is_refused(orchestrator, stage_service, project):
    brief, _ = await brief_result(orchestrator, stage_service, project)

    with pytest.raises(StageActionNotAllowed):
        await orchestrator.regenerate(project.id, brief.id)


async def test_regenerate_unknown_row_raises_not_found(orchestrator, project):
    with pytest.raises(StageRowNotFound):
        await orchestrator.regenerate(project.id, "nope")


# --- watchdog -------------------------------------------------------------------


async def test_a_row_running_past_the_timeout_becomes_a_stuck_timeout_error(orchestrator, stage_service, project, session, fake_events):
    await start(orchestrator, project)
    (brief,) = await stage_service.get_rows(project.id)
    brief.started_at = datetime.now(timezone.utc) - timedelta(seconds=1801)
    await session.commit()
    fake_events.events.clear()

    await GenerationOrchestrator(session, stage_service, FakeQueue(), fake_events, stuck_timeout_seconds=1800).expire_stuck([project.id])

    assert brief.status == StageStatus.ERROR
    assert brief.error["code"] == StageErrorCode.STUCK_TIMEOUT
    assert [(e.stage_row_id, e.status) for e in fake_events.events] == [(brief.id, StageStatus.ERROR)]


async def test_the_watchdog_leaves_old_rows_that_are_not_running_alone(orchestrator, stage_service, project, session):
    await stage_service.create_rows(project.id, chain_specs())
    await walk_to_done(stage_service, project.id, "brief")
    old = datetime.now(timezone.utc) - timedelta(hours=3)
    brief = await stage_service.get_row(project.id, "brief")
    brief.started_at = old  # DONE, but long ago
    em0 = await stage_service.get_row(project.id, "em0")
    await stage_service.transition(em0, StageStatus.RUNNING)
    em0.started_at = old  # stuck
    await session.commit()

    await orchestrator.expire_stuck([project.id])

    assert brief.status == StageStatus.DONE
    assert em0.status == StageStatus.ERROR


async def test_a_row_within_the_timeout_is_left_running(orchestrator, stage_service, project, session):
    await start(orchestrator, project)
    (brief,) = await stage_service.get_rows(project.id)
    brief.started_at = datetime.now(timezone.utc) - timedelta(seconds=1700)
    await session.commit()

    await orchestrator.expire_stuck([project.id])

    assert brief.status == StageStatus.RUNNING


async def test_expire_stuck_only_looks_at_the_given_projects(orchestrator, stage_service, project, session):
    await start(orchestrator, project)
    (brief,) = await stage_service.get_rows(project.id)
    brief.started_at = datetime.now(timezone.utc) - timedelta(hours=3)
    await session.commit()

    await orchestrator.expire_stuck([])

    assert brief.status == StageStatus.RUNNING


async def test_a_late_result_for_a_stuck_row_is_stale(orchestrator, stage_service, project, session):
    brief, result = await brief_result(orchestrator, stage_service, project)
    brief.started_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await session.commit()
    await orchestrator.expire_stuck([project.id])

    with pytest.raises(StaleAttempt):
        await orchestrator.apply_result(project.id, result)
