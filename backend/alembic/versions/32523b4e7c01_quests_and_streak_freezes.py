"""Generated quests, streak freezes, and exercise tags.

- `exercises.tags`: what kind of work an exercise is. Filled by
  scripts.import_exercises, which the deploy runs right after this migration,
  so there is no backfill here.
- `quest_templates`, `quest_assignments`, `quest_rerolls`: generated quests
  (app/core/quest_board.py). Templates are seeded by
  scripts.seed_quest_templates.
- `streak_freeze_events` and two `users` columns: streak freezes
  (app/core/streak_freezes.py).
- `ck_points_ledger_source` admits 'quest_completed' and 'quest_bonus'.
  Hand-written, as CHECK constraints are not diffed by autogenerate. Neither
  joins uq_points_ledger_once: a quest award can be reversed and paid again,
  like a set award, and is serialised by the level_progress lock instead.

Revision ID: 32523b4e7c01
Revises: c1a5f8d3b620
Create Date: 2026-10-05 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '32523b4e7c01'
down_revision: str | None = 'c1a5f8d3b620'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCES_BEFORE = (
    "'set_logged', 'session_completed', 'pr_achieved', 'streak_bonus', 'duel_won', 'reversal'"
)
SOURCES_AFTER = SOURCES_BEFORE.replace(
    "'reversal'", "'quest_completed', 'quest_bonus', 'reversal'"
)
TAGS = "'big3', 'compound_heavy', 'compound', 'compound_light', 'isolation', 'mobility', 'plyometric'"
OBJECTIVES = (
    "'complete_sessions', 'log_working_sets', 'total_volume', 'sets_in_rep_range',"
    " 'sets_with_exercise_tag', 'intensity_sets', 'hit_pr'"
)


def upgrade() -> None:
    op.add_column(
        'exercises',
        sa.Column(
            'tags', postgresql.ARRAY(sa.String(length=24)),
            server_default=sa.text("'{}'"), nullable=False,
        ),
    )
    op.create_check_constraint(
        'ck_exercises_tags', 'exercises', f"tags <@ ARRAY[{TAGS}]::varchar[]"
    )

    op.add_column('users', sa.Column('freeze_settled_through', sa.String(length=16), nullable=True))
    op.add_column('users', sa.Column('streak_seen_at', sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        'quest_templates',
        sa.Column('code', sa.String(length=60), nullable=False),
        sa.Column('title', sa.String(length=80), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('period', sa.String(length=8), nullable=False),
        sa.Column('objective_type', sa.String(length=32), nullable=False),
        sa.Column(
            'objective_params', postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"), nullable=False,
        ),
        sa.Column('target_value', sa.Integer(), nullable=False),
        sa.Column('reward_points', sa.Integer(), nullable=False),
        sa.Column(
            'eligible_categories', postgresql.ARRAY(sa.String(length=16)),
            server_default=sa.text("'{}'"), nullable=False,
        ),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('code'),
        sa.CheckConstraint("period IN ('daily', 'weekly')", name='ck_quest_templates_period'),
        sa.CheckConstraint(f"objective_type IN ({OBJECTIVES})", name='ck_quest_templates_objective'),
        sa.CheckConstraint('target_value >= 1', name='ck_quest_templates_target'),
        sa.CheckConstraint(
            'reward_points >= 1 AND reward_points <= 1000', name='ck_quest_templates_reward'
        ),
        sa.CheckConstraint(
            "eligible_categories <@ ARRAY['powerlifter', 'bodybuilder', 'athlete']::varchar[]",
            name='ck_quest_templates_categories',
        ),
    )

    op.create_table(
        'quest_assignments',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('template_code', sa.String(length=60), nullable=False),
        sa.Column('period', sa.String(length=8), nullable=False),
        sa.Column('period_key', sa.String(length=16), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('title', sa.String(length=80), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('objective_type', sa.String(length=32), nullable=False),
        sa.Column(
            'objective_params', postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"), nullable=False,
        ),
        sa.Column('target_value', sa.Integer(), nullable=False),
        sa.Column('reward_points', sa.Integer(), nullable=False),
        sa.Column('progress_value', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=16), server_default='active', nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_code'], ['quest_templates.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("period IN ('daily', 'weekly')", name='ck_quest_assignments_period'),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'rerolled')", name='ck_quest_assignments_status'
        ),
        sa.CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)",
            name='ck_quest_assignments_completed',
        ),
        sa.CheckConstraint('period_end > period_start', name='ck_quest_assignments_window'),
    )
    op.create_index(
        'ix_quest_assignments_template_code', 'quest_assignments', ['template_code']
    )
    op.create_index(
        'ix_quest_assignments_user_period', 'quest_assignments', ['user_id', 'period_key']
    )
    op.create_index(
        'uq_quest_assignments_once', 'quest_assignments',
        ['user_id', 'period_key', 'template_code'],
        unique=True, postgresql_where=sa.text("status <> 'rerolled'"),
    )

    op.create_table(
        'quest_rerolls',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('day_key', sa.String(length=16), nullable=False),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assignment_id'], ['quest_assignments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'day_key', 'ordinal', name='uq_quest_rerolls_slot'),
        sa.CheckConstraint('ordinal >= 1', name='ck_quest_rerolls_ordinal'),
    )
    op.create_index('ix_quest_rerolls_assignment_id', 'quest_rerolls', ['assignment_id'])

    op.create_table(
        'streak_freeze_events',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('delta', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=32), nullable=False),
        sa.Column('week_key', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'week_key', 'reason', name='uq_streak_freeze_once'),
        sa.CheckConstraint('delta IN (-1, 1)', name='ck_streak_freeze_delta'),
        sa.CheckConstraint(
            "reason IN ('streak_milestone', 'weekly_quests_complete', 'missed_week_covered')",
            name='ck_streak_freeze_reason',
        ),
        sa.CheckConstraint(
            "(reason = 'missed_week_covered') = (delta = -1)",
            name='ck_streak_freeze_reason_sign',
        ),
    )

    op.drop_constraint('ck_points_ledger_source', 'points_ledger', type_='check')
    op.create_check_constraint(
        'ck_points_ledger_source', 'points_ledger', f"source_type IN ({SOURCES_AFTER})"
    )


def downgrade() -> None:
    op.drop_constraint('ck_points_ledger_source', 'points_ledger', type_='check')
    # Quest rows, and the reversals of them, would violate the narrower CHECK.
    op.execute(
        "DELETE FROM points_ledger WHERE source_type = 'reversal' AND source_id IN ("
        "SELECT id FROM points_ledger WHERE source_type IN ('quest_completed', 'quest_bonus'))"
    )
    op.execute("DELETE FROM points_ledger WHERE source_type IN ('quest_completed', 'quest_bonus')")
    op.create_check_constraint(
        'ck_points_ledger_source', 'points_ledger', f"source_type IN ({SOURCES_BEFORE})"
    )
    op.drop_table('streak_freeze_events')
    op.drop_index('ix_quest_rerolls_assignment_id', table_name='quest_rerolls')
    op.drop_table('quest_rerolls')
    op.drop_index('uq_quest_assignments_once', table_name='quest_assignments')
    op.drop_index('ix_quest_assignments_user_period', table_name='quest_assignments')
    op.drop_index('ix_quest_assignments_template_code', table_name='quest_assignments')
    op.drop_table('quest_assignments')
    op.drop_table('quest_templates')
    op.drop_column('users', 'streak_seen_at')
    op.drop_column('users', 'freeze_settled_through')
    op.drop_constraint('ck_exercises_tags', 'exercises', type_='check')
    op.drop_column('exercises', 'tags')
