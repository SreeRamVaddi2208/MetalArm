"""The social graph (overhaul phase 4): who follows whom, reactions to
workouts, and the notifications those (and the game) produce.

Friends are MUTUAL follows - they can duel and see followers-only workouts
both ways. A follow is one row; unfollowing deletes it (nothing else points
at it). Reactions are one per user per session per type; notifications are
read by setting read_at, never deleted by the app.
"""

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import UUIDPrimaryKey

REACTION_TYPES = ("spotted",)
NOTIFICATION_TYPES = ("follow", "reaction", "duel_challenge", "friend_pr", "quest_complete")


class Follow(Base):
    __tablename__ = "follows"

    follower_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    followee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("follower_id <> followee_id", name="ck_follows_not_self"),
        # "Who follows me" - the PK serves "whom do I follow".
        Index("ix_follows_followee", "followee_id", "follower_id"),
    )


class Reaction(UUIDPrimaryKey, Base):
    __tablename__ = "reactions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workout_sessions.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="spotted")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "session_id", "type", name="uq_reactions_once"),
        CheckConstraint("type IN ('spotted')", name="ck_reactions_type"),
        Index("ix_reactions_session", "session_id"),
    )


class Notification(UUIDPrimaryKey, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Who did it; NULL for the game's own (a quest completing).
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    # What it is about: 'session' / 'duel' / 'user' / 'quest', and its id.
    target_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    # A line of context the list shows ("Bench Press 100 kg x 5").
    detail: Mapped[str | None] = mapped_column(String(160), nullable=True)
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "type IN ('follow', 'reaction', 'duel_challenge', 'friend_pr', 'quest_complete')",
            name="ck_notifications_type"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
        # Deleting an account cascades through the notifications it caused.
        Index("ix_notifications_actor", "actor_user_id"),
        # The bell's unread count.
        Index("ix_notifications_unread", "user_id", postgresql_where=text("read_at IS NULL")),
    )
