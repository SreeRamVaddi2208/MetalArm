"""Enumerations used by the ORM layer.

Only genuinely stable state sets get a native Postgres enum. Sets we expect to
grow use VARCHAR + CHECK instead, because `ALTER TYPE ... ADD VALUE` cannot be
used in the same transaction that adds it, which fights Alembic's transactional
migrations - and renaming or removing a value requires recreating the type
outright.

Stable (native enum):     Rank, QuestStatus, PartyRole
Expected to grow (CHECK): recurrence - see RECURRENCE_VALUES below
"""

import enum

from sqlalchemy import Enum as SAEnum


class Rank(str, enum.Enum):
    """Hunter rank ladder. Fixed by the concept: E is the floor, S the ceiling."""

    E = "E"
    D = "D"
    C = "C"
    B = "B"
    A = "A"
    S = "S"


class QuestStatus(str, enum.Enum):
    """Lifecycle of a quest DEFINITION.

    Deliberately has no 'completed' member: completion is per-period and lives
    in quest_completions. A recurring quest is never 'completed', only done for
    a given period.
    """

    ACTIVE = "active"
    ARCHIVED = "archived"


class PartyRole(str, enum.Enum):
    """Structural: a party has exactly one owner; everyone else is a member."""

    OWNER = "owner"
    MEMBER = "member"


class Recurrence(str, enum.Enum):
    """Not a native DB enum - see module docstring.

    Kept as a Python enum for type-safety in application code, while the column
    is VARCHAR + CHECK so adding 'monthly' is a one-line constraint change.
    """

    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"


RECURRENCE_VALUES: tuple[str, ...] = tuple(r.value for r in Recurrence)

# Sentinel period_key for non-recurring quests, so the UNIQUE constraint
# applies uniformly instead of relying on NULL (which never equals itself and
# would therefore permit unlimited duplicate completions).
ONE_OFF_PERIOD_KEY = "once"


def pg_enum(py_enum: type[enum.Enum], name: str) -> "SAEnum":
    """Native Postgres enum column that persists member VALUES, not names.

    SQLAlchemy's default is to store the member NAME (`ACTIVE`), not `.value`
    (`active`). That silently diverges from any `server_default=X.value` and
    fails at migration time with:
        invalid input value for enum quest_status: "active"

    It is easy to miss because an enum whose names equal its values - Rank
    (E, D, C...) - works either way. values_callable makes all of them behave
    the same, so the DB stores the lowercase values the API also speaks.
    """
    return SAEnum(
        py_enum,
        name=name,
        native_enum=True,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )
