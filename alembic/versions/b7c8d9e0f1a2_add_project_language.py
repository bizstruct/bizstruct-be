"""add project language column

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-08-28 00:00:00.000000

Adds a dedicated `language` column to `projects` — part E of the
data-quality-fixes brief needs an actual generation-language parameter
fixed per project ("uk" or "en"). `translation_key` was NOT this: it's a
pre-existing, unrelated field holding frontend i18n lookup keys for demo
project titles (see seed.py — "project.ecosync", "project.smart_grid",
etc.), not a language code. An earlier pass in this task mistakenly reused
`translation_key` as if it were the language field; this migration and
the accompanying code changes correct that.

No data migration needed — there's no production data (see
a1b2c3d4e5f6's docstring for the same note).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'projects',
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en'),
    )


def downgrade() -> None:
    op.drop_column('projects', 'language')
