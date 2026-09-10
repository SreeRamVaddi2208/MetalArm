"""PR detection: Epley, the rep-dominance rule, baselines, and replay.

Pure logic, no database. The replay tests matter most: after a delete, the
stored records must match what logging the surviving sets from scratch would
have produced - including sets that only become records once a better set is
gone.
"""

from decimal import Decimal

import pytest

from app.core import personal_records as prs
from app.core.personal_records import ExerciseBests, LiftSet, ReplaySession
from app.models.workout_enums import RecordType as RT


def lift(weight: float | str, reps: int | None, warmup: bool = False) -> LiftSet:
    return LiftSet(Decimal(str(weight)), reps, warmup)


def after(*lifts: LiftSet) -> ExerciseBests:
    bests = ExerciseBests()
    for item in lifts:
        bests = prs.absorb(bests, item)
    return bests


def kinds(events: list[prs.PrEvent]) -> set[RT]:
    return {e.record_type for e in events}


def by_kind(events: list[prs.PrEvent], kind: RT) -> prs.PrEvent:
    return next(e for e in events if e.record_type is kind)


# --------------------------------------------------------------------------
# Estimated 1RM
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("weight", "reps", "expected"),
    [
        (100, 1, "100.00"),  # a single IS the 1RM
        (100, 10, "133.33"),  # 100 * 40/30
        (60, 12, "84.00"),  # the last rep count the formula is trusted at
        (100, 13, None),  # beyond it
        (0, 5, None),  # bodyweight: nothing to estimate
    ],
)
def test_est_1rm(weight: int, reps: int, expected: str | None) -> None:
    result = prs.est_1rm(Decimal(weight), reps)
    assert result == (Decimal(expected) if expected else None)


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------


def test_the_first_set_is_a_baseline_for_every_record_it_sets() -> None:
    events = prs.detect(ExerciseBests(), lift(100, 5))
    assert kinds(events) == {RT.MAX_WEIGHT, RT.MAX_REPS_AT_WEIGHT, RT.EST_1RM}
    assert all(e.is_baseline and e.previous is None for e in events)


def test_a_heavier_set_is_a_weight_pr_against_the_old_record() -> None:
    events = prs.detect(after(lift(100, 5)), lift(105, 3))
    weight_pr = by_kind(events, RT.MAX_WEIGHT)
    assert weight_pr.previous == Decimal("100")
    assert weight_pr.is_baseline is False
    # 105x3 estimates to 115.5, below 100x5's 116.67 - no e1RM record.
    assert RT.EST_1RM not in kinds(events)


def test_more_reps_at_the_same_weight_is_a_rep_pr() -> None:
    events = prs.detect(after(lift(100, 5)), lift(100, 6))
    assert kinds(events) == {RT.MAX_REPS_AT_WEIGHT, RT.EST_1RM}
    assert by_kind(events, RT.MAX_REPS_AT_WEIGHT).previous == Decimal(5)


def test_a_dominated_set_is_not_a_pr() -> None:
    """90x5 after 100x5: something heavier already did as many reps."""
    assert prs.detect(after(lift(100, 5)), lift(90, 5)) == []


def test_a_heavier_set_with_more_reps_dominates_lighter_rep_attempts() -> None:
    assert prs.detect(after(lift(100, 8)), lift(90, 7)) == []


def test_more_reps_at_a_lighter_weight_is_a_rep_pr() -> None:
    """Nothing at 60kg or heavier ever reached 12 reps."""
    events = prs.detect(after(lift(100, 5)), lift(60, 12))
    assert kinds(events) == {RT.MAX_REPS_AT_WEIGHT}
    assert by_kind(events, RT.MAX_REPS_AT_WEIGHT).weight_kg == Decimal("60.00")


def test_warmups_never_set_or_count_toward_records() -> None:
    assert prs.detect(ExerciseBests(), lift(200, 1, warmup=True)) == []
    assert after(lift(200, 1, warmup=True)).has_history is False


def test_a_set_without_reps_is_ignored() -> None:
    """Cardio / timed sets have no strength record."""
    assert prs.detect(ExerciseBests(), lift(0, None)) == []


def test_bodyweight_sets_only_track_reps() -> None:
    events = prs.detect(after(lift(0, 10)), lift(0, 11))
    assert kinds(events) == {RT.MAX_REPS_AT_WEIGHT}
    assert by_kind(events, RT.MAX_REPS_AT_WEIGHT).previous == Decimal(10)


