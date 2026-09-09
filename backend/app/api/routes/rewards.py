"""Rewards shop: user-defined rewards and the points that buy them.

Points are EARNED on quest completion (see routes/quests.py) and SPENT here.
The spend path mirrors the completion path's transaction shape for the same
reason: balance checks are races, so the database has to be the authority.
"""

import datetime as dt
import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.core.progression import lock_progress
from app.models.quest import QuestCompletion
from app.models.reward import RewardItem, RewardRedemption
from app.models.user import LevelProgress, User
from app.schemas.reward import (
    RedeemResponse,
    RedemptionOut,
    RewardCreate,
    RewardOut,
    RewardUpdate,
    WalletOut,
)

logger = logging.getLogger("levelforge.rewards")

router = APIRouter(prefix="/rewards", tags=["rewards"])


def _get_owned_reward(db: Session, reward_id: uuid.UUID, user: User) -> RewardItem:
    """404 rather than 403 for another user's reward - a 403 would confirm the
    id exists. Same rule as quests."""
    reward = db.execute(
        select(RewardItem).where(
            RewardItem.id == reward_id, RewardItem.owner_id == user.id
        )
    ).scalar_one_or_none()
    if reward is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reward not found"
        )
    return reward


def _balance_of(db: Session, user: User) -> int:
    return db.execute(
        select(LevelProgress.points_balance).where(LevelProgress.user_id == user.id)
    ).scalar_one()


def _serialize_many(
    db: Session, rewards: list[RewardItem], balance: int
) -> list[RewardOut]:
    """Attach affordability and redemption counts.

    One grouped query for all counts rather than a lookup per reward, so the
    shop's cost does not grow with the number of rewards defined.
    """
    counts: dict[uuid.UUID, int] = {}
    if rewards:
        rows = db.execute(
            select(
                RewardRedemption.reward_item_id, func.count(RewardRedemption.id)
            )
            .where(RewardRedemption.reward_item_id.in_([r.id for r in rewards]))
            .group_by(RewardRedemption.reward_item_id)
        ).all()
        counts = {row[0]: row[1] for row in rows}

    return [
        RewardOut(
            id=r.id,
            title=r.title,
            point_cost=r.point_cost,
            is_active=r.is_active,
            created_at=r.created_at,
            affordable=balance >= r.point_cost,
            times_redeemed=counts.get(r.id, 0),
        )
        for r in rewards
    ]


# ---------------------------------------------------------------------------
# Literal paths MUST be declared before /{reward_id}. FastAPI matches routes in
# declaration order, so a later literal would instead be parsed as a UUID path
# parameter and fail with a 422.
# ---------------------------------------------------------------------------


@router.get("/wallet", response_model=WalletOut)
def read_wallet(current_user: CurrentUser, db: DbSession) -> WalletOut:
    """Balance plus lifetime earned/spent totals."""
    earned = db.execute(
        select(func.coalesce(func.sum(QuestCompletion.points_awarded), 0)).where(
            QuestCompletion.user_id == current_user.id
        )
    ).scalar_one()
    spent = db.execute(
        select(func.coalesce(func.sum(RewardRedemption.points_spent), 0)).where(
            RewardRedemption.user_id == current_user.id
        )
    ).scalar_one()

    return WalletOut(
        points_balance=_balance_of(db, current_user),
        total_points_earned=int(earned),
        total_points_spent=int(spent),
    )


