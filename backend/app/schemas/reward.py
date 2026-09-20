"""Rewards shop request/response shapes."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.reward import MAX_POINT_COST


class RewardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    # ge=1/le mirror ck_reward_items_cost_range. A zero-cost reward would be a
    # free infinite loop, so the floor is enforced here too and returns a 422
    # rather than letting the database raise.
    point_cost: int = Field(ge=1, le=MAX_POINT_COST)


class RewardUpdate(BaseModel):
    """PATCH - unset fields are left alone (see QuestUpdate for the reasoning)."""

    title: str | None = Field(default=None, min_length=1, max_length=140)
    point_cost: int | None = Field(default=None, ge=1, le=MAX_POINT_COST)
    is_active: bool | None = None


class RewardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    point_cost: int
    is_active: bool
    created_at: dt.datetime

    # Computed per request against the caller's current balance, so the shop
    # can disable what they cannot yet buy without duplicating the comparison.
    affordable: bool
    times_redeemed: int


class RedemptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reward_item_id: uuid.UUID
    # Denormalized for the history list. Safe to join for: the redemption FK is
    # ON DELETE RESTRICT, so a reward with history cannot be deleted out from
    # under its own ledger entries.
    reward_title: str
    points_spent: int
    redeemed_at: dt.datetime


class RedeemResponse(BaseModel):
    """The redemption plus the resulting balance, so the client does not need a
    second call to refresh the wallet."""

    redemption: RedemptionOut
    points_balance: int


class WalletOut(BaseModel):
    """The points ledger.

    `points_balance` is the authoritative stored value and is the only number
    to spend against. The other two are aggregates over surviving history:
    earned from quest_completions, spent from reward_redemptions.

    They do NOT always reconcile. Deleting a quest cascades its completions
    away, so `total_points_earned` drops while the balance - correctly - does
    not, since the points were genuinely earned and possibly already spent.
    Verified: earning 100, spending 80, then deleting the earning quest leaves
    balance=20, earned=0, spent=80.

    So do not render `earned - spent` as if it were the balance, and do not
    treat a mismatch as corruption. Redemptions never vanish this way: their
    FK is ON DELETE RESTRICT.
    """

    points_balance: int
    total_points_earned: int
    total_points_spent: int
