"""Quest engine: how far a generated quest has got, from facts about a period.

Pure, like points_engine.py: no database, no clock, no request. The store half
(app/core/quest_board.py) loads one period's facts and persists what this
decides, so every objective can be tested at its exact edge.

Progress is ALWAYS recomputed from the sets, never accumulated. An accumulated
counter has to be decremented correctly on every edit, delete and abandon; a
recomputed one is right by construction, and a quest cannot be completed twice
by replaying the same set, because the same set is only ever counted once.

Warm-ups never count. A session only counts toward complete_sessions if it
qualified (points_engine.session_qualifies) - the same bar the weekly streak
uses, so a start/finish tap does not advance a quest any more than a streak.
"""

from __future__ import annotations

import dataclasses
import hashlib
import math
import random
import uuid
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal

from app.models.quest_board import QuestObjective
from app.models.workout_enums import ExerciseTag


@dataclasses.dataclass(frozen=True)
class SetFact:
    session_id: uuid.UUID
    exercise_id: uuid.UUID
    weight_kg: Decimal
    reps: int | None
    is_warmup: bool
    tags: frozenset[str] = frozenset()


@dataclasses.dataclass(frozen=True)
class PrFact:
    """One record-setting moment (several record types beaten by one set are
    one PR, not several)."""

    exercise_id: uuid.UUID
    tags: frozenset[str] = frozenset()


@dataclasses.dataclass(frozen=True)
class PeriodFacts:
    # Sets logged in the period, from sessions that were not abandoned.
    sets: tuple[SetFact, ...] = ()
    # Qualifying sessions FINISHED in the period.
    qualified_sessions: frozenset[uuid.UUID] = frozenset()
    prs: tuple[PrFact, ...] = ()
    # Best estimated 1RM per exercise from BEFORE the period began. A fixed
    # bar: measuring against a 1RM the same period keeps raising would make an
    # intensity quest harder the better the week goes.
    e1rm_before: Mapping[uuid.UUID, Decimal] = dataclasses.field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

_TAGS = {t.value for t in ExerciseTag}

# Which params each objective accepts, and which it requires.
_PARAMS: dict[QuestObjective, tuple[set[str], set[str]]] = {
    QuestObjective.COMPLETE_SESSIONS: ({"tag", "min_tag_sets"}, set()),
    QuestObjective.LOG_WORKING_SETS: ({"tag"}, set()),
    QuestObjective.TOTAL_VOLUME: ({"tag"}, set()),
    QuestObjective.SETS_IN_REP_RANGE: ({"rep_low", "rep_high", "tag"}, {"rep_low", "rep_high"}),
    QuestObjective.SETS_WITH_EXERCISE_TAG: ({"tag"}, {"tag"}),
    QuestObjective.INTENSITY_SETS: ({"pct_e1rm", "tag"}, {"pct_e1rm"}),
    QuestObjective.HIT_PR: ({"tag"}, set()),
}


def validate_params(objective: QuestObjective, params: Mapping[str, object]) -> None:
    """Raise ValueError if `params` do not make sense for `objective`. Run on
    every template at seed time, so a typo in the JSON fails the deploy rather
    than silently producing a quest nobody can finish."""
    allowed, required = _PARAMS[objective]
    unknown = set(params) - allowed
    if unknown:
        raise ValueError(f"{objective.value}: unknown params {sorted(unknown)}")
    missing = required - set(params)
    if missing:
        raise ValueError(f"{objective.value}: missing params {sorted(missing)}")
    if "tag" in params and params["tag"] not in _TAGS:
        raise ValueError(f"{objective.value}: unknown tag {params['tag']!r}")
    if "rep_low" in params:
        low, high = params["rep_low"], params["rep_high"]
        if not (isinstance(low, int) and isinstance(high, int) and 1 <= low <= high):
            raise ValueError(f"{objective.value}: bad rep range {low}-{high}")
    if "pct_e1rm" in params:
        pct = params["pct_e1rm"]
        if not (isinstance(pct, (int, float)) and 0 < pct <= 1):
            raise ValueError(f"{objective.value}: pct_e1rm must be in (0, 1]")
    if "min_tag_sets" in params:
        if "tag" not in params:
            raise ValueError(f"{objective.value}: min_tag_sets needs a tag")
        if not (isinstance(params["min_tag_sets"], int) and params["min_tag_sets"] >= 1):
            raise ValueError(f"{objective.value}: min_tag_sets must be a positive int")


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


