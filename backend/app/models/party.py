"""Parties/guilds: membership, shared quests, and shared-quest completions."""

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
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import RECURRENCE_VALUES, PartyRole, pg_enum
from app.models.mixins import Timestamps, UUIDPrimaryKey
from app.models.quest import MAX_XP_REWARD

_RECURRENCE_CHECK = ", ".join(f"'{v}'" for v in RECURRENCE_VALUES)

# Settled with the user on 2026-09-10: parties cap at 10 members, are freely
# created and dissolved, and a leaving owner hands off rather than orphaning
# the party. Stored per-party so a future tier could raise it without a
# migration; the column CHECK still bounds it at 100.
DEFAULT_MAX_MEMBERS = 10


class Party(UUIDPrimaryKey, Timestamps, Base):
    """A party/guild. Freely created and dissolved.

    Dissolving sets is_active = false rather than deleting, so members keep
    their completion history and earned XP.
    """

    __tablename__ = "parties"

    name: Mapped[str] = mapped_column(String(60), nullable=False)
    # The join key, so it is indexed and unique. 8-char base32 excluding
    # 0/O/1/I to stay unambiguous when read aloud or retyped.
    invite_code: Mapped[str] = mapped_column(
        String(10), nullable=False, unique=True, index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Per-party rather than a hardcoded constant, so the cap is tunable
    # without a migration.
    max_members: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=str(DEFAULT_MAX_MEMBERS)
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    memberships: Mapped[list["PartyMembership"]] = relationship(
        back_populates="party", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "max_members >= 1 AND max_members <= 100", name="ck_parties_max_members"
        ),
    )


class PartyMembership(Base):
    """Join table. A user MAY belong to multiple parties (confirmed decision).

    If that is ever capped at one, it becomes a partial unique index on
    user_id WHERE the party is active - cheap now, painful once populated.
    """

    __tablename__ = "party_memberships"

    party_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("parties.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[PartyRole] = mapped_column(
        pg_enum(PartyRole, "party_role"),
        nullable=False,
        server_default=PartyRole.MEMBER.value,
    )
    joined_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    party: Mapped["Party"] = relationship(back_populates="memberships")

    __table_args__ = (
        # "Which parties am I in?" - the common lookup from the user side.
        Index("ix_party_memberships_user", "user_id"),
    )


class PartyQuest(UUIDPrimaryKey, Timestamps, Base):
    """A shared quest visible to every member of the party."""

    __tablename__ = "party_quests"

    party_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        # The quest outlives its author leaving the party.
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    xp_reward: Mapped[int] = mapped_column(Integer, nullable=False)
    points_reward: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    recurrence: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="none"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    due_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    completions: Mapped[list["PartyQuestCompletion"]] = relationship(
        back_populates="party_quest", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            f"recurrence IN ({_RECURRENCE_CHECK})", name="ck_party_quests_recurrence"
        ),
        CheckConstraint(
            f"xp_reward >= 0 AND xp_reward <= {MAX_XP_REWARD}",
            name="ck_party_quests_xp_reward_range",
        ),
        CheckConstraint(
            "points_reward >= 0", name="ck_party_quests_points_non_negative"
        ),
    )


class PartyQuestCompletion(UUIDPrimaryKey, Base):
    """Each member may complete a shared quest once per period.

    Contributes to BOTH the member's personal total_xp and the party total.
    Party XP is derived (SUM over these rows); Redis holds the sorted set for
    ranking in Sprint 5, with Postgres remaining the source of truth - so a
    Redis flush costs a rebuild, never data.
    """

    __tablename__ = "party_quest_completions"

    party_quest_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("party_quests.id", ondelete="CASCADE"),
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
    xp_awarded: Mapped[int] = mapped_column(Integer, nullable=False)
    points_awarded: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    party_quest: Mapped["PartyQuest"] = relationship(back_populates="completions")

    __table_args__ = (
        UniqueConstraint(
            "party_quest_id",
            "user_id",
            "period_key",
            name="uq_party_quest_completion_period",
        ),
        CheckConstraint("xp_awarded >= 0", name="ck_pq_completion_xp_non_negative"),
        CheckConstraint(
            "points_awarded >= 0", name="ck_pq_completion_points_non_negative"
        ),
    )
