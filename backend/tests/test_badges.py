"""Badge rules are pure: inputs in, earned/progress out."""

from app.core import badges
from app.core.badges import Badge, BadgeInputs


def _by_id(result: list[Badge]) -> dict[str, Badge]:
    return {b.id: b for b in result}


def test_fresh_user_has_no_badges_but_sees_every_target() -> None:
    result = badges.evaluate(BadgeInputs())
    assert badges.earned_count(result) == 0
    assert len(result) == len({b.id for b in result})
    # A level-1 user has not reached level 10, but progress still shows.
    assert _by_id(result)["level_10"].progress == 1


def test_badge_is_earned_exactly_at_its_target() -> None:
    just_short = _by_id(badges.evaluate(BadgeInputs(quests_completed=9)))
    at_target = _by_id(badges.evaluate(BadgeInputs(quests_completed=10)))
    assert not just_short["ten_quests"].earned
    assert just_short["ten_quests"].progress == 9
    assert at_target["ten_quests"].earned


def test_progress_is_capped_at_the_target() -> None:
    result = _by_id(badges.evaluate(BadgeInputs(quests_completed=10_000)))
    assert result["first_quest"].progress == result["first_quest"].target == 1
    assert result["first_quest"].percent == 100


def test_percent_for_partial_progress() -> None:
    result = _by_id(badges.evaluate(BadgeInputs(quests_completed=5)))
    assert result["ten_quests"].percent == 50


def test_percent_with_a_zero_target() -> None:
    assert Badge("x", "x", "x", "x", earned=True, progress=0, target=0).percent == 100
    assert Badge("x", "x", "x", "x", earned=False, progress=0, target=0).percent == 0


def test_workout_badges_use_the_workout_inputs() -> None:
    result = _by_id(
        badges.evaluate(
            BadgeInputs(workouts_completed=10, workout_prs=1, longest_workout_streak=4)
        )
    )
    assert result["first_workout"].earned
    assert result["ten_workouts"].earned
    assert not result["fifty_workouts"].earned
    assert result["first_pr"].earned
    assert result["workout_streak_4"].earned


def test_streak_badges_key_off_the_longest_streak() -> None:
    result = _by_id(badges.evaluate(BadgeInputs(longest_streak=30)))
    assert result["streak_7"].earned
    assert result["streak_30"].earned
    assert not result["streak_100"].earned


def test_earned_count_matches_earned_flags() -> None:
    result = badges.evaluate(BadgeInputs(quests_completed=50, rewards_redeemed=1))
    assert badges.earned_count(result) == sum(b.earned for b in result)
    assert badges.earned_count(result) >= 4
