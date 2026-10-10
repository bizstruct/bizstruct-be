import asyncio
import uuid

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from bizstruct_domain import StageErrorCode, StageStatus

from app.core.database import Base, settings
from app.models import Project, Stage, User
from app.services.orchestrator import GenerationOrchestrator
from app.services.stage import StageService
from tests.fakes.queue import FakeQueue

# Own engine/session, same NullPool rationale as test_stage_service.py: one
# connection per test's event loop, nothing held across test boundaries.
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
def stage_service(session):
    return StageService(session)


@pytest_asyncio.fixture
def fake_queue():
    return FakeQueue()


@pytest_asyncio.fixture
def orchestrator(session, stage_service, fake_queue):
    return GenerationOrchestrator(session, stage_service, fake_queue)


async def _run_to_done(stage_service, project_id, stage_type):
    """Walks a stage all the way from `pending` to `done`, bypassing the orchestrator."""
    stage = await stage_service.get_stage(project_id, stage_type)
    await stage_service.transition(stage, StageStatus.RUNNING)
    await stage_service.transition(stage, StageStatus.CONSISTENCY_CHECK)
    await stage_service.transition(stage, StageStatus.DONE)


# --- run_stage -------------------------------------------------------------


async def test_run_stage_transitions_to_running_and_commits(orchestrator, stage_service, project, session):
    await stage_service.create_stages(project.id)
    await session.commit()

    result = await orchestrator.run_stage(project.id, "brief", project_language="en")
    assert result.status == StageStatus.RUNNING

    async with _SessionLocal() as other_session:
        other_stage = await StageService(other_session).get_stage(project.id, "brief")
        assert other_stage.status == StageStatus.RUNNING


async def test_run_stage_sends_exactly_one_generation_message(orchestrator, stage_service, project, session, fake_queue):
    await stage_service.create_stages(project.id)
    await session.commit()

    await orchestrator.run_stage(project.id, "brief", project_language="en")

    assert len(fake_queue.generation_messages) == 1
    message = fake_queue.generation_messages[0]
    assert message["project_id"] == project.id
    assert message["stage_type"] == "brief"
    assert message["language"] == "en"


async def test_run_stage_comment_reaches_the_message(orchestrator, stage_service, project, session, fake_queue):
    await stage_service.create_stages(project.id)
    await session.commit()

    await orchestrator.run_stage(project.id, "brief", project_language="en", comment="please redo the intro")

    assert fake_queue.generation_messages[0]["comment"] == "please redo the intro"


async def test_run_stage_reset_retry_resets_retry_count(orchestrator, stage_service, project, session):
    await stage_service.create_stages(project.id)
    await session.commit()

    brief = await stage_service.get_stage(project.id, "brief")
    await stage_service.transition(brief, StageStatus.RUNNING)
    await stage_service.transition(brief, StageStatus.CONSISTENCY_CHECK)
    await stage_service.transition(brief, StageStatus.NEEDS_RETRY)
    brief.retry_count = 5
    await session.commit()

    result = await orchestrator.run_stage(project.id, "brief", project_language="en", reset_retry=True)
    assert result.retry_count == 0


async def test_run_stage_increment_retry_increments_retry_count(orchestrator, stage_service, project, session):
    await stage_service.create_stages(project.id)
    await session.commit()

    brief = await stage_service.get_stage(project.id, "brief")
    await stage_service.transition(brief, StageStatus.RUNNING)
    await stage_service.transition(brief, StageStatus.CONSISTENCY_CHECK)
    await stage_service.transition(brief, StageStatus.NEEDS_RETRY)
    brief.retry_count = 2
    await session.commit()

    result = await orchestrator.run_stage(project.id, "brief", project_language="en", increment_retry=True)
    assert result.retry_count == 3


async def test_run_stage_force_flag_reflects_retry_flags(orchestrator, stage_service, project, session, fake_queue):
    await stage_service.create_stages(project.id)
    await session.commit()

    brief = await stage_service.get_stage(project.id, "brief")
    await stage_service.transition(brief, StageStatus.RUNNING)
    await stage_service.transition(brief, StageStatus.CONSISTENCY_CHECK)
    await stage_service.transition(brief, StageStatus.NEEDS_RETRY)
    await session.commit()

    await orchestrator.run_stage(project.id, "brief", project_language="en", increment_retry=True)
    assert fake_queue.generation_messages[0]["force"] is True


