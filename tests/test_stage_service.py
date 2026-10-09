import asyncio
import itertools
import random
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from bizstruct_domain import (
    STAGE_IDS,
    ArtifactRecord,
    ArtifactType,
    ConsistencyReport,
    Stage,
    StageErrorCode,
    StageFailure,
    StageStatus,
)
from bizstruct_domain.stage_machine import STAGE_TRANSITIONS

from app.exceptions.stage import InvalidStageTransition, StageRowNotFound
from app.models import Project, StageRow
from app.services.orchestration import NewRow
from app.services.stage import MAX_ERROR_MESSAGE_LENGTH, StageService, to_wire_row

S = Stage
FAILURE = StageFailure(code=StageErrorCode.GENERATION_FAILED, message="boom")


@pytest.fixture
def service(session):
    return StageService(session)


def spec(row_id: str, stage: Stage, refs: dict[Stage, list[str]] | None = None, index: int = 0) -> NewRow:
    return NewRow(id=row_id, stage=stage, instance_index=index, refs=refs or {})


def chain_specs() -> list[NewRow]:
    """brief -> two empathy maps -> a scenario and an ideation each; an unrelated environment_scan."""
    return [
        spec("brief", S.BRIEF),
        spec("em0", S.EMPATHY_MAP, {S.BRIEF: ["brief"]}, 0),
        spec("em1", S.EMPATHY_MAP, {S.BRIEF: ["brief"]}, 1),
        spec("cs0", S.CUSTOMER_SCENARIO, {S.EMPATHY_MAP: ["em0"]}),
        spec("cs1", S.CUSTOMER_SCENARIO, {S.EMPATHY_MAP: ["em1"]}),
        spec("id0", S.IDEATION, {S.EMPATHY_MAP: ["em0"]}),
        spec("id1", S.IDEATION, {S.EMPATHY_MAP: ["em1"]}),
        spec("scan", S.ENVIRONMENT_SCAN, {S.BRIEF: ["brief"]}),
    ]


async def walk_to_done(service: StageService, project_id, row_id: str) -> None:
    row = await service.get_row(project_id, row_id)
    await service.transition(row, StageStatus.RUNNING)
    await service.transition(row, StageStatus.CONSISTENCY_CHECK)
    await service.transition(row, StageStatus.DONE)


# --- create_rows -------------------------------------------------------


async def test_create_rows_creates_pending_rows_with_the_given_ids_and_refs(service, project, session):
    rows = await service.create_rows(project.id, chain_specs())
    await session.commit()

    assert [r.id for r in rows] == [s.id for s in chain_specs()]
    assert all(r.status == StageStatus.PENDING for r in rows)
    em1 = next(r for r in rows if r.id == "em1")
    assert em1.stage == S.EMPATHY_MAP
    assert em1.instance_index == 1
    assert em1.refs == {"brief": ["brief"]}
    assert em1.artifacts == [] and em1.attempt_id is None and em1.retry_count == 0


async def test_a_stage_can_have_several_rows(service, project, session):
    rows = await service.create_rows(project.id, [spec("a", S.EMPATHY_MAP, index=0), spec("b", S.EMPATHY_MAP, index=1)])
    await session.commit()

    assert {r.stage for r in rows} == {S.EMPATHY_MAP}
    assert len(await service.get_rows(project.id)) == 2


async def test_create_rows_persists_json_columns(service, project, session, session_factory):
    await service.create_rows(project.id, chain_specs())
    await session.commit()

    async with session_factory() as other:
        row = await StageService(other).get_row(project.id, "cs0")
        assert row.refs == {"empathy_map": ["em0"]}
        assert row.error is None and row.consistency is None


# --- get_rows ---------------------------------------------------------


async def test_get_rows_returns_graph_order_then_instance_index_not_insertion_order(service, project, session):
    specs = chain_specs()
    random.Random(7).shuffle(specs)
    for s in specs:
        session.add(StageRow(id=s.id, project_id=project.id, stage=s.stage, instance_index=s.instance_index, refs={}))
    await session.commit()

    rows = await service.get_rows(project.id)
    order = {stage: i for i, stage in enumerate(STAGE_IDS)}
    assert [(order[r.stage], r.instance_index) for r in rows] == sorted((order[r.stage], r.instance_index) for r in rows)
    assert [r.id for r in rows if r.stage == S.EMPATHY_MAP] == ["em0", "em1"]


