"""Head-to-head duels, and the activity feed they feed into.

A duel is a window and a metric, nothing more: who is ahead is never stored,
it is summed from the sets and sessions inside the window whenever anyone
looks - the same reason a league's standings are not stored
(app/core/leagues.py) and a raid boss's HP is derived from its hits
(app/core/raids.py). A stored score can drift out of step with the sets behind
it; a summed one cannot.

The one number that IS stored is `rival_target`, because the opponent may be
synthetic. It is generated once, at creation, from the CHALLENGER'S OWN
history - never from another person's data - so the rival is a pace to beat
rather than a fake account, and so that pace does not wander between reads.

Resolution is lazy. There is no cron in MetalArm: a duel whose window has
closed is judged the first time somebody asks about it, which is also the
moment the winner's points and the feed entry are written.
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
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import Timestamps, UUIDPrimaryKey
from app.models.workout_enums import check_in


class DuelMetric(str, enum.Enum):
    """What the two of you are measured on over the window."""

    VOLUME = "volume"      # kilograms lifted in working sets
    SETS = "sets"          # working sets logged
    SESSIONS = "sessions"  # workouts finished


class DuelStatus(str, enum.Enum):
    PENDING = "pending"      # challenged, not yet accepted
    ACTIVE = "active"        # accepted (or synthetic), window running
    COMPLETED = "completed"  # window closed and judged
    DECLINED = "declined"    # turned down, or withdrawn before acceptance


class ActivityType(str, enum.Enum):
    """What happened. One row per thing worth telling a party about."""

    PR_ACHIEVED = "pr_achieved"
    RANK_UP = "rank_up"
    SESSION_COMPLETED = "session_completed"
    DUEL_WON = "duel_won"
    QUEST_COMPLETED = "quest_completed"


class Duel(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "duels"

    challenger_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # NULL exactly when the opponent is synthetic - the CHECK below ties the
    # two together so a duel can never be half-rival, half-person.
    opponent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    is_ai_opponent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    metric: Mapped[str] = mapped_column(String(16), nullable=False)
    window_start: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    # NULL after resolution means a draw, which is why it cannot be inferred
    # from status alone.
    winner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # The synthetic opponent's final score, fixed at creation. NULL for a duel
    # between two people.
    rival_target: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    __table_args__ = (
        CheckConstraint(check_in("metric", DuelMetric), name="ck_duels_metric"),
        CheckConstraint(check_in("status", DuelStatus), name="ck_duels_status"),
        CheckConstraint("window_end > window_start", name="ck_duels_window"),
        # A synthetic opponent has no user row, and a real one is not synthetic.
        CheckConstraint(
            "(is_ai_opponent AND opponent_id IS NULL AND rival_target IS NOT NULL)"
            " OR (NOT is_ai_opponent AND opponent_id IS NOT NULL AND rival_target IS NULL)",
            name="ck_duels_opponent",
        ),
        CheckConstraint(
            "challenger_id <> opponent_id OR opponent_id IS NULL",
            name="ck_duels_not_self",
        ),
        # Judged means judged: a completed duel always says when.
        CheckConstraint(
            "(status = 'completed') = (resolved_at IS NOT NULL)",
            name="ck_duels_resolved",
        ),
        Index("ix_duels_challenger", "challenger_id", "status"),
        Index("ix_duels_opponent", "opponent_id", "status"),
    )


class ActivityEvent(UUIDPrimaryKey, Base):
    """One thing that happened, fanned out for a party to read.

    A read model, not a source of truth: every row points back at the record
    that caused it (a PersonalRecord, a WorkoutSession, a Duel...), and could
    be rebuilt from those. `party_id` is copied in at write time rather than
    joined at read time, because a member who later leaves should not retroact-
    ively vanish from the party's history - nor keep appearing in it.
    """

    __tablename__ = "activity_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    party_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("parties.id", ondelete="CASCADE"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    # What it happened to. Nullable because a rank-up is not a row anywhere.
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    # Rendered by the client; stored so a feed page needs no further lookups.
    headline: Mapped[str] = mapped_column(String(140), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    __table_args__ = (
        CheckConstraint(check_in("event_type", ActivityType), name="ck_activity_type"),
        # Writing the same event twice - a retried finish, a replayed PR - must
        # not double it in the feed. party_id is part of the key because ONE
        # event legitimately becomes several rows, one per party plus a
        # personal copy; NULLS NOT DISTINCT is what stops the personal copy
        # (party_id NULL) being written twice, since Postgres would otherwise
        # treat every NULL as a different value and dedupe nothing.
        UniqueConstraint(
            "user_id",
            "event_type",
            "source_id",
            "party_id",
            name="uq_activity_once",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_activity_party_time", "party_id", "created_at"),
        Index("ix_activity_user_time", "user_id", "created_at"),
    )