def _has_tag(fact: SetFact | PrFact, params: Mapping[str, object]) -> bool:
    tag = params.get("tag")
    return tag is None or tag in fact.tags


def progress(
    objective: QuestObjective, params: Mapping[str, object], facts: PeriodFacts
) -> int:
    """How far toward its target a quest is. Never negative; may exceed the
    target (the caller clamps for display)."""
    working = [s for s in facts.sets if not s.is_warmup and _has_tag(s, params)]

    if objective is QuestObjective.COMPLETE_SESSIONS:
        sessions = facts.qualified_sessions
        if "min_tag_sets" in params:
            per_session = Counter(s.session_id for s in working)
            sessions = frozenset(
                sid for sid in sessions if per_session[sid] >= int(params["min_tag_sets"])  # type: ignore[arg-type]
            )
        return len(sessions)

    if objective is QuestObjective.LOG_WORKING_SETS:
        return len(working)

    if objective is QuestObjective.TOTAL_VOLUME:
        # Whole kilograms, rounded down: a quest for 5000 kg is not done at
        # 4999.5.
        volume = sum((s.weight_kg * s.reps for s in working if s.reps), Decimal(0))
        return math.floor(volume)

    if objective is QuestObjective.SETS_IN_REP_RANGE:
        low, high = int(params["rep_low"]), int(params["rep_high"])  # type: ignore[arg-type]
        return sum(1 for s in working if s.reps is not None and low <= s.reps <= high)

    if objective is QuestObjective.SETS_WITH_EXERCISE_TAG:
        return len(working)

    if objective is QuestObjective.INTENSITY_SETS:
        pct = Decimal(str(params["pct_e1rm"]))
        count = 0
        for s in working:
            best = facts.e1rm_before.get(s.exercise_id)
            # No history means no bar to measure against: the set cannot count,
            # rather than counting against a bar of zero.
            if best and s.reps and s.weight_kg > 0 and s.weight_kg >= best * pct:
                count += 1
        return count

    if objective is QuestObjective.HIT_PR:
        return sum(1 for pr in facts.prs if _has_tag(pr, params))

    raise ValueError(f"unsupported objective: {objective!r}")


# ---------------------------------------------------------------------------
# Choosing quests
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Candidate:
    code: str
    eligible_categories: tuple[str, ...] = ()


def eligible(pool: Iterable[Candidate], category: str) -> list[Candidate]:
    """Templates open to someone on this training path. A template with no
    categories is open to everyone - including someone with no path yet."""
    return [c for c in pool if not c.eligible_categories or category in c.eligible_categories]


def choose(
    pool: Sequence[Candidate], *, seed: str, count: int, exclude: Iterable[str] = ()
) -> list[str]:
    """`count` template codes from `pool`, deterministically for `seed`.

    The seed is the user and the period, so a refresh - or two requests racing
    to generate the same period - always picks the same quests. Sorted first,
    so the pick does not depend on the order the database returned the pool.
    Path-specific templates are preferred: they are what makes a powerlifter's
    week look different from an athlete's, and the open ones fill any gap.
    """
    skip = set(exclude)
    rng = random.Random(int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], "big"))
    specific = sorted(c.code for c in pool if c.eligible_categories and c.code not in skip)
    general = sorted(c.code for c in pool if not c.eligible_categories and c.code not in skip)
    # Mostly the path's own quests, but always room for one open one when
    # there are enough of both, so a day is not only one kind of thing.
    take_specific = min(len(specific), max(count - 1, 0) if general else count)
    picked = rng.sample(specific, take_specific)
    picked += rng.sample(general, min(len(general), count - len(picked)))
    if len(picked) < count:
        rest = [c for c in specific if c not in picked]
        picked += rng.sample(rest, min(len(rest), count - len(picked)))
    return picked
