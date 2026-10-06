"""Library: programs, favourites, the library listing, suggestions."""

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field

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
