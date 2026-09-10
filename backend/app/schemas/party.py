"""Party/guild request and response shapes."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Recurrence
from app.models.party import DEFAULT_MAX_MEMBERS
from app.models.quest import MAX_XP_REWARD


class PartyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    max_members: int = Field(default=DEFAULT_MAX_MEMBERS, ge=2, le=100)


class PartyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)


class JoinRequest(BaseModel):
    invite_code: str = Field(min_length=1, max_length=20)


class MemberOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    role: str
    joined_at: dt.datetime
    level: int
    rank: str
    # XP this member has contributed to THIS party, which counts only what was
    # earned while a member - a party quest cannot be completed by an outsider.
    party_xp: int


class PartyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    max_members: int
    member_count: int
    is_active: bool
    created_at: dt.datetime

    # The caller's own relationship to this party.
    my_role: str
    # Only shown to members - the code is a capability, not public metadata.
    invite_code: str | None = None
    total_party_xp: int = 0


class LeaderboardEntry(BaseModel):
    position: int
    user_id: uuid.UUID
    display_name: str
    party_xp: int
    level: int
    rank: str
    is_me: bool


class LeaderboardOut(BaseModel):
    party_id: uuid.UUID
    total_party_xp: int
    entries: list[LeaderboardEntry]


class PartyQuestCreate(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    description: str | None = None
    xp_reward: int = Field(default=25, ge=0, le=MAX_XP_REWARD)
    points_reward: int = Field(default=0, ge=0)
    recurrence: Recurrence = Recurrence.NONE
    due_at: dt.datetime | None = None


class PartyQuestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=140)
    description: str | None = None
    xp_reward: int | None = Field(default=None, ge=0, le=MAX_XP_REWARD)
    points_reward: int | None = Field(default=None, ge=0)
    recurrence: Recurrence | None = None
    is_active: bool | None = None
    due_at: dt.datetime | None = None


class PartyQuestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    party_id: uuid.UUID
    title: str
    description: str | None
    xp_reward: int
    points_reward: int
    recurrence: str
    is_active: bool
    due_at: dt.datetime | None
    created_at: dt.datetime

    # Per-period, per-caller: a shared quest is done by each member
    # independently, so this is "have *I* done it this period", not the party's.
    current_period_key: str
    completed_in_current_period: bool
    # How many members have completed it this period - the shared-board signal
    # that makes it feel collaborative.
    completed_by_count: int


class PartyQuestCompleteResponse(BaseModel):
    """Mirrors the personal quest completion response, plus party effect."""

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
    party_xp_contributed: int
    total_party_xp: int
