"""XP curve and rank thresholds.

Deliberately the ONLY place these numbers appear. Because level_progress stores
cumulative total_xp as the source of truth, retuning anything here re-derives
every user correctly rather than corrupting stored progress - which is what
keeps Section 11's open question ("exact XP curve / rank cutoffs") cheap to
answer later.

PLACEHOLDER NUMBERS. Tune with the user in Sprint 3.
"""

from app.models.enums import Rank

# XP required to advance FROM level n to n+1: BASE * n ** EXPONENT.
XP_BASE = 50
XP_EXPONENT = 1.5

# Level at which each rank is attained. Must stay ascending.
RANK_THRESHOLDS: tuple[tuple[int, Rank], ...] = (
    (1, Rank.E),
    (10, Rank.D),
    (20, Rank.C),
    (35, Rank.B),
    (50, Rank.A),
    (75, Rank.S),
)

MAX_LEVEL = 999


def xp_for_level(level: int) -> int:
    """Cumulative XP required to REACH `level`. Level 1 costs nothing."""
    if level <= 1:
        return 0
    return sum(int(XP_BASE * (n**XP_EXPONENT)) for n in range(1, level))


def level_for_xp(total_xp: int) -> int:
    """Derive level from cumulative XP.

    Linear scan is fine: MAX_LEVEL is small, this runs only on XP change, and
    the result is cached in level_progress.current_level.
    """
    if total_xp <= 0:
        return 1
    level = 1
    while level < MAX_LEVEL and xp_for_level(level + 1) <= total_xp:
        level += 1
    return level


def rank_for_level(level: int) -> Rank:
    rank = Rank.E
    for threshold, candidate in RANK_THRESHOLDS:
        if level >= threshold:
            rank = candidate
        else:
            break
    return rank


def progress_into_level(total_xp: int) -> tuple[int, int]:
    """(xp earned into the current level, xp needed to finish it).

    This is what the Stat Panel XP bar renders.
    """
    level = level_for_xp(total_xp)
    floor = xp_for_level(level)
    if level >= MAX_LEVEL:
        return (0, 0)
    ceiling = xp_for_level(level + 1)
    return (total_xp - floor, ceiling - floor)
