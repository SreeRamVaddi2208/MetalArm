"""The fair duel modes, scored against each side's own baseline. Pure."""

import datetime as dt
import uuid
from decimal import Decimal as D

from app.core import duel_scoring as fair

BENCH, SQUAT, CURL = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
MON = dt.date(2026, 10, 5)


def sess(day_offset: int, qualified: bool = True) -> fair.WindowSession:
    return fair.WindowSession(uuid.uuid4(), MON + dt.timedelta(days=day_offset), qualified)


def sets_for(session: fair.WindowSession, n: int, exercise=BENCH, weight="100", reps=5):
    return [fair.WindowSet(session.id, exercise, D(weight), reps) for _ in range(n)]


# --- consistency ---------------------------------------------------------------


def test_consistency_counts_one_per_day_and_needs_three_working_sets() -> None:
    a, b, c, d = sess(0), sess(0), sess(1), sess(2, qualified=False)
    sets = sets_for(a, 3) + sets_for(b, 3) + sets_for(c, 2) + sets_for(d, 5)
    score = fair.consistency([a, b, c, d], sets)
    assert score.value == 1  # Monday once; Tuesday too few sets; Wednesday unqualified
    assert score.tiebreak == len(sets)


def test_consistency_ties_go_to_total_sets() -> None:
    a, b = sess(0), sess(0)
    lighter = fair.consistency([a], sets_for(a, 3))
    busier = fair.consistency([b], sets_for(b, 6))
    assert fair.winner(lighter, busier) == -1


def test_load_is_irrelevant_to_consistency() -> None:
    a, b = sess(0), sess(0)
    light = fair.consistency([a], sets_for(a, 3, weight="20"))
    heavy = fair.consistency([b], sets_for(b, 3, weight="200"))
    assert fair.winner(light, heavy) == 0


# --- progress ------------------------------------------------------------------


def test_progress_sums_percent_gains_over_each_own_baseline() -> None:
    s = sess(0)
    # 100 x 5 -> e1RM 116.67; baseline 110 -> +6.06%
    score = fair.progress({BENCH: D("110")}, sets_for(s, 1))
    assert score.value == 6.1
    assert [line.value for line in score.breakdown] == [6.1]


def test_progress_is_capped_per_exercise() -> None:
    s = sess(0)
    score = fair.progress({BENCH: D("50"), SQUAT: D("50")},
                          sets_for(s, 1) + sets_for(s, 1, exercise=SQUAT))
    assert score.value == 20.0  # two lifts, each held to +10%


def test_exactly_at_the_cap_counts_in_full() -> None:
    s = sess(0)
    # A single: e1RM is the weight itself. 110 over a 100 baseline is +10%.
    score = fair.progress({BENCH: D("100")}, sets_for(s, 1, weight="110", reps=1))
    assert score.value == 10.0


def test_a_lift_with_no_baseline_cannot_score_and_a_drop_scores_zero() -> None:
    s = sess(0)
    score = fair.progress({BENCH: D("200")}, sets_for(s, 1) + sets_for(s, 1, exercise=CURL))
    assert score.value == 0 and score.breakdown == ()


def test_no_baseline_at_all_is_zero_not_an_error() -> None:
    assert fair.progress({}, sets_for(sess(0), 3)).value == 0


def test_a_beginner_and_a_veteran_meet_on_equal_terms() -> None:
    s = sess(0)
    beginner = fair.progress({BENCH: D("40")}, sets_for(s, 1, weight="44", reps=1))
    veteran = fair.progress({BENCH: D("150")}, sets_for(s, 1, weight="165", reps=1))
    assert beginner.value == veteran.value == 10.0


# --- relative volume -------------------------------------------------------------


def test_relative_volume_is_a_percent_of_the_users_own_week() -> None:
    s = sess(0)
    score = fair.relative_volume(D("1000"), sets_for(s, 3, weight="100", reps=5), 7)
    assert score.value == 150.0


def test_a_light_lifter_training_more_beats_a_heavy_one_coasting() -> None:
    s = sess(0)
    light = fair.relative_volume(D("1000"), sets_for(s, 3, weight="50", reps=10), 7)   # 1500 kg
    heavy = fair.relative_volume(D("10000"), sets_for(s, 10, weight="160", reps=5), 7)  # 8000 kg
    assert fair.winner(light, heavy) == 1


def test_relative_volume_scales_to_the_window_length() -> None:
    s = sess(0)
    assert fair.relative_volume(D("700"), sets_for(s, 1, weight="100", reps=1), 1).value == 100.0


def test_no_baseline_volume_scores_zero() -> None:
    assert fair.relative_volume(D("0"), sets_for(sess(0), 3), 7).value == 0


def test_baseline_weekly_average() -> None:
    assert fair.baseline_avg_weekly(D("4000")) == D("1000")
