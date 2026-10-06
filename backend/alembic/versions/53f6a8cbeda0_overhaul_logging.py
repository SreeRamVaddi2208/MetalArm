"""Overhaul phase 1: exercise cards in a session, set types, session totals,
programs and favourites.

Backfills, so every existing workout keeps working:
- session_exercises: one card per exercise each session already has, in the
  order its first set was logged;
- set_entries.session_exercise_id: each set joined to its card, then NOT NULL;
- set_entries.set_type: 'warmup' where is_warmup, else 'normal' - and a CHECK
  keeps the two in step from now on;
- workout_sessions totals for every finished session (volume, working sets,
  records, duration), and visibility 'followers';
- routine_exercises rep ranges from the old single target.

Revision ID: 53f6a8cbeda0
Revises: 283a16dfbc66
Create Date: 2026-10-06 16:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '53f6a8cbeda0'
down_revision: str | None = '283a16dfbc66'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'programs',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('owner_user_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('training_category', sa.String(length=16), nullable=True),
        sa.Column('level', sa.String(length=12), nullable=True),
        sa.Column('weeks', sa.Integer(), nullable=True),
        sa.Column('sessions_per_week', sa.Integer(), nullable=True),
        sa.Column('is_public', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('cover_color', sa.String(length=9), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('length(name) >= 1', name='ck_programs_name'),
        sa.CheckConstraint(
            "training_category IS NULL OR training_category IN ('powerlifter', 'bodybuilder', 'athlete')",
            name='ck_programs_category'),
        sa.CheckConstraint(
            "level IS NULL OR level IN ('beginner', 'intermediate', 'advanced')", name='ck_programs_level'),
        sa.CheckConstraint('weeks IS NULL OR (weeks >= 1 AND weeks <= 52)', name='ck_programs_weeks'),
        sa.CheckConstraint(
            'sessions_per_week IS NULL OR (sessions_per_week >= 1 AND sessions_per_week <= 14)',
            name='ck_programs_sessions'),
    )
    op.create_index('ix_programs_owner_user_id', 'programs', ['owner_user_id'])

    op.create_table(
        'favorites',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('target_type', sa.String(length=10), nullable=False),
        sa.Column('target_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("target_type IN ('routine', 'exercise', 'program')", name='ck_favorites_type'),
        sa.UniqueConstraint('user_id', 'target_type', 'target_id', name='uq_favorites_once'),
    )
    op.create_index('ix_favorites_target', 'favorites', ['target_type', 'target_id'])

    op.add_column('routines', sa.Column('program_id', sa.Uuid(as_uuid=True), nullable=True))
    op.add_column('routines', sa.Column('order_in_program', sa.Integer(), nullable=True))
    op.add_column('routines', sa.Column('color', sa.String(length=9), nullable=True))
    op.create_foreign_key('routines_program_id_fkey', 'routines', 'programs', ['program_id'], ['id'],
                          ondelete='SET NULL')
    op.create_index('ix_routines_program_id', 'routines', ['program_id'])

    op.add_column('routine_exercises', sa.Column('target_reps_low', sa.Integer(), nullable=True))
    op.add_column('routine_exercises', sa.Column('target_reps_high', sa.Integer(), nullable=True))
    op.add_column('routine_exercises', sa.Column('superset_group', sa.Integer(), nullable=True))
    op.add_column('routine_exercises', sa.Column('notes', sa.Text(), nullable=True))
    op.execute("UPDATE routine_exercises SET target_reps_low = target_reps, target_reps_high = target_reps "
               "WHERE target_reps IS NOT NULL")
    op.create_check_constraint(
        'ck_routine_exercises_rep_range', 'routine_exercises',
        'target_reps_low IS NULL OR target_reps_high IS NULL OR target_reps_low <= target_reps_high')

    op.add_column('workout_sessions', sa.Column('visibility', sa.String(length=10),
                                                server_default='followers', nullable=False))
    op.add_column('workout_sessions', sa.Column('total_volume_kg', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('workout_sessions', sa.Column('total_working_sets', sa.Integer(), nullable=True))
    op.add_column('workout_sessions', sa.Column('total_prs', sa.Integer(), nullable=True))
    op.add_column('workout_sessions', sa.Column('duration_seconds', sa.Integer(), nullable=True))
    op.create_check_constraint('ck_workout_sessions_visibility', 'workout_sessions',
                               "visibility IN ('public', 'followers', 'private')")
    op.execute("""
        UPDATE workout_sessions s SET
          duration_seconds = GREATEST(0, EXTRACT(EPOCH FROM (s.ended_at - s.started_at)))::int,
          total_volume_kg = COALESCE((SELECT SUM(e.weight_kg * COALESCE(e.reps, 0)) FROM set_entries e
                                      WHERE e.session_id = s.id AND NOT e.is_warmup), 0),
          total_working_sets = (SELECT COUNT(*) FROM set_entries e
                                WHERE e.session_id = s.id AND NOT e.is_warmup),
          total_prs = (SELECT COUNT(*) FROM personal_records p
                       WHERE p.session_id = s.id AND NOT p.is_baseline)
        WHERE s.status = 'completed'
    """)

    op.create_table(
        'session_exercises',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('session_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('exercise_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('superset_group', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('rest_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['workout_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('position >= 0', name='ck_session_exercises_position'),
        sa.CheckConstraint('rest_seconds IS NULL OR (rest_seconds >= 0 AND rest_seconds <= 3600)',
                           name='ck_session_exercises_rest'),
    )
    op.create_index('ix_session_exercises_session_position', 'session_exercises', ['session_id', 'position'])
    op.create_index('ix_session_exercises_exercise_id', 'session_exercises', ['exercise_id'])
    # One card per exercise a session already has, in first-logged order.
    op.execute("""
        INSERT INTO session_exercises (session_id, exercise_id, position)
        SELECT session_id, exercise_id,
               (ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY MIN(completed_at), exercise_id) - 1)::int
        FROM set_entries
        GROUP BY session_id, exercise_id
    """)

    op.add_column('set_entries', sa.Column('set_type', sa.String(length=8), server_default='normal', nullable=False))
    op.execute("UPDATE set_entries SET set_type = 'warmup' WHERE is_warmup")
    op.create_check_constraint('ck_set_entries_set_type', 'set_entries',
                               "set_type IN ('normal', 'warmup', 'drop', 'failure')")
    op.create_check_constraint('ck_set_entries_warmup_type', 'set_entries', "is_warmup = (set_type = 'warmup')")
    op.add_column('set_entries', sa.Column('session_exercise_id', sa.Uuid(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE set_entries e SET session_exercise_id = c.id
        FROM session_exercises c
        WHERE c.session_id = e.session_id AND c.exercise_id = e.exercise_id
    """)
    op.alter_column('set_entries', 'session_exercise_id', nullable=False)
    op.create_foreign_key('set_entries_session_exercise_id_fkey', 'set_entries', 'session_exercises',
                          ['session_exercise_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_set_entries_session_exercise_id', 'set_entries', ['session_exercise_id'])


def downgrade() -> None:
    op.drop_index('ix_set_entries_session_exercise_id', table_name='set_entries')
    op.drop_constraint('set_entries_session_exercise_id_fkey', 'set_entries', type_='foreignkey')
    op.drop_column('set_entries', 'session_exercise_id')
    op.drop_constraint('ck_set_entries_warmup_type', 'set_entries', type_='check')
    op.drop_constraint('ck_set_entries_set_type', 'set_entries', type_='check')
    op.drop_column('set_entries', 'set_type')
    op.drop_index('ix_session_exercises_exercise_id', table_name='session_exercises')
    op.drop_index('ix_session_exercises_session_position', table_name='session_exercises')
    op.drop_table('session_exercises')
    op.drop_constraint('ck_workout_sessions_visibility', 'workout_sessions', type_='check')
    for column in ('duration_seconds', 'total_prs', 'total_working_sets', 'total_volume_kg', 'visibility'):
        op.drop_column('workout_sessions', column)
    op.drop_constraint('ck_routine_exercises_rep_range', 'routine_exercises', type_='check')
    for column in ('notes', 'superset_group', 'target_reps_high', 'target_reps_low'):
        op.drop_column('routine_exercises', column)
    op.drop_index('ix_routines_program_id', table_name='routines')
    op.drop_constraint('routines_program_id_fkey', 'routines', type_='foreignkey')
    for column in ('color', 'order_in_program', 'program_id'):
        op.drop_column('routines', column)
    op.drop_index('ix_favorites_target', table_name='favorites')
    op.drop_table('favorites')
    op.drop_index('ix_programs_owner_user_id', table_name='programs')
    op.drop_table('programs')
