import asyncio
import itertools
import random
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from bizstruct_domain import STAGE_IDS, StageErrorCode, StageStatus
from bizstruct_domain.stage_machine import STAGE_TRANSITIONS

from app.core.database import Base, settings
from app.exceptions.stage import InvalidStageTransition, StageNotFound, StagesAlreadyExist
from app.models import Project, Stage, User
from app.services.stage import MAX_ERROR_MESSAGE_LENGTH, StageService

# Isolated from tests/conftest.py's engine, which is wired to the legacy
# app.database.Base (the pre-Stage hook architecture). Stage/Project/User
# live on app.core.database.Base, so this suite needs its own engine —
# same NullPool rationale as conftest.py: one connection per test's event
# loop, nothing held across test boundaries.
_engine = create_async_engine(settings.database_url, poolclass=NullPool)
_SessionLocal = async_sessionmaker(bind=_engine, expire_on_commit=False, autoflush=False)

_schema_ready = False


@pytest_asyncio.fixture(autouse=True)
async def _create_schema():
    global _schema_ready
    if not _schema_ready:
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        _schema_ready = True
    yield


@pytest_asyncio.fixture
async def session():
    async with _SessionLocal() as s:
        yield s


@pytest_asyncio.fixture
async def user(session):
    u = User(email=f"{uuid.uuid4()}@example.com", password_hash="x")
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


@pytest_asyncio.fixture
async def project(session, user):
    p = Project(user_id=user.id, title="Test", idea="An idea", language="en")
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


@pytest_asyncio.fixture
def service(session):
    return StageService(session)


# --- create_stages -----------------------------------------------------


async def test_create_stages_creates_one_per_domain_stage_in_pending(service, project, session):
    stages = await service.create_stages(project.id)

    assert len(stages) == len(STAGE_IDS)
    assert [s.type for s in stages] == list(STAGE_IDS)
    assert all(s.status == StageStatus.PENDING for s in stages)
    await session.commit()


async def test_create_stages_twice_raises_stages_already_exist(service, project, session):
    await service.create_stages(project.id)
    await session.commit()

    with pytest.raises(StagesAlreadyExist):
        await service.create_stages(project.id)

    count = await session.execute(
        Stage.__table__.select().where(Stage.project_id == project.id)
    )
    assert len(count.fetchall()) == len(STAGE_IDS)


# --- get_stages ----------------------------------------------------------


async def test_get_stages_returns_domain_graph_order_not_creation_order(service, project, session):
    # Bypass create_stages and insert rows directly in a shuffled order, so
    # a pass based on created_at or insertion order would fail here.
    shuffled_ids = list(STAGE_IDS)
    random.Random(42).shuffle(shuffled_ids)
    assert shuffled_ids != list(STAGE_IDS)  # sanity: the shuffle actually changed the order

    for stage_id in shuffled_ids:
        session.add(Stage(project_id=project.id, type=stage_id, status=StageStatus.PENDING))
    await session.commit()

    stages = await service.get_stages(project.id)
    assert [s.type for s in stages] == list(STAGE_IDS)


# --- get_stage -------------------------------------------------------------


async def test_get_stage_returns_the_matching_stage(service, project, session):
    await service.create_stages(project.id)
    await session.commit()

    stage = await service.get_stage(project.id, STAGE_IDS[0])
    assert stage.type == STAGE_IDS[0]


async def test_get_stage_missing_raises_stage_not_found(service, project):
    with pytest.raises(StageNotFound):
        await service.get_stage(project.id, STAGE_IDS[0])


async def test_get_stage_existing_type_wrong_project_raises_stage_not_found(service, project, session, user):
    await service.create_stages(project.id)
    await session.commit()

    other_project = Project(user_id=user.id, title="Other", idea="Another idea", language="en")
    session.add(other_project)
    await session.commit()
    await session.refresh(other_project)

    with pytest.raises(StageNotFound):
        await service.get_stage(other_project.id, STAGE_IDS[0])


