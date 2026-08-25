"""rename canvas_data to canvas

Revision ID: a1b2c3d4e5f6
Revises: e82520318cd1
Create Date: 2026-08-25 00:00:00.000000

Renames the `canvas_data` column to `canvas`, matching the wire-level
rename (queue message block id, hook payload key, ProjectState field,
frontend types) done across the other three repos in the same task — see
bizstruct-domain's `Canvas`/`CanvasGenerated` and bizstruct_domain.chain's
`canvas` stage id, which this column name previously required an explicit
`_STAGE_ID_OVERRIDES` bridge to match.

No data migration needed beyond the rename itself — there's no production
data, and a plain column rename preserves whatever's already in any dev
database (ALTER TABLE ... RENAME COLUMN keeps existing values as-is).
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e82520318cd1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('projects', 'canvas_data', new_column_name='canvas')


def downgrade() -> None:
    op.alter_column('projects', 'canvas', new_column_name='canvas_data')
