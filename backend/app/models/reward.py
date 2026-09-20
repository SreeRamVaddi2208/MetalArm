"""Rewards shop: user-defined rewards and the redemptions that spend points."""

import datetime as dt
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import Timestamps, UUIDPrimaryKey


# A price no one can reach is a bug, not a feature: unbounded it overflowed the
# INTEGER column and the request failed with a 500.
MAX_POINT_COST = 1_000_000


class RewardItem(UUIDPrimaryKey, Timestamps, Base):
    """A reward the user defines for themselves, e.g. "order takeout"."""

    __tablename__ = "reward_items"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    point_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    redemptions: Mapped[list["RewardRedemption"]] = relationship(
        back_populates="reward_item"
    )

    __table_args__ = (
        # A zero-cost reward would be a free infinite loop.
        CheckConstraint(
            f"point_cost > 0 AND point_cost <= {MAX_POINT_COST}",
            name="ck_reward_items_cost_range",
        ),
        Index("ix_reward_items_owner_active", "owner_id", "is_active"),
    )


class RewardRedemption(UUIDPrimaryKey, Base):
    """A spend event.

    Redeeming debits level_progress.points_balance in the SAME transaction as
    this insert; the CHECK (points_balance >= 0) on level_progress is the
    backstop against concurrent double-spend.
    """

    __tablename__ = "reward_redemptions"

    reward_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        # RESTRICT, not CASCADE: deleting a reward must not erase the history
        # of what was already spent on it.
        ForeignKey("reward_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Snapshotted: repricing a reward later must not rewrite spend history.
    points_spent: Mapped[int] = mapped_column(Integer, nullable=False)
    redeemed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    reward_item: Mapped["RewardItem"] = relationship(back_populates="redemptions")

    __table_args__ = (
        CheckConstraint("points_spent >= 0", name="ck_redemption_points_non_negative"),
    )
