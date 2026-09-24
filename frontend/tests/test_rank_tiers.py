"""The rank-up tier table: budgets, escalation, and the ladder it must cover.

Pure data, so these run without Reflex installed - the one test that needs it
skips itself. What is worth pinning is not the exact numbers (they are meant to
be tuned) but the invariants: every promotion is louder than the one below it,
nothing exceeds the performance or patience budget, and no tier in the ladder
is left without a celebration.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalarm import rank_tiers  # noqa: E402

# Ascending, as ranks.RANK_TITLES has them. Untrained is where everyone starts,
# so nothing is ever promoted INTO it.
LADDER = ("E", "D", "C", "B", "A", "S")
PROMOTIONS = LADDER[1:]


def test_every_promotion_has_a_tier() -> None:
    assert tuple(rank_tiers.TIERS) == PROMOTIONS


def test_the_starting_rank_has_no_celebration() -> None:
    assert "E" not in rank_tiers.TIERS


def test_the_ladder_matches_the_titles_the_app_shows() -> None:
    """ranks.py is the source of the ladder; this table must cover it."""
    pytest.importorskip("reflex", reason="ranks.py imports Reflex")
    from metalarm import ranks

    assert tuple(ranks.RANK_TITLES) == LADDER


@pytest.mark.parametrize("rank", PROMOTIONS)
def test_a_tier_stays_inside_its_budgets(rank: str) -> None:
    tier = rank_tiers.TIERS[rank]
    assert tier.particles <= rank_tiers.MAX_PARTICLES
    assert len(rank_tiers.particles(tier)) == tier.particles
    assert tier.duration_ms <= rank_tiers.MAX_DURATION_MS


def test_each_promotion_is_louder_than_the_one_below() -> None:
    """The whole point: Novice is a flourish, World Class is an event."""
    tiers = [rank_tiers.TIERS[rank] for rank in PROMOTIONS]
    for quieter, louder in zip(tiers, tiers[1:]):
        assert louder.duration_ms > quieter.duration_ms
        assert louder.rings >= quieter.rings
        assert louder.shake_px >= quieter.shake_px
        assert louder.zoom >= quieter.zoom
        assert louder.pop >= quieter.pop
        assert len(louder.layers) >= len(quieter.layers)
        assert len(louder.sound) >= len(quieter.sound)
        assert len(louder.haptic) >= len(quieter.haptic)


def test_the_top_tier_is_the_full_treatment() -> None:
    top = rank_tiers.TIERS["S"]
    assert top.ornament == "regalia"
    assert top.shock
    assert "fanfare" in top.sound
    # Dust that outlasts the burst is what makes the top tier linger.
    assert "ambient" in top.layers


def test_a_level_up_is_quieter_than_any_promotion() -> None:
    quietest = rank_tiers.TIERS["D"]
    assert rank_tiers.LEVEL_UP.duration_ms <= quietest.duration_ms
    assert rank_tiers.LEVEL_UP.particles <= quietest.particles
    assert not rank_tiers.LEVEL_UP.shock


def test_an_unknown_rank_still_celebrates() -> None:
    """A rank added server-side must not silently render nothing."""
    assert rank_tiers.tier_for("Z") is rank_tiers.LEVEL_UP
    assert rank_tiers.tier_for("") is rank_tiers.LEVEL_UP


def test_particles_carry_everything_the_css_needs() -> None:
    burst = rank_tiers.particles(rank_tiers.TIERS["S"])
    assert {key for entry in burst for key in entry} == {"cls", "a", "d", "x", "delay"}
    # Deterministic, so a recorded tour or a screenshot diff is reproducible.
    assert burst == rank_tiers.particles(rank_tiers.TIERS["S"])
    assert {entry["cls"].split()[-1] for entry in burst} == {
        f"lf-{layer}" for layer in rank_tiers.TIERS["S"].layers
    }
