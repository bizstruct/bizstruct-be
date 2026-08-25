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


def _minimal_valid_scenario() -> dict:
    """A placeholder Scenario satisfying the domain model's constraints
    (exactly 5 timeline steps, in step_type order)."""
    steps = ["context", "goal", "action", "result", "impact"]
    return {
        "persona": {
            "name_uk": "Заповнювач", "name_en": "Placeholder",
            "role_uk": "Заповнювач", "role_en": "Placeholder",
            "pain_point_uk": "Заповнювач болю персони довжиною понад 10 символів",
            "pain_point_en": "Placeholder persona pain point over 10 characters",
        },
        "timeline": [
            {
                "step_type": step_type,
                "text_uk": f"Заповнювач кроку {step_type}", "text_en": f"Placeholder step {step_type}",
            }
            for step_type in steps
        ],
        "metrics": {
            "before": {"value_uk": "X", "value_en": "X", "label_uk": "Заповнювач", "label_en": "Placeholder"},
            "after": {"value_uk": "Y", "value_en": "Y", "label_uk": "Заповнювач", "label_en": "Placeholder"},
        },
    }


def _minimal_valid_pitch() -> dict:
    """A placeholder Pitch satisfying the domain model's constraints
    (exactly 5 slides per deck, in fixed order, headline <=80 chars)."""
    def _slide(slide_type: str) -> dict:
        return {
            "type": slide_type,
            "headline_uk": "Заповнювач", "headline_en": "Placeholder",
            "content_uk": "Заповнювач вмісту слайду довжиною понад 10 символів",
            "content_en": "Placeholder slide content over 10 characters long",
        }

    return {
        "investor": [_slide(t) for t in ("hook", "problem", "solution", "traction", "ask")],
        "customer": [_slide(t) for t in ("opening", "empathy", "transformation", "social_proof", "invitation")],
    }


def _minimal_valid_hypotheses() -> dict:
    """A placeholder Hypotheses satisfying the domain model's constraints
    (minimum 5, covering all three categories)."""
    def _h(i: int, category: str, quadrant: str) -> dict:
        return {
            "id": f"H{i}.1",
            "text": "A placeholder falsifiable claim involving a 10% metric",
            "category": category,
            "quadrant": quadrant,
        }

    return {
        "hypotheses": [
            _h(1, "desirability", "q1"),
            _h(2, "viability", "q2"),
            _h(3, "feasibility", "q3"),
            _h(4, "desirability", "q4"),
            _h(5, "viability", "q1"),
        ]
    }


def _minimal_valid_models_options() -> dict:
    """A placeholder ModelsOptions satisfying the domain model's constraints
    (exactly 3 options, each field meeting its min_length)."""
    def _option(i: int, monetization: str) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "title": f"Заповнювач варіант {i}",
            "audience": f"Заповнювач аудиторія {i}",
            "value_proposition": f"Заповнювач ціннісна пропозиція {i}",
            "description": f"Заповнювач розгорнутий опис моделі номер {i}, довший за 20 символів",
            "monetization": monetization,
            "key_metric": "MRR",
            "time_to_value": "2 weeks",
            "score": 50,
            "score_rationale": f"Заповнювач обґрунтування оцінки для варіанта {i}",
        }

    return {
        "options": [
            _option(1, "subscription"),
            _option(2, "transaction_fee"),
            _option(3, "retainer_plus_saas"),
        ],
        "selected_id": None,
    }


@pytest_asyncio.fixture
async def project_ready_for_architecture(db_session):
    """A project with every other block already filled, waiting on architecture."""
    p = Project(
        id=uuid.uuid4(),
        title="Test Project",
        idea="A test idea",
        status="generating",
        models_options=_minimal_valid_models_options(),
        canvas={"key_partners": []},
        empathy_map=_minimal_valid_empathy_map(),
        hypotheses=_minimal_valid_hypotheses(),
        pitch=_minimal_valid_pitch(),
        scenario=_minimal_valid_scenario(),
        what_if={"scenarios": []},
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    yield p


INTERNAL_HEADERS = {"x-api-key": "test-internal-key"}
