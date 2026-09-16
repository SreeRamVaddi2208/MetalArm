"""Weekly league payloads (app/core/leagues.py)."""

import datetime as dt
import uuid

from pydantic import BaseModel


class LeagueEntryOut(BaseModel):
    position: int
    user_id: uuid.UUID
    display_name: str
    points: int
    level: int
    rank: str
    is_me: bool


class LeagueOut(BaseModel):
    """This week's league for the caller. Standings come from the points
    ledger, so they always agree with the wallet."""

    week_key: str
    division: int
    division_label: str
    group_no: int
    ends_at: dt.datetime
    # Where the user finished last week, when that is what placed them here.
    promoted_from: int | None
    # Positions at or above this promote; positions above `demote_cutoff` go down.
    promote_cutoff: int
    demote_cutoff: int
    entries: list[LeagueEntryOut]
