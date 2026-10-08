"""Library: programs, favourites, the library listing, suggestions."""

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.workout import ExerciseOut

Category = Literal["powerlifter", "bodybuilder", "athlete"]
Level = Literal["beginner", "intermediate", "advanced"]


class ProgramIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    training_category: Category | None = None
    level: Level | None = None
    weeks: int | None = Field(default=None, ge=1, le=52)
    sessions_per_week: int | None = Field(default=None, ge=1, le=14)
    is_public: bool = False
    cover_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class ProgramRoutineOut(BaseModel):
    id: uuid.UUID
    name: str
    order_in_program: int | None
    exercise_count: int
    last_performed_at: dt.datetime | None


class ProgramOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    training_category: str | None
    level: str | None
    weeks: int | None
    sessions_per_week: int | None
    is_public: bool
    cover_color: str | None
    # Null for a curated program shipped with the app.
    owner_user_id: uuid.UUID | None
    routines: list[ProgramRoutineOut]
    favorite: bool = False


class FavoriteIn(BaseModel):
    target_type: Literal["routine", "exercise", "program"]
    target_id: uuid.UUID


class LibraryItem(BaseModel):
    # 'program' | 'routine' | 'exercise'
    type: str
    id: uuid.UUID
    title: str
    # "6 routines", "5 exercises", "Chest · Barbell".
    subtitle: str
    color: str | None = None
    image: str | None = None
    favorite: bool
    last_used_at: dt.datetime | None = None


class LibraryPage(BaseModel):
    items: list[LibraryItem]
    # Counts for the "Favorites · N routines" row.
    favorite_count: int
    # Pass back as `cursor` for the next page; null at the end.
    next_cursor: str | None = None


class SuggestedOut(BaseModel):
    routine_id: uuid.UUID
    name: str
    # Two letters for the tile.
    abbreviation: str
    color: str | None
    exercise_count: int
    last_performed_at: dt.datetime | None
    # Null when never done.
    days_since: int | None
    fits_path: bool


class CuratedExerciseOut(BaseModel):
    exercise_id: uuid.UUID
    name: str
    thumbnail_url: str | None
    target_sets: int
    target_reps_low: int
    target_reps_high: int
    rest_seconds: int
    superset_group: int | None = None


class CuratedRoutineOut(BaseModel):
    name: str
    exercises: list[CuratedExerciseOut]


class CuratedProgramOut(BaseModel):
    slug: str
    name: str
    category: str
    level: str
    weeks: int
    sessions_per_week: int
    description: str
    routines: list[CuratedRoutineOut]
    # The caller's saved copy, if they have one.
    saved_program_id: uuid.UUID | None = None


class ExerciseCardOut(BaseModel):
    """A browse row: enough to list, not the whole exercise."""

    id: uuid.UUID
    name: str
    category: str
    equipment: str
    primary_muscle_groups: list[str]
    thumbnail_url: str | None
    is_custom: bool
    # The artwork's credit (CC-BY-SA needs it wherever the picture is).
    media_author: str | None = None
    media_license: str | None = None
    media_source_url: str | None = None


class ExerciseBrowsePage(BaseModel):
    items: list[ExerciseCardOut]
    total: int
    next_cursor: str | None = None


# ---------------------------------------------------------------------------
# The Library tab: catalog workouts and programs, and following a program.
# `recommended` and `sort` are decided by the server (app/api/routes/
# library_catalog.py) so a client never works out what to lead with.
# ---------------------------------------------------------------------------


class LibraryWorkoutCard(BaseModel):
    slug: str
    name: str
    description: str | None
    category: Category
    category_label: str
    difficulty: Level
    duration_minutes: int
    exercise_count: int
    equipment: list[str]
    focus_tags: list[str]
    recommended: bool
    sort: int


class LibraryProgramCard(BaseModel):
    slug: str
    name: str
    description: str | None
    category: Category
    category_label: str
    difficulty: Level
    weeks: int
    days_per_week: int
    equipment: list[str]
    recommended: bool
    sort: int
    following: bool


class LibraryWorkoutExerciseOut(BaseModel):
    position: int
    exercise: ExerciseOut
    target_sets: int
    rep_low: int
    rep_high: int
    rest_seconds: int
    note: str | None
    superset_group: int


class LibraryWorkoutOut(LibraryWorkoutCard):
    exercises: list[LibraryWorkoutExerciseOut]
    # The user's routine copied from it by save-to-routines or a start, if any.
    routine_id: uuid.UUID | None


class ScheduleDayOut(BaseModel):
    day: int
    # Null on a rest day.
    workout_slug: str | None
    workout_name: str | None


class ScheduleWeekOut(BaseModel):
    week: int
    days: list[ScheduleDayOut]


class EnrollmentOut(BaseModel):
    id: uuid.UUID
    program_slug: str
    status: Literal["active", "paused", "completed"]
    started_at: dt.datetime
    current_week: int
    current_day: int
    # The workout to do next; null once the program is complete.
    next_workout: LibraryWorkoutCard | None


class LibraryProgramOut(LibraryProgramCard):
    schedule: list[ScheduleWeekOut]
    workouts: list[LibraryWorkoutCard]
    enrollment: EnrollmentOut | None


class YourProgramOut(BaseModel):
    program: LibraryProgramCard
    enrollment: EnrollmentOut


class PathCountOut(BaseModel):
    category: Category
    label: str
    programs: int
    workouts: int


class LibraryHomeOut(BaseModel):
    # The user's training path; "" when they have not picked one.
    path: str
    # True when there is no path: show "choose your path" and all three
    # paths with equal weight, never an empty screen.
    needs_path: bool
    your_program: YourProgramOut | None
    recommended_programs: list[LibraryProgramCard]
    recommended_workouts: list[LibraryWorkoutCard]
    other_paths: list[PathCountOut]