async def test_get_stage_lock_blocks_a_second_transaction(project, session):
    setup_service = StageService(session)
    await setup_service.create_stages(project.id)
    await session.commit()

    session_a = _SessionLocal()
    session_b = _SessionLocal()
    try:
        service_a = StageService(session_a)
        service_b = StageService(session_b)

        async with session_a.begin():
            await service_a.get_stage(project.id, STAGE_IDS[0], lock=True)

            async with session_b.begin():
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(
                        service_b.get_stage(project.id, STAGE_IDS[0], lock=True),
                        timeout=0.5,
                    )
                await session_b.rollback()

        # Released once session_a's transaction ends; session_b can now
        # acquire the lock.
        async with session_b.begin():
            stage = await asyncio.wait_for(
                service_b.get_stage(project.id, STAGE_IDS[0], lock=True),
                timeout=2,
            )
            assert stage.type == STAGE_IDS[0]
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
async def stage(service, project, session):
    stages = await service.create_stages(project.id)
    await session.commit()
    return stages[0]


@pytest.mark.parametrize("current,target", STAGE_TRANSITIONS)
async def test_every_allowed_edge_is_accepted(service, stage, current, target, session):
    stage.status = current
    session.add(stage)
    await session.flush()

    kwargs = {}
    if target == StageStatus.ERROR:
        kwargs["error_code"] = StageErrorCode.GENERATION_FAILED

    result = await service.transition(stage, target, **kwargs)
    assert result.status == target


@pytest.mark.parametrize("current,target", FORBIDDEN_SAMPLE)
async def test_forbidden_edges_are_rejected(service, stage, current, target, session):
    stage.status = current
    session.add(stage)
    await session.flush()

    with pytest.raises(InvalidStageTransition):
        await service.transition(stage, target)

    assert stage.status == current  # untouched


_VALID_TRANSITIONS_SET = set(STAGE_TRANSITIONS)


@pytest.mark.parametrize("current,target", list(itertools.product(ALL_STATUSES, ALL_STATUSES)))
async def test_all_status_pairs_transition_table(service, stage, current, target, session):
    """Table-driven over every (current, target) pair: the 16 valid edges land on `target`
    exactly, the remaining 33 raise InvalidStageTransition."""
    stage.status = current
    session.add(stage)
    await session.flush()

    kwargs = {"error_code": StageErrorCode.GENERATION_FAILED} if target == StageStatus.ERROR else {}

    if (current, target) in _VALID_TRANSITIONS_SET:
        result = await service.transition(stage, target, **kwargs)
        assert result.status == target
    else:
        with pytest.raises(InvalidStageTransition):
            await service.transition(stage, target, **kwargs)
        assert stage.status == current


# --- transition: field side effects -------------------------------------


async def test_entering_running_sets_started_and_clears_others(service, stage, session):
    stage.status = StageStatus.PENDING
    session.add(stage)
    await session.flush()

    await service.transition(stage, StageStatus.RUNNING)

    assert stage.started_at is not None
    assert stage.finished_at is None
    assert stage.approved_at is None
    assert stage.error is None
    assert stage.error_code is None


async def test_running_to_running_clears_stale_error_state(service, stage, session):
    stage.status = StageStatus.RUNNING
    stage.error = "stale"
    stage.error_code = StageErrorCode.GENERATION_FAILED
    stage.approved_at = None
    await session.flush()

    await service.transition(stage, StageStatus.RUNNING)

    assert stage.error is None
    assert stage.error_code is None
    assert stage.started_at is not None


@pytest.mark.parametrize(
    "current,target",
    [
        (StageStatus.AWAITING_DECISION, StageStatus.DONE),
        (StageStatus.RUNNING, StageStatus.ERROR),
        (StageStatus.CONSISTENCY_CHECK, StageStatus.AWAITING_DECISION),
    ],
)
async def test_entering_finished_states_sets_finished_at(service, stage, current, target, session):
    stage.status = current
    session.add(stage)
    await session.flush()

    kwargs = {"error_code": StageErrorCode.GENERATION_FAILED} if target == StageStatus.ERROR else {}
    await service.transition(stage, target, **kwargs)

    assert stage.finished_at is not None


async def test_entering_consistency_check_does_not_set_finished_at(service, stage, session):
    stage.status = StageStatus.RUNNING
    session.add(stage)
    await session.flush()

    await service.transition(stage, StageStatus.CONSISTENCY_CHECK)
    assert stage.finished_at is None


async def test_entering_awaiting_decision_only_touches_finished_at_and_status(service, stage, session):
    await service.transition(stage, StageStatus.RUNNING)
    started_before = stage.started_at
    assert started_before is not None

    await service.transition(stage, StageStatus.CONSISTENCY_CHECK)
    await service.transition(stage, StageStatus.AWAITING_DECISION)

    assert stage.status == StageStatus.AWAITING_DECISION
    assert stage.finished_at is not None
    assert stage.started_at == started_before  # untouched by entering awaiting_decision
    assert stage.approved_at is None
    assert stage.error is None
    assert stage.error_code is None


async def test_approved_at_only_set_when_marked_as_approval(service, stage, session):
    stage.status = StageStatus.AWAITING_DECISION
    session.add(stage)
    await session.flush()

    await service.transition(stage, StageStatus.DONE)
    assert stage.approved_at is None


async def test_approved_at_set_when_transition_marked_as_approval(service, stage, session):
    stage.status = StageStatus.AWAITING_DECISION
    session.add(stage)
    await session.flush()

    await service.transition(stage, StageStatus.DONE, approved=True)
    assert stage.approved_at is not None
    assert stage.finished_at is not None


async def test_approved_true_with_non_done_target_raises_value_error(service, stage, session):
    stage.status = StageStatus.PENDING
    session.add(stage)
    await session.flush()

    with pytest.raises(ValueError):
        await service.transition(stage, StageStatus.RUNNING, approved=True)


async def test_entering_pending_clears_everything(service, stage, session):
    stage.status = StageStatus.ERROR
    stage.started_at = None
    stage.finished_at = None
    stage.approved_at = None
    stage.error = "boom"
    stage.error_code = StageErrorCode.GENERATION_FAILED
    session.add(stage)
    await session.flush()

    await service.transition(stage, StageStatus.PENDING)

    assert stage.started_at is None
    assert stage.finished_at is None
    assert stage.approved_at is None
    assert stage.error is None
    assert stage.error_code is None


async def test_entering_error_requires_error_code(service, stage, session):
    stage.status = StageStatus.RUNNING
    session.add(stage)
    await session.flush()

    with pytest.raises(ValueError):
        await service.transition(stage, StageStatus.ERROR)


async def test_entering_error_truncates_message(service, stage, session):
    stage.status = StageStatus.RUNNING
    session.add(stage)
    await session.flush()

    long_message = "x" * (MAX_ERROR_MESSAGE_LENGTH + 100)
    await service.transition(
        stage, StageStatus.ERROR, error_code=StageErrorCode.GENERATION_FAILED, error=long_message
    )

    assert stage.error is not None
    assert len(stage.error) == MAX_ERROR_MESSAGE_LENGTH


async def test_entering_error_without_error_message_leaves_error_none(service, stage, session):
    stage.status = StageStatus.RUNNING
    session.add(stage)
    await session.flush()

    await service.transition(stage, StageStatus.ERROR, error_code=StageErrorCode.GENERATION_FAILED)

    assert stage.error is None
    assert stage.error_code == StageErrorCode.GENERATION_FAILED
    assert stage.finished_at is not None


