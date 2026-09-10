"""Typed views of the API payloads.

Plain dataclasses, not raw dicts, so templates get real attribute access and a
renamed field fails loudly here instead of rendering blank in the UI.

`rx.Base` was REMOVED in Reflex 0.9 (`rx.Base` now raises "No reflex attribute
Base"). Reflex 0.9 recognises standard dataclasses as state-var models
instead - see reflex/istate/proxy.py, which dispatches on
`dataclasses.is_dataclass`.

Every `from_api` coerces nulls to safe defaults: the API returns `null` for
optional fields, and passing None into a Reflex text component renders the
string "None".
"""

from __future__ import annotations

import dataclasses
from typing import Any


@dataclasses.dataclass
class Progress:
    """Progression state - what the Stat Panel renders."""

    total_xp: int = 0
    current_level: int = 1
    points_balance: int = 0
    longest_streak: int = 0
    xp_into_level: int = 0
    xp_for_next_level: int = 0
    current_streak: int = 0
    streak_is_active: bool = False
    rank: str = "E"
    # What the level alone has earned. When it outranks `rank`, the user has
    # qualified but needs a streak to hold it - the UI says so explicitly.
    rank_by_level: str = "E"
    next_rank: str = ""
    next_rank_level: int = 0
    next_rank_streak: int = 0

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Progress":
        return cls(
            total_xp=data.get("total_xp") or 0,
            current_level=data.get("current_level") or 1,
            points_balance=data.get("points_balance") or 0,
            longest_streak=data.get("longest_streak") or 0,
            xp_into_level=data.get("xp_into_level") or 0,
            xp_for_next_level=data.get("xp_for_next_level") or 0,
            current_streak=data.get("current_streak") or 0,
            streak_is_active=bool(data.get("streak_is_active")),
            rank=data.get("rank") or "E",
            rank_by_level=data.get("rank_by_level") or "E",
            next_rank=data.get("next_rank") or "",
            next_rank_level=data.get("next_rank_level") or 0,
            next_rank_streak=data.get("next_rank_streak") or 0,
        )

    # NOTE: no @property helpers here on purpose - see Quest.recurrence_label.
    # Derived values the UI needs are exposed as rx.var on AuthState, which is
    # evaluated server-side and shipped to the client as plain data.


_RECURRENCE_LABELS = {"daily": "DAILY", "weekly": "WEEKLY", "none": "ONE-OFF"}


@dataclasses.dataclass
class Quest:
    id: str = ""
    title: str = ""
    description: str = ""
    xp_reward: int = 0
    points_reward: int = 0
    recurrence: str = "none"
    status: str = "active"
    current_period_key: str = ""
    # A recurring quest is never "completed" outright, only done for the
    # current period - so the board renders from this, not a boolean.
    completed_in_current_period: bool = False
    # Stored, not derived: Reflex compiles templates to JS, so a Python
    # @property on an rx.Base model is invisible to the rendered component.
    recurrence_label: str = "ONE-OFF"

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Quest":
        return cls(
            id=data.get("id") or "",
            title=data.get("title") or "",
            description=data.get("description") or "",
            xp_reward=data.get("xp_reward") or 0,
            points_reward=data.get("points_reward") or 0,
            recurrence=data.get("recurrence") or "none",
            status=data.get("status") or "active",
            current_period_key=data.get("current_period_key") or "",
            completed_in_current_period=bool(data.get("completed_in_current_period")),
            recurrence_label=_RECURRENCE_LABELS.get(
                data.get("recurrence") or "none", "ONE-OFF"
            ),
        )


@dataclasses.dataclass
class Reward:
    id: str = ""
    title: str = ""
    point_cost: int = 0
    is_active: bool = True
    affordable: bool = False
    times_redeemed: int = 0

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Reward":
        return cls(
            id=data.get("id") or "",
            title=data.get("title") or "",
            point_cost=data.get("point_cost") or 0,
            is_active=bool(data.get("is_active", True)),
            affordable=bool(data.get("affordable")),
            times_redeemed=data.get("times_redeemed") or 0,
        )


@dataclasses.dataclass
class Redemption:
    id: str = ""
    reward_title: str = ""
    points_spent: int = 0
    redeemed_at: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Redemption":
        return cls(
            id=data.get("id") or "",
            reward_title=data.get("reward_title") or "",
            points_spent=data.get("points_spent") or 0,
            # Trimmed to minutes; the raw value is a full ISO timestamp.
            redeemed_at=(data.get("redeemed_at") or "")[:16].replace("T", " "),
        )


@dataclasses.dataclass
class Party:
    id: str = ""
    name: str = ""
    my_role: str = "member"
    member_count: int = 0
    max_members: int = 10
    invite_code: str = ""
    total_party_xp: int = 0
    is_active: bool = True
    # Stored, not derived - see the note on Quest.recurrence_label.
    is_owner: bool = False
    seats_label: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Party":
        role = data.get("my_role") or "member"
        count = data.get("member_count") or 0
        cap = data.get("max_members") or 10
        return cls(
            id=data.get("id") or "",
            name=data.get("name") or "",
            my_role=role,
            member_count=count,
            max_members=cap,
            invite_code=data.get("invite_code") or "",
            total_party_xp=data.get("total_party_xp") or 0,
            is_active=bool(data.get("is_active", True)),
            is_owner=(role == "owner"),
            seats_label=f"{count}/{cap} MEMBERS",
        )


@dataclasses.dataclass
class PartyQuest:
    id: str = ""
    title: str = ""
    description: str = ""
    xp_reward: int = 0
    points_reward: int = 0
    recurrence: str = "none"
    recurrence_label: str = "ONE-OFF"
    current_period_key: str = ""
    completed_in_current_period: bool = False
    completed_by_count: int = 0
    # Reads "2 of 4 done" on the shared board - the signal that makes it feel
    # collaborative rather than a private list.
    progress_label: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any], member_count: int = 0) -> "PartyQuest":
        done = data.get("completed_by_count") or 0
        return cls(
            id=data.get("id") or "",
            title=data.get("title") or "",
            description=data.get("description") or "",
            xp_reward=data.get("xp_reward") or 0,
            points_reward=data.get("points_reward") or 0,
            recurrence=data.get("recurrence") or "none",
            recurrence_label=_RECURRENCE_LABELS.get(
                data.get("recurrence") or "none", "ONE-OFF"
            ),
            current_period_key=data.get("current_period_key") or "",
            completed_in_current_period=bool(data.get("completed_in_current_period")),
            completed_by_count=done,
            progress_label=f"{done} of {member_count} done" if member_count else f"{done} done",
        )


@dataclasses.dataclass
class LeaderboardRow:
    position: int = 0
    user_id: str = ""
    display_name: str = ""
    party_xp: int = 0
    level: int = 1
    rank: str = "E"
    is_me: bool = False

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "LeaderboardRow":
        return cls(
            position=data.get("position") or 0,
            user_id=data.get("user_id") or "",
            display_name=data.get("display_name") or "",
            party_xp=data.get("party_xp") or 0,
            level=data.get("level") or 1,
            rank=data.get("rank") or "E",
            is_me=bool(data.get("is_me")),
        )
