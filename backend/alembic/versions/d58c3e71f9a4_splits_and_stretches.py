"""Splits, stretches, and the Recommended panel.

Stretches are EXERCISES - the table already had name, muscle groups,
instructions, media and custom ownership, so this adds the only two columns a
stretch needs that a lift does not, and both are NULL on every lift.

Sits on 8d1f4c60ba57, main's head. Two other branches revise the same parent
(a3f61d92c485 waitlist, c47e9a1b52f0 web push); whichever merges last needs its
down_revision repointed, or alembic sees several heads.

Revision ID: d58c3e71f9a4
Revises: 8d1f4c60ba57
Create Date: 2026-09-30 09:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'd58c3e71f9a4'
down_revision: str | None = '8d1f4c60ba57'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SPLITS = "'push', 'pull', 'legs', 'custom'"


def upgrade() -> None:
    op.create_table(
        'split_profiles',
        sa.Column('split_type', sa.String(length=16), nullable=False),
        sa.Column('display_name', sa.String(length=40), nullable=False),
        sa.Column('tagline', sa.String(length=120), nullable=False),
        sa.Column('target_muscle_groups', sa.ARRAY(sa.String(length=32)), nullable=False),
        sa.Column('position', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('split_type'),
        sa.CheckConstraint(f"split_type IN ({SPLITS})", name='ck_split_profiles_type'),
    )

    op.add_column('exercises', sa.Column('stretch_phase', sa.String(length=8), nullable=True))
    op.add_column('exercises', sa.Column('hold_seconds', sa.Integer(), nullable=True))
    # A phase is only ever 'pre' or 'post', and NULL means "not a stretch".
    op.create_check_constraint(
        'ck_exercises_stretch_phase', 'exercises',
        "stretch_phase IS NULL OR stretch_phase IN ('pre', 'post')",
    )

    for table in ('workout_sessions', 'routines'):
        op.add_column(table, sa.Column('split_type', sa.String(length=16), nullable=True))
        op.create_check_constraint(
            f'ck_{table}_split_type', table,
            f"split_type IS NULL OR split_type IN ({SPLITS})",
        )

    op.create_table(
        'recommended_stretches',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('session_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('exercise_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('phase', sa.String(length=8), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['workout_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("source IN ('auto_matched', 'user_added')", name='ck_recommended_source'),
        sa.CheckConstraint("phase IN ('pre', 'post')", name='ck_recommended_phase'),
        # The panel is a set: adding the same stretch twice is a no-op.
        sa.UniqueConstraint('session_id', 'exercise_id', 'phase', name='uq_recommended_once'),
    )
    op.create_index('ix_recommended_session', 'recommended_stretches', ['session_id', 'phase'])

    # Which routines someone reaches for. Only the pin is stored: how often and
    # how recently a routine was used is counted from the sessions that name
    # it, so it cannot drift from them.
    op.add_column('routines', sa.Column('pinned_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('routines', 'pinned_at')
    op.drop_index('ix_recommended_session', table_name='recommended_stretches')
    op.drop_table('recommended_stretches')
    for table in ('workout_sessions', 'routines'):
        op.drop_constraint(f'ck_{table}_split_type', table, type_='check')
        op.drop_column(table, 'split_type')
    op.drop_constraint('ck_exercises_stretch_phase', 'exercises', type_='check')
    op.drop_column('exercises', 'hold_seconds')
    op.drop_column('exercises', 'stretch_phase')
    op.drop_table('split_profiles')