async def test_entering_error_short_message_not_truncated(service, stage, session):
    stage.status = StageStatus.RUNNING
    session.add(stage)
    await session.flush()

    await service.transition(
        stage, StageStatus.ERROR, error_code=StageErrorCode.GENERATION_FAILED, error="boom"
    )

    assert stage.error == "boom"


async def test_retry_count_untouched_by_default(service, stage, session):
    stage.status = StageStatus.NEEDS_RETRY
    stage.retry_count = 3
    session.add(stage)
    await session.flush()

    await service.transition(stage, StageStatus.RUNNING)
    assert stage.retry_count == 3


async def test_retry_count_increment_is_explicit(service, stage, session):
    stage.status = StageStatus.NEEDS_RETRY
    stage.retry_count = 3
    stage.error = "stale"
    stage.error_code = StageErrorCode.GENERATION_FAILED
    session.add(stage)
    await session.flush()

    await service.transition(stage, StageStatus.RUNNING, increment_retry=True)
    assert stage.retry_count == 4
    assert stage.started_at is not None
    assert stage.error is None
    assert stage.error_code is None


async def test_increment_retry_with_non_running_target_raises_value_error(service, stage, session):
    stage.status = StageStatus.AWAITING_DECISION
    session.add(stage)
    await session.flush()

    with pytest.raises(ValueError):
        await service.transition(stage, StageStatus.DONE, increment_retry=True)


async def test_reset_retry_with_non_running_target_raises_value_error(service, stage, session):
    stage.status = StageStatus.AWAITING_DECISION
    session.add(stage)
    await session.flush()

    with pytest.raises(ValueError):
        await service.transition(stage, StageStatus.DONE, reset_retry=True)


async def test_retry_count_reset_is_explicit(service, stage, session):
    stage.status = StageStatus.NEEDS_RETRY
    stage.retry_count = 3
    session.add(stage)
    await session.flush()

    await service.transition(stage, StageStatus.RUNNING, reset_retry=True)
    assert stage.retry_count == 0


async def test_increment_and_reset_together_rejected(service, stage, session):
    stage.status = StageStatus.NEEDS_RETRY
    session.add(stage)
    await session.flush()

    with pytest.raises(ValueError):
        await service.transition(stage, StageStatus.RUNNING, increment_retry=True, reset_retry=True)


async def test_transition_flushes_but_does_not_commit(service, stage, session, project):
    stage.status = StageStatus.PENDING
    session.add(stage)
    await session.flush()
    stage_type = stage.type
    project_id = project.id

    await service.transition(stage, StageStatus.RUNNING)

    # Visible within the same session/transaction before any commit.
    same_session_stage = await service.get_stage(project_id, stage_type)
    assert same_session_stage.status == StageStatus.RUNNING

    # Not yet visible to a separate connection/transaction.
    async with _SessionLocal() as other_session:
        other_stage = await StageService(other_session).get_stage(project_id, stage_type)
        assert other_stage.status == StageStatus.PENDING

    await session.rollback()

    # After rollback, nothing was persisted.
    async with _SessionLocal() as other_session:
        other_stage = await StageService(other_session).get_stage(project_id, stage_type)
        assert other_stage.status == StageStatus.PENDING


# --- reset_from ----------------------------------------------------------


async def test_reset_from_puts_stage_and_dependents_back_to_pending(service, project, session):
    await service.create_stages(project.id)
    await session.commit()

    # Walk "brief" all the way to "running", then to "consistency_check",
    # then to "done" so it's non-pending and eligible to reset.
    brief = await service.get_stage(project.id, "brief")
    await service.transition(brief, StageStatus.RUNNING)
    await service.transition(brief, StageStatus.CONSISTENCY_CHECK)
    await service.transition(brief, StageStatus.DONE)

    empathy_map = await service.get_stage(project.id, "empathy_map")
    await service.transition(empathy_map, StageStatus.RUNNING)
    await service.transition(empathy_map, StageStatus.CONSISTENCY_CHECK)
    await service.transition(empathy_map, StageStatus.DONE)

    reset_stages = await service.reset_from(project.id, "brief")

    # Only "brief" and "empathy_map" were moved out of pending above; every
    # other dependent of "brief" is still pending and must be skipped.
    reset_types = {s.type for s in reset_stages}
    assert reset_types == {"brief", "empathy_map"}

    all_stages = await service.get_stages(project.id)
    for s in all_stages:
        if s.type in reset_types:
            assert s.status == StageStatus.PENDING


