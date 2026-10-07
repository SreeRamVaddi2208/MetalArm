"""The social graph and the game strip (overhaul phase 4)."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class UserCard(BaseModel):
    """A person, as every list shows them: name, rank tier for the avatar
    frame, and where you stand with them."""

    id: uuid.UUID
    display_name: str
    username: str | None
    avatar_url: str | None
    rank: str
    level: int
    training_category: str | None
    you_follow: bool
    follows_you: bool
    # A line of why they are suggested ("Followed by Maya", "In your party").
    reason: str | None = None


class UserPage(BaseModel):
    items: list[UserCard]
    next_cursor: str | None = None


class ProfileOut(BaseModel):
    user: UserCard
    bio: str | None
    followers: int
    following: int
    workouts: int
    is_friend: bool
    is_me: bool


class FeedExercise(BaseModel):
    name: str
    thumbnail_url: str | None
    sets: int


class FeedItem(BaseModel):
    session_id: uuid.UUID
    user: UserCard
    name: str | None
    started_at: dt.datetime
    ended_at: dt.datetime
    visibility: str
    duration_seconds: int
    volume_kg: float
    working_sets: int
    records: int
    points: int
    # Up to six, in workout order, and how many more.
    exercises: list[FeedExercise]
    more_exercises: int
    spotted: int
    spotted_by_me: bool


class FeedPage(BaseModel):
    items: list[FeedItem]
    next_cursor: str | None = None


class ReactionOut(BaseModel):
    spotted: int
    spotted_by_me: bool


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    actor: UserCard | None
    target_type: str | None
    target_id: uuid.UUID | None
    detail: str | None
    read: bool
    created_at: dt.datetime


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    unread: int
    next_cursor: str | None = None


class ReadIn(BaseModel):
    # Empty: mark everything read.
    ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)


class ReadOut(BaseModel):
    unread: int


class GameOut(BaseModel):
    """One row of game for Home: rank, the XP to the next one, this week."""

    rank: str
    level: int
    next_rank: str | None
    # XP held, and the XP the next rank's level needs (null at the top).
    xp: int
    xp_next_rank: int | None
    points_this_week: int
    quests_done: int
    quests_total: int
    streak_weeks: int
    unread_notifications: int


class LeaderboardRow(BaseModel):
    position: int
    user: UserCard
    points: int
    is_me: bool


class LeaderboardOut(BaseModel):
    period: str
    rows: list[LeaderboardRow]
    # The caller's own row, also when it is beyond the rows returned.
    me: LeaderboardRow
