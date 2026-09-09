"""User + progression response shapes."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class ProgressOut(BaseModel):
    """Progression state - everything the Stat Panel renders.

    The derived fields are computed per request rather than stored, so they
    stay correct after the XP curve is retuned.
    """

    model_config = ConfigDict(from_attributes=True)

    total_xp: int
    current_level: int
    points_balance: int
    longest_streak: int
    last_completed_on: dt.date | None

    # --- XP bar ---
    xp_into_level: int
    xp_for_next_level: int

    # --- Streak ---
    # The streak as it stands NOW: 0 once it has lapsed. The stored counter is
    # frozen while a user is away, so reporting it raw would show a dormant
    # user a streak they no longer have.
    current_streak: int
    streak_is_active: bool

    # --- Rank ---
    # The rank actually held, after the streak gate on A and S.
    rank: str
    # The rank the level alone would grant. When this outranks `rank`, the user
    # has earned it but needs the streak to hold it - which is what the UI
    # should say rather than silently showing the lower badge.
    rank_by_level: str
    next_rank: str | None
    next_rank_level: int | None
    next_rank_streak: int | None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    timezone: str
    created_at: dt.datetime


class MeOut(UserOut):
    progress: ProgressOut
