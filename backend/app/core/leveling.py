"""XP curve, rank ladder, and the streak gate on high ranks.

Deliberately the ONLY place these numbers appear. Because level_progress
stores cumulative total_xp as the source of truth, retuning anything here
re-derives every user correctly rather than corrupting stored progress.

AFTER CHANGING ANY NUMBER IN THIS FILE, run:
    docker compose run --rm tests python -m scripts.recompute_progression
level_progress.current_level and .rank are caches of this curve, and a retune
leaves them stale until they are recomputed.

Curve settled with the user on 2026-09-10 ("steady climb"). Targets, assuming
an active user earning ~268 XP/day (3 dailies at 75 XP plus a weekly at 300):
    D ~6 days, C ~6 weeks, B ~4.4 months, A ~11 months, S ~2.1 years.
The previous placeholder (BASE=50, EXPONENT=1.5) put S rank 9.8 years out,
which made the top half of the ladder dead content.
"""

import bisect
import datetime as dt

from app.models.enums import Rank

# XP required to advance FROM level n to n+1: BASE * n ** EXPONENT.
XP_BASE = 40
XP_EXPONENT = 1.25

MAX_LEVEL = 999

# Level at which each rank becomes attainable. Must stay ascending.
RANK_THRESHOLDS: tuple[tuple[int, Rank], ...] = (
    (1, Rank.E),
    (8, Rank.D),
    (18, Rank.C),
    (30, Rank.B),
    (45, Rank.A),
    (65, Rank.S),
)

# Section 2 of the brief: rank derives from level AND consistency. Level alone
# gates E-B; the top two ranks additionally require an active streak, so an S
# beside someone's name means they are currently active, not merely long-lived.
#
# A lapsed user falls back to the highest rank they still qualify for (S -> A
# -> B), never to E: level and total_xp are never lost, only the top badge.
RANK_STREAK_REQUIREMENTS: dict[Rank, int] = {
    Rank.A: 14,
    Rank.S: 30,
}

# A streak counts as active only if the user completed something today or
# yesterday in their own timezone. Without this, a dormant user's stored
# current_streak stays frozen at its old value forever - nothing decrements it,
# because nothing runs while they are away - and the streak gate above would
# never actually demote anyone.
STREAK_GRACE_DAYS = 1


def _build_cumulative_table() -> tuple[int, ...]:
    """Cumulative XP to reach each level, precomputed once at import.

    Computed as a running total rather than re-summing per level: the naive
    form makes xp_for_level O(n) and level_for_xp O(n^2), which matters once
    Sprint 5's leaderboard derives a level per row.

    Index i holds the XP needed to reach level i; index 0 is padding so the
    list is indexable by level directly.
    """
    table = [0, 0]
    total = 0
    for n in range(1, MAX_LEVEL):
        total += int(XP_BASE * (n**XP_EXPONENT))
        table.append(total)
    return tuple(table)


_CUMULATIVE_XP: tuple[int, ...] = _build_cumulative_table()


def xp_for_level(level: int) -> int:
    """Cumulative XP required to REACH `level`. Level 1 costs nothing."""
    if level <= 1:
        return 0
    if level > MAX_LEVEL:
        level = MAX_LEVEL
    return _CUMULATIVE_XP[level]


def level_for_xp(total_xp: int) -> int:
    """Derive level from cumulative XP - the reverse of xp_for_level."""
    if total_xp <= 0:
        return 1
    # Highest level whose cumulative cost has been paid. Index 1 also holds 0,
    # so bisect_right lands past both zero entries and total_xp=0 gives level 1.
    level = bisect.bisect_right(_CUMULATIVE_XP, total_xp) - 1
    return min(max(level, 1), MAX_LEVEL)


def progress_into_level(total_xp: int) -> tuple[int, int]:
    """(xp earned into the current level, xp needed to finish it).

    This is what the Stat Panel's XP bar renders. At MAX_LEVEL there is no
    next level, so both are 0 and the bar should read as full.
    """
    level = level_for_xp(total_xp)
    if level >= MAX_LEVEL:
        return (0, 0)
    floor = xp_for_level(level)
    ceiling = xp_for_level(level + 1)
    return (total_xp - floor, ceiling - floor)


def streak_is_active(
    last_completed_on: dt.date | None, today: dt.date
) -> bool:
    """Whether a stored streak still counts.

    `today` must be the user's LOCAL date - a streak must not read as broken
    merely because the server rolled over to tomorrow first.
    """
    if last_completed_on is None:
        return False
    return (today - last_completed_on).days <= STREAK_GRACE_DAYS


def effective_streak(
    current_streak: int, last_completed_on: dt.date | None, today: dt.date
) -> int:
    """The streak as it stands right now, which is 0 once it has lapsed.

    Read-time derivation, because nothing runs on a dormant user's behalf to
    zero out the stored value.
    """
    if not streak_is_active(last_completed_on, today):
        return 0
    return current_streak


def rank_by_level(level: int) -> Rank:
    """Highest rank the level alone qualifies for, ignoring any streak gate.

    Used to tell a user they have earned A on level but still need the streak
    to actually hold it.
    """
    rank = Rank.E
    for threshold, candidate in RANK_THRESHOLDS:
        if level >= threshold:
            rank = candidate
        else:
            break
    return rank


# Ranks that also need strength trials (app/core/rank_trials.py): a bench,
# squat and deadlift at a multiple of bodyweight, so a high rank means real
# strength and not only time spent. Cumulative - A needs the B trial too.
TRIAL_RANKS: tuple[Rank, ...] = (Rank.B, Rank.A, Rank.S)


def trials_needed(rank: Rank) -> tuple[Rank, ...]:
    """The trials a rank requires: its own and every trial rank below it."""
    if rank not in TRIAL_RANKS:
        return ()
    return TRIAL_RANKS[: TRIAL_RANKS.index(rank) + 1]


def rank_for(level: int, streak: int, trials: str = "") -> Rank:
    """The rank actually held, applying the streak gate to A and S and the
    strength trials to B, A and S (`trials`: the letters passed, e.g. "BA").

    Walks the ladder downward and returns the highest rank whose level,
    streak AND trial requirements are all met, so a lapsed S lands on A or B
    rather than falling all the way to E.
    """
    for threshold, candidate in reversed(RANK_THRESHOLDS):
        if level < threshold:
            continue
        if streak < RANK_STREAK_REQUIREMENTS.get(candidate, 0):
            continue
        if any(needed.value not in trials for needed in trials_needed(candidate)):
            continue
        return candidate
    return Rank.E


def next_rank_requirement(
    level: int, streak: int, trials: str = ""
) -> tuple[Rank, int, int] | None:
    """What it takes to reach the next rank up: (rank, level needed, streak needed).

    Returns None at the top of the ladder. Drives the Stat Panel's "next rank"
    line without the frontend hardcoding a single threshold.
    """
    held = rank_for(level, streak, trials)
    order = [rank for _, rank in RANK_THRESHOLDS]
    position = order.index(held)
    if position + 1 >= len(order):
        return None
    target = order[position + 1]
    threshold = next(lvl for lvl, rank in RANK_THRESHOLDS if rank is target)
    return (target, threshold, RANK_STREAK_REQUIREMENTS.get(target, 0))
