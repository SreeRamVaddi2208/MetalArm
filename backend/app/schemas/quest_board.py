"""Generated quests and streak freezes: response shapes."""

import datetime as dt
import uuid

from pydantic import BaseModel

from app.core.quest_board import QuestUpdate
from app.models.quest_board import AssignmentStatus
from app.schemas.quest import ProgressionDeltaOut


class AssignmentOut(BaseModel):
    id: uuid.UUID
    template_code: str
    title: str
    description: str
    # 'daily' | 'weekly'
    period: str
    objective_type: str
    # Clamped to target_value; computed server-side from the sets logged.
    progress: int
    target: int
    reward_points: int
    # 'active' | 'completed'
    status: str
    completed_at: dt.datetime | None
    # When the period ends and the quest expires, in UTC.
    ends_at: dt.datetime
    # Daily, still active, and a reroll is left today.
    can_reroll: bool


class QuestBoardOut(BaseModel):
    daily: list[AssignmentOut]
    weekly: list[AssignmentOut]
    rerolls_left: int


class QuestProgressOut(BaseModel):
    """One current quest after a set was logged, edited or deleted, or a
    workout finished - so the UI can show "Rep range 9/15" without a second
    request."""

    assignment_id: uuid.UUID
    title: str
    period: str
    progress: int
    target: int
    # This action moved it forward. The in-session chip shows only these.
    advanced: bool
    completed: bool
    # This action completed it - time for the quest-complete moment.
    completed_now: bool
    reward_points: int

    @classmethod
    def from_update(cls, update: QuestUpdate) -> "QuestProgressOut":
        a = update.assignment
        return cls(
            assignment_id=a.id,
            title=a.title,
            period=a.period,
            progress=update.after,
            target=a.target_value,
            advanced=update.advanced,
            completed=a.status == AssignmentStatus.COMPLETED.value,
            completed_now=update.completed_now,
            reward_points=a.reward_points,
        )


class RerollResponse(BaseModel):
    replaced: uuid.UUID
    quest: AssignmentOut
    rerolls_left: int
    # A new quest can be done already (a "finish a workout" quest swapped in
    # after a workout), and is paid on the spot.
    progression: ProgressionDeltaOut | None = None


class StreakStatusOut(BaseModel):
    weeks: int
    this_week_sessions: int
    target: int
    this_week_done: bool
    sessions_to_go: int
    freezes_held: int
    freeze_cap: int
    # Counting weeks until the streak milestone that earns a freeze.
    weeks_to_next_freeze: int
    # ISO weeks a freeze covered since the user last acknowledged - shown once
    # as "your streak was saved", then cleared with POST /streak/seen.
    freezes_used_unseen: list[str]
