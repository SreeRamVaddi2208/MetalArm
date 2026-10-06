"""Plausibility: which sets stay out of competitions. Pure."""

from decimal import Decimal as D

from app.core import plausibility as P
from app.core import workout_rules as rules


def check(weight="100", reps=5, *, warmup=False, equipment="barbell", best=None):
    return P.check(weight_kg=D(weight), reps=reps, is_warmup=warmup, equipment=equipment,
                   recent_best_e1rm=D(best) if best else None)


def test_an_ordinary_set_is_clear() -> None:
    assert check(best="115") == P.CLEAR


def test_a_jump_past_the_threshold_is_flagged() -> None:
    # 100 x 5 -> e1RM 116.67, more than 15% over a 100 best
    assert check(best="100") == P.Verdict(True, "e1rm_jump")


def test_a_jump_inside_the_threshold_is_not() -> None:
    assert not check(best="102").flagged  # 116.67 <= 117.3


def test_no_recent_history_means_no_jump_check() -> None:
    assert not check(weight="300", best=None).flagged


def test_too_many_reps_with_weight_is_flagged() -> None:
    assert check(weight="20", reps=rules.FLAG_MAX_WEIGHTED_REPS + 1).reason == "reps_implausible"


def test_bodyweight_high_reps_are_fine() -> None:
    assert not check(weight="0", reps=80, equipment="bodyweight").flagged


def test_the_ceiling_depends_on_equipment() -> None:
    assert check(weight="130", reps=1, equipment="dumbbell").reason == "over_ceiling"
    assert not check(weight="130", reps=1, equipment="barbell").flagged


def test_warmups_are_never_flagged() -> None:
    assert not check(weight="900", reps=1, warmup=True).flagged
