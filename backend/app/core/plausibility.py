"""Plausibility checks on a logged set - for fairness, not for policing.

Once a result can beat someone else's, a typo or a fib costs a friend a duel.
This flags sets that are very unlikely to be real so they can be kept out of
duels and leaderboards. Nothing more: a flagged set is still logged, still in
history, still earns its owner's points and records, and the UI only says it
"won't count toward competitions". It never says why it might be wrong.

Pure: the caller loads the recent best and passes it in.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from app.core import workout_rules as rules
from app.core.personal_records import est_1rm


@dataclasses.dataclass(frozen=True)
class Verdict:
    flagged: bool
    reason: str | None = None


CLEAR = Verdict(False)


def check(
    *,
    weight_kg: Decimal,
    reps: int | None,
    is_warmup: bool,
    equipment: str,
    recent_best_e1rm: Decimal | None,
) -> Verdict:
    """Whether one set is too unlikely to count toward competitions.

    `recent_best_e1rm` is the best estimated 1RM on the same exercise over the
    last FLAG_E1RM_LOOKBACK_DAYS days, excluding this set; None when there is
    none (a first session cannot jump from anything).
    """
    if is_warmup or reps is None:
        return CLEAR
    if weight_kg > 0 and reps > rules.FLAG_MAX_WEIGHTED_REPS:
        return Verdict(True, "reps_implausible")
    ceiling = rules.FLAG_CEILING_KG.get(equipment)
    if ceiling is not None and weight_kg > ceiling:
        return Verdict(True, "over_ceiling")
    if recent_best_e1rm:
        estimate = est_1rm(weight_kg, reps)
        if estimate is not None and estimate > recent_best_e1rm * Decimal(
            str(1 + rules.FLAG_E1RM_JUMP)
        ):
            return Verdict(True, "e1rm_jump")
    return CLEAR
