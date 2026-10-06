"""The quest engine: every objective at its edges, warm-up exclusion, and
deterministic choice. Pure logic, no database."""

import json
import uuid
from decimal import Decimal

import pytest

from app.core import quest_engine as engine
from app.core import quest_templates, training_categories
from app.models.quest_board import QuestObjective as O

S1, S2, S3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
BENCH, CURL = uuid.uuid4(), uuid.uuid4()


def s(
    reps: int | None = 10,
    weight: float = 50,
    *,
    warmup: bool = False,
    tags: tuple[str, ...] = (),
    session: uuid.UUID = S1,
    exercise: uuid.UUID = BENCH,
) -> engine.SetFact:
    return engine.SetFact(
        session_id=session,
        exercise_id=exercise,
        weight_kg=Decimal(str(weight)),
        reps=reps,
        is_warmup=warmup,
        tags=frozenset(tags),
    )


def facts(*sets: engine.SetFact, **kw) -> engine.PeriodFacts:
    return engine.PeriodFacts(sets=sets, **kw)


# --- complete_sessions -------------------------------------------------------


def test_only_qualifying_sessions_count() -> None:
    f = facts(s(), qualified_sessions=frozenset({S1, S2}))
    assert engine.progress(O.COMPLETE_SESSIONS, {}, f) == 2


def test_a_tagged_session_quest_needs_enough_tagged_sets_in_each_session() -> None:
    f = facts(
        s(tags=("mobility",), session=S1),
        s(tags=("mobility",), session=S1),
        s(tags=("mobility",), session=S2),
        s(tags=("mobility",), session=S2, warmup=True),
        qualified_sessions=frozenset({S1, S2}),
    )
    params = {"tag": "mobility", "min_tag_sets": 2}
    # S2 has one working mobility set; its warm-up does not make up the second.
    assert engine.progress(O.COMPLETE_SESSIONS, params, f) == 1


# --- log_working_sets / warm-ups ---------------------------------------------


def test_warmups_never_count() -> None:
    f = facts(s(), s(warmup=True), s())
    assert engine.progress(O.LOG_WORKING_SETS, {}, f) == 2


# --- total_volume ------------------------------------------------------------


def test_volume_is_whole_kilograms_rounded_down_and_skips_warmups() -> None:
    f = facts(s(reps=3, weight=33.5), s(reps=10, weight=100, warmup=True), s(reps=None))
    assert engine.progress(O.TOTAL_VOLUME, {}, f) == 100  # 100.5 -> 100


# --- sets_in_rep_range -------------------------------------------------------


def test_rep_range_is_inclusive_at_both_ends() -> None:
    f = facts(s(reps=11), s(reps=12), s(reps=20), s(reps=21), s(reps=None))
    assert engine.progress(O.SETS_IN_REP_RANGE, {"rep_low": 12, "rep_high": 20}, f) == 2


# --- sets_with_exercise_tag --------------------------------------------------


def test_tagged_sets_count_only_with_the_tag() -> None:
    f = facts(s(tags=("isolation",)), s(tags=("compound",)), s(tags=("isolation",), warmup=True))
    assert engine.progress(O.SETS_WITH_EXERCISE_TAG, {"tag": "isolation"}, f) == 1


# --- intensity_sets ----------------------------------------------------------


def test_intensity_is_measured_against_the_e1rm_from_before_the_period() -> None:
    f = facts(
        s(reps=3, weight=85),  # exactly 85% of 100
        s(reps=3, weight=84.9),
        s(reps=3, weight=90, exercise=CURL),  # no history: cannot count
        s(reps=3, weight=95, warmup=True),
        e1rm_before={BENCH: Decimal("100")},
    )
    assert engine.progress(O.INTENSITY_SETS, {"pct_e1rm": 0.85}, f) == 1


def test_intensity_respects_a_tag_filter() -> None:
    f = facts(
        s(reps=1, weight=90, tags=("compound_heavy",)),
        s(reps=1, weight=90, exercise=CURL),
        e1rm_before={BENCH: Decimal("100"), CURL: Decimal("100")},
    )
    assert engine.progress(O.INTENSITY_SETS, {"pct_e1rm": 0.85, "tag": "compound_heavy"}, f) == 1


# --- hit_pr ------------------------------------------------------------------


