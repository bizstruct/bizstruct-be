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
# unset — both adapters no-op when they're empty, and the API tests replace
# the queue and the event publisher with in-memory fakes anyway, so nothing
# ever touches a real Azure resource.

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import MetaData, delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core import dependencies
from app.core.database import Base, settings
from app.core.security import create_access_token
from app.main import app
from app.models import Project, StageRow, User
from tests.fakes.events import FakeEvents
from tests.fakes.queue import FakeQueue

# pytest-asyncio (mode=auto) gives every test function its own event loop.
# A pooled asyncpg connection opened on one test's loop can't be reused by
# the next test's loop ("attached to a different loop"). NullPool sidesteps
# this entirely: every checkout opens a fresh connection on the loop that's
# actually asking for one, and nothing is held across test boundaries.
_engine = create_async_engine(settings.database_url, poolclass=NullPool)
_SessionLocal = async_sessionmaker(bind=_engine, expire_on_commit=False, autoflush=False)

INTERNAL_HEADERS = {"x-api-key": "test-internal-key"}

_schema_ready = False


def _drop_everything(connection) -> None:
    """Drops every table in the test database, including ones the current models no
    longer know (e.g. `stages` from before ADR-0011), which `Base.metadata.drop_all` would miss."""
    leftover = MetaData()
    leftover.reflect(bind=connection)
    leftover.drop_all(bind=connection)


@pytest_asyncio.fixture
async def database():
    """Schema ready and every table empty. Not autouse: the pure unit tests never touch the database."""
    global _schema_ready
    if not _schema_ready:
        async with _engine.begin() as conn:
            await conn.run_sync(_drop_everything)
            await conn.run_sync(Base.metadata.create_all)
        _schema_ready = True
    # Fixed row ids in tests (and tidy assertions on "all rows") need an empty
    # database at the start of every test.
    async with _SessionLocal() as cleanup:
        for table in (StageRow, Project, User):
            await cleanup.execute(delete(table))
        await cleanup.commit()
    yield


@pytest.fixture
def session_factory(database):
    return _SessionLocal


@pytest_asyncio.fixture
async def session(session_factory):
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def user(session):
    u = User(email=f"{uuid.uuid4()}@example.com", password_hash="x")
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


@pytest_asyncio.fixture
async def other_user(session):
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


@pytest.fixture
def fake_queue():
    return FakeQueue()


@pytest.fixture
def fake_events():
    return FakeEvents()


@pytest.fixture
def auth_headers(user):
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest_asyncio.fixture
async def client(session_factory, fake_queue, fake_events):
    async def _session_override():
        async with _SessionLocal() as s:
            try:
                yield s
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[dependencies.get_db_session] = _session_override
    app.dependency_overrides[dependencies.get_queue] = lambda: fake_queue
    app.dependency_overrides[dependencies.get_events] = lambda: fake_events
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