async def test_reset_from_leaves_upstream_and_unrelated_stages_untouched(service, project, session):
    await service.create_stages(project.id)
    await session.commit()

    # "value_map" depends on "empathy_map", which depends on "brief".
    # "environment_scan" depends on "brief"/"empathy_map" but is not a
    # dependent of "value_map" — neither of these should be touched by
    # reset_from("value_map").
    for stage_id in ("brief", "empathy_map", "environment_scan", "value_map"):
        s = await service.get_stage(project.id, stage_id)
        await service.transition(s, StageStatus.RUNNING)
        await service.transition(s, StageStatus.CONSISTENCY_CHECK)
        await service.transition(s, StageStatus.DONE)

    reset_stages = await service.reset_from(project.id, "value_map")
    reset_types = {s.type for s in reset_stages}
    assert "brief" not in reset_types
    assert "empathy_map" not in reset_types
    assert "environment_scan" not in reset_types

    brief = await service.get_stage(project.id, "brief")
    empathy_map = await service.get_stage(project.id, "empathy_map")
    environment_scan = await service.get_stage(project.id, "environment_scan")
    assert brief.status == StageStatus.DONE
    assert empathy_map.status == StageStatus.DONE
    assert environment_scan.status == StageStatus.DONE

    value_map = await service.get_stage(project.id, "value_map")
    assert value_map.status == StageStatus.PENDING


async def test_reset_from_does_not_touch_retry_count(service, project, session):
    await service.create_stages(project.id)
    await session.commit()

    brief = await service.get_stage(project.id, "brief")
    await service.transition(brief, StageStatus.RUNNING)
    await service.transition(brief, StageStatus.CONSISTENCY_CHECK)
    await service.transition(brief, StageStatus.DONE)
    brief.retry_count = 7
    await session.flush()

    reset_stages = await service.reset_from(project.id, "brief")

    reset_brief = next(s for s in reset_stages if s.type == "brief")
    assert reset_brief.status == StageStatus.PENDING
    assert reset_brief.retry_count == 7


async def test_reset_from_skips_stages_already_pending(service, project, session):
    await service.create_stages(project.id)
    await session.commit()

    reset_stages = await service.reset_from(project.id, "brief")

    # Every dependent stage was already pending, so nothing to transition.
    assert reset_stages == []


async def test_reset_from_processes_in_graph_order(service, project, session):
    await service.create_stages(project.id)
    await session.commit()

    for stage_id in ("brief", "empathy_map", "value_map"):
        s = await service.get_stage(project.id, stage_id)
        await service.transition(s, StageStatus.RUNNING)
        await service.transition(s, StageStatus.CONSISTENCY_CHECK)
        await service.transition(s, StageStatus.DONE)

    reset_stages = await service.reset_from(project.id, "brief")
    order = {stage_id: i for i, stage_id in enumerate(STAGE_IDS)}
    reset_order = [order[s.type] for s in reset_stages]
    assert reset_order == sorted(reset_order)


# --- no commit ----------------------------------------------------------


async def test_service_never_commits(project, session):
    project_id = project.id
    service = StageService(session)
    await service.create_stages(project_id)
    # No commit here — roll back and check nothing landed in a fresh
    # session/transaction, proving the service itself never committed.
    await session.rollback()

    async with _SessionLocal() as other_session:
        other_service = StageService(other_session)
        with pytest.raises(StageNotFound):
            await other_service.get_stage(project_id, STAGE_IDS[0])
