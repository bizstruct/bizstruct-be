"""stage rows (ADR-0011): replace the one-row-per-stage model

Revision ID: f1a2b3c4d5e6
Revises: d4e5f6a7b8c9
Create Date: 2026-10-08 00:00:00.000000

Removes the `stages` table (UNIQUE(project_id, type): one row per stage) and
creates `stage_rows` (any number of rows per stage, with refs, attempt,
consistency and the artifacts). On `projects`, removes the columns the project
no longer owns (`mode`; `status`, now derived from the rows; `consistency_loop`)
and adds `enabled_optional` and `auto_approve`.

NO DATA MIGRATION. The previous rows describe a different model and cannot be
carried over: recreate the database volume (or at least empty `projects`)
before running generation again. No revision of this chain ever created
`stages` or `consistency_loop` (the models were only built with `create_all`),
so those two are removed only where they exist.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if inspector.has_table('stages'):
        op.drop_table('stages')

    existing_columns = {column['name'] for column in inspector.get_columns('projects')}
    for obsolete in ('mode', 'status', 'consistency_loop'):
        if obsolete in existing_columns:
            op.drop_column('projects', obsolete)
    op.add_column(
        'projects',
        sa.Column('enabled_optional', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    )
    op.add_column(
        'projects',
        sa.Column('auto_approve', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )

    op.create_table(
        'stage_rows',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('stage', sa.String(length=32), nullable=False),
        sa.Column('instance_index', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('status', sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('refs', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('attempt_id', sa.String(length=64), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('error', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('consistency', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('artifacts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint('retry_count >= 0', name='chk_stage_rows_retry_count_non_negative'),
        sa.CheckConstraint('instance_index >= 0', name='chk_stage_rows_instance_index_non_negative'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_stage_rows_project_id_stage_instance_index',
        'stage_rows',
        ['project_id', 'stage', 'instance_index'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_stage_rows_project_id_stage_instance_index', table_name='stage_rows')
    op.drop_table('stage_rows')

    op.drop_column('projects', 'auto_approve')
    op.drop_column('projects', 'enabled_optional')
    op.add_column('projects', sa.Column('status', sa.String(length=32), server_default='pending', nullable=False))
    op.add_column('projects', sa.Column('mode', sa.String(length=32), server_default='pipeline', nullable=False))
    # `stages` and `consistency_loop` are not restored: no revision of this chain ever created them.
