"""The marketing site's waitlist.

Deliberately the smallest table that can hold an email honestly: no account,
no password, no profile. Someone who joins the waitlist has not signed up for
MetalArm - conflating the two would mean a half-account that can never log in.

Email is stored lower-cased and UNIQUE, so joining twice is idempotent rather
than a way to find out whether an address is already on the list.
"""

import datetime as dt

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import UUIDPrimaryKey


class WaitlistEntry(UUIDPrimaryKey, Base):
    __tablename__ = "waitlist_entries"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    # Which section of the page the person was looking at when they joined.
    # Free text, capped: useful for knowing what actually sells the product,
    # and harmless if it is ever junk.
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
