"""Personal-record detection.

Pure: no database and no clock. The route layer loads a user's current bests,
asks this module what a new set beats, and persists the answer. Keeping the
rules here means they are testable in microseconds and cannot drift between
the "log a set" path and the "rebuild after a delete" path - both call the same
detect()/absorb() pair.

Record types
------------
max_weight          Heaviest working set, any reps. Weighted sets only.
max_reps_at_weight  A set is a rep PR when NO earlier working set was both at
                    least as heavy and at least as many reps. So 100x6 after a
                    100x5 is a PR, and so is 60x12 if nothing at 60kg or more
                    ever reached 12 reps. The set of undominated (weight, reps)
                    points is the "frontier" below.
est_1rm             Epley estimate, w * (1 + reps/30), only up to
                    EST_1RM_MAX_REPS reps, where the formula stays meaningful.
max_volume          Best single-session volume (sum of weight x reps over
                    working sets) for the exercise. Judged when the session
                    FINISHES: judged per set, it would re-fire on every set of
                    a good session.

Warm-up sets and sets without reps (cardio, timed holds) never set a record.

A "baseline" is the first time a record exists at all for an exercise. It is
recorded - the UI can say "first log" - but is not a PR worth a bonus: with
custom exercises, a baseline bonus would pay for creating exercises.
"""

import dataclasses
from collections.abc import Hashable, Iterable, Sequence
from decimal import ROUND_HALF_UP, Decimal

from app.core import workout_rules as rules
from app.models.workout_enums import RecordType

_CENTS = Decimal("0.01")
_ZERO = Decimal("0")


