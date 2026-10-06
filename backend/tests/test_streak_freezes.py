"""Streak freezes: covered weeks in the streak, and settling closed weeks.
Pure logic, no database - the API side is in test_quest_board.py."""

from app.core import streak_freezes as fz
from app.core.workout_streaks import longest_weekly_streak, weekly_streak
from app.models.quest_board import FreezeReason as R

T = 3


def settle(weeks, counts, *, balance=0, covered=(), earned=(), quests=(), every=4, cap=2):
    return fz.settle(
        weeks,
        sessions_per_week=counts,
        covered=set(covered),
        earned=set(earned),
        balance=balance,
        quests_done_weeks=set(quests),
        target=T,
        every=every,
        cap=cap,
    )


# --- the streak with covered weeks ---------------------------------------------


def test_a_covered_week_keeps_the_streak_without_adding_to_it() -> None:
    counts = {"2026-W35": 3, "2026-W37": 3}
    assert weekly_streak(counts, "2026-W37", T).weeks == 1
    assert weekly_streak(counts, "2026-W37", T, covered={"2026-W36"}).weeks == 2


def test_a_covered_week_bridges_into_the_current_unfinished_week() -> None:
    counts = {"2026-W35": 3, "2026-W36": 3, "2026-W38": 1}
    assert weekly_streak(counts, "2026-W38", T, covered={"2026-W37"}).weeks == 2


def test_a_freeze_covers_one_week_not_two() -> None:
    counts = {"2026-W35": 3, "2026-W38": 3}
    assert weekly_streak(counts, "2026-W38", T, covered={"2026-W36"}).weeks == 1


def test_the_longest_streak_counts_through_a_covered_week() -> None:
    counts = {"2026-W30": 3, "2026-W31": 3, "2026-W33": 3, "2026-W40": 3}
    assert longest_weekly_streak(counts, T) == 2
    assert longest_weekly_streak(counts, T, covered={"2026-W32"}) == 3


# --- settling --------------------------------------------------------------------


def test_a_short_week_after_a_live_streak_spends_a_held_freeze() -> None:
    events = settle(["2026-W37"], {"2026-W36": 3, "2026-W37": 1}, balance=1)
    assert events == [fz.FreezeEvent("2026-W37", -1, R.MISSED_WEEK_COVERED)]


def test_nothing_is_spent_when_there_is_no_streak_to_save() -> None:
    assert settle(["2026-W37"], {"2026-W37": 1}, balance=2) == []


def test_nothing_is_spent_without_a_freeze() -> None:
    assert settle(["2026-W37"], {"2026-W36": 3}, balance=0) == []


def test_two_short_weeks_spend_two_freezes_and_the_streak_survives() -> None:
    counts = {"2026-W35": 3}
    events = settle(["2026-W36", "2026-W37"], counts, balance=2)
    assert [e.week for e in events] == ["2026-W36", "2026-W37"]
    covered = {e.week for e in events}
    counts["2026-W38"] = 3
    assert weekly_streak(counts, "2026-W38", T, covered=covered).weeks == 2


def test_a_freeze_is_earned_every_n_counting_weeks() -> None:
    counts = {f"2026-W{w:02d}": 3 for w in range(30, 38)}
    events = settle([f"2026-W{w:02d}" for w in range(30, 38)], counts, every=4)
    assert [(e.week, e.reason) for e in events] == [
        ("2026-W33", R.STREAK_MILESTONE),
        ("2026-W37", R.STREAK_MILESTONE),
    ]


def test_covered_weeks_do_not_count_toward_the_milestone() -> None:
    counts = {"2026-W30": 3, "2026-W31": 3, "2026-W33": 3, "2026-W34": 3}
    events = settle(["2026-W33", "2026-W34"], counts, covered={"2026-W32"}, every=4)
    assert events == [fz.FreezeEvent("2026-W34", 1, R.STREAK_MILESTONE)]


def test_earning_stops_at_the_cap() -> None:
    counts = {f"2026-W{w:02d}": 3 for w in range(30, 34)}
    events = settle(["2026-W33"], counts, balance=2, quests={"2026-W33"}, every=4, cap=2)
    assert events == []


def test_finishing_the_weeks_quests_earns_a_freeze() -> None:
    events = settle(["2026-W37"], {"2026-W37": 1}, quests={"2026-W37"})
    assert events == [fz.FreezeEvent("2026-W37", 1, R.WEEKLY_QUESTS_COMPLETE)]


def test_a_freeze_earned_one_week_can_cover_the_next() -> None:
    counts = {"2026-W36": 3}
    events = settle(["2026-W36", "2026-W37"], counts, quests={"2026-W36"})
    assert [(e.week, e.delta) for e in events] == [("2026-W36", 1), ("2026-W37", -1)]


def test_settling_again_is_idempotent() -> None:
    earned = {("2026-W37", R.WEEKLY_QUESTS_COMPLETE)}
    assert settle(["2026-W37"], {"2026-W37": 1}, quests={"2026-W37"}, earned=earned) == []


def test_weeks_to_next_freeze() -> None:
    assert fz.weeks_to_next(0, every=4) == 4
    assert fz.weeks_to_next(3, every=4) == 1
    assert fz.weeks_to_next(4, every=4) == 4
