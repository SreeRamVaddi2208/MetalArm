"""Weekly party raids: one boss per party per ISO week, and the hits members
land on it by finishing workouts. The rules live in app/core/raids.py."""

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import Timestamps, UUIDPrimaryKey


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class RaidBoss(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "raid_bosses"

    party_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("parties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # ISO week in UTC, e.g. "2026-W37": one boss, one clock for the whole party.
    week_key: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    # Fixed when the week's boss first appears, from the party's size then.
    max_hp: Mapped[int] = mapped_column(Integer, nullable=False)
    # Total damage landed. Healing on idle days is derived on read, not stored.
    damage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    defeated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("party_id", "week_key", name="uq_raid_bosses_party_week"),
        CheckConstraint("max_hp > 0", name="ck_raid_bosses_max_hp"),
        CheckConstraint("damage >= 0", name="ck_raid_bosses_damage"),
    )


class RaidHit(UUIDPrimaryKey, Base):
    __tablename__ = "raid_hits"

    boss_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("raid_bosses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workout_sessions.id", ondelete="CASCADE"), nullable=False
    )
    damage: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        # A workout hits a boss once, however many times its finish is retried.
        UniqueConstraint("boss_id", "session_id", name="uq_raid_hits_boss_session"),
        CheckConstraint("damage > 0", name="ck_raid_hits_damage"),
    )
