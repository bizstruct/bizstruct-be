"""The Alembic chain, as a fresh machine runs it (`alembic upgrade head` on an empty database).

Catches a missing parent revision (e.g. one that is git-ignored and so absent from a clean
clone), more than one head, and any drift between the migrations and the models.
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401 — registers every model on Base.metadata
from app.core.config import settings
from app.core.database import Base

ROOT = Path(__file__).resolve().parent.parent


def _admin_url() -> str:
    return (
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/postgres"
    )


@pytest_asyncio.fixture
async def empty_database():
    """A brand-new database on the test server; its name is yielded and it is removed afterwards."""
    name = f"bizstruct_migration_{uuid.uuid4().hex[:12]}"
    admin = create_async_engine(_admin_url(), isolation_level="AUTOCOMMIT", poolclass=NullPool)
    async with admin.connect() as conn:
        await conn.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield name
    finally:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await admin.dispose()


def _alembic(database: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Runs the alembic CLI exactly as docker compose does, against `database`."""
    env = {**os.environ, "POSTGRES_DB": database}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_there_is_exactly_one_head_and_the_chain_is_linear_from_the_first_revision():
    script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))

    assert len(script.get_heads()) == 1
    revisions = list(script.walk_revisions())  # head -> base; raises if a parent file is missing
    assert all(len(r.nextrev) <= 1 for r in revisions), "a revision has two children: the chain forks"
    assert all(isinstance(r.down_revision, (str, type(None))) for r in revisions), "a merge revision"
    assert sum(r.down_revision is None for r in revisions) == 1, "exactly one first revision"


async def test_upgrade_head_on_an_empty_database_matches_the_models(empty_database):
    result = _alembic(empty_database, "upgrade", "head")
    assert result.returncode == 0, result.stderr[-2000:]

    engine = create_async_engine(
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{empty_database}",
        poolclass=NullPool,
    )
    try:
        async with engine.connect() as conn:
            diffs = await conn.run_sync(lambda sync_conn: compare_metadata(MigrationContext.configure(sync_conn), Base.metadata))
    finally:
        await engine.dispose()

    assert diffs == []


async def test_upgrade_head_creates_the_stage_rows_table_and_no_stages_table(empty_database):
    assert _alembic(empty_database, "upgrade", "head").returncode == 0

    engine = create_async_engine(
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{empty_database}",
        poolclass=NullPool,
    )
    try:
        async with engine.connect() as conn:
            tables = {row[0] for row in await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))}
    finally:
        await engine.dispose()

    assert {"users", "projects", "stage_rows"} <= tables
    assert "stages" not in tables
