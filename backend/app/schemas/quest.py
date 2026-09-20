"""Quest request/response shapes."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import QuestStatus, Recurrence
from app.models.quest import MAX_POINTS_REWARD, MAX_XP_REWARD


class QuestCreate(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    description: str | None = None
    # Bounded to match ck_quests_xp_reward_range. Enforced here too so an
    # over-large reward is a 422 with a useful message rather than a 500 from
    # the database rejecting it.
    xp_reward: int = Field(default=10, ge=0, le=MAX_XP_REWARD)
    points_reward: int = Field(default=0, ge=0, le=MAX_POINTS_REWARD)
    recurrence: Recurrence = Recurrence.NONE
    due_at: dt.datetime | None = None


class QuestUpdate(BaseModel):
    """Every field optional - this is a PATCH.

    Fields left unset are distinguished from fields explicitly set to null via
    `exclude_unset`, so clearing a description is possible without accidentally
    clearing it on every unrelated edit.
    """

    title: str | None = Field(default=None, min_length=1, max_length=140)
    description: str | None = None
    xp_reward: int | None = Field(default=None, ge=0, le=MAX_XP_REWARD)
    points_reward: int | None = Field(default=None, ge=0, le=MAX_POINTS_REWARD)
    recurrence: Recurrence | None = None
    status: QuestStatus | None = None
    due_at: dt.datetime | None = None


class QuestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    xp_reward: int
    points_reward: int
    recurrence: str
    status: str
    due_at: dt.datetime | None
    created_at: dt.datetime

    # Per-period state, computed per request in the caller's timezone. A
    # recurring quest is never "completed" outright - only done for the current
    # period - so the board renders from these two fields, not a boolean.
    current_period_key: str
    completed_in_current_period: bool


class CompletionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    quest_id: uuid.UUID
    period_key: str
    completed_at: dt.datetime
    xp_awarded: int
    points_awarded: int


class ProgressionDeltaOut(BaseModel):
    """What the completion changed. `leveled_up` / `ranked_up` are what
    trigger the Section 7 animations, so the client never has to infer a
    level-up by diffing two responses."""

    xp_awarded: int
    points_awarded: int
    total_xp: int
    level_before: int
    level_after: int
    rank_before: str
    rank_after: str
    current_streak: int
    longest_streak: int
    leveled_up: bool
    ranked_up: bool


class CompleteQuestResponse(BaseModel):
    completion: CompletionOut
    progression: ProgressionDeltaOut
