"""Badges for the Stat Panel (Section 2).

Every badge is DERIVED from data the app already stores - completion counts,
longest streak, level, redemptions, party membership. Nothing is persisted, so
there is no award-time write path to get wrong, no way for a badge to drift out
of sync with the facts behind it, and no migration needed to add one.

The tiers deliberately key off values that never go DOWN:
  - `longest_streak`, not the current streak, so losing a streak cannot take
    away a badge that was genuinely earned.
  - level, which only rises, rather than rank, which is streak-gated at A and S
    and would otherwise revoke a badge when someone takes a week off.

Unearned badges are returned too, with their progress, so the panel can show
what is close rather than only what is done.
"""

import dataclasses


@dataclasses.dataclass(frozen=True)
class Badge:
    id: str
    name: str
    description: str
    icon: str
    earned: bool
    progress: int
    target: int

    @property
    def percent(self) -> int:
        if self.target <= 0:
            return 100 if self.earned else 0
        return min(100, int(self.progress * 100 / self.target))


@dataclasses.dataclass(frozen=True)
class BadgeInputs:
    """Everything the badge rules read. Assembled once by the caller so the
    rules stay pure and trivially testable."""

    quests_completed: int = 0
    longest_streak: int = 0
    current_level: int = 1
    rewards_redeemed: int = 0
    parties_joined: int = 0
    party_xp: int = 0
    total_xp: int = 0


# (id, name, description, icon, field, target)
_TIERS: tuple[tuple[str, str, str, str, str, int], ...] = (
    ("first_quest", "First Steps", "Complete your first quest", "🌱", "quests_completed", 1),
    ("ten_quests", "Getting Going", "Complete 10 quests", "⚔️", "quests_completed", 10),
    ("fifty_quests", "Seasoned", "Complete 50 quests", "🛡️", "quests_completed", 50),
    ("hundred_quests", "Veteran", "Complete 250 quests", "👑", "quests_completed", 250),
    ("streak_7", "Consistent", "Reach a 7-day streak", "🔥", "longest_streak", 7),
    ("streak_30", "Unbroken", "Reach a 30-day streak", "💠", "longest_streak", 30),
    ("streak_100", "Relentless", "Reach a 100-day streak", "☄️", "longest_streak", 100),
    ("level_10", "Rising", "Reach level 10", "📈", "current_level", 10),
    ("level_25", "Ascendant", "Reach level 25", "🌟", "current_level", 25),
    ("level_50", "Monarch", "Reach level 50", "🜲", "current_level", 50),
    ("first_reward", "Well Earned", "Redeem your first reward", "🎁", "rewards_redeemed", 1),
    ("party_member", "Not Alone", "Join or create a party", "🤝", "parties_joined", 1),
    ("party_1000", "Backbone", "Contribute 1,000 XP to a party", "🏛️", "party_xp", 1000),
)


def evaluate(inputs: BadgeInputs) -> list[Badge]:
    """All badges, earned and not, in definition order.

    Returning the unearned ones with progress is the point: a panel that only
    lists what you already have gives you nothing to aim at.
    """
    badges: list[Badge] = []
    for badge_id, name, description, icon, field, target in _TIERS:
        value = int(getattr(inputs, field))
        badges.append(
            Badge(
                id=badge_id,
                name=name,
                description=description,
                icon=icon,
                earned=value >= target,
                progress=min(value, target),
                target=target,
            )
        )
    return badges


def earned_count(badges: list[Badge]) -> int:
    return sum(1 for b in badges if b.earned)