def test_the_frontier_keeps_only_undominated_points() -> None:
    bests = after(lift(100, 5), lift(100, 6), lift(80, 10), lift(90, 8), lift(70, 9))
    assert bests.frontier == (
        (Decimal("100"), 6),
        (Decimal("90"), 8),
        (Decimal("80"), 10),
    )


# --------------------------------------------------------------------------
# Volume
# --------------------------------------------------------------------------


def test_the_first_session_volume_is_a_baseline() -> None:
    event = prs.detect_volume(ExerciseBests(), Decimal("1000"))
    assert event is not None and event.is_baseline


def test_volume_must_beat_the_best_earlier_session() -> None:
    bests = prs.absorb_volume(ExerciseBests(), Decimal("1000"))
    assert prs.detect_volume(bests, Decimal("1000")) is None
    better = prs.detect_volume(bests, Decimal("1100"))
    assert better is not None
    assert better.previous == Decimal("1000") and not better.is_baseline


def test_zero_volume_is_never_a_record() -> None:
    assert prs.detect_volume(ExerciseBests(), Decimal("0")) is None


def test_session_volume_skips_warmups() -> None:
    volume = prs.session_volume([lift(100, 5), lift(60, 10, warmup=True)])
    assert volume == Decimal("500")


# --------------------------------------------------------------------------
# Rebuilding from stored rows, and replay
# --------------------------------------------------------------------------


def test_bests_rebuilt_from_record_rows_match_bests_from_the_sets() -> None:
    """The incremental path reads bests back from personal_records rows rather
    than every set, which is only valid if the two agree."""
    history = [lift(100, 5), lift(90, 8), lift(100, 6), lift(110, 1), lift(60, 15)]
    result = prs.replay([ReplaySession("s1", False, [(i, s) for i, s in enumerate(history)])])
    rows = [(e.record_type, e.value, e.weight_kg) for _, e in result.set_events]

    rebuilt = prs.bests_from_records(rows)
    direct = after(*history)
    assert rebuilt.max_weight == direct.max_weight
    assert rebuilt.est_1rm == direct.est_1rm
    assert rebuilt.frontier == direct.frontier


def test_deleting_the_record_holder_promotes_the_next_best_set() -> None:
    """B (100x4) was dominated by A (100x5). Once A is gone, B is the record -
    which an incremental fix-up would miss, and why replay exists."""
    with_a = prs.replay(
        [
            ReplaySession("s1", True, [("a", lift(100, 5))]),
            ReplaySession("s2", True, [("b", lift(100, 4))]),
        ]
    )
    assert [key for key, _ in with_a.set_events if key == "b"] == []

    without_a = prs.replay(
        [
            ReplaySession("s1", True, []),
            ReplaySession("s2", True, [("b", lift(100, 4))]),
        ]
    )
    b_events = [e for key, e in without_a.set_events if key == "b"]
    assert kinds(b_events) == {RT.MAX_WEIGHT, RT.MAX_REPS_AT_WEIGHT, RT.EST_1RM}
    assert all(e.is_baseline for e in b_events)


def test_an_unfinished_session_sets_no_volume_record() -> None:
    result = prs.replay([ReplaySession("live", False, [("a", lift(100, 5))])])
    assert result.volume_events == []


def test_replay_matches_logging_incrementally() -> None:
    sessions = [
        ReplaySession("s1", True, [("a", lift(80, 8)), ("b", lift(85, 6))]),
        ReplaySession("s2", True, [("c", lift(85, 7)), ("d", lift(60, 12, warmup=True))]),
        ReplaySession("s3", True, [("e", lift(90, 5)), ("f", lift(70, 12))]),
    ]

    incremental: list[tuple[str, prs.PrEvent]] = []
    volume_events: list[tuple[str, prs.PrEvent]] = []
    bests = ExerciseBests()
    for session in sessions:
        for key, item in session.sets:
            incremental += [(key, e) for e in prs.detect(bests, item)]
            bests = prs.absorb(bests, item)
        volume = prs.session_volume(item for _, item in session.sets)
        event = prs.detect_volume(bests, volume)
        if event:
            volume_events.append((session.key, event))
            bests = prs.absorb_volume(bests, volume)

    result = prs.replay(sessions)
    assert result.set_events == incremental
    assert result.volume_events == volume_events
