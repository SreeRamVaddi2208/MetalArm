"""What each training path means, as data.

A user's path is `users.character_class` - the same three values the character
sheet already used (app/core/character.py). It used to be cosmetic: it decided
which stats were highlighted and nothing else. It now also says how the app
should train you, and THIS table is where that meaning lives: rep ranges, load
and volume, rest, and the tags that say which exercises suit the path.

In a table rather than in Python for the same reason the points engine keeps
its values in one place: the definitions are tuning, and tuning should be
editable - and readable by both clients through one endpoint - without a code
change. Seeded from app/data/training_categories.json.

Nothing here touches points, XP, records or a leaderboard. A path changes what
is SUGGESTED, never what is scored, so no one can pick a path to score better.
"""

from sqlalchemy import ARRAY, CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import Timestamps


class TrainingCategoryProfile(Timestamps, Base):
    __tablename__ = "training_category_profiles"

    # Matches users.character_class, which is the user's chosen path.
    category: Mapped[str] = mapped_column(String(16), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(40), nullable=False)
    # One line, for the onboarding card.
    tagline: Mapped[str] = mapped_column(String(120), nullable=False)
    # The longer version, for anywhere with room to explain.
    description: Mapped[str] = mapped_column(Text, nullable=False)

    rep_range_low: Mapped[int] = mapped_column(Integer, nullable=False)
    rep_range_high: Mapped[int] = mapped_column(Integer, nullable=False)
    relative_load: Mapped[str] = mapped_column(String(16), nullable=False)
    relative_volume: Mapped[str] = mapped_column(String(16), nullable=False)
    rest_seconds_guidance: Mapped[int] = mapped_column(Integer, nullable=False)
    # Which kinds of exercise suit this path. Read by whatever suggests work;
    # the exercise library is not tagged yet, so nothing filters on them today.
    emphasis_tags: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "category IN ('powerlifter', 'bodybuilder', 'athlete')",
            name="ck_training_categories_category",
        ),
        CheckConstraint(
            "rep_range_low >= 1 AND rep_range_low <= rep_range_high",
            name="ck_training_categories_rep_range",
        ),
        CheckConstraint(
            "rest_seconds_guidance >= 0 AND rest_seconds_guidance <= 3600",
            name="ck_training_categories_rest",
        ),
        CheckConstraint(
            "relative_load IN ('low', 'moderate', 'moderate_high', 'heavy')",
            name="ck_training_categories_load",
        ),
        CheckConstraint(
            "relative_volume IN ('low', 'moderate', 'moderate_high', 'high')",
            name="ck_training_categories_volume",
        ),
    )
