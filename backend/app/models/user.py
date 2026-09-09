"""User and progression models."""

import datetime as dt
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import Rank, pg_enum
from app.models.mixins import Timestamps, UUIDPrimaryKey


class User(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "users"

    # Stored as the user typed it, for display and correspondence.
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    # Lowercased/stripped copy carrying the UNIQUE constraint, so A@b.com and
    # a@b.com cannot both register. Chosen over CITEXT to avoid requiring a
    # Postgres extension. The application is responsible for keeping this in
    # sync - it is always written via the same helper that sets `email`.
    email_normalized: Mapped[str] = mapped_column(
        String(320), nullable=False, unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(50), nullable=False)
    # IANA zone name. Load-bearing: a "daily" quest resets at the USER's
    # midnight, not the server's, so period_key is computed in this zone.
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="UTC"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    progress: Mapped["LevelProgress"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (
        CheckConstraint("length(display_name) >= 1", name="ck_users_display_name"),
    )


class LevelProgress(Timestamps, Base):
    """One row per user. Progression state.

    total_xp is the SOURCE OF TRUTH; current_level and rank are cached
    derivations recomputed whenever XP changes.

    Storing cumulative XP rather than an authoritative (level, xp-into-level)
    pair means retuning the XP curve - explicitly left open in Section 11 -
    re-derives every user correctly instead of silently corrupting progress.
    The cached columns exist only so leaderboard queries don't recompute a
    curve per row. See app/core/leveling.py for the curve itself.
    """

    __tablename__ = "level_progress"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    total_xp: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    current_level: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    rank: Mapped[Rank] = mapped_column(
        pg_enum(Rank, "rank"),
        nullable=False,
        server_default=Rank.E.value,
    )
    points_balance: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    current_streak: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    longest_streak: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    # Stored as the user's LOCAL date, so streaks don't break across timezones.
    last_completed_on: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    user: Mapped["User"] = relationship(back_populates="progress")

    __table_args__ = (
        # Backstop against concurrent double-spend in the rewards shop; the
        # redemption path debits in the same transaction as the insert.
        CheckConstraint("points_balance >= 0", name="ck_progress_points_non_negative"),
        CheckConstraint("total_xp >= 0", name="ck_progress_xp_non_negative"),
        CheckConstraint("current_level >= 1", name="ck_progress_level_min"),
    )
