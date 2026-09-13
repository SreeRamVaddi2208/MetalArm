"""Signed-in device sessions."""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import Timestamps, UUIDPrimaryKey


class AuthSession(UUIDPrimaryKey, Timestamps, Base):
    """One signed-in device.

    Every login starts a session, and the access and refresh tokens it issues
    carry the session id (`sid`). Signing out of one device revokes only its
    session; signing out everywhere bumps users.token_version instead. Deleting
    the account deletes its sessions.
    """

    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Set when the device signs out. Kept rather than deleted, so a token that
    # names a revoked session is told apart from a forged one in logs.
    revoked_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