async def test_get_rows_only_returns_the_projects_rows(service, project, session, user):
    await service.create_rows(project.id, [spec("mine", S.BRIEF)])
    other = Project(user_id=user.id, title="Other", idea="Another idea", language="en")
    session.add(other)
    await session.commit()
    await service.create_rows(other.id, [spec("theirs", S.BRIEF)])
    await session.commit()

    assert [r.id for r in await service.get_rows(project.id)] == ["mine"]


# --- get_row -----------------------------------------------------------


async def test_get_row_returns_the_matching_row(service, project, session):
    await service.create_rows(project.id, chain_specs())
    await session.commit()

    assert (await service.get_row(project.id, "id1")).stage == S.IDEATION


async def test_get_row_missing_raises_not_found(service, project):
    with pytest.raises(StageRowNotFound):
        await service.get_row(project.id, "nope")


async def test_get_row_of_another_project_raises_not_found(service, project, session, user):
    await service.create_rows(project.id, [spec("r", S.BRIEF)])
    await session.commit()
    other = Project(user_id=user.id, title="Other", idea="Another idea", language="en")
    session.add(other)
    await session.commit()
    await session.refresh(other)

    with pytest.raises(StageRowNotFound):
        await service.get_row(other.id, "r")


async def test_get_row_lock_blocks_a_second_transaction(project, session, session_factory):
    await StageService(session).create_rows(project.id, [spec("r", S.BRIEF)])
    await session.commit()

    session_a = session_factory()
    session_b = session_factory()
    try:
        service_a = StageService(session_a)
        service_b = StageService(session_b)

        async with session_a.begin():
            await service_a.get_row(project.id, "r", lock=True)

            async with session_b.begin():
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(service_b.get_row(project.id, "r", lock=True), timeout=0.5)
                await session_b.rollback()

        # Released once session_a's transaction ends; session_b can now acquire the lock.
        async with session_b.begin():
            row = await asyncio.wait_for(service_b.get_row(project.id, "r", lock=True), timeout=2)
            assert row.id == "r"
    finally:
        await session_a.close()
        await session_b.close()


# --- transition: validity ---------------------------------------------


ALL_STATUSES = list(StageStatus)
FORBIDDEN_SAMPLE = [
    (StageStatus.PENDING, StageStatus.DONE),
    (StageStatus.PENDING, StageStatus.ERROR),
    (StageStatus.DONE, StageStatus.RUNNING),
    (StageStatus.NEEDS_RETRY, StageStatus.ERROR),
    (StageStatus.NEEDS_RETRY, StageStatus.PENDING),
    (StageStatus.ERROR, StageStatus.RUNNING),
    (StageStatus.ERROR, StageStatus.DONE),
]


@pytest_asyncio.fixture
async def row(service, project, session):
    rows = await service.create_rows(project.id, [spec("r", S.BRIEF)])
    await session.commit()
    return rows[0]


@pytest.mark.parametrize("current,target", STAGE_TRANSITIONS)
async def test_every_allowed_edge_is_accepted(service, row, current, target, session):
    row.status = current
    session.add(row)
    await session.flush()

    result = await service.transition(row, target, failure=FAILURE if target == StageStatus.ERROR else None)
    assert result.status == target


@pytest.mark.parametrize("current,target", FORBIDDEN_SAMPLE)
async def test_forbidden_edges_are_rejected(service, row, current, target, session):
    row.status = current
    session.add(row)
    await session.flush()

    with pytest.raises(InvalidStageTransition):
        await service.transition(row, target)

    assert row.status == current  # untouched


_VALID_TRANSITIONS_SET = set(STAGE_TRANSITIONS)


@pytest.mark.parametrize("current,target", list(itertools.product(ALL_STATUSES, ALL_STATUSES)))
async def test_all_status_pairs_transition_table(service, row, current, target, session):
    """Table-driven over every (current, target) pair: the valid edges of the domain's
    stage machine land on `target` exactly, every other pair raises InvalidStageTransition."""
    row.status = current
    session.add(row)
    await session.flush()

    failure = FAILURE if target == StageStatus.ERROR else None

    if (current, target) in _VALID_TRANSITIONS_SET:
        result = await service.transition(row, target, failure=failure)
        assert result.status == target
    else:
        with pytest.raises(InvalidStageTransition):
            await service.transition(row, target, failure=failure)
        assert row.status == current


# --- transition: field side effects -------------------------------------


async def test_entering_running_sets_started_and_a_new_attempt_and_clears_others(service, row, session):
    await service.transition(row, StageStatus.RUNNING)

    assert row.started_at is not None
    assert row.attempt_id is not None
    assert row.finished_at is None
    assert row.approved_at is None
    assert row.error is None


