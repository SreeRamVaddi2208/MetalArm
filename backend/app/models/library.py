"""The Library: ready-made workouts and programs for each training path, and
the user's place in a program they follow.

The catalog (LibraryWorkout, LibraryProgram and their rows) is shipped content,
imported from app/data/library_catalog.json by scripts/import_library.py and
checked by app/core/catalog_validator.py. Nothing here belongs to a user;
starting a workout copies it into a routine of the user's own (see
routes/workouts.py), exactly as the old ready-made workouts did. Following a
program is a ProgramEnrollment: which program, and where in it.

Named library_* rather than programs: `programs` is the user's own programs
(app/models/program.py), which a curated program is copied into on save.
"""

import datetime as dt
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import Timestamps, UUIDPrimaryKey

CATEGORY_CHECK = "category IN ('powerlifter', 'bodybuilder', 'athlete')"
DIFFICULTY_CHECK = "difficulty IN ('beginner', 'intermediate', 'advanced')"


class LibraryWorkout(UUIDPrimaryKey, Timestamps, Base):
    """One session: an ordered list of exercises with targets, never weights."""

    __tablename__ = "library_workouts"

    # Doubles as routines.preset_slug for the user's copy, hence 60.
    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(12), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # Derived from the exercises at import: what a gym needs to run it.
    equipment: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, server_default="{}"
    )
    focus_tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, server_default="{}"
    )
    # False for a workout that only exists as a day of a program.
    is_standalone: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # 'curated' or 'preset': the content the old /programs/curated and
    # /workouts/presets endpoints serve. Never shown in the Library.
    legacy_source: Mapped[str | None] = mapped_column(String(10), nullable=True)

    exercises: Mapped[list["LibraryWorkoutExercise"]] = relationship(
        back_populates="workout", cascade="all, delete-orphan",
        order_by="LibraryWorkoutExercise.position",
    )

    __table_args__ = (
        CheckConstraint(CATEGORY_CHECK, name="ck_library_workouts_category"),
        CheckConstraint(DIFFICULTY_CHECK, name="ck_library_workouts_difficulty"),
        CheckConstraint("duration_minutes > 0", name="ck_library_workouts_duration"),
        CheckConstraint(
            "legacy_source IS NULL OR legacy_source IN ('curated', 'preset')",
            name="ck_library_workouts_legacy",
        ),
    )


class LibraryWorkoutExercise(UUIDPrimaryKey, Base):
    __tablename__ = "library_workout_exercises"

    workout_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("library_workouts.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("exercises.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    target_sets: Mapped[int] = mapped_column(Integer, nullable=False)
    rep_low: Mapped[int] = mapped_column(Integer, nullable=False)
    rep_high: Mapped[int] = mapped_column(Integer, nullable=False)
    rest_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # Slots sharing a number are done back to back; 0 is none.
    superset_group: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    workout: Mapped[LibraryWorkout] = relationship(back_populates="exercises")

    __table_args__ = (
        UniqueConstraint("workout_id", "position", name="uq_library_workout_exercises_position"),
        CheckConstraint("target_sets >= 1", name="ck_library_workout_exercises_sets"),
        CheckConstraint("rep_low >= 1 AND rep_low <= rep_high", name="ck_library_workout_exercises_reps"),
        CheckConstraint("rest_seconds >= 0", name="ck_library_workout_exercises_rest"),
    )


class LibraryProgram(UUIDPrimaryKey, Timestamps, Base):
    """A plan: workouts placed on a weekly schedule."""

    __tablename__ = "library_programs"

    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(12), nullable=False)
    weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    days_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    equipment: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, server_default="{}"
    )
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    legacy_source: Mapped[str | None] = mapped_column(String(10), nullable=True)

    days: Mapped[list["LibraryProgramDay"]] = relationship(
        back_populates="program", cascade="all, delete-orphan",
        order_by="[LibraryProgramDay.week_number, LibraryProgramDay.day_number]",
    )

    __table_args__ = (
        CheckConstraint(CATEGORY_CHECK, name="ck_library_programs_category"),
        CheckConstraint(DIFFICULTY_CHECK, name="ck_library_programs_difficulty"),
        CheckConstraint("weeks >= 1 AND weeks <= 52", name="ck_library_programs_weeks"),
        CheckConstraint("days_per_week >= 1 AND days_per_week <= 7", name="ck_library_programs_days"),
        CheckConstraint(
            "legacy_source IS NULL OR legacy_source = 'curated'", name="ck_library_programs_legacy"
        ),
    )


class LibraryProgramDay(UUIDPrimaryKey, Base):
    """One day of one week. A rest day has no workout."""

    __tablename__ = "library_program_days"

    program_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("library_programs.id", ondelete="CASCADE"), nullable=False
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    workout_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("library_workouts.id"), nullable=True, index=True
    )

    program: Mapped[LibraryProgram] = relationship(back_populates="days")

    __table_args__ = (
        UniqueConstraint("program_id", "week_number", "day_number", name="uq_library_program_days_slot"),
        CheckConstraint("week_number >= 1", name="ck_library_program_days_week"),
        CheckConstraint("day_number >= 1 AND day_number <= 7", name="ck_library_program_days_day"),
    )


class ProgramEnrollment(UUIDPrimaryKey, Base):
    """A user following a library program: where they are in it.

    Week and day numbers, not a LibraryProgramDay id, so re-importing the
    catalog (which replaces day rows) never strands an enrollment."""

    __tablename__ = "program_enrollments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("library_programs.id"), nullable=False, index=True
    )
    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    current_week: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    current_day: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="active")
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "program_id", name="uq_program_enrollments_once"),
        CheckConstraint(
            "status IN ('active', 'completed', 'paused')", name="ck_program_enrollments_status"
        ),
        CheckConstraint("current_week >= 1", name="ck_program_enrollments_week"),
        CheckConstraint("current_day >= 1 AND current_day <= 7", name="ck_program_enrollments_day"),
        # One program at a time: following another pauses this one.
        Index(
            "uq_program_enrollments_one_active", "user_id", unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )
