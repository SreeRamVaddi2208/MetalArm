"""Programs (a plan of routines) and favourites.

A program is a named, ordered set of routines - "Upper/Lower, 4 days" holds
four. A curated program (owner NULL) is shipped with the app and offered in
Explore by training category; a user's own is theirs alone unless public.
"""

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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import Timestamps, UUIDPrimaryKey


class Program(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "programs"

    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # users.character_class values, or NULL for any path.
    training_category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    level: Mapped[str | None] = mapped_column(String(12), nullable=True)
    weeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sessions_per_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    cover_color: Mapped[str | None] = mapped_column(String(9), nullable=True)

    __table_args__ = (
        CheckConstraint("length(name) >= 1", name="ck_programs_name"),
        CheckConstraint(
            "training_category IS NULL OR training_category IN ('powerlifter', 'bodybuilder', 'athlete')",
            name="ck_programs_category",
        ),
        CheckConstraint(
            "level IS NULL OR level IN ('beginner', 'intermediate', 'advanced')",
            name="ck_programs_level",
        ),
        CheckConstraint("weeks IS NULL OR (weeks >= 1 AND weeks <= 52)", name="ck_programs_weeks"),
        CheckConstraint(
            "sessions_per_week IS NULL OR (sessions_per_week >= 1 AND sessions_per_week <= 14)",
            name="ck_programs_sessions",
        ),
    )


class Favorite(UUIDPrimaryKey, Base):
    """A routine, exercise or program the user starred."""

    __tablename__ = "favorites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(10), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "target_type IN ('routine', 'exercise', 'program')", name="ck_favorites_type"
        ),
        UniqueConstraint("user_id", "target_type", "target_id", name="uq_favorites_once"),
        Index("ix_favorites_target", "target_type", "target_id"),
    )
