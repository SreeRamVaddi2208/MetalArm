"""Training splits, as data.

What someone is training today - push, pull, legs, or something of their own -
and which muscle groups that covers. The muscle groups are the whole point:
they are what filters the stretch library, so adding an Upper/Lower split later
is a row in app/data/splits.json rather than new branching in the matcher.

Modelled on TrainingCategoryProfile, which does the same job for training
paths: a string primary key matching the value stored on the rows that
reference it, seeded on deploy, never written by a request.
"""

import enum

from sqlalchemy import CheckConstraint, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import Timestamps
from app.models.workout_enums import check_in


class SplitType(str, enum.Enum):
    PUSH = "push"
    PULL = "pull"
    LEGS = "legs"
    # Anything that is not one of the three. Deliberately still carries muscle
    # groups - a general set - so its panel suggests something rather than
    # nothing at all.
    CUSTOM = "custom"


class StretchPhase(str, enum.Enum):
    PRE = "pre"    # dynamic, before the work
    POST = "post"  # static holds, after it


class SplitProfile(Timestamps, Base):
    __tablename__ = "split_profiles"

    # Matches workout_sessions.split_type and routines.split_type.
    split_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(40), nullable=False)
    # One line for the picker, which is a single tap and has no room for more.
    tagline: Mapped[str] = mapped_column(String(120), nullable=False)
    # What this split trains. Overlap with an exercise's primary_muscle_groups
    # is the entire matching rule (app/core/splits.py).
    target_muscle_groups: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False)
    # Where it sits in the picker.
    position: Mapped[int] = mapped_column(nullable=False, server_default="0")

    __table_args__ = (
        CheckConstraint(check_in("split_type", SplitType), name="ck_split_profiles_type"),
    )