@router.get("/redemptions", response_model=list[RedemptionOut])
def list_redemptions(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[RedemptionOut]:
    """Spend history, newest first."""
    rows = db.execute(
        select(RewardRedemption, RewardItem.title)
        .join(RewardItem, RewardItem.id == RewardRedemption.reward_item_id)
        .where(RewardRedemption.user_id == current_user.id)
        .order_by(RewardRedemption.redeemed_at.desc())
        .limit(limit)
    ).all()

    return [
        RedemptionOut(
            id=redemption.id,
            reward_item_id=redemption.reward_item_id,
            reward_title=title,
            points_spent=redemption.points_spent,
            redeemed_at=redemption.redeemed_at,
        )
        for redemption, title in rows
    ]


# ---------------------------------------------------------------------------
# Reward CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[RewardOut])
def list_rewards(
    current_user: CurrentUser,
    db: DbSession,
    include_inactive: bool = Query(
        default=False,
        description="Include deactivated rewards. Hidden by default.",
    ),
) -> list[RewardOut]:
    query = select(RewardItem).where(RewardItem.owner_id == current_user.id)
    if not include_inactive:
        query = query.where(RewardItem.is_active.is_(True))

    rewards = list(db.execute(query.order_by(RewardItem.point_cost)).scalars())
    return _serialize_many(db, rewards, _balance_of(db, current_user))


@router.post("", response_model=RewardOut, status_code=status.HTTP_201_CREATED)
def create_reward(
    payload: RewardCreate, current_user: CurrentUser, db: DbSession
) -> RewardOut:
    reward = RewardItem(
        owner_id=current_user.id,
        title=payload.title.strip(),
        point_cost=payload.point_cost,
        is_active=True,
    )
    db.add(reward)
    db.commit()
    db.refresh(reward)
    return _serialize_many(db, [reward], _balance_of(db, current_user))[0]


@router.get("/{reward_id}", response_model=RewardOut)
def get_reward(
    reward_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> RewardOut:
    reward = _get_owned_reward(db, reward_id, current_user)
    return _serialize_many(db, [reward], _balance_of(db, current_user))[0]


@router.patch("/{reward_id}", response_model=RewardOut)
def update_reward(
    reward_id: uuid.UUID,
    payload: RewardUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> RewardOut:
    """Partial update.

    Repricing does NOT rewrite spend history: points_spent is snapshotted on
    the redemption row, so past redemptions keep the price actually paid.
    """
    reward = _get_owned_reward(db, reward_id, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(reward, field, value.strip() if field == "title" and value else value)

    db.commit()
    db.refresh(reward)
    return _serialize_many(db, [reward], _balance_of(db, current_user))[0]


@router.delete("/{reward_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reward(
    reward_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    """Delete a reward that has never been redeemed.

    The redemption FK is ON DELETE RESTRICT so that deleting a reward cannot
    erase the record of points already spent on it. Once there is history the
    reward can only be DEACTIVATED (PATCH is_active=false), which hides it from
    the shop while leaving the ledger intact.
    """
    reward = _get_owned_reward(db, reward_id, current_user)

    redeemed = db.execute(
        select(func.count(RewardRedemption.id)).where(
            RewardRedemption.reward_item_id == reward.id
        )
    ).scalar_one()
    if redeemed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Reward has been redeemed {redeemed} time(s) and cannot be "
                "deleted without erasing spend history. Deactivate it instead "
                "(PATCH is_active=false)."
            ),
        )

    db.delete(reward)
    db.commit()


# ---------------------------------------------------------------------------
# Spending
# ---------------------------------------------------------------------------


@router.post("/{reward_id}/redeem", response_model=RedeemResponse)
def redeem_reward(
    reward_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> RedeemResponse:
    """Spend points on a reward.

    Same transaction shape as completing a quest, and for the same reason:

    1. Lock level_progress FOR UPDATE *before* reading the balance. Checking
       the balance without the lock is a race - two concurrent redeems both
       read 100, both spend 80, and the user gets 160 points of rewards for
       100 points. The lock is taken in the same order as the completion path,
       so the two cannot deadlock against each other.
    2. Insert the redemption and debit in the same transaction, so points can
       never leave the wallet without a matching ledger row.
    3. CHECK (points_balance >= 0) is the backstop if the guard above is ever
       bypassed.
    """
    reward = _get_owned_reward(db, reward_id, current_user)

    if not reward.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot redeem a deactivated reward",
        )

    progress = lock_progress(db, current_user.id)

    if progress.points_balance < reward.point_cost:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Insufficient points: {reward.title} costs {reward.point_cost}, "
                f"balance is {progress.points_balance}"
            ),
        )

    redemption = RewardRedemption(
        reward_item_id=reward.id,
        user_id=current_user.id,
        # Snapshotted, so repricing later cannot rewrite what was paid.
        points_spent=reward.point_cost,
        redeemed_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(redemption)
    progress.points_balance -= reward.point_cost

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Insufficient points",
        ) from None

    db.commit()
    db.refresh(redemption)
    logger.info(
        "user %s redeemed %s for %s points", current_user.id, reward.id, reward.point_cost
    )

    return RedeemResponse(
        redemption=RedemptionOut(
            id=redemption.id,
            reward_item_id=redemption.reward_item_id,
            reward_title=reward.title,
            points_spent=redemption.points_spent,
            redeemed_at=redemption.redeemed_at,
        ),
        points_balance=progress.points_balance,
    )
