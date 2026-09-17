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
    # Gym workout module.
    workouts_completed: int = 0
    # Sets that beat an existing record (first-ever baselines excluded).
    workout_prs: int = 0
    # Working-set volume across finished workouts, in kg.
    total_volume_kg: float = 0.0
    # Longest run of weeks that met the weekly workout target.
    longest_workout_streak: int = 0


class ProfileOut(BaseModel):
    user: UserOut
    progress: ProgressOut
    stats: LifetimeStats
    badges: list[BadgeOut]
    badges_earned: int
    badges_total: int


class TrialOut(BaseModel):
    """A strength trial gating rank B, A or S (app/core/rank_trials.py)."""

    rank: str
    lift: str
    description: str
    multiplier: float
    # Null until a bodyweight is logged.
    target_kg: float | None
    best_kg: float | None
    passed: bool


class StatOut(BaseModel):
    """One character stat, 0-100 with the number behind it."""

    key: str
    label: str
    value: int
    detail: str
    highlighted: bool


class CharacterOut(BaseModel):
    """The character sheet (app/core/character.py). The class is cosmetic."""

    character_class: str
    class_label: str
    stats: list[StatOut]
