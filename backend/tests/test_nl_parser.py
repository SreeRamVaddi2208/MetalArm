"""Tier 1 of natural-language logging, driven by tests/fixtures/
nl_utterances.json against the REAL exercise library and alias file - so a
renamed exercise or a dropped alias fails here. Pure: no database."""

import json
import time
import uuid
from decimal import Decimal
from pathlib import Path

import pytest

from app.core import exercise_aliases
from app.core import nl_parser as P
from scripts.import_exercises import DEFAULT_FILE

CASES = json.loads((Path(__file__).parent / "fixtures" / "nl_utterances.json").read_text())
LIBRARY = json.loads(DEFAULT_FILE.read_text())
# Stable ids per slug, so expectations can name exercises by slug.
IDS = {e["slug"]: uuid.uuid5(uuid.NAMESPACE_URL, e["slug"]) for e in LIBRARY}
SLUGS = {v: k for k, v in IDS.items()}
CANDIDATES = [
    P.Candidate(IDS[e["slug"]], e["name"], e["equipment"] == "bodyweight") for e in LIBRARY
]
ALIASES = {
    alias: IDS[slug]
    for slug, aliases in exercise_aliases.definitions().items()
    for alias in aliases
}


def ctx_for(case: dict) -> P.ParseContext:
    last = case.get("last")
    return P.ParseContext(
        candidates=CANDIDATES,
        aliases=ALIASES,
        current_exercise_id=IDS[case["current"]] if case.get("current") else None,
        last_set=(
            P.LastSet(IDS[last["slug"]], Decimal(str(last["weight_kg"])), last["reps"])
            if last
            else None
        ),
        unit=case.get("user_unit", "kg"),
    )


def test_there_are_enough_cases() -> None:
    assert len(CASES) >= 40


@pytest.mark.parametrize("case", CASES, ids=[c["text"] or "<empty>" for c in CASES])
def test_utterance(case: dict) -> None:
    result = P.parse(case["text"], ctx_for(case))
    expect = case["expect"]
    if "problem" in expect:
        assert not result.ok, result
        assert expect["problem"] in result.problem
        return
    assert result.ok, result.problem
    first = result.sets[0]
    assert SLUGS.get(first.exercise_id) == expect["exercise"]
    assert first.weight == pytest.approx(expect["weight"])
    assert first.unit == expect["unit"]
    assert first.reps == expect["reps"]
    assert len(result.sets) == expect["sets"]
    assert first.rpe == expect["rpe"]
    assert first.is_warmup is expect["warmup"]
    if "unparsed" in expect:
        assert list(result.unparsed) == expect["unparsed"]


def test_a_weak_exercise_match_offers_alternatives() -> None:
    result = P.parse("tricep thing 20 for 10", ctx_for({"current": None}))
    assert result.ok
    assert result.exercise_confidence < P.CONFIDENT
    assert 1 <= len(result.alternatives) <= 3


def test_a_personal_alias_wins_over_the_shipped_one() -> None:
    ctx = ctx_for({"current": None})
    mine = P.ParseContext(
        candidates=ctx.candidates,
        aliases={**ctx.aliases, "press": IDS["machine-shoulder-press"]},
    )
    result = P.parse("press 40 for 10", mine)
    assert SLUGS[result.sets[0].exercise_id] == "machine-shoulder-press"


def test_an_alias_for_an_exercise_the_user_cannot_see_is_ignored() -> None:
    ctx = P.ParseContext(
        candidates=[c for c in CANDIDATES if c.id != IDS["romanian-deadlift"]],
        aliases=ALIASES,
    )
    result = P.parse("rdl 100 for 8", ctx)
    assert all(s.exercise_id != IDS["romanian-deadlift"] for s in result.sets)


def test_repeating_a_lb_users_last_set_shows_it_in_pounds() -> None:
    ctx = P.ParseContext(
        candidates=CANDIDATES,
        last_set=P.LastSet(IDS["barbell-bench-press"], Decimal("100"), 5),
        unit="lb",
    )
    first = P.parse("same again", ctx).sets[0]
    assert (first.unit, first.weight) == ("lb", pytest.approx(220.5, abs=0.1))


def test_tier_one_is_fast() -> None:
    """The latency target is under 50 ms per parse; this checks a generous
    average over the whole fixture against the real library."""
    started = time.perf_counter()
    for case in CASES:
        P.parse(case["text"], ctx_for(case))
    average_ms = (time.perf_counter() - started) * 1000 / len(CASES)
    assert average_ms < 50
