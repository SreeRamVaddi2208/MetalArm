"""Scoring the fair duel modes: each side against their OWN baseline.

A 100 kg bencher beats a 60 kg beginner on tonnage every week, and the
beginner quits. These modes measure what both can control - showing up,
improving, doing more than usual - so who you are matched with stops deciding
who wins.

Pure: baselines and the window's facts in, a score and its breakdown out. No
database (app/core/duels.py loads the facts), so every mode is tested at its
edges. Flagged sets (plausibility.py) never reach here - the loader drops them.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal

from app.core import workout_rules as rules
from app.core.personal_records import est_1rm

# Progress counts at most +10% per exercise: enough to reward a real gain,
# little enough that a beginner's first-month jumps, or a baseline sandbagged
# with a deliberately light week, cannot run away with it.
PROGRESS_CAP = Decimal("0.10")
# How far back a baseline looks, at the moment the duel starts.
BASELINE_DAYS = 28


@dataclasses.dataclass(frozen=True)
class WindowSet:
    session_id: uuid.UUID
    exercise_id: uuid.UUID
    weight_kg: Decimal
    reps: int | None


@dataclasses.dataclass(frozen=True)
class WindowSession:
    id: uuid.UUID
    # The user's local date it finished on.
    day: dt.date
    qualified: bool


@dataclasses.dataclass(frozen=True)
class Line:
    label: str
    value: float


@dataclasses.dataclass(frozen=True)
class Score:
    value: float
    # Breaks an exact tie on `value`; only consistency has one.
    tiebreak: float = 0.0
    breakdown: tuple[Line, ...] = ()


# ---------------------------------------------------------------------------
# Consistency: days trained
# ---------------------------------------------------------------------------


def consistency(sessions: Sequence[WindowSession], sets: Sequence[WindowSet]) -> Score:
    """One point per day with a qualifying session (one a day at most, however
    many sessions). Tiebreak: total working sets. Load never matters."""
    per_session = defaultdict(int)
    for s in sets:
        per_session[s.session_id] += 1
    days = sorted(
        {
            session.day
            for session in sessions
            if session.qualified and per_session[session.id] >= rules.SESSION_MIN_WORKING_SETS
        }
    )
    return Score(
        value=float(len(days)),
        tiebreak=float(len(sets)),
        breakdown=tuple(Line(day.strftime("%a %d %b"), 1.0) for day in days),
    )


# ---------------------------------------------------------------------------
# Progress: % e1RM gained over your own recent best
# ---------------------------------------------------------------------------


def best_e1rm(sets: Sequence[WindowSet]) -> dict[uuid.UUID, Decimal]:
    best: dict[uuid.UUID, Decimal] = {}
    for s in sets:
        estimate = est_1rm(s.weight_kg, s.reps) if s.reps else None
        if estimate is not None and estimate > best.get(s.exercise_id, Decimal(0)):
            best[s.exercise_id] = estimate
    return best


def progress(
    baselines: Mapping[uuid.UUID, Decimal],
    sets: Sequence[WindowSet],
    names: Mapping[uuid.UUID, str] | None = None,
) -> Score:
    """Sum, over exercises with a baseline, of the % gain in best e1RM - each
    capped at PROGRESS_CAP, and never below zero (an off day on one lift does
    not erase a gain on another). An exercise with no baseline cannot score:
    there is nothing to have improved on."""
    names = names or {}
    now = best_e1rm(sets)
    total = Decimal(0)
    lines: list[Line] = []
    for exercise_id, base in sorted(baselines.items(), key=lambda kv: names.get(kv[0], "")):
        if base <= 0 or exercise_id not in now:
            continue
        gain = min(PROGRESS_CAP, max(Decimal(0), (now[exercise_id] - base) / base))
        if gain > 0:
            total += gain
            lines.append(Line(names.get(exercise_id, "Exercise"), round(float(gain * 100), 1)))
    return Score(value=round(float(total * 100), 1), breakdown=tuple(lines))


# ---------------------------------------------------------------------------
# Relative volume: this window vs your own average
# ---------------------------------------------------------------------------


def relative_volume(avg_weekly_kg: Decimal, sets: Sequence[WindowSet], window_days: float) -> Score:
    """Working volume in the window as a % of the user's own average for a
    window that long. 100 means a normal week; a light lifter training more
    than usual beats a heavy one coasting."""
    volume = sum((s.weight_kg * s.reps for s in sets if s.reps), Decimal(0))
    expected = avg_weekly_kg * Decimal(str(window_days)) / Decimal(7)
    if expected <= 0:
        return Score(0.0)
    pct = round(float(volume / expected * 100), 1)
    return Score(
        value=pct,
        breakdown=(Line("Volume this duel (kg)", round(float(volume), 1)),
                   Line("Your usual for this long (kg)", round(float(expected), 1))),
    )


def baseline_avg_weekly(volume_kg: Decimal, days: int = BASELINE_DAYS) -> Decimal:
    return volume_kg / Decimal(days) * Decimal(7)


def winner(a: Score, b: Score) -> int:
    """1 if `a` wins, -1 if `b` does, 0 for a draw."""
    if (a.value, a.tiebreak) > (b.value, b.tiebreak):
        return 1
    if (a.value, a.tiebreak) < (b.value, b.tiebreak):
        return -1
    return 0
