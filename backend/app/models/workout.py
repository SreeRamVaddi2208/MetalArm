"""Gym workout tracking: the exercise library, routines, sessions, sets,
personal records, the points ledger, and body measurements.

Foreign keys onto `exercises` use the default NO ACTION rather than RESTRICT,
on purpose. Deleting a user cascades to their custom exercises AND to the sets
and routine rows that reference them, in one statement. RESTRICT is checked
immediately, row by row, so it can fire before the referencing row's own
cascade has run; NO ACTION is checked at the end of the statement, after every
cascade. Deleting a referenced custom exercise on its own is still refused -
the API archives it instead.
"""

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import workout_rules as rules
from app.db.session import Base
from app.models.mixins import Timestamps, UUIDPrimaryKey
from app.models.workout_enums import (
    Equipment,
    ExerciseCategory,
    LedgerSource,
    MeasurementMetric,
    MeasurementUnit,
    MuscleGroup,
    RecordType,
    SessionStatus,
    check_in,
    values,
)

_MUSCLES_ARRAY = ", ".join(f"'{v}'" for v in values(MuscleGroup))


class Exercise(UUIDPrimaryKey, Timestamps, Base):
    """A library exercise (shared, created_by_user_id NULL) or a user's own.

    Library rows are loaded by scripts/import_exercises.py and keyed by `slug`,
    so re-running an import updates them in place rather than duplicating.
    """

    __tablename__ = "exercises"

    # Library only: the stable import key. Custom exercises have none.
    slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Lowercased, whitespace-collapsed name carrying the uniqueness rules - the
    # same approach as users.email_normalized, and for the same reason: no
    # expression index, which `alembic check` cannot compare.
    name_key: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    primary_muscle_groups: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, server_default=text("'{}'")
    )
    equipment: Mapped[str] = mapped_column(String(32), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_custom: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Hidden from the picker but kept, because history still points at it.
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    __table_args__ = (
        CheckConstraint(check_in("category", ExerciseCategory), name="ck_exercises_category"),
        CheckConstraint(check_in("equipment", Equipment), name="ck_exercises_equipment"),
        CheckConstraint(
            f"primary_muscle_groups <@ ARRAY[{_MUSCLES_ARRAY}]::varchar[] "
            "AND cardinality(primary_muscle_groups) >= 1",
            name="ck_exercises_muscle_groups",
        ),
        # Exactly one owner model: library rows belong to nobody, custom rows
        # to exactly one user.
        CheckConstraint(
            "(is_custom AND created_by_user_id IS NOT NULL AND slug IS NULL) OR "
            "(NOT is_custom AND created_by_user_id IS NULL AND slug IS NOT NULL)",
            name="ck_exercises_owner",
        ),
        Index(
            "uq_exercises_library_slug",
            "slug",
            unique=True,
            postgresql_where=text("NOT is_custom"),
        ),
        Index(
            "uq_exercises_library_name",
            "name_key",
            unique=True,
            postgresql_where=text("NOT is_custom"),
        ),
        Index(
            "uq_exercises_custom_name",
            "created_by_user_id",
            "name_key",
            unique=True,
            postgresql_where=text("is_custom"),
        ),
        # Muscle-group filter: `primary_muscle_groups @> ARRAY['chest']`.
        Index(
            "ix_exercises_muscle_groups",
            "primary_muscle_groups",
            postgresql_using="gin",
        ),
    )


class Routine(UUIDPrimaryKey, Timestamps, Base):
    """A reusable workout template a session can be started from."""

    __tablename__ = "routines"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    exercises: Mapped[list["RoutineExercise"]] = relationship(
        back_populates="routine",
        cascade="all, delete-orphan",
        order_by="RoutineExercise.position",
    )

    __table_args__ = (
        CheckConstraint("length(name) >= 1", name="ck_routines_name"),
    )


class RoutineExercise(UUIDPrimaryKey, Base):
    """One ordered slot in a routine, with optional targets."""

    __tablename__ = "routine_exercises"

    routine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("routines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # NO ACTION - see the module docstring.
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("exercises.id"), nullable=False, index=True
    )
    target_sets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_weight_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 2), nullable=True
    )
    rest_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    routine: Mapped["Routine"] = relationship(back_populates="exercises")
    exercise: Mapped["Exercise"] = relationship()

    __table_args__ = (
        UniqueConstraint("routine_id", "position", name="uq_routine_exercise_position"),
        CheckConstraint("position >= 0", name="ck_routine_exercises_position"),
        CheckConstraint(
            "target_sets IS NULL OR (target_sets >= 1 AND target_sets <= 50)",
            name="ck_routine_exercises_target_sets",
        ),
        CheckConstraint(
            f"target_reps IS NULL OR (target_reps >= 1 AND target_reps <= {rules.MAX_REPS})",
            name="ck_routine_exercises_target_reps",
        ),
        CheckConstraint(
            "target_weight_kg IS NULL OR "
            f"(target_weight_kg >= 0 AND target_weight_kg <= {rules.MAX_WEIGHT_KG})",
            name="ck_routine_exercises_target_weight",
        ),
        CheckConstraint(
            "rest_seconds IS NULL OR (rest_seconds >= 0 AND rest_seconds <= 3600)",
            name="ck_routine_exercises_rest",
        ),
    )