async def test_run_stage_no_retry_flags_force_is_false(orchestrator, stage_service, project, session, fake_queue):
    await stage_service.create_stages(project.id)
    await session.commit()

    await orchestrator.run_stage(project.id, "brief", project_language="en")
    assert fake_queue.generation_messages[0]["force"] is False


async def test_run_stage_compensates_on_queue_failure(orchestrator, stage_service, project, session, fake_queue):
    await stage_service.create_stages(project.id)
    await session.commit()

    fake_queue.fail_next_enqueue = True
    result = await orchestrator.run_stage(project.id, "brief", project_language="en")

    assert result.status == StageStatus.ERROR
    assert result.error_code == StageErrorCode.QUEUE_UNAVAILABLE
    assert fake_queue.generation_messages == []

    async with _SessionLocal() as other_session:
        other_stage = await StageService(other_session).get_stage(project.id, "brief")
        assert other_stage.status == StageStatus.ERROR
        assert other_stage.error_code == StageErrorCode.QUEUE_UNAVAILABLE


# --- advance -----------------------------------------------------------


async def test_advance_fresh_project_starts_only_the_root_stage(orchestrator, stage_service, project, session, fake_queue):
    await stage_service.create_stages(project.id)
    await session.commit()

    started = await orchestrator.advance(project.id, project_language="en")

    assert [s.type for s in started] == ["brief"]
    assert started[0].status == StageStatus.RUNNING
    assert len(fake_queue.generation_messages) == 1


async def test_advance_called_twice_starts_nothing_the_second_time(orchestrator, stage_service, project, session, fake_queue):
    await stage_service.create_stages(project.id)
    await session.commit()

    first = await orchestrator.advance(project.id, project_language="en")
    assert len(first) == 1

    second = await orchestrator.advance(project.id, project_language="en")
    assert second == []
    assert len(fake_queue.generation_messages) == 1  # no new messages


async def test_advance_starts_parallel_ready_stages_together_in_graph_order(
    orchestrator, stage_service, project, session, fake_queue
):
    await stage_service.create_stages(project.id)
    await session.commit()

    # canvas and scenario share the exact same depends_on
    # (empathy_map, value_map, models_options) — once all three are done,
    # both become ready in the same call. environment_scan only depends on
    # brief/empathy_map, so it's also completed here to keep it from
    # becoming ready too and muddying the assertion.
    for stage_type in ("brief", "empathy_map", "environment_scan", "value_map", "models_options"):
        await _run_to_done(stage_service, project.id, stage_type)
    await session.commit()

    started = await orchestrator.advance(project.id, project_language="en")

    assert [s.type for s in started] == ["canvas", "scenario"]
    assert len(fake_queue.generation_messages) == 2


async def test_advance_serializes_concurrent_calls_for_the_same_project(stage_service, project, session, fake_queue):
    """Two advance() calls racing on the same project must not both start
    "brief": the second one's ready-snapshot has to be taken after the
    first one's run_stage has already committed, not before."""
    await stage_service.create_stages(project.id)
    await session.commit()

    async def run_advance():
        async with _SessionLocal() as own_session:
            own_orchestrator = GenerationOrchestrator(own_session, StageService(own_session), fake_queue)
            return await own_orchestrator.advance(project.id, project_language="en")

    results = await asyncio.gather(run_advance(), run_advance())

    all_started = [s.type for r in results for s in r]
    assert all_started == ["brief"]  # started exactly once, by exactly one of the two calls
    assert len(fake_queue.generation_messages) == 1


# --- fail ----------------------------------------------------------------


async def test_fail_moves_the_stage_to_error(orchestrator, stage_service, project, session):
    await stage_service.create_stages(project.id)
    await session.commit()

    brief = await stage_service.get_stage(project.id, "brief")
    await stage_service.transition(brief, StageStatus.RUNNING)
    await session.commit()

    result = await orchestrator.fail(project.id, "brief", error_code=StageErrorCode.GENERATION_FAILED, error="boom")

    assert result.status == StageStatus.ERROR
    assert result.error_code == StageErrorCode.GENERATION_FAILED
    assert result.error == "boom"


