"""Quest definitions and per-period completions."""

import datetime as dt
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import RECURRENCE_VALUES, QuestStatus, pg_enum
from app.models.mixins import Timestamps, UUIDPrimaryKey

# Reused by personal and party quests.
_RECURRENCE_CHECK = ", ".join(f"'{v}'" for v in RECURRENCE_VALUES)
MAX_XP_REWARD = 10_000
# Points are spent in the user's own shop, so they are self-authored too - and
# unbounded they overflowed the INTEGER column, which reached the client as a
# 500 rather than a 422.
MAX_POINTS_REWARD = 10_000


class Quest(UUIDPrimaryKey, Timestamps, Base):
    """A quest DEFINITION owned by one user.

    Note there is no `completed` status. Completion is per-period and lives in
    QuestCompletion, because a single status field cannot express "done today
    but not yesterday" for a daily quest.
    """

    __tablename__ = "quests"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    xp_reward: Mapped[int] = mapped_column(Integer, nullable=False)
    points_reward: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    # VARCHAR + CHECK rather than a native enum: 'monthly' / 'every N days' are
    # plausible additions, and ALTER TYPE ... ADD VALUE fights Alembic's
    # transactional migrations.
    recurrence: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="none"
    )
    status: Mapped[QuestStatus] = mapped_column(
        pg_enum(QuestStatus, "quest_status"),
        nullable=False,
        server_default=QuestStatus.ACTIVE.value,
    )
    due_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    completions: Mapped[list["QuestCompletion"]] = relationship(
        back_populates="quest", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            f"recurrence IN ({_RECURRENCE_CHECK})", name="ck_quests_recurrence"
        ),
        # Bounded so a self-authored quest can't mint arbitrary XP.
        CheckConstraint(
            f"xp_reward >= 0 AND xp_reward <= {MAX_XP_REWARD}",
            name="ck_quests_xp_reward_range",
        ),
        CheckConstraint(
            f"points_reward >= 0 AND points_reward <= {MAX_POINTS_REWARD}",
            name="ck_quests_points_reward_range",
        ),
        # Drives the quest board: a user's active quests, newest first.
        Index("ix_quests_owner_status", "owner_id", "status"),
    )


class QuestCompletion(UUIDPrimaryKey, Base):
    """One completion of one quest for one period.

    The UNIQUE(quest_id, user_id, period_key) constraint is what makes
    recurrence correct AND is the only real defense against XP farming by
    double-submitting: that is a race, so an application-level "already
    completed?" check cannot close it - only the database can.

    period_key is derived from completed_at in the USER's timezone:
        daily   -> '2026-09-10'
        weekly  -> '2026-W37'   (ISO week)
        none    -> 'once'       (sentinel, not NULL - NULL never equals itself,
                                 so a NULL key would permit endless duplicates)
    """

    __tablename__ = "quest_completions"

    quest_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("quests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period_key: Mapped[str] = mapped_column(String(16), nullable=False)
    completed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Snapshotted at completion time so editing a quest's reward later cannot
    # rewrite history. Makes total_xp auditable as SUM(xp_awarded).
    xp_awarded: Mapped[int] = mapped_column(Integer, nullable=False)
    points_awarded: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    quest: Mapped["Quest"] = relationship(back_populates="completions")

    __table_args__ = (
        UniqueConstraint(
            "quest_id", "user_id", "period_key", name="uq_quest_completion_period"
        ),
        CheckConstraint("xp_awarded >= 0", name="ck_completion_xp_non_negative"),
        CheckConstraint(
            "points_awarded >= 0", name="ck_completion_points_non_negative"
        ),
        # Streak calculation walks a user's completions in time order.
        Index("ix_quest_completions_user_time", "user_id", "completed_at"),
    )