async def test_every_entry_into_running_issues_a_new_attempt(service, row, session):
    await service.transition(row, StageStatus.RUNNING)
    first = row.attempt_id
    await service.transition(row, StageStatus.PENDING)
    await service.transition(row, StageStatus.RUNNING)

    assert row.attempt_id is not None and row.attempt_id != first


async def test_running_again_issues_a_new_attempt_even_without_passing_through_pending(service, row, session):
    await service.transition(row, StageStatus.RUNNING)
    first = row.attempt_id

    await service.transition(row, StageStatus.RUNNING)

    assert row.attempt_id is not None and row.attempt_id != first


async def test_running_to_running_clears_stale_error_state(service, row, session):
    row.status = StageStatus.RUNNING
    row.error = FAILURE.model_dump(mode="json")
    await session.flush()

    await service.transition(row, StageStatus.RUNNING)

    assert row.error is None
    assert row.started_at is not None


@pytest.mark.parametrize(
    "current,target",
    [
        (StageStatus.AWAITING_DECISION, StageStatus.DONE),
        (StageStatus.RUNNING, StageStatus.ERROR),
        (StageStatus.CONSISTENCY_CHECK, StageStatus.AWAITING_DECISION),
    ],
)
async def test_entering_finished_states_sets_finished_at(service, row, current, target, session):
    row.status = current
    session.add(row)
    await session.flush()

    await service.transition(row, target, failure=FAILURE if target == StageStatus.ERROR else None)

    assert row.finished_at is not None


async def test_entering_consistency_check_does_not_set_finished_at(service, row, session):
    row.status = StageStatus.RUNNING
    await session.flush()

    await service.transition(row, StageStatus.CONSISTENCY_CHECK)
    assert row.finished_at is None


async def test_entering_awaiting_decision_only_touches_finished_at_and_status(service, row, session):
    await service.transition(row, StageStatus.RUNNING)
    started_before = row.started_at
    attempt_before = row.attempt_id
    assert started_before is not None

    await service.transition(row, StageStatus.CONSISTENCY_CHECK)
    await service.transition(row, StageStatus.AWAITING_DECISION)

    assert row.status == StageStatus.AWAITING_DECISION
    assert row.finished_at is not None
    assert row.started_at == started_before  # untouched by entering awaiting_decision
    assert row.attempt_id == attempt_before
    assert row.approved_at is None
    assert row.error is None


async def test_approved_at_only_set_when_marked_as_approval(service, row, session):
    row.status = StageStatus.AWAITING_DECISION
    await session.flush()

    await service.transition(row, StageStatus.DONE)
    assert row.approved_at is None


async def test_approved_at_set_when_transition_marked_as_approval(service, row, session):
    row.status = StageStatus.AWAITING_DECISION
    await session.flush()

    await service.transition(row, StageStatus.DONE, approved=True)
    assert row.approved_at is not None
    assert row.finished_at is not None


async def test_approved_true_with_non_done_target_raises_value_error(service, row, session):
    with pytest.raises(ValueError):
        await service.transition(row, StageStatus.RUNNING, approved=True)


async def test_entering_pending_clears_attempt_error_artifacts_and_report(service, row, session):
    row.status = StageStatus.ERROR
    row.attempt_id = "attempt"
    row.error = FAILURE.model_dump(mode="json")
    row.artifacts = [{"id": "a", "type": "brief", "data": {}}]
    row.consistency = {"score": 3, "violations": []}
    row.started_at = datetime.now(timezone.utc)
    row.approved_at = datetime.now(timezone.utc)
    await session.flush()

    await service.transition(row, StageStatus.PENDING)

    assert row.started_at is None and row.finished_at is None and row.approved_at is None
    assert row.error is None
    assert row.attempt_id is None
    assert row.artifacts == []
    assert row.consistency is None


async def test_entering_pending_keeps_the_row_id_and_refs(service, project, session):
    (child,) = await service.create_rows(project.id, [spec("c", S.EMPATHY_MAP, {S.BRIEF: ["brief"]})])
    child.status = StageStatus.DONE
    await session.flush()

    await service.transition(child, StageStatus.PENDING)

    assert child.id == "c"
    assert child.refs == {"brief": ["brief"]}


async def test_entering_error_requires_a_failure(service, row, session):
    row.status = StageStatus.RUNNING
    await session.flush()

    with pytest.raises(ValueError):
        await service.transition(row, StageStatus.ERROR)


async def test_entering_error_stores_the_failure_as_json(service, row, session):
    row.status = StageStatus.RUNNING
    await session.flush()

    await service.transition(row, StageStatus.ERROR, failure=FAILURE)

    assert row.error == {"code": "generation_failed", "message": "boom"}
    assert row.finished_at is not None