async def test_fail_does_not_touch_the_queue(orchestrator, stage_service, project, session, fake_queue):
    await stage_service.create_stages(project.id)
    await session.commit()

    brief = await stage_service.get_stage(project.id, "brief")
    await stage_service.transition(brief, StageStatus.RUNNING)
    await session.commit()

    await orchestrator.fail(project.id, "brief", error_code=StageErrorCode.GENERATION_FAILED)

    assert fake_queue.generation_messages == []
    assert fake_queue.control_messages == []


async def test_fail_does_not_touch_other_stages(orchestrator, stage_service, project, session):
    await stage_service.create_stages(project.id)
    await session.commit()

    brief = await stage_service.get_stage(project.id, "brief")
    await stage_service.transition(brief, StageStatus.RUNNING)
    await session.commit()

    await orchestrator.fail(project.id, "brief", error_code=StageErrorCode.GENERATION_FAILED)

    empathy_map = await stage_service.get_stage(project.id, "empathy_map")
    assert empathy_map.status == StageStatus.PENDING


# --- cancel --------------------------------------------------------------


async def test_cancel_moves_active_stages_to_error_and_sends_control_messages(
    orchestrator, stage_service, project, session, fake_queue
):
    await stage_service.create_stages(project.id)
    await session.commit()

    brief = await stage_service.get_stage(project.id, "brief")
    await stage_service.transition(brief, StageStatus.RUNNING)

    empathy_map = await stage_service.get_stage(project.id, "empathy_map")
    await stage_service.transition(empathy_map, StageStatus.RUNNING)
    await stage_service.transition(empathy_map, StageStatus.CONSISTENCY_CHECK)

    # needs_retry is not "active" for cancel purposes: nothing is running
    # for it, and the domain has no needs_retry -> error edge (D26).
    value_map = await stage_service.get_stage(project.id, "value_map")
    await stage_service.transition(value_map, StageStatus.RUNNING)
    await stage_service.transition(value_map, StageStatus.CONSISTENCY_CHECK)
    await stage_service.transition(value_map, StageStatus.NEEDS_RETRY)

    await session.commit()

    canceled = await orchestrator.cancel(project.id)

    canceled_types = {s.type for s in canceled}
    assert canceled_types == {"brief", "empathy_map"}
    for stage in canceled:
        assert stage.status == StageStatus.ERROR
        assert stage.error_code == StageErrorCode.CANCELED_BY_USER

    assert len(fake_queue.control_messages) == 2
    control_types = {m["stage_type"] for m in fake_queue.control_messages}
    assert control_types == {"brief", "empathy_map"}

    value_map = await stage_service.get_stage(project.id, "value_map")
    assert value_map.status == StageStatus.NEEDS_RETRY  # left untouched


async def test_cancel_leaves_untouched_stages_alone(orchestrator, stage_service, project, session):
    await stage_service.create_stages(project.id)
    await session.commit()

    brief = await stage_service.get_stage(project.id, "brief")
    await stage_service.transition(brief, StageStatus.RUNNING)
    await session.commit()

    await orchestrator.cancel(project.id)

    empathy_map = await stage_service.get_stage(project.id, "empathy_map")
    assert empathy_map.status == StageStatus.PENDING


async def test_cancel_commits_before_sending_control_messages(orchestrator, stage_service, project, session):
    await stage_service.create_stages(project.id)
    await session.commit()

    brief = await stage_service.get_stage(project.id, "brief")
    await stage_service.transition(brief, StageStatus.RUNNING)
    await session.commit()

    class _AssertCommittedQueue(FakeQueue):
        async def request_cancellation(self, **kwargs):
            async with _SessionLocal() as verify_session:
                verify_stage = await StageService(verify_session).get_stage(project.id, kwargs["stage_type"])
                assert verify_stage.status == StageStatus.ERROR
            await super().request_cancellation(**kwargs)

    checking_queue = _AssertCommittedQueue()
    checking_orchestrator = GenerationOrchestrator(session, stage_service, checking_queue)

    await checking_orchestrator.cancel(project.id)
    assert len(checking_queue.control_messages) == 1


async def test_cancel_on_a_project_with_nothing_active_is_a_noop(orchestrator, stage_service, project, session, fake_queue):
    await stage_service.create_stages(project.id)
    await session.commit()

    canceled = await orchestrator.cancel(project.id)

    assert canceled == []
    assert fake_queue.control_messages == []
