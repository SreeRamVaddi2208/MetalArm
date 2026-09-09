"""User + progression response shapes."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class ProgressOut(BaseModel):
    """Progression state. `xp_into_level` / `xp_for_next_level` are derived
    here rather than stored, so the Stat Panel's XP bar stays correct after the
    curve is retuned."""

    model_config = ConfigDict(from_attributes=True)

    total_xp: int
    current_level: int
    rank: str
    points_balance: int
    current_streak: int
    longest_streak: int
    last_completed_on: dt.date | None
    xp_into_level: int
    xp_for_next_level: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    timezone: str
    created_at: dt.datetime


class MeOut(UserOut):
    progress: ProgressOut
