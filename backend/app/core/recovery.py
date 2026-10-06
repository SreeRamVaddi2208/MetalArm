"""Per-muscle recovery: an ESTIMATE from training volume (rules,
"Analytics"). Never present it as physiology - the UI says so.

Pure: working sets in, percentages out. For each muscle group,

    fatigue  = sum over working sets in the window of
               load (1.0 primary / 0.5 secondary) x 0.5 ** (age_h / half_life)
    recovery = 100 - min(100, fatigue / threshold x 100)

with half-life and threshold by the muscle's size class. Overall recovery is
the average over muscles trained in the last RECOVERY_OVERALL_DAYS, weighted
by each one's undecayed load in that time; 100 when nothing was trained.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Iterable, Mapping, Sequence

from app.core import workout_rules as rules
from app.core.analytics import PRIMARY_WEIGHT, SECONDARY_WEIGHT

NOT_A_PLACE = ("cardio", "full_body")


@dataclasses.dataclass(frozen=True)
class WorkingSet:
    at: dt.datetime
    primary: Sequence[str]
    secondary: Sequence[str]


@dataclasses.dataclass(frozen=True)
class Recovery:
    overall: int                    # 0-100
    muscles: dict[str, int]         # code -> 0-100, every muscle that has a size class


def _loads(s: WorkingSet) -> Iterable[tuple[str, float]]:
    for code in s.primary:
        yield code, PRIMARY_WEIGHT
    for code in s.secondary:
        if code not in s.primary:
            yield code, SECONDARY_WEIGHT


def recovery(sets: Iterable[WorkingSet], now: dt.datetime, size_class: Mapping[str, str]) -> Recovery:
    window = dt.timedelta(hours=rules.RECOVERY_WINDOW_HOURS)
    recent = dt.timedelta(days=rules.RECOVERY_OVERALL_DAYS)
    fatigue: dict[str, float] = {}
    trained: dict[str, float] = {}
    for s in sets:
        age = now - s.at
        if age < dt.timedelta(0):
            age = dt.timedelta(0)
        for code, load in _loads(s):
            if code in NOT_A_PLACE or code not in size_class:
                continue
            if age <= recent:
                trained[code] = trained.get(code, 0.0) + load
            if age <= window:
                half_life = rules.RECOVERY_HALF_LIFE_HOURS[size_class[code]]
                hours = age.total_seconds() / 3600
                fatigue[code] = fatigue.get(code, 0.0) + load * 0.5 ** (hours / half_life)

    def pct(code: str) -> float:
        threshold = rules.RECOVERY_THRESHOLD[size_class[code]]
        return 100.0 - min(100.0, fatigue.get(code, 0.0) / threshold * 100.0)

    muscles = {code: round(pct(code)) for code in sorted(size_class) if code not in NOT_A_PLACE}
    weight = sum(trained.values())
    overall = round(sum(pct(c) * w for c, w in trained.items()) / weight) if weight else 100
    return Recovery(overall=overall, muscles=muscles)
