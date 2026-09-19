"""Devices registered for server push (APNs)."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import Timestamps, UUIDPrimaryKey


class PushDevice(UUIDPrimaryKey, Timestamps, Base):
    """One APNs device token, and whose it is.

    Tied to the sign-in session that registered it, not just the user: a phone
    that signs out must stop receiving that account's notifications, so signing
    out of a session deletes its devices (and signing out everywhere deletes
    them all). Deleting the account cascades.

    The token is UNIQUE across users. It identifies the app install, not the
    person, so when a second account signs in on the same phone the row moves
    to that account rather than notifying both.
    """

    __tablename__ = "push_devices"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Null only for a token from before device sessions existed.
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("auth_sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Lowercase hex, as the app reads it from the token bytes. Apple does not
    # promise a length (32 bytes today), so this leaves room.
    token: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    # Which APNs gateway the token belongs to: a sandbox token (a debug build)
    # is rejected by the production gateway, and the reverse.
    environment: Mapped[str] = mapped_column(String(10), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "environment IN ('sandbox', 'production')", name="ck_push_devices_environment"
        ),
    )
