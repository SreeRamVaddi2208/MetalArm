"""Fair duels: relative modes, baselines, set flags, draw and participation.

- `duels.metric` admits consistency / progress / relative_volume, and
  `duels.status` expired / cancelled. Hand-written CHECK swaps.
- `duel_baselines`: each side's starting point, snapshotted as a fair duel's
  window opens (app/core/duels.py).
- `set_entries.is_flagged` / `flag_reason`: plausibility (app/core/
  plausibility.py). Flagged sets stay out of duels and leaderboards; a partial
  index keeps the boards' exclusion lookup to the few that are flagged.
- The ledger admits 'duel_draw' and 'duel_participation', and both join
  uq_points_ledger_once: each is keyed per (duel, person), so the index still
  pays each side once.

Revision ID: 7a3e9f0b5c42
Revises: 4e8b1c2d9a17
Create Date: 2026-10-05 18:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '7a3e9f0b5c42'
down_revision: str | None = '4e8b1c2d9a17'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

METRICS_BEFORE = "'volume', 'sets', 'sessions'"
METRICS_AFTER = METRICS_BEFORE + ", 'consistency', 'progress', 'relative_volume'"
STATUS_BEFORE = "'pending', 'active', 'completed', 'declined'"
STATUS_AFTER = STATUS_BEFORE + ", 'expired', 'cancelled'"
SOURCES_BEFORE = (
    "'set_logged', 'session_completed', 'pr_achieved', 'streak_bonus', 'duel_won',"
    " 'quest_completed', 'quest_bonus', 'reversal'"
)
SOURCES_AFTER = SOURCES_BEFORE.replace(
    "'reversal'", "'duel_draw', 'duel_participation', 'reversal'"
)
ONCE_BEFORE = "source_type IN ('session_completed', 'streak_bonus', 'duel_won', 'reversal')"
ONCE_AFTER = (
    "source_type IN ('session_completed', 'streak_bonus', 'duel_won', "
    "'duel_draw', 'duel_participation', 'reversal')"
)


def _swap_check(name: str, table: str, condition: str) -> None:
    op.drop_constraint(name, table, type_='check')
    op.create_check_constraint(name, table, condition)


def upgrade() -> None:
    _swap_check('ck_duels_metric', 'duels', f"metric IN ({METRICS_AFTER})")
    _swap_check('ck_duels_status', 'duels', f"status IN ({STATUS_AFTER})")

    op.create_table(
        'duel_baselines',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('duel_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('exercise_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('baseline_type', sa.String(length=24), nullable=False),
        sa.Column('baseline_value', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(['duel_id'], ['duels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "baseline_type IN ('e1rm', 'avg_weekly_volume')", name='ck_duel_baselines_type'
        ),
        sa.CheckConstraint('baseline_value > 0', name='ck_duel_baselines_value'),
        sa.CheckConstraint(
            "(baseline_type = 'e1rm') = (exercise_id IS NOT NULL)", name='ck_duel_baselines_scope'
        ),
        sa.UniqueConstraint(
            'duel_id', 'user_id', 'exercise_id',
            name='uq_duel_baselines_once', postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index('ix_duel_baselines_user_id', 'duel_baselines', ['user_id'])
    op.create_index('ix_duel_baselines_exercise_id', 'duel_baselines', ['exercise_id'])

    op.add_column(
        'set_entries',
        sa.Column('is_flagged', sa.Boolean(), server_default='false', nullable=False),
    )
    op.add_column('set_entries', sa.Column('flag_reason', sa.String(length=32), nullable=True))
    op.create_check_constraint(
        'ck_set_entries_flag_reason', 'set_entries', 'is_flagged = (flag_reason IS NOT NULL)'
    )
    op.create_index(
        'ix_set_entries_flagged', 'set_entries', ['id'], postgresql_where=sa.text('is_flagged')
    )

    _swap_check('ck_points_ledger_source', 'points_ledger', f"source_type IN ({SOURCES_AFTER})")
    op.drop_index('uq_points_ledger_once', table_name='points_ledger')
    op.create_index(
        'uq_points_ledger_once', 'points_ledger', ['source_type', 'source_id'],
        unique=True, postgresql_where=sa.text(ONCE_AFTER),
    )


def downgrade() -> None:
    op.drop_index('uq_points_ledger_once', table_name='points_ledger')
    op.create_index(
        'uq_points_ledger_once', 'points_ledger', ['source_type', 'source_id'],
        unique=True, postgresql_where=sa.text(ONCE_BEFORE),
    )
    op.drop_constraint('ck_points_ledger_source', 'points_ledger', type_='check')
    op.execute(
        "DELETE FROM points_ledger WHERE source_type IN ('duel_draw', 'duel_participation')"
    )
    op.create_check_constraint(
        'ck_points_ledger_source', 'points_ledger', f"source_type IN ({SOURCES_BEFORE})"
    )
    op.drop_index('ix_set_entries_flagged', table_name='set_entries')
    op.drop_constraint('ck_set_entries_flag_reason', 'set_entries', type_='check')
    op.drop_column('set_entries', 'flag_reason')
    op.drop_column('set_entries', 'is_flagged')
    op.drop_index('ix_duel_baselines_exercise_id', table_name='duel_baselines')
    op.drop_index('ix_duel_baselines_user_id', table_name='duel_baselines')
    op.drop_table('duel_baselines')
    op.execute("DELETE FROM duels WHERE metric IN ('consistency', 'progress', 'relative_volume')")
    op.execute("UPDATE duels SET status = 'declined' WHERE status IN ('expired', 'cancelled')")
    _swap_check('ck_duels_status', 'duels', f"status IN ({STATUS_BEFORE})")
    _swap_check('ck_duels_metric', 'duels', f"metric IN ({METRICS_BEFORE})")
