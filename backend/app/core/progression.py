"""Applying the result of a completion to a user's progression state.

Reads the curve from app/core/leveling.py and never hardcodes a threshold, so
retuning the curve in Sprint 3 changes exactly one file.
"""

import dataclasses
import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import leveling
from app.core.periods import local_date
from app.models.user import LevelProgress


@dataclasses.dataclass(frozen=True)
class ProgressionDelta:
    """What a completion did. Returned to the client so the UI can play the
    level-up sequence (Section 7) without a second round-trip or a guess."""

    xp_awarded: int
    points_awarded: int
    total_xp: int
    level_before: int
    level_after: int
    rank_before: str
    rank_after: str
    current_streak: int
    longest_streak: int

    @property
    def leveled_up(self) -> bool:
        return self.level_after > self.level_before

    @property
    def ranked_up(self) -> bool:
        """True only on promotion.

        Rank can also move DOWN when a streak lapses (the gate on A and S), and
        a demotion must not fire the celebratory rank-up animation.
        """
        order = [rank.value for _, rank in leveling.RANK_THRESHOLDS]
        return order.index(self.rank_after) > order.index(self.rank_before)


def lock_progress(db: Session, user_id: uuid.UUID) -> LevelProgress:
    """Fetch the user's progression row and hold a row lock until commit.

    SELECT ... FOR UPDATE, not a plain read: two completions submitted at once
    would otherwise both read total_xp=100, both write 150, and one award would
    vanish (a classic lost update). Callers must take this lock BEFORE
    inserting the completion row, so every writer acquires locks in the same
    order and no deadlock is possible.
    """
    progress = db.execute(
        select(LevelProgress).where(LevelProgress.user_id == user_id).with_for_update()
    ).scalar_one()
    return progress


def apply_completion(
    progress: LevelProgress,
    *,
    xp: int,
    points: int,
    completed_at: dt.datetime,
    tz_name: str,
) -> ProgressionDelta:
    """Mutate `progress` in place for one completion. Does not commit.

    The caller owns the transaction, because the completion row and this update
    must land together or not at all - awarding XP for a completion that then
    fails to insert would let a user farm XP by retrying.
    """
    today = local_date(completed_at, tz_name)

    level_before = progress.current_level
    # The rank held going in, judged against the streak as it stood BEFORE this
    # completion. Using the stored column instead would report a spurious
    # rank-up for a lapsed user whose cached rank was never demoted.
    rank_before = leveling.rank_for(
        progress.current_level,
        leveling.effective_streak(
            progress.current_streak, progress.last_completed_on, today
        ),
    )

    progress.total_xp += xp
    progress.points_balance += points
    progress.current_level = leveling.level_for_xp(progress.total_xp)

    # Streak first: rank depends on it, so computing rank beforehand would use
    # a stale streak and under-report a promotion earned by this very
    # completion.
    _apply_streak(progress, today)

    progress.rank = leveling.rank_for(progress.current_level, progress.current_streak)

    return ProgressionDelta(
        xp_awarded=xp,
        points_awarded=points,
        total_xp=progress.total_xp,
        level_before=level_before,
        level_after=progress.current_level,
        rank_before=rank_before.value,
        rank_after=progress.rank.value,
        current_streak=progress.current_streak,
        longest_streak=progress.longest_streak,
    )


def _apply_streak(progress: LevelProgress, today: dt.date) -> None:
    """Advance the streak using the user's LOCAL date.

    last_completed_on is stored as a local date precisely so that travelling
    across timezones doesn't read as a missed day.
    """
    last = progress.last_completed_on

    if last is None:
        progress.current_streak = 1
    elif last == today:
        # Already counted today; more completions today don't extend a streak.
        pass
    elif last == today - dt.timedelta(days=1):
        progress.current_streak += 1
    elif last < today:
        # A day (or more) was missed.
        progress.current_streak = 1
    else:
        # last > today: backdated completion or a client clock skew. Leave the
        # streak untouched rather than corrupting it, and don't move the marker
        # backwards.
        return

    progress.last_completed_on = max(last, today) if last else today
    progress.longest_streak = max(progress.longest_streak, progress.current_streak)
