"""routines remember their preset

Adds routines.preset_slug: set when a routine was materialised from a
ready-made workout (app/core/presets.py). A session takes its targets, planned
order and ghost values from a routine, so a preset has to become one - and the
UNIQUE(user_id, preset_slug) is what makes starting the same preset twice reuse
that routine instead of stacking up copies. NULL for every hand-made routine,
and Postgres treats NULLs as distinct, so the constraint does not restrict them.

Revision ID: 4b81c0d5e7a2
Revises: 9f2c1b7ad403
Create Date: 2026-09-20 17:20:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '4b81c0d5e7a2'
down_revision: str | None = '9f2c1b7ad403'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('routines', sa.Column('preset_slug', sa.String(length=60), nullable=True))
    op.create_unique_constraint('uq_routines_user_preset', 'routines', ['user_id', 'preset_slug'])


def downgrade() -> None:
    op.drop_constraint('uq_routines_user_preset', 'routines', type_='unique')
    op.drop_column('routines', 'preset_slug')