async def test_entering_error_truncates_message(service, row, session):
    row.status = StageStatus.RUNNING
    await session.flush()

    failure = StageFailure(code=StageErrorCode.GENERATION_FAILED, message="x" * (MAX_ERROR_MESSAGE_LENGTH + 100))
    await service.transition(row, StageStatus.ERROR, failure=failure)

    assert row.error is not None
    assert len(row.error["message"]) == MAX_ERROR_MESSAGE_LENGTH


async def test_retry_count_untouched_by_default(service, row, session):
    row.status = StageStatus.NEEDS_RETRY
    row.retry_count = 3
    await session.flush()

    await service.transition(row, StageStatus.RUNNING)
    assert row.retry_count == 3


async def test_retry_count_increment_is_explicit(service, row, session):
    row.status = StageStatus.NEEDS_RETRY
    row.retry_count = 3
    row.error = FAILURE.model_dump(mode="json")
    await session.flush()

    await service.transition(row, StageStatus.RUNNING, increment_retry=True)
    assert row.retry_count == 4
    assert row.started_at is not None
    assert row.error is None


async def test_increment_retry_with_non_running_target_raises_value_error(service, row, session):
    row.status = StageStatus.AWAITING_DECISION
    await session.flush()

    with pytest.raises(ValueError):
        await service.transition(row, StageStatus.DONE, increment_retry=True)


async def test_reset_retry_with_non_running_target_raises_value_error(service, row, session):
    row.status = StageStatus.AWAITING_DECISION
    await session.flush()

    with pytest.raises(ValueError):
        await service.transition(row, StageStatus.DONE, reset_retry=True)


async def test_retry_count_reset_is_explicit(service, row, session):
    row.status = StageStatus.NEEDS_RETRY
    row.retry_count = 3
    await session.flush()

    await service.transition(row, StageStatus.RUNNING, reset_retry=True)
    assert row.retry_count == 0


async def test_increment_and_reset_together_rejected(service, row, session):
    row.status = StageStatus.NEEDS_RETRY
    await session.flush()

    with pytest.raises(ValueError):
        await service.transition(row, StageStatus.RUNNING, increment_retry=True, reset_retry=True)


async def test_transition_flushes_but_does_not_commit(service, row, session, project, session_factory):
    project_id = project.id

    await service.transition(row, StageStatus.RUNNING)

    # Visible within the same session/transaction before any commit.
    assert (await service.get_row(project_id, "r")).status == StageStatus.RUNNING

    # Not yet visible to a separate connection/transaction.
    async with session_factory() as other_session:
        assert (await StageService(other_session).get_row(project_id, "r")).status == StageStatus.PENDING

    await session.rollback()

    # After rollback, nothing was persisted.
    async with session_factory() as other_session:
        assert (await StageService(other_session).get_row(project_id, "r")).status == StageStatus.PENDING


# --- record_result ----------------------------------------------------


def record(artifact_id: str) -> ArtifactRecord:
    return ArtifactRecord(id=artifact_id, type=ArtifactType.BRIEF, data={"k": artifact_id})


async def test_record_result_stores_artifacts_and_the_report(service, row, session):
    report = ConsistencyReport(score=4)

    await service.record_result(row, [record("a"), record("b")], report)

    assert [a["id"] for a in row.artifacts] == ["a", "b"]
    assert row.consistency["score"] == 4


async def test_record_result_replaces_the_whole_artifact_set(service, row, session):
    await service.record_result(row, [record("a"), record("b"), record("c")], ConsistencyReport(score=5))
    await service.record_result(row, [record("a")], None)

    assert [a["id"] for a in row.artifacts] == ["a"]
    assert row.consistency is None


async def test_record_result_does_not_change_the_status(service, row, session):
    await service.record_result(row, [record("a")], None)
    assert row.status == StageStatus.PENDING


# --- reset_from -----------------------------------------------------------


async def test_reset_from_puts_the_row_and_its_dependents_back_to_pending(service, project, session):
    await service.create_rows(project.id, chain_specs())
    await session.commit()
    for row_id in ("brief", "em0", "cs0"):
        await walk_to_done(service, project.id, row_id)

    reset = await service.reset_from(project.id, "em0")

    # em0 and its dependent cs0 were moved out of pending; id0 (also a dependent) was already pending and is skipped.
    assert {r.id for r in reset} == {"em0", "cs0"}
    assert all(r.status == StageStatus.PENDING for r in reset)


