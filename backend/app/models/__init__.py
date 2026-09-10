"""ORM models.

Every model module must be imported here so Base.metadata is fully populated
before Alembic autogenerate runs - a model that isn't imported is invisible to
autogenerate and silently omitted from migrations.
"""

from app.models.party import (
    Party,
    PartyMembership,
    PartyQuest,
    PartyQuestCompletion,
)
from app.models.quest import Quest, QuestCompletion
from app.models.reward import RewardItem, RewardRedemption
from app.models.user import LevelProgress, User
from app.models.workout import (
    BodyMeasurement,
    Exercise,
    PersonalRecord,
    PointsLedgerEntry,
    Routine,
    RoutineExercise,
    SetEntry,
    WorkoutSession,
)

__all__ = [
    "User",
    "LevelProgress",
    "Quest",
    "QuestCompletion",
    "RewardItem",
    "RewardRedemption",
    "Party",
    "PartyMembership",
    "PartyQuest",
    "PartyQuestCompletion",
    "Exercise",
    "Routine",
    "RoutineExercise",
    "WorkoutSession",
    "SetEntry",
    "PersonalRecord",
    "PointsLedgerEntry",
    "BodyMeasurement",
]
