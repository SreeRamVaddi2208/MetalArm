"""What to try next on an exercise: double progression, plateaus, deloads.

The rule is the one most lifters actually use. Work a rep range
(`rules.HINT_REP_RANGE`): while the top set is below the top of the range, add
a rep; once it reaches the top, add the smallest loadable jump and drop back to
the bottom of the range. Two things override it:

- **Plateau.** No new best estimated 1RM for `rules.PLATEAU_SESSIONS` sessions
  means adding another rep is not the answer, so the hint says to back off
  about 10% and build up again.
- **Deload.** An unbroken climb running `rules.DELOAD_AFTER_WEEKS` weeks earns
  a lighter week. Because it needs every session to hold or beat the one
  before, it fires rarely - which is the point.

Pure: the caller supplies the top set of each recent completed session
(`workout_store.recent_top_sets`, newest first) and gets a hint or None. A
never-performed exercise gets None - the card already says it sets a baseline.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Sequence
from decimal import ROUND_FLOOR, Decimal

from app.core import personal_records as prs
from app.core import workout_rules as rules

# Equipment loaded in plate-sized jumps; everything else (dumbbells, cables,
# most machines) moves in smaller ones.
_PLATE_EQUIPMENT = frozenset({"barbell", "trap_bar", "ez_bar", "smith_machine"})
_LB = Decimal(str(rules.LB_TO_KG))
_TENTH = Decimal("0.1")


@dataclasses.dataclass(frozen=True)
class TopSet:
    """The heaviest working set of one completed session."""

    performed_at: dt.datetime
    weight_kg: Decimal
    reps: int

    @property
    def est_1rm(self) -> Decimal:
        """0 where Epley isn't meaningful, so comparisons stay total."""
        return prs.est_1rm(self.weight_kg, self.reps) or Decimal(0)


@dataclasses.dataclass(frozen=True)
class Hint:
    # progress | plateau | deload
    kind: str
    text: str
    target_weight_kg: Decimal | None
    target_reps: int | None


def step_for(equipment: str) -> Decimal:
    return (
        Decimal(str(rules.WEIGHT_STEP_KG))
        if equipment in _PLATE_EQUIPMENT
        else Decimal(str(rules.SMALL_WEIGHT_STEP_KG))
    )


def _floor_to_step(weight_kg: Decimal, step: Decimal) -> Decimal:
    """Down to something actually loadable, and never below one step."""
    steps = (weight_kg / step).to_integral_value(rounding=ROUND_FLOOR)
    return max(step, steps * step)


def _fmt(weight_kg: Decimal, unit: str) -> str:
    value = (weight_kg / _LB) if unit == "lb" else weight_kg
    value = value.quantize(_TENTH)
    whole = value.to_integral_value()
    return f"{whole if value == whole else value} {unit}"


def _climbing(oldest_first: Sequence[TopSet]) -> bool:
    """Every session held or beat the one before it, and at least one gained."""
    gained = False
    for earlier, later in zip(oldest_first, oldest_first[1:]):
        if later.est_1rm < earlier.est_1rm:
            return False
        if later.est_1rm > earlier.est_1rm:
            gained = True
    return gained


def suggest(
    top_sets: Sequence[TopSet], *, equipment: str, unit: str = "kg"
) -> Hint | None:
    """`top_sets` newest first, as `workout_store.recent_top_sets` returns."""
    if not top_sets:
        return None

    last = top_sets[0]
    step = step_for(equipment)
    low, high = rules.HINT_REP_RANGE

    recent = top_sets[: rules.PLATEAU_SESSIONS]
    earlier = top_sets[rules.PLATEAU_SESSIONS :]
    if earlier:
        best_before = max(t.est_1rm for t in earlier)
        if all(t.est_1rm <= best_before for t in recent):
            back_off = _floor_to_step(last.weight_kg * Decimal("0.9"), step)
            return Hint(
                kind="plateau",
                text=(
                    f"No new best in {len(recent)} sessions. "
                    f"Back off to {_fmt(back_off, unit)} x {high} and build up again."
                ),
                target_weight_kg=back_off,
                target_reps=high,
            )

    span = last.performed_at - top_sets[-1].performed_at
    if (
        len(top_sets) >= 3
        and span >= dt.timedelta(weeks=rules.DELOAD_AFTER_WEEKS)
        and _climbing(list(reversed(top_sets)))
    ):
        lighter = _floor_to_step(last.weight_kg * Decimal("0.8"), step)
        return Hint(
            kind="deload",
            text=(
                f"{rules.DELOAD_AFTER_WEEKS} weeks of climbing. Take a lighter week "
                f"around {_fmt(lighter, unit)}, then push again."
            ),
            target_weight_kg=lighter,
            target_reps=high,
        )

    if last.reps >= high:
        target = last.weight_kg + step
        return Hint(
            kind="progress",
            text=f"Try {_fmt(target, unit)} x {low}",
            target_weight_kg=target,
            target_reps=low,
        )
    return Hint(
        kind="progress",
        text=f"Try {_fmt(last.weight_kg, unit)} x {last.reps + 1}",
        target_weight_kg=last.weight_kg,
        target_reps=last.reps + 1,
    )