async def test_reset_from_clears_artifacts_and_keeps_row_ids(service, project, session):
    await service.create_rows(project.id, chain_specs())
    await session.commit()
    await walk_to_done(service, project.id, "brief")
    brief = await service.get_row(project.id, "brief")
    await service.record_result(brief, [record("a")], ConsistencyReport(score=5))

    await service.reset_from(project.id, "brief")

    assert brief.id == "brief"
    assert brief.artifacts == [] and brief.consistency is None


async def test_reset_from_leaves_upstream_siblings_and_unrelated_rows_untouched(service, project, session):
    await service.create_rows(project.id, chain_specs())
    await session.commit()
    for row_id in ("brief", "em0", "em1", "scan", "cs0"):
        await walk_to_done(service, project.id, row_id)

    reset = await service.reset_from(project.id, "cs0")

    assert {r.id for r in reset} == {"cs0"}
    for untouched in ("brief", "em0", "em1", "scan"):
        assert (await service.get_row(project.id, untouched)).status == StageStatus.DONE


async def test_reset_from_does_not_touch_retry_count(service, project, session):
    await service.create_rows(project.id, chain_specs())
    await session.commit()
    await walk_to_done(service, project.id, "brief")
    brief = await service.get_row(project.id, "brief")
    brief.retry_count = 7
    await session.flush()

    (reset_brief,) = await service.reset_from(project.id, "brief")

    assert reset_brief.status == StageStatus.PENDING
    assert reset_brief.retry_count == 7


async def test_reset_from_skips_rows_already_pending(service, project, session):
    await service.create_rows(project.id, chain_specs())
    await session.commit()

    assert await service.reset_from(project.id, "brief") == []


async def test_reset_from_processes_in_graph_order(service, project, session):
    await service.create_rows(project.id, chain_specs())
    await session.commit()
    for row_id in ("brief", "em0", "cs0", "id0"):
        await walk_to_done(service, project.id, row_id)

    reset = await service.reset_from(project.id, "brief")

    order = {stage: i for i, stage in enumerate(STAGE_IDS)}
    positions = [order[r.stage] for r in reset]
    assert positions == sorted(positions)


async def test_reset_from_unknown_row_raises_not_found(service, project, session):
    await service.create_rows(project.id, chain_specs())
    await session.commit()

    with pytest.raises(StageRowNotFound):
        await service.reset_from(project.id, "nope")


async def test_reset_from_a_dependent_that_cannot_go_back_raises(service, project, session):
    await service.create_rows(project.id, chain_specs())
    await session.commit()
    await walk_to_done(service, project.id, "brief")
    em0 = await service.get_row(project.id, "em0")
    em0.status = StageStatus.NEEDS_RETRY  # needs_retry has no edge to pending
    await session.flush()

    with pytest.raises(InvalidStageTransition):
        await service.reset_from(project.id, "brief")


# --- stale_running_rows ------------------------------------------------


async def test_stale_running_rows_selects_only_old_running_rows(service, project, session):
    await service.create_rows(project.id, chain_specs())
    now = datetime.now(timezone.utc)
    brief = await service.get_row(project.id, "brief")
    em0 = await service.get_row(project.id, "em0")
    em1 = await service.get_row(project.id, "em1")
    for r, started in ((brief, now - timedelta(hours=2)), (em0, now - timedelta(seconds=5))):
        r.status = StageStatus.RUNNING
        r.started_at = started
    em1.status = StageStatus.DONE
    em1.started_at = now - timedelta(hours=3)
    await session.commit()

    stale = await service.stale_running_rows([project.id], now - timedelta(hours=1))

    assert [r.id for r in stale] == ["brief"]


# --- wire mapping ----------------------------------------------------------


async def test_to_wire_row_flattens_the_stored_failure(service, project, session):
    (r,) = await service.create_rows(project.id, [spec("r", S.BRIEF)])
    await service.transition(r, StageStatus.RUNNING)
    await service.transition(r, StageStatus.ERROR, failure=FAILURE)

    wire = to_wire_row(r)

    assert wire.error_code == StageErrorCode.GENERATION_FAILED
    assert wire.error == "boom"
    assert wire.stage == S.BRIEF and wire.status == StageStatus.ERROR


# --- no commit ----------------------------------------------------------


async def test_service_never_commits(project, session, session_factory):
    project_id = project.id
    service = StageService(session)
    await service.create_rows(project_id, [spec("r", S.BRIEF)])
    # No commit here — roll back and check nothing landed in a fresh
    # session/transaction, proving the service itself never committed.
    await session.rollback()

    async with session_factory() as other_session:
        with pytest.raises(StageRowNotFound):
            await StageService(other_session).get_row(project_id, "r")
