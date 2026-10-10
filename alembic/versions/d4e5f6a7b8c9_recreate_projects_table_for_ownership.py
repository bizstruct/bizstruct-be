"""recreate projects table for user ownership

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-21 00:00:00.000000

Drops the old hook/block-feature `projects` table (canvas, empathy_map,
hypotheses, pitch, scenario, what_if, architecture, models_options,
translation_key — all owned by the disabled hook routers) and replaces it
with a fresh table for the new user-owned projects feature
(app/models/project.py). Per user: the old table's data is disposable and
the old feature's code is being removed separately.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('projects')

    op.create_table(
        'projects',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('idea', sa.Text(), nullable=False),
        sa.Column('language', sa.String(length=32), nullable=False),
        sa.Column('mode', sa.String(length=32), nullable=False, server_default='pipeline'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_projects_user_id'), 'projects', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_projects_user_id'), table_name='projects')
    op.drop_table('projects')

    op.create_table(
        'projects',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('idea', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('translation_key', sa.String(length=255), nullable=True),
        sa.Column('models_options', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('canvas', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('empathy_map', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('hypotheses', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('pitch', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('scenario', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('what_if', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('architecture', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en'),
        sa.PrimaryKeyConstraint('id'),
    )