class WorkoutSession(UUIDPrimaryKey, Timestamps, Base):
    """One workout, from start to finish (or abandonment)."""

    __tablename__ = "workout_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # SET NULL: deleting a routine must not erase the workouts done from it.
    routine_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("routines.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=SessionStatus.IN_PROGRESS.value
    )
    # Set at finish. Whether the session was a real workout (points_engine.
    # session_qualifies) - only qualifying sessions count toward the streak.
    qualified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # ISO week (user's timezone) the session finished in. Stored so the weekly
    # streak is a GROUP BY, not a timezone conversion per row.
    week_key: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Shop points credited at finish, snapshotted: equal to the session's net
    # ledger total at that moment. See routes/workouts.py.
    points_credited: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    sets: Mapped[list["SetEntry"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SetEntry.completed_at",
    )

    __table_args__ = (
        CheckConstraint(check_in("status", SessionStatus), name="ck_workout_sessions_status"),
        # A live session has no end; a finished or abandoned one must.
        CheckConstraint(
            "(status = 'in_progress') = (ended_at IS NULL)",
            name="ck_workout_sessions_ended",
        ),
        CheckConstraint(
            "points_credited >= 0", name="ck_workout_sessions_points_non_negative"
        ),
        # ONE live session per user, enforced by the database. Two concurrent
        # "start workout" taps cannot both succeed, and parallel sessions cannot
        # be used to multiply the per-session caps.
        Index(
            "uq_workout_sessions_one_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
        ),
        Index("ix_workout_sessions_user_started", "user_id", "started_at"),
        Index("ix_workout_sessions_user_week", "user_id", "week_key"),
    )


class SetEntry(UUIDPrimaryKey, Base):
    """One logged set."""

    __tablename__ = "set_entries"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workout_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalised from the session so an exercise's full history for a user -
    # the PR replay and the progress chart - is one indexed range scan.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # NO ACTION - see the module docstring.
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("exercises.id"), nullable=False, index=True
    )
    # 1-based within (session, exercise). Renumbered on delete, so no UNIQUE:
    # a renumbering UPDATE would trip it mid-statement.
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Always kilograms; a request may submit pounds and is converted.
    weight_kg: Mapped[Decimal] = mapped_column(
        Numeric(7, 2), nullable=False, server_default="0"
    )
    reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rpe: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_warmup: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # Computed server-side: whether this set beat an existing record. A
    # first-ever baseline holds personal_records rows but is NOT a PR.
    is_pr: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    completed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Client-generated id for a submit. A retried or double-tapped submit
    # carries the same id and resolves to the original set, not a second one.
    # NULLs are distinct in a UNIQUE constraint, so it stays optional.
    client_set_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )

    session: Mapped["WorkoutSession"] = relationship(back_populates="sets")
    exercise: Mapped["Exercise"] = relationship()

    __table_args__ = (
        UniqueConstraint("session_id", "client_set_id", name="uq_set_entries_client_id"),
        CheckConstraint("set_number >= 1", name="ck_set_entries_set_number"),
        CheckConstraint(
            f"weight_kg >= 0 AND weight_kg <= {rules.MAX_WEIGHT_KG}",
            name="ck_set_entries_weight",
        ),
        CheckConstraint(
            f"reps IS NULL OR (reps >= 1 AND reps <= {rules.MAX_REPS})",
            name="ck_set_entries_reps",
        ),
        CheckConstraint("rpe IS NULL OR (rpe >= 1 AND rpe <= 10)", name="ck_set_entries_rpe"),
        CheckConstraint(
            "duration_seconds IS NULL OR "
            f"(duration_seconds >= 1 AND duration_seconds <= {rules.MAX_DURATION_SECONDS})",
            name="ck_set_entries_duration",
        ),
        CheckConstraint(
            f"distance_m IS NULL OR (distance_m > 0 AND distance_m <= {rules.MAX_DISTANCE_M})",
            name="ck_set_entries_distance",
        ),
        # A set must record SOMETHING.
        CheckConstraint(
            "reps IS NOT NULL OR duration_seconds IS NOT NULL OR distance_m IS NOT NULL",
            name="ck_set_entries_has_measure",
        ),
        Index("ix_set_entries_user_exercise_time", "user_id", "exercise_id", "completed_at"),
    )


