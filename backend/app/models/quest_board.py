"""Generated quests and streak freezes.

Generated quests sit beside the user-written ones in quest.py rather than
inside them: a written quest is ticked off by its owner and pays what its owner
set, while a generated quest is ticked off by the SERVER from the sets the user
logged and pays what workout_rules.py says. One table for both would need every
column to mean two things.

- QuestTemplate is config, seeded from app/data/quest_templates.json the same
  way the training paths are, so a quest can be retuned without a release.
- QuestAssignment is one template handed to one user for one period. Its
  progress is a cache - the truth is always recomputed from the sets
  (app/core/quest_engine.py) - but its status is real state: it is what the
  ledger row for the reward points back at.
- StreakFreezeEvent is append-only, like the points ledger: a balance is a SUM,
  never a counter that can drift from the events behind it.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import Timestamps, UUIDPrimaryKey
from app.models.workout_enums import check_in


class QuestPeriod(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


class QuestObjective(str, enum.Enum):
    """What a generated quest measures. Every one is computed from data the
    backend already records - see app/core/quest_engine.py."""

    COMPLETE_SESSIONS = "complete_sessions"
    LOG_WORKING_SETS = "log_working_sets"
    TOTAL_VOLUME = "total_volume"
    SETS_IN_REP_RANGE = "sets_in_rep_range"
    SETS_WITH_EXERCISE_TAG = "sets_with_exercise_tag"
    INTENSITY_SETS = "intensity_sets"
    HIT_PR = "hit_pr"


class AssignmentStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    # Swapped out by the daily reroll. Kept, not deleted, so a reroll cannot
    # be used to hand back a quest and draw it again.
    REROLLED = "rerolled"


class FreezeReason(str, enum.Enum):
    # Earned: the weekly streak reached a multiple of FREEZE_EARN_EVERY_WEEKS.
    STREAK_MILESTONE = "streak_milestone"
    # Earned: every weekly quest done.
    WEEKLY_QUESTS_COMPLETE = "weekly_quests_complete"
    # Spent: a week that fell short was covered.
    MISSED_WEEK_COVERED = "missed_week_covered"


class QuestTemplate(Timestamps, Base):
    __tablename__ = "quest_templates"

    # The stable seed key, like exercises.slug.
    code: Mapped[str] = mapped_column(String(60), primary_key=True)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    period: Mapped[str] = mapped_column(String(8), nullable=False)
    objective_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # {"rep_low": 12, "rep_high": 20}, {"tag": "mobility"}, {"pct_e1rm": 0.85}...
    # Validated against the objective when seeded (app/core/quest_templates.py).
    objective_params: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    target_value: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_points: Mapped[int] = mapped_column(Integer, nullable=False)
    # users.character_class values; empty means every path, including none.
    eligible_categories: Mapped[list[str]] = mapped_column(
        ARRAY(String(16)), nullable=False, server_default=text("'{}'")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        CheckConstraint(check_in("period", QuestPeriod), name="ck_quest_templates_period"),
        CheckConstraint(
            check_in("objective_type", QuestObjective), name="ck_quest_templates_objective"
        ),
        CheckConstraint("target_value >= 1", name="ck_quest_templates_target"),
        CheckConstraint(
            "reward_points >= 1 AND reward_points <= 1000", name="ck_quest_templates_reward"
        ),
        CheckConstraint(
            "eligible_categories <@ "
            "ARRAY['powerlifter', 'bodybuilder', 'athlete']::varchar[]",
            name="ck_quest_templates_categories",
        ),
    )


class QuestAssignment(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "quest_assignments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    template_code: Mapped[str] = mapped_column(
        String(60), ForeignKey("quest_templates.code", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    period: Mapped[str] = mapped_column(String(8), nullable=False)
    # periods.period_key in the user's timezone: '2026-10-05' or '2026-W41'.
    period_key: Mapped[str] = mapped_column(String(16), nullable=False)
    period_start: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Snapshotted from the template, so retuning a template never moves the
    # goalposts on a quest someone is halfway through.
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    objective_type: Mapped[str] = mapped_column(String(32), nullable=False)
    objective_params: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    target_value: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_points: Mapped[int] = mapped_column(Integer, nullable=False)
    # A cache of the last computed progress. Never trusted for a reward.
    progress_value: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=AssignmentStatus.ACTIVE.value
    )
    completed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(check_in("period", QuestPeriod), name="ck_quest_assignments_period"),
        CheckConstraint(
            check_in("status", AssignmentStatus), name="ck_quest_assignments_status"
        ),
        CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)",
            name="ck_quest_assignments_completed",
        ),
        CheckConstraint("period_end > period_start", name="ck_quest_assignments_window"),
        # The same quest cannot be handed out twice in one period - which is
        # also what makes concurrent first reads of a period generate once.
        # A rerolled row steps aside, so the slot it held can be refilled.
        Index(
            "uq_quest_assignments_once",
            "user_id",
            "period_key",
            "template_code",
            unique=True,
            postgresql_where=text("status <> 'rerolled'"),
        ),
        Index("ix_quest_assignments_user_period", "user_id", "period_key"),
    )


class QuestReroll(UUIDPrimaryKey, Base):
    """One row per reroll. The UNIQUE is the daily limit; a Python count of
    today's rerolls would let two concurrent taps both pass."""

    __tablename__ = "quest_rerolls"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The user's local date.
    day_key: Mapped[str] = mapped_column(String(16), nullable=False)
    # 1-based, so REROLLS_PER_DAY > 1 needs no schema change.
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("quest_assignments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "day_key", "ordinal", name="uq_quest_rerolls_slot"),
        CheckConstraint("ordinal >= 1", name="ck_quest_rerolls_ordinal"),
    )


class StreakFreezeEvent(UUIDPrimaryKey, Base):
    """+1 when a freeze is earned, -1 when one covers a week. Balance is the
    sum; app/core/streak_freezes.py keeps it within FREEZE_CAP."""

    __tablename__ = "streak_freeze_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    # The ISO week the event is ABOUT: the week covered for a spend, the week
    # that earned it for an earn. Not when it was written - freezes are settled
    # lazily, so that can be weeks later.
    week_key: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("delta IN (-1, 1)", name="ck_streak_freeze_delta"),
        CheckConstraint(check_in("reason", FreezeReason), name="ck_streak_freeze_reason"),
        CheckConstraint(
            "(reason = 'missed_week_covered') = (delta = -1)",
            name="ck_streak_freeze_reason_sign",
        ),
        # Each reason happens at most once per week: a week is covered once,
        # and earns each kind of freeze once. That is what makes settling
        # idempotent, however many requests race to do it.
        # Leads with user_id, so it also serves every per-user read.
        UniqueConstraint("user_id", "week_key", "reason", name="uq_streak_freeze_once"),
    )
