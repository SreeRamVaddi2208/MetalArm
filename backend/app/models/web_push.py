"""Browsers subscribed to Web Push.

The Android half of what push_devices does for iOS, and a separate table
because the two are different shapes: an APNs token is a short opaque string,
while a Web Push subscription is a long endpoint URL belonging to whichever
push service the browser uses, plus the two keys the payload is encrypted
with. Forcing both into one row would mean half the columns null on every row.

Everything else follows push_devices deliberately, because the reasoning has
not changed: a subscription belongs to the sign-in session that created it, so
signing out stops the notifications; the endpoint is UNIQUE across users
because it identifies the browser install rather than the person; and deleting
the account cascades.
"""

import uuid

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import Timestamps, UUIDPrimaryKey


class WebPushSubscription(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "web_push_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("auth_sessions.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    # A push service URL. No standard caps its length and they are already
    # long, so Text rather than a guessed String(n).
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # The subscription's public key and auth secret, base64url as the browser
    # hands them over. Stored as given: the sender feeds them straight back.
    p256dh: Mapped[str] = mapped_column(String(200), nullable=False)
    auth: Mapped[str] = mapped_column(String(100), nullable=False)
