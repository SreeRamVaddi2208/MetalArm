"""Profile page payload (Section 2: the Stat Panel as a character sheet)."""

import datetime as dt

from pydantic import BaseModel

from app.schemas.user import ProgressOut, UserOut


class BadgeOut(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    earned: bool
    # Progress toward an unearned badge, so the panel can show what is close
    # rather than only what is done.
    progress: int
    target: int
    percent: int


class LifetimeStats(BaseModel):
    """Totals across everything, for the character-sheet header."""

    quests_completed: int
    party_quests_completed: int
    rewards_redeemed: int
    points_earned: int
    points_spent: int
    parties_joined: int
    party_xp_contributed: int
    member_since: dt.datetime


class ProfileOut(BaseModel):
    user: UserOut
    progress: ProgressOut
    stats: LifetimeStats
    badges: list[BadgeOut]
    badges_earned: int
    badges_total: int