def test_prs_count_and_filter_by_tag() -> None:
    f = facts(prs=(engine.PrFact(BENCH, frozenset({"big3"})), engine.PrFact(CURL)))
    assert engine.progress(O.HIT_PR, {}, f) == 2
    assert engine.progress(O.HIT_PR, {"tag": "big3"}, f) == 1


# --- params ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("objective", "params"),
    [
        (O.SETS_IN_REP_RANGE, {}),
        (O.SETS_IN_REP_RANGE, {"rep_low": 10, "rep_high": 5}),
        (O.SETS_WITH_EXERCISE_TAG, {"tag": "cardio-ish"}),
        (O.INTENSITY_SETS, {"pct_e1rm": 1.5}),
        (O.COMPLETE_SESSIONS, {"min_tag_sets": 2}),
        (O.LOG_WORKING_SETS, {"reps": 5}),
    ],
)
def test_bad_params_are_rejected(objective: O, params: dict) -> None:
    with pytest.raises(ValueError):
        engine.validate_params(objective, params)


# --- choosing ----------------------------------------------------------------

POOL = [
    engine.Candidate("pl-a", ("powerlifter",)),
    engine.Candidate("pl-b", ("powerlifter",)),
    engine.Candidate("pl-c", ("powerlifter",)),
    engine.Candidate("ath-a", ("athlete",)),
    engine.Candidate("any-a"),
    engine.Candidate("any-b"),
]


def test_choice_is_deterministic_for_a_user_and_period() -> None:
    pool = engine.eligible(POOL, "powerlifter")
    first = engine.choose(pool, seed="u1:2026-10-05", count=2)
    assert first == engine.choose(list(reversed(pool)), seed="u1:2026-10-05", count=2)
    assert len(set(first)) == 2


def test_choice_varies_between_periods() -> None:
    pool = engine.eligible(POOL, "powerlifter")
    picks = {tuple(engine.choose(pool, seed=f"u1:day{i}", count=2)) for i in range(20)}
    assert len(picks) > 1


def test_a_path_gets_its_own_quests_and_never_another_paths() -> None:
    pool = engine.eligible(POOL, "powerlifter")
    for i in range(20):
        picked = engine.choose(pool, seed=f"u{i}", count=3)
        assert "ath-a" not in picked
        assert sum(code.startswith("pl-") for code in picked) == 2


def test_no_path_gets_only_open_quests() -> None:
    pool = engine.eligible(POOL, "")
    assert sorted(engine.choose(pool, seed="x", count=3)) == ["any-a", "any-b"]


def test_excluded_codes_are_never_chosen() -> None:
    pool = engine.eligible(POOL, "powerlifter")
    picked = engine.choose(pool, seed="x", count=5, exclude={"pl-a", "any-a"})
    assert sorted(picked) == ["any-b", "pl-b", "pl-c"]


# --- the shipped templates ---------------------------------------------------


def test_the_shipped_templates_are_valid() -> None:
    shipped = quest_templates.definitions()
    by_category: dict[str, list[dict]] = {}
    for record in shipped:
        for category in record["eligible_categories"] or ["any"]:
            by_category.setdefault(category, []).append(record)
    for category in ("athlete", "bodybuilder", "powerlifter"):
        assert len(by_category[category]) >= 8, category
    assert len(by_category["any"]) >= 4
    # A user with no path still gets a full board.
    open_weekly = [r for r in by_category["any"] if r["period"] == "weekly"]
    open_daily = [r for r in by_category["any"] if r["period"] == "daily"]
    assert len(open_weekly) >= 3 and len(open_daily) >= 2


def test_path_rep_range_quests_use_that_paths_rep_range() -> None:
    """The quest text says "8-15 reps" because the bodybuilder path does; if
    the path is retuned, this fails until the quests follow."""
    ranges = {
        d["category"]: (d["rep_range_low"], d["rep_range_high"])
        for d in training_categories.definitions()
    }
    for record in quest_templates.definitions():
        params = record["objective_params"]
        if record["objective_type"] == "sets_in_rep_range" and record["eligible_categories"]:
            for category in record["eligible_categories"]:
                assert (params["rep_low"], params["rep_high"]) == ranges[category], record["code"]


def test_every_tag_a_quest_asks_for_exists_on_some_exercise() -> None:
    from scripts.import_exercises import DEFAULT_FILE

    tagged = {t for e in json.loads(DEFAULT_FILE.read_text()) for t in e.get("tags", [])}
    for record in quest_templates.definitions():
        tag = record["objective_params"].get("tag")
        assert tag is None or tag in tagged, record["code"]
