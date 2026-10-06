"""Natural-language set logging: exercise aliases and the parse log.

Neither table touches scoring. A parse only PROPOSES sets; the user confirms
them and they go through the ordinary log-set endpoint, so points, records and
quests are judged exactly as for a tapped-in set.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import UUIDPrimaryKey
from app.models.workout_enums import check_in


class AliasSource(str, enum.Enum):
    # Shipped in app/data/exercise_aliases.json; global.
    SEED = "seed"
    # Added by the user through POST /exercises/aliases.
    USER = "user"
    # Learned from the user correcting the same phrase to the same exercise.
    LEARNED = "learned"


class ParserUsed(str, enum.Enum):
    GRAMMAR = "grammar"
    LLM = "llm"
    # Neither understood it.
    NONE = "none"


class ExerciseAlias(UUIDPrimaryKey, Base):
    """Another name for an exercise: "bench", "rdl", "ohp".

    A global alias (user_id NULL) is shipped with the library; a personal one
    belongs to one user and wins over a global one with the same text."""

    __tablename__ = "exercise_aliases"

    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    # exercise_names.name_key form: lowercased, whitespace collapsed.
    alias: Mapped[str] = mapped_column(String(60), nullable=False)
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True,
        index=True,
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(check_in("source", AliasSource), name="ck_exercise_aliases_source"),
        CheckConstraint("length(alias) >= 1", name="ck_exercise_aliases_alias"),
        CheckConstraint(
            "(source = 'seed') = (user_id IS NULL)", name="ck_exercise_aliases_owner"
        ),
        # One meaning per alias per owner. NULLS NOT DISTINCT so the global
        # set (user_id NULL) is unique too.
        UniqueConstraint(
            "alias", "user_id", name="uq_exercise_aliases_alias", postgresql_nulls_not_distinct=True
        ),
    )


class ParseLog(UUIDPrimaryKey, Base):
    """One parse request: the text, what came back, and whether the user
    took it as-is. TEXT ONLY - audio never reaches the server."""

    __tablename__ = "parse_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parser_used: Mapped[str] = mapped_column(String(8), nullable=False)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # NULL until the user confirms or edits the proposal.
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    corrected_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(check_in("parser_used", ParserUsed), name="ck_parse_logs_parser"),
        CheckConstraint("latency_ms >= 0", name="ck_parse_logs_latency"),
        Index("ix_parse_logs_user_time", "user_id", "created_at"),
    )
