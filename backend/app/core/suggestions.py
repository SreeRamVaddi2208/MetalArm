"""Which routine to do next: the one longest left alone, nudged toward the
user's training path. Pure - the route loads the routines and their last-done
dates."""

from __future__ import annotations

import dataclasses
import datetime as dt
import uuid

from app.core import workout_rules as rules


@dataclasses.dataclass(frozen=True)
class Candidate:
    routine_id: uuid.UUID
    name: str
    last_performed_at: dt.datetime | None
    category: str | None


@dataclasses.dataclass(frozen=True)
class Ranked:
    candidate: Candidate
    days_since: int | None
    fits_path: bool
    score: float


def rank(candidates: list[Candidate], *, path: str, now: dt.datetime,
         limit: int = rules.SUGGEST_LIMIT) -> list[Ranked]:
    """Staler first. A routine for the user's path is treated as
    SUGGEST_CATEGORY_BONUS_DAYS staler; one never done as
    SUGGEST_NEVER_DONE_DAYS old. Ties go to the name, so the order is stable."""
    out = []
    for c in candidates:
        days = None if c.last_performed_at is None else max(0, (now - c.last_performed_at).days)
        fits = bool(path) and c.category == path
        score = (rules.SUGGEST_NEVER_DONE_DAYS if days is None else days) + (
            rules.SUGGEST_CATEGORY_BONUS_DAYS if fits else 0)
        out.append(Ranked(c, days, fits, float(score)))
    out.sort(key=lambda r: (-r.score, r.candidate.name.casefold()))
    return out[:limit]


def abbreviation(name: str) -> str:
    """Two letters for a routine tile: "Lower A" -> "Lo", "Push day" -> "Pu"."""
    letters = [c for c in name if c.isalnum()]
    if not letters:
        return "?"
    return (letters[0].upper() + (letters[1].lower() if len(letters) > 1 else ""))
