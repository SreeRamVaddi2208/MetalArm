"""Duel and activity-feed request and response shapes."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.duel import DuelMetric

# A window short enough to stay interesting, long enough to train inside.
MIN_DAYS = 1
MAX_DAYS = 28


class DuelCreate(BaseModel):
    """Challenge someone, or the rival.

    Exactly one of `opponent_id` / `against_rival` - a duel is either with a
    person or with a pace, and the difference matters enough to be explicit
    rather than inferred from a missing field.
    """

    metric: DuelMetric = DuelMetric.VOLUME
    days: int = Field(default=7, ge=MIN_DAYS, le=MAX_DAYS)
    opponent_id: uuid.UUID | None = None
    against_rival: bool = False

    @model_validator(mode="after")
    def _one_opponent(self) -> "DuelCreate":
        if self.against_rival == (self.opponent_id is not None):
            raise ValueError("Name an opponent, or set against_rival - not both, not neither")
        return self


class DuelSide(BaseModel):
    """One half of a duel, as the client renders it."""

    user_id: uuid.UUID | None  # None for the rival, which has no account
    display_name: str
    score: float
    is_rival: bool = False


class DuelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    metric: str
    status: str
    window_start: dt.datetime
    window_end: dt.datetime
    challenger: DuelSide
    opponent: DuelSide
    # None while it runs, and after a draw. `is_draw` tells the two apart.
    winner_id: uuid.UUID | None = None
    is_draw: bool = False
    resolved_at: dt.datetime | None = None
    # Set on the response that JUST judged a duel the caller won, so the
    # client knows to celebrate rather than diffing two fetches.
    points_awarded: int | None = None


class DuelListOut(BaseModel):
    active: list[DuelOut]
    pending: list[DuelOut]
    completed: list[DuelOut]


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    event_type: str
    headline: str
    party_id: uuid.UUID | None
    source_id: uuid.UUID | None
    created_at: dt.datetime


class FeedOut(BaseModel):
    entries: list[ActivityOut]
    # Pass back as `before` to page; None when there is nothing older.
    next_before: dt.datetime | None = None
