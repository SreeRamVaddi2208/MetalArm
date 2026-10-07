"""The Library: catalog workouts and programs, program enrollments, and where a
session came from.

Revision ID: a7d3c1e5b902
Revises: 9c2d4e6f8a10
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a7d3c1e5b902"
down_revision = "9c2d4e6f8a10"
branch_labels = None
depends_on = None

CATEGORY = "category IN ('powerlifter', 'bodybuilder', 'athlete')"
DIFFICULTY = "difficulty IN ('beginner', 'intermediate', 'advanced')"


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "library_workouts",
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("difficulty", sa.String(length=12), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("equipment", postgresql.ARRAY(sa.String(length=32)), server_default="{}", nullable=False),
        sa.Column("focus_tags", postgresql.ARRAY(sa.String(length=32)), server_default="{}", nullable=False),
        sa.Column("is_standalone", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("legacy_source", sa.String(length=10), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(CATEGORY, name="ck_library_workouts_category"),
        sa.CheckConstraint(DIFFICULTY, name="ck_library_workouts_difficulty"),
        sa.CheckConstraint("duration_minutes > 0", name="ck_library_workouts_duration"),
        sa.CheckConstraint(
            "legacy_source IS NULL OR legacy_source IN ('curated', 'preset')", name="ck_library_workouts_legacy"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "library_workout_exercises",
        sa.Column("workout_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("target_sets", sa.Integer(), nullable=False),
        sa.Column("rep_low", sa.Integer(), nullable=False),
        sa.Column("rep_high", sa.Integer(), nullable=False),
        sa.Column("rest_seconds", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=160), nullable=True),
        sa.Column("superset_group", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("target_sets >= 1", name="ck_library_workout_exercises_sets"),
        sa.CheckConstraint("rep_low >= 1 AND rep_low <= rep_high", name="ck_library_workout_exercises_reps"),
        sa.CheckConstraint("rest_seconds >= 0", name="ck_library_workout_exercises_rest"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"]),
        sa.ForeignKeyConstraint(["workout_id"], ["library_workouts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workout_id", "position", name="uq_library_workout_exercises_position"),
    )
    op.create_index(
        op.f("ix_library_workout_exercises_exercise_id"), "library_workout_exercises", ["exercise_id"]
    )
    op.create_table(
        "library_programs",
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("difficulty", sa.String(length=12), nullable=False),
        sa.Column("weeks", sa.Integer(), nullable=False),
        sa.Column("days_per_week", sa.Integer(), nullable=False),
        sa.Column("equipment", postgresql.ARRAY(sa.String(length=32)), server_default="{}", nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("legacy_source", sa.String(length=10), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(CATEGORY, name="ck_library_programs_category"),
        sa.CheckConstraint(DIFFICULTY, name="ck_library_programs_difficulty"),
        sa.CheckConstraint("weeks >= 1 AND weeks <= 52", name="ck_library_programs_weeks"),
        sa.CheckConstraint("days_per_week >= 1 AND days_per_week <= 7", name="ck_library_programs_days"),
        sa.CheckConstraint("legacy_source IS NULL OR legacy_source = 'curated'", name="ck_library_programs_legacy"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "library_program_days",
        sa.Column("program_id", sa.Uuid(), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("workout_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("week_number >= 1", name="ck_library_program_days_week"),
        sa.CheckConstraint("day_number >= 1 AND day_number <= 7", name="ck_library_program_days_day"),
        sa.ForeignKeyConstraint(["program_id"], ["library_programs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workout_id"], ["library_workouts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("program_id", "week_number", "day_number", name="uq_library_program_days_slot"),
    )
    op.create_index(op.f("ix_library_program_days_workout_id"), "library_program_days", ["workout_id"])
    op.create_table(
        "program_enrollments",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("program_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("current_week", sa.Integer(), server_default="1", nullable=False),
        sa.Column("current_day", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=10), server_default="active", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("status IN ('active', 'completed', 'paused')", name="ck_program_enrollments_status"),
        sa.CheckConstraint("current_week >= 1", name="ck_program_enrollments_week"),
        sa.CheckConstraint("current_day >= 1 AND current_day <= 7", name="ck_program_enrollments_day"),
        sa.ForeignKeyConstraint(["program_id"], ["library_programs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "program_id", name="uq_program_enrollments_once"),
    )
    op.create_index(op.f("ix_program_enrollments_program_id"), "program_enrollments", ["program_id"])
    op.create_index(
        "uq_program_enrollments_one_active", "program_enrollments", ["user_id"], unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.add_column("workout_sessions", sa.Column("library_workout_id", sa.Uuid(), nullable=True))
    op.add_column("workout_sessions", sa.Column("program_enrollment_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "workout_sessions_library_workout_id_fkey", "workout_sessions", "library_workouts",
        ["library_workout_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "workout_sessions_program_enrollment_id_fkey", "workout_sessions", "program_enrollments",
        ["program_enrollment_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(op.f("ix_workout_sessions_library_workout_id"), "workout_sessions", ["library_workout_id"])
    op.create_index(
        op.f("ix_workout_sessions_program_enrollment_id"), "workout_sessions", ["program_enrollment_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_workout_sessions_program_enrollment_id"), table_name="workout_sessions")
    op.drop_index(op.f("ix_workout_sessions_library_workout_id"), table_name="workout_sessions")
    op.drop_constraint("workout_sessions_program_enrollment_id_fkey", "workout_sessions", type_="foreignkey")
    op.drop_constraint("workout_sessions_library_workout_id_fkey", "workout_sessions", type_="foreignkey")
    op.drop_column("workout_sessions", "program_enrollment_id")
    op.drop_column("workout_sessions", "library_workout_id")
    op.drop_index("uq_program_enrollments_one_active", table_name="program_enrollments")
    op.drop_index(op.f("ix_program_enrollments_program_id"), table_name="program_enrollments")
    op.drop_table("program_enrollments")
    op.drop_index(op.f("ix_library_program_days_workout_id"), table_name="library_program_days")
    op.drop_table("library_program_days")
    op.drop_table("library_programs")
    op.drop_index(op.f("ix_library_workout_exercises_exercise_id"), table_name="library_workout_exercises")
    op.drop_table("library_workout_exercises")
    op.drop_table("library_workouts")