class PersonalRecord(UUIDPrimaryKey, Base):
    """A record-setting EVENT: the moment a set (or session) beat a record.

    The current record for a type is the best row. Keeping every event rather
    than one mutable row per type gives the PR timeline for free, and lets the
    rows be rebuilt from the sets after a delete (personal_records.replay).
    """

    __tablename__ = "personal_records"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("exercises.id", ondelete="CASCADE"),
        nullable=False,
    )
    record_type: Mapped[str] = mapped_column(String(24), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # The weight it was set at: the qualifier for a rep PR ("12 @ 60 kg").
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    # The record this beat, NULL for a baseline, so the UI can say "by 5 kg".
    previous_value: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    is_baseline: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    achieved_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workout_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # NULL only for max_volume, which belongs to a session rather than a set.
    set_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("set_entries.id", ondelete="CASCADE"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(check_in("record_type", RecordType), name="ck_personal_records_type"),
        CheckConstraint("value > 0", name="ck_personal_records_value_positive"),
        CheckConstraint(
            "(record_type = 'max_volume') = (set_id IS NULL)",
            name="ck_personal_records_set_scope",
        ),
        # A set sets each record type at most once...
        UniqueConstraint("set_id", "record_type", name="uq_personal_records_set_type"),
        # ...and a session at most one volume record per exercise.
        Index(
            "uq_personal_records_session_volume",
            "session_id",
            "exercise_id",
            unique=True,
            postgresql_where=text("record_type = 'max_volume'"),
        ),
        Index(
            "ix_personal_records_user_exercise_type",
            "user_id",
            "exercise_id",
            "record_type",
        ),
    )


class PointsLedgerEntry(UUIDPrimaryKey, Base):
    """Append-only record of every workout point awarded or reversed.

    Never UPDATEd or DELETEd by the application: undoing an award appends a
    `reversal` row carrying the negated amount and the original row's id as its
    source_id. A user's workout points are SUM(points); XP and shop points were
    applied from these rows as they were written.

    Friend leaderboards read this table directly (brief, Section 7), which is
    why every row carries user_id and created_at with an index on both.
    """

    __tablename__ = "points_ledger"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    # set_logged / pr_achieved -> set id; session_completed / streak_bonus ->
    # session id; reversal -> the ledger row being reversed.
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workout_sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # streak_bonus only: the ISO week it was paid for.
    period_key: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(check_in("source_type", LedgerSource), name="ck_points_ledger_source"),
        # Only a reversal may subtract, and a reversal may only subtract.
        CheckConstraint(
            "(source_type = 'reversal' AND points < 0) OR "
            "(source_type <> 'reversal' AND points > 0)",
            name="ck_points_ledger_sign",
        ),
        # The database-level guard against double awards, for the awards that
        # happen exactly once: a session cannot be completed or streak-paid
        # twice, and an entry cannot be reversed twice. Set-level awards are not
        # covered, because editing a set legitimately reverses and then
        # re-awards the same set; those are serialised by the level_progress
        # row lock instead.
        Index(
            "uq_points_ledger_once",
            "source_type",
            "source_id",
            unique=True,
            postgresql_where=text(
                "source_type IN ('session_completed', 'streak_bonus', 'reversal')"
            ),
        ),
        # One streak bonus per ISO week.
        Index(
            "uq_points_ledger_streak_week",
            "user_id",
            "period_key",
            unique=True,
            postgresql_where=text("source_type = 'streak_bonus'"),
        ),
        CheckConstraint(
            "(source_type = 'streak_bonus') = (period_key IS NOT NULL)",
            name="ck_points_ledger_period_key",
        ),
        Index("ix_points_ledger_user_time", "user_id", "created_at"),
    )


class BodyMeasurement(UUIDPrimaryKey, Base):
    """A body-weight / body-fat / custom measurement. Never earns points: a
    measurement is trivial to log repeatedly and says nothing about effort."""

    __tablename__ = "body_measurements"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric: Mapped[str] = mapped_column(String(16), nullable=False)
    # Required for custom metrics ("waist", "bicep"), otherwise NULL.
    label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    value: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    recorded_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(check_in("metric", MeasurementMetric), name="ck_body_measurements_metric"),
        CheckConstraint(check_in("unit", MeasurementUnit), name="ck_body_measurements_unit"),
        CheckConstraint(
            "value > 0 AND value < 100000", name="ck_body_measurements_value"
        ),
        CheckConstraint(
            "(metric = 'custom') = (label IS NOT NULL)",
            name="ck_body_measurements_label",
        ),
        # The unit must make sense for the metric; custom metrics are free-form.
        CheckConstraint(
            "(metric = 'weight' AND unit IN ('kg', 'lb')) OR "
            "(metric = 'body_fat' AND unit = 'percent') OR "
            "metric = 'custom'",
            name="ck_body_measurements_unit_for_metric",
        ),
        Index(
            "ix_body_measurements_user_metric_time", "user_id", "metric", "recorded_at"
        ),
    )
