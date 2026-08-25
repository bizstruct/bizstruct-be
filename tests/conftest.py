import os

# Point at the test Postgres instance before any app module (settings are
# read at import time via pydantic-settings) is imported.
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "55432")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
os.environ.setdefault("POSTGRES_DB", "bizstruct_test")
os.environ.setdefault("INTERNAL_API_KEY", "test-internal-key")
# Leave SERVICE_BUS_CONNECTION_STRING / AZURE_WEB_PUBSUB_CONNECTION_STRING
# unset — both app.servicebus and app.pubsub no-op when they're empty, so
# hook/generation tests never touch a real Azure resource.

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.database as database
from app.database import Base
from app.main import app
from app.models import Project

# pytest-asyncio (mode=auto) gives every test function its own event loop.
# A pooled asyncpg connection opened on one test's loop can't be reused by
# the next test's loop ("attached to a different loop"). NullPool sidesteps
# this entirely: every checkout opens a fresh connection on the loop that's
# actually asking for one, and nothing is held across test boundaries.
# Swap this in for the app's real (pooled) engine/sessionmaker before any
# request is made — get_db() looks up `database.AsyncSessionLocal` fresh on
# every call, so replacing the module attribute here is enough.
_test_engine = create_async_engine(database.settings.database_url, poolclass=NullPool)
database.engine = _test_engine
database.AsyncSessionLocal = async_sessionmaker(
    bind=_test_engine, class_=database.AsyncSession, expire_on_commit=False
)


_schema_ready = False


@pytest_asyncio.fixture(autouse=True)
async def _create_schema():
    # Function-scoped (like every other fixture here) to match
    # pytest-asyncio's per-test event loop, but only does the DDL once —
    # NullPool means there's no persistent pool to accidentally straddle
    # loops between tests anyway.
    global _schema_ready
    if not _schema_ready:
        async with _test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        _schema_ready = True
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    async with database.AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def project(db_session):
    """A bare project with no blocks generated yet."""
    p = Project(
        id=uuid.uuid4(),
        title="Test Project",
        idea="A test idea",
        status="generating",
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    yield p


def _minimal_valid_empathy_map() -> dict:
    """A placeholder EmpathyMap satisfying the domain model's constraints
    (min_length=3 items per section, min_length=10 chars per item text)."""
    def _item(i: int) -> dict:
        return {"id": i, "text_uk": f"Заповнювач елемент {i}", "text_en": f"Placeholder item {i}"}

    section = [_item(1), _item(2), _item(3)]
    return {s: section for s in ("says", "thinks", "does", "feels", "pains", "gains")}


@pytest_asyncio.fixture
async def project_ready_for_architecture(db_session):
    """A project with every other block already filled, waiting on architecture."""
    p = Project(
        id=uuid.uuid4(),
        title="Test Project",
        idea="A test idea",
        status="generating",
        models_options={"models": []},
        canvas_data={"key_partners": []},
        empathy_map=_minimal_valid_empathy_map(),
        # NB: ProjectResponse types this dict[str, Any] | None even though
        # blocks.py's own hypotheses endpoints store a list — pre-existing
        # mismatch, not something this task touches. Use a dict here so this
        # fixture doesn't trip it.
        hypotheses={},
        pitch={"uk": {}},
        scenario={"uk": {}},
        what_if={"scenarios": []},
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    yield p


INTERNAL_HEADERS = {"x-api-key": "test-internal-key"}