def quantize(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def est_1rm(weight_kg: Decimal, reps: int) -> Decimal | None:
    """Epley one-rep-max estimate, or None where it would not be meaningful."""
    if weight_kg <= 0 or reps < 1 or reps > rules.EST_1RM_MAX_REPS:
        return None
    if reps == 1:
        # Epley gives w * 31/30 for a single; a single IS the 1RM.
        return quantize(weight_kg)
    return quantize(weight_kg * (Decimal(30) + reps) / Decimal(30))


@dataclasses.dataclass(frozen=True)
class LiftSet:
    weight_kg: Decimal
    reps: int | None
    is_warmup: bool = False

    @property
    def counts(self) -> bool:
        """Whether this set can set or be judged against a record."""
        return not self.is_warmup and self.reps is not None and self.reps >= 1

    @property
    def volume(self) -> Decimal:
        if not self.counts:
            return _ZERO
        return self.weight_kg * self.reps  # type: ignore[operator]


@dataclasses.dataclass(frozen=True)
class PrEvent:
    record_type: RecordType
    value: Decimal
    # The weight the record was set at. For a rep PR this is the qualifier
    # ("12 reps at 60 kg"); for volume it is None.
    weight_kg: Decimal | None
    # The record this beat, or None if there was nothing comparable before.
    previous: Decimal | None
    is_baseline: bool


@dataclasses.dataclass(frozen=True)
class ExerciseBests:
    """One user's current records on one exercise."""

    max_weight: Decimal | None = None
    est_1rm: Decimal | None = None
    max_volume: Decimal | None = None
    # Undominated (weight, reps) points, heaviest first.
    frontier: tuple[tuple[Decimal, int], ...] = ()

    @property
    def has_history(self) -> bool:
        # Any counting set lands on (or once landed on) the frontier, so an
        # empty frontier means nothing has ever been logged.
        return bool(self.frontier)


def _best_reps_at_or_above(
    frontier: Sequence[tuple[Decimal, int]], weight: Decimal
) -> int | None:
    return max((reps for w, reps in frontier if w >= weight), default=None)


def _prune(points: Iterable[tuple[Decimal, int]]) -> tuple[tuple[Decimal, int], ...]:
    """Reduce (weight, reps) points to the undominated frontier."""
    frontier: list[tuple[Decimal, int]] = []
    # Heaviest first; for equal weight, most reps first, so the first point
    # seen at each weight is the one that survives.
    for weight, reps in sorted(points, key=lambda p: (-p[0], -p[1])):
        best_heavier = max((r for _, r in frontier), default=None)
        if best_heavier is None or reps > best_heavier:
            frontier.append((weight, reps))
    return tuple(frontier)


def detect(bests: ExerciseBests, lift: LiftSet) -> list[PrEvent]:
    """The per-set records this set breaks, judged against `bests`."""
    if not lift.counts:
        return []

    baseline = not bests.has_history
    weight, reps = lift.weight_kg, lift.reps
    assert reps is not None  # guaranteed by lift.counts
    events: list[PrEvent] = []

    if weight > 0 and (bests.max_weight is None or weight > bests.max_weight):
        events.append(
            PrEvent(
                RecordType.MAX_WEIGHT,
                quantize(weight),
                quantize(weight),
                bests.max_weight,
                baseline,
            )
        )

    previous_reps = _best_reps_at_or_above(bests.frontier, weight)
    if previous_reps is None or reps > previous_reps:
        events.append(
            PrEvent(
                RecordType.MAX_REPS_AT_WEIGHT,
                Decimal(reps),
                quantize(weight),
                Decimal(previous_reps) if previous_reps is not None else None,
                baseline,
            )
        )

    estimate = est_1rm(weight, reps)
    if estimate is not None and (bests.est_1rm is None or estimate > bests.est_1rm):
        events.append(
            PrEvent(
                RecordType.EST_1RM, estimate, quantize(weight), bests.est_1rm, baseline
            )
        )

    return events


def absorb(bests: ExerciseBests, lift: LiftSet) -> ExerciseBests:
    """`bests` after this set has been logged."""
    if not lift.counts:
        return bests
    weight, reps = lift.weight_kg, lift.reps
    assert reps is not None

    max_weight = bests.max_weight
    if weight > 0:
        max_weight = weight if max_weight is None else max(max_weight, weight)

    estimate = est_1rm(weight, reps)
    best_estimate = bests.est_1rm
    if estimate is not None:
        best_estimate = estimate if best_estimate is None else max(best_estimate, estimate)

    return dataclasses.replace(
        bests,
        max_weight=max_weight,
        est_1rm=best_estimate,
        frontier=_prune([*bests.frontier, (weight, reps)]),
    )


def session_volume(lifts: Iterable[LiftSet]) -> Decimal:
    return sum((lift.volume for lift in lifts), _ZERO)


def detect_volume(bests: ExerciseBests, volume: Decimal) -> PrEvent | None:
    """A session-volume record, judged at finish against earlier sessions."""
    if volume <= 0:
        return None
    if bests.max_volume is not None and volume <= bests.max_volume:
        return None
    return PrEvent(
        RecordType.MAX_VOLUME,
        quantize(volume),
        None,
        bests.max_volume,
        is_baseline=bests.max_volume is None,
    )


def absorb_volume(bests: ExerciseBests, volume: Decimal) -> ExerciseBests:
    if volume <= 0:
        return bests
    current = bests.max_volume
    return dataclasses.replace(
        bests, max_volume=volume if current is None else max(current, volume)
    )


def bests_from_records(
    rows: Iterable[tuple[RecordType | str, Decimal, Decimal | None]],
) -> ExerciseBests:
    """Rebuild current bests from stored personal_records rows.

    Correct because every set that is on the frontier today was, when logged,
    undominated by anything earlier - so it was stored as a rep-PR row. Pruning
    those rows therefore reproduces the frontier exactly, without reading every
    set the user ever logged.
    """
    max_weight = est = volume = None
    rep_points: list[tuple[Decimal, int]] = []

    for record_type, value, weight in rows:
        kind = RecordType(record_type)
        if kind is RecordType.MAX_WEIGHT:
            max_weight = value if max_weight is None else max(max_weight, value)
        elif kind is RecordType.EST_1RM:
            est = value if est is None else max(est, value)
        elif kind is RecordType.MAX_VOLUME:
            volume = value if volume is None else max(volume, value)
        elif kind is RecordType.MAX_REPS_AT_WEIGHT and weight is not None:
            rep_points.append((weight, int(value)))

    return ExerciseBests(
        max_weight=max_weight,
        est_1rm=est,
        max_volume=volume,
        frontier=_prune(rep_points),
    )


@dataclasses.dataclass(frozen=True)
class ReplaySession:
    key: Hashable
    completed: bool
    # (set key, lift) in the order they were logged.
    sets: Sequence[tuple[Hashable, LiftSet]]


@dataclasses.dataclass(frozen=True)
class ReplayResult:
    set_events: list[tuple[Hashable, PrEvent]]
    volume_events: list[tuple[Hashable, PrEvent]]


def replay(sessions: Sequence[ReplaySession]) -> ReplayResult:
    """Recompute every record for one exercise from its full set history.

    Used after a set is deleted or edited, or a session is abandoned: in those
    cases the stored rows describe a history that no longer exists, and an
    incremental fix-up would miss sets that only become records once a better
    set is gone. `sessions` must be in chronological order and exclude
    abandoned sessions.
    """
    bests = ExerciseBests()
    set_events: list[tuple[Hashable, PrEvent]] = []
    volume_events: list[tuple[Hashable, PrEvent]] = []

    for session in sessions:
        for key, lift in session.sets:
            for event in detect(bests, lift):
                set_events.append((key, event))
            bests = absorb(bests, lift)

        if session.completed:
            volume = session_volume(lift for _, lift in session.sets)
            event = detect_volume(bests, volume)
            if event is not None:
                volume_events.append((session.key, event))
                bests = absorb_volume(bests, volume)

    return ReplayResult(set_events=set_events, volume_events=volume_events)
