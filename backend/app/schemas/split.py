"""Splits, stretches and the Recommended panel."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.split import SplitType, StretchPhase


class SplitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    split_type: str
    display_name: str
    tagline: str
    target_muscle_groups: list[str]


class StretchOut(BaseModel):
    """A stretch, which is an exercise with a phase and a hold."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    primary_muscle_groups: list[str]
    instructions: str | None = None
    media_url: str | None = None
    stretch_phase: str | None = None
    hold_seconds: int | None = None
    # Whether MetalArm suggested it or the user put it there. Absent when the
    # stretch is merely being listed rather than shown in a session's panel.
    source: str | None = None


class SetSplit(BaseModel):
    split_type: SplitType


class AddRecommended(BaseModel):
    exercise_id: uuid.UUID
    phase: StretchPhase


class RecommendedPanel(BaseModel):
    """What a session's panel holds, in the order it should be read: what was
    matched, then what the user added."""

    split_type: str | None = None
    pre: list[StretchOut] = Field(default_factory=list)
    post: list[StretchOut] = Field(default_factory=list)


class LibraryRoutine(BaseModel):
    """A routine someone reaches for. `use_count` and `last_used_at` are
    counted from the sessions that name it, never stored."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    split_type: str | None = None
    exercise_count: int = 0
    is_pinned: bool = False
    use_count: int = 0
    last_used_at: str | None = None
