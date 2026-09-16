"""Progression hints (app/core/progression_hints.py): double progression
against the rep range, the smallest loadable jump per equipment, a plateau
after sessions with no new best, a deload after a long unbroken climb, and
the hint on the last-performance endpoint."""

import datetime as dt
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import progression_hints as hints
from app.core import workout_rules as rules
from tests.test_workouts import exercise_id, full_workout

EX = "/api/v1/exercises"
DAY = dt.timedelta(days=1)
START = dt.datetime(2026, 9, 14, 12, 0, tzinfo=dt.timezone.utc)


def tops(*pairs: tuple[str, int], apart: dt.timedelta = 7 * DAY) -> list[hints.TopSet]:
    """Top sets newest first, `apart` between sessions."""
    return [
        hints.TopSet(performed_at=START - index * apart, weight_kg=Decimal(weight), reps=reps)
        for index, (weight, reps) in enumerate(pairs)
    ]


def test_a_new_exercise_gets_no_hint() -> None:
    assert hints.suggest([], equipment="barbell") is None


def test_below_the_top_of_the_range_it_adds_a_rep() -> None:
    hint = hints.suggest(tops(("100", 5)), equipment="barbell")
    assert hint.kind == "progress"
    assert hint.text == "Try 100 kg x 6"
    assert hint.target_weight_kg == Decimal(100)
    assert hint.target_reps == 6


def test_at_the_top_of_the_range_it_adds_weight_and_drops_the_reps() -> None:
    low, high = rules.HINT_REP_RANGE
    hint = hints.suggest(tops(("100", high)), equipment="barbell")
    assert hint.target_weight_kg == Decimal(100) + Decimal(str(rules.WEIGHT_STEP_KG))
    assert hint.target_reps == low
    assert hint.text == f"Try 102.5 kg x {low}"


def test_the_jump_matches_the_equipment() -> None:
    _, high = rules.HINT_REP_RANGE
    dumbbell = hints.suggest(tops(("30", high)), equipment="dumbbell")
    assert dumbbell.target_weight_kg == Decimal(30) + Decimal(str(rules.SMALL_WEIGHT_STEP_KG))


def test_hints_are_written_in_the_users_unit() -> None:
    hint = hints.suggest(tops(("100", 5)), equipment="barbell", unit="lb")
    assert hint.text == "Try 220.5 lb x 6"
    # The target stays in kilograms for the client.
    assert hint.target_weight_kg == Decimal(100)


def test_no_new_best_for_three_sessions_is_a_plateau() -> None:
    # An older, better session then three that never beat it.
    hint = hints.suggest(
        tops(("100", 5), ("100", 5), ("100", 5), ("100", 6)), equipment="barbell"
    )
    assert hint.kind == "plateau"
    assert hint.target_weight_kg == Decimal("90")
    assert "build up again" in hint.text


def test_a_long_unbroken_climb_earns_a_deload() -> None:
    # Eight weekly sessions, each one heavier than the last.
    climb = tops(("120", 5), ("117.5", 5), ("115", 5), ("112.5", 5), ("110", 5), ("107.5", 5), ("105", 5), ("102.5", 5))
    hint = hints.suggest(climb, equipment="barbell")
    assert hint.kind == "deload"
    assert hint.target_weight_kg == Decimal("95")
    assert "lighter week" in hint.text


def test_a_climb_inside_six_weeks_is_not_a_deload() -> None:
    climb = tops(("120", 5), ("117.5", 5), ("115", 5), ("112.5", 5), apart=DAY)
    assert hints.suggest(climb, equipment="barbell").kind == "progress"


def test_the_endpoint_says_what_to_try_next(
    client: TestClient, auth: dict, db: Session
) -> None:
    exercise = exercise_id(client, auth)
    full_workout(client, auth, db, exercise)

    body = client.get(f"{EX}/{exercise}/last-performance", headers=auth).json()
    assert body["hint"]["kind"] == "progress"
    assert body["hint"]["target_reps"] == 6
    assert body["hint"]["text"].startswith("Try ")


def test_an_exercise_never_done_has_no_hint(client: TestClient, auth: dict) -> None:
    exercise = exercise_id(client, auth)
    body = client.get(f"{EX}/{exercise}/last-performance", headers=auth).json()
    assert body["sets"] == []
    assert body["hint"] is None
