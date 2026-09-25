"""Duels and the activity feed.

Two new tables, and two edits to the points ledger's guards:

- `ck_points_ledger_source` has to admit 'duel_won'. CHECK constraints are not
  diffed by autogenerate, so this is hand-written - the same reason
  9f2c1b7ad403 was.
- `uq_points_ledger_once`, the partial UNIQUE that makes an award idempotent,
  has to cover 'duel_won' too. A duel is judged by whoever reads it first, and
  two simultaneous readers must not both pay the winner; the transaction takes
  the level_progress lock, and this index is the guarantee underneath it.

Revision ID: 8d1f4c60ba57
Revises: 7c93ad2f1b64
Create Date: 2026-09-26 09:40:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '8d1f4c60ba57'
down_revision: str | None = '7c93ad2f1b64'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCES_BEFORE = "'set_logged', 'session_completed', 'pr_achieved', 'streak_bonus', 'reversal'"
SOURCES_AFTER = SOURCES_BEFORE.replace("'reversal'", "'duel_won', 'reversal'")
ONCE_BEFORE = "source_type IN ('session_completed', 'streak_bonus', 'reversal')"
ONCE_AFTER = "source_type IN ('session_completed', 'streak_bonus', 'duel_won', 'reversal')"


def upgrade() -> None:
    op.create_table(
        'duels',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('challenger_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('opponent_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('is_ai_opponent', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('metric', sa.String(length=16), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=16), server_default='pending', nullable=False),
        sa.Column('winner_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rival_target', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['challenger_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['opponent_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['winner_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("metric IN ('volume', 'sets', 'sessions')", name='ck_duels_metric'),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'completed', 'declined')", name='ck_duels_status'
        ),
        sa.CheckConstraint('window_end > window_start', name='ck_duels_window'),
        sa.CheckConstraint(
            "(is_ai_opponent AND opponent_id IS NULL AND rival_target IS NOT NULL)"
            " OR (NOT is_ai_opponent AND opponent_id IS NOT NULL AND rival_target IS NULL)",
            name='ck_duels_opponent',
        ),
        sa.CheckConstraint(
            'challenger_id <> opponent_id OR opponent_id IS NULL', name='ck_duels_not_self'
        ),
        sa.CheckConstraint(
            "(status = 'completed') = (resolved_at IS NOT NULL)", name='ck_duels_resolved'
        ),
    )
    op.create_index('ix_duels_challenger', 'duels', ['challenger_id', 'status'])
    op.create_index('ix_duels_opponent', 'duels', ['opponent_id', 'status'])

    op.create_table(
        'activity_events',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('party_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('event_type', sa.String(length=24), nullable=False),
        sa.Column('source_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('headline', sa.String(length=140), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['party_id'], ['parties.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "event_type IN ('pr_achieved', 'rank_up', 'session_completed', 'duel_won',"
            " 'quest_completed')",
            name='ck_activity_type',
        ),
        # One event becomes several rows - a personal copy plus one per party -
        # so party_id belongs in the key. NULLS NOT DISTINCT (Postgres 15+; we
        # run 17) is what makes the personal copy, whose party_id is NULL,
        # dedupe at all.
        sa.UniqueConstraint(
            'user_id', 'event_type', 'source_id', 'party_id',
            name='uq_activity_once', postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index('ix_activity_party_time', 'activity_events', ['party_id', 'created_at'])
    op.create_index('ix_activity_user_time', 'activity_events', ['user_id', 'created_at'])

    op.drop_constraint('ck_points_ledger_source', 'points_ledger', type_='check')
    op.create_check_constraint(
        'ck_points_ledger_source', 'points_ledger', f"source_type IN ({SOURCES_AFTER})"
    )
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
    # Any duel_won rows would violate the narrower CHECK, so they go first.
    op.execute("DELETE FROM points_ledger WHERE source_type = 'duel_won'")
    op.create_check_constraint(
        'ck_points_ledger_source', 'points_ledger', f"source_type IN ({SOURCES_BEFORE})"
    )
    op.drop_index('ix_activity_user_time', table_name='activity_events')
    op.drop_index('ix_activity_party_time', table_name='activity_events')
    op.drop_table('activity_events')
    op.drop_index('ix_duels_opponent', table_name='duels')
    op.drop_index('ix_duels_challenger', table_name='duels')
    op.drop_table('duels')
