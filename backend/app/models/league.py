"""Weekly leagues: a user's place in one week's league (app/core/leagues.py).

One row per user per ISO week. The row says which division and which group of
that division they are in; the standings themselves are never stored - they are
the points ledger summed over the week, so a league can't drift out of step
with the wallet.
"""

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import Timestamps, UUIDPrimaryKey


class LeagueMembership(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "league_memberships"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # ISO week in UTC ("2026-W38"): one window for everyone on a board.
    week_key: Mapped[str] = mapped_column(String(16), nullable=False)
    # 0 is the bottom division; app/core/leagues.py names them.
    division: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # Which league of that division, since a division holds many groups.
    group_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # The position the PREVIOUS week ended on, kept so the client can say
    # "promoted" or "relegated" without re-judging a finished week.
    promoted_from: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "week_key", name="uq_league_memberships_user_week"),
        Index("ix_league_memberships_group", "week_key", "division", "group_no"),
        CheckConstraint("division >= 0", name="ck_league_memberships_division"),
        CheckConstraint("group_no >= 0", name="ck_league_memberships_group"),
    )
